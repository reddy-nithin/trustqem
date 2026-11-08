"""Amendment 4, scale of the alarm: Clifford canaries on a simulated 156-qubit chip, watched by the same martingale.

No mitigator can be trained at 156 qubits (nobody can compute ideal values of random circuits that large), so the
monitored score is the raw canary error: mean |noisy value - ideal value| over the Z and ZZ observables. Pure
Clifford canaries (k = 0) keep both the ideal values (stabilizer state) and the noisy runs (Aer stabilizer method,
Pauli noise) classically cheap at any size. This shows that the alarm step scales; it is not a coverage result.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Pauli, StabilizerState
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error

from trustqem.circuits import build_clifford_twin, build_random_records
from trustqem.monitor import CanaryMonitor

logger = logging.getLogger(__name__)

QUBITS = 156                      # an IBM Heron chip (ibm_fez)
LAYERS, CX_PROBABILITY, SHOTS = 12, 0.5, 1000
ONE_QUBIT_RATE, TWO_QUBIT_RATE, READOUT_FLIP = 0.001, 0.01, 0.01
DRIFT_MULTIPLIER = 1.5           # gate errors x1.5 after the drift (like D1)
REFERENCE, POOL, PER_DAY, QUIET_DAYS, DRIFT_DAYS, SEQUENCES = 60, 150, 30, 5, 5, 200
CLIFFORD_ONE_QUBIT = ("s", "sdg", "z", "sx", "sxdg", "x", "y", "h")

# rotation by k * pi/2, as exact Clifford gates (equal up to a global phase, checked in tests/test_monitor.py)
CLIFFORD_ROTATIONS = {
    "rz": {1: ["s"], 2: ["z"], 3: ["sdg"]},
    "rx": {1: ["sx"], 2: ["x"], 3: ["sxdg"]},
    "ry": {1: ["z", "h"], 2: ["y"], 3: ["h", "z"]},
}


def to_clifford_gates(circuit: QuantumCircuit) -> QuantumCircuit:
    """Rewrite rx/ry/rz at multiples of pi/2 as named Clifford gates, which the stabilizer simulator accepts."""
    mapped = QuantumCircuit(circuit.num_qubits)
    for instruction in circuit.data:
        name, qubits = instruction.operation.name, instruction.qubits
        if name == "cx":
            mapped.cx(*qubits)
            continue
        quarter_turns = float(instruction.operation.params[0]) / (np.pi / 2)
        k = int(round(quarter_turns)) % 4
        if abs(quarter_turns - round(quarter_turns)) > 1e-9:
            raise ValueError(f"{name} angle {instruction.operation.params[0]} is not a Clifford angle")
        for gate in CLIFFORD_ROTATIONS[name].get(k, []):
            getattr(mapped, gate)(*qubits)
    return mapped


def observable_labels(qubit_count: int) -> list[tuple[int, ...]]:
    """Z on each qubit, then ZZ on each neighbouring pair, as qubit index tuples."""
    return [(q,) for q in range(qubit_count)] + [(q, q + 1) for q in range(qubit_count - 1)]


def ideal_values(circuit: QuantumCircuit, observables: list[tuple[int, ...]]) -> np.ndarray:
    state, n = StabilizerState(circuit), circuit.num_qubits
    values = []
    for qubits in observables:
        label = ["I"] * n
        for q in qubits:
            label[n - 1 - q] = "Z"
        values.append(state.expectation_value(Pauli("".join(label))))
    return np.array(values, dtype=float)


def noise_model(multiplier: float) -> NoiseModel:
    model = NoiseModel()
    model.add_all_qubit_quantum_error(depolarizing_error(multiplier * ONE_QUBIT_RATE, 1), list(CLIFFORD_ONE_QUBIT))
    model.add_all_qubit_quantum_error(depolarizing_error(multiplier * TWO_QUBIT_RATE, 2), ["cx"])
    model.add_all_qubit_readout_error(ReadoutError([[1 - READOUT_FLIP, READOUT_FLIP], [READOUT_FLIP, 1 - READOUT_FLIP]]))
    return model


def noisy_values(circuit: QuantumCircuit, simulator: AerSimulator, observables: list[tuple[int, ...]],
                 seed: int) -> np.ndarray:
    measured = circuit.copy()
    measured.measure_all()
    memory = simulator.run(measured, shots=SHOTS, memory=True, seed_simulator=seed).result().get_memory()
    bits = np.array([[int(b) for b in reversed(shot)] for shot in memory], dtype=np.int8)   # bits[:, q] is qubit q
    signs = 1 - 2 * bits
    return np.array([np.prod(signs[:, list(qubits)], axis=1).mean() for qubits in observables])


@dataclass(frozen=True)
class CanaryPool:
    scores: np.ndarray            # one raw canary error per circuit
    seconds_per_circuit: float


def simulate_canaries(count: int, multiplier: float, rng: np.random.Generator, qubits: int = QUBITS) -> CanaryPool:
    simulator = AerSimulator(method="stabilizer", noise_model=noise_model(multiplier))
    observables = observable_labels(qubits)
    start, scores = time.time(), []
    for record in build_random_records(count, qubits, LAYERS, CX_PROBABILITY, rng):
        canary = to_clifford_gates(build_clifford_twin(record, 0, rng).circuit)
        error = np.abs(noisy_values(canary, simulator, observables, int(rng.integers(0, 2**31)))
                       - ideal_values(canary, observables))
        scores.append(error.mean())
    return CanaryPool(np.array(scores), (time.time() - start) / count)


def alarm_days(reference: CanaryPool, quiet: CanaryPool, drifted: CanaryPool, rng: np.random.Generator) -> list:
    """First alarm day per resampled 10-day sequence (days 1 to 5 quiet, 6 to 10 drifted); None if no alarm."""
    days = []
    for _ in range(SEQUENCES):
        monitor, first = CanaryMonitor(reference.scores, rng), None
        for day in range(1, QUIET_DAYS + DRIFT_DAYS + 1):
            pool = quiet if day <= QUIET_DAYS else drifted
            _, alarm = monitor.observe(rng.choice(pool.scores, size=PER_DAY, replace=False))
            if alarm:
                first = day
                break
        days.append(first)
    return days


def run(profile_name: str, results_root: Path) -> Path:
    """Profile "q156" (default chip size) or "q<n>" for another chip size."""
    qubits = int(profile_name.removeprefix("q")) if profile_name.startswith("q") else QUBITS
    rng = np.random.default_rng(qubits)
    reference = simulate_canaries(REFERENCE, 1.0, rng, qubits)
    logger.info("reference canaries: %.2f s per circuit at %d qubits", reference.seconds_per_circuit, qubits)
    quiet = simulate_canaries(POOL, 1.0, rng, qubits)
    drifted = simulate_canaries(POOL, DRIFT_MULTIPLIER, rng, qubits)
    first = alarm_days(reference, quiet, drifted, rng)
    false = [d is not None and d <= QUIET_DAYS for d in first]
    delays = [d - QUIET_DAYS for d in first if d is not None and d > QUIET_DAYS]
    summary = {
        "qubits": qubits, "observables": len(observable_labels(qubits)), "shots": SHOTS,
        "seconds_per_canary": float(np.mean([p.seconds_per_circuit for p in (reference, quiet, drifted)])),
        "mean_score_quiet": float(quiet.scores.mean()), "mean_score_drifted": float(drifted.scores.mean()),
        "sequences": SEQUENCES, "false_alarm_rate_quiet_days": float(np.mean(false)),
        "detection_rate": len(delays) / SEQUENCES,
        "mean_delay_days": float(np.mean(delays)) if delays else None,
        "delay_counts": {str(d): delays.count(d) for d in sorted(set(delays))}}
    output_dir = results_root / "canary_scale" / f"q{qubits}"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    delay = "n/a" if summary["mean_delay_days"] is None else f"{summary['mean_delay_days']:.1f} days"
    (output_dir / "verdict.md").write_text("\n".join([
        f"# Scale of the alarm, {qubits}-qubit simulated chip (Amendment 4, reported, not judged)", "",
        f"- {summary['observables']} observables per canary, {SHOTS} shots, "
        f"{summary['seconds_per_canary']:.2f} s per canary on one machine",
        f"- raw canary error: {summary['mean_score_quiet']:.4f} quiet, {summary['mean_score_drifted']:.4f} after "
        f"gate errors x{DRIFT_MULTIPLIER}",
        f"- false alarms on quiet days: {summary['false_alarm_rate_quiet_days']:.3f} of {SEQUENCES} sequences",
        f"- drift detected in {summary['detection_rate']:.2f} of sequences, mean delay {delay}", ""]))
    return output_dir
