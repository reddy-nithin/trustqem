"""Device-realistic noise: an IBM Heron calibration, its native gates, gate folding, and calibration drift.

Monday is the FakeFez calibration snapshot on 4 connected physical qubits. Tuesday scenarios perturb that
calibration the way real devices drift. Noise is amplified by folding gates (G -> G G_dagger G), which is how it has
to be done on hardware, instead of scaling error rates inside the simulator.
"""

from dataclasses import asdict, dataclass, replace
from itertools import pairwise

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Delay, Parameter
from qiskit.circuit.library import CZGate, RZGate, SXGate, XGate
from qiskit.quantum_info import average_gate_fidelity
from qiskit.transpiler import CouplingMap, InstructionProperties, PassManager, Target
from qiskit.transpiler.passes import ALAPScheduleAnalysis, PadDelay
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, QuantumError, ReadoutError, depolarizing_error, thermal_relaxation_error
from qiskit_aer.noise.passes import RelaxationNoisePass

from trustqem.config import ExperimentConfig

NATIVE_GATES = ("cz", "rz", "sx", "x")     # IBM Heron basis (rz is virtual: a frame change, no error, no time)
CHAIN_LENGTH = 4


@dataclass(frozen=True)
class DeviceCalibration:
    """One day's calibration of a 4-qubit chain. Compact qubit i is physical qubit physical_qubits[i]; edge i joins
    compact qubits i and i + 1. Times are in seconds, errors are probabilities."""

    backend_name: str
    physical_qubits: tuple[int, ...]
    t1: tuple[float, ...]
    t2: tuple[float, ...]
    readout_p01: tuple[float, ...]      # P(read 1 | prepared 0)
    readout_p10: tuple[float, ...]      # P(read 0 | prepared 1)
    sx_error: tuple[float, ...]
    x_error: tuple[float, ...]
    cz_error: tuple[float, ...]
    sx_duration: tuple[float, ...]
    x_duration: tuple[float, ...]
    cz_duration: tuple[float, ...]

    def to_dict(self) -> dict:
        """Plain dict version for saving in result files."""
        return asdict(self)

    @property
    def truncated_t2(self) -> tuple[float, ...]:
        """T2 capped at 2 T1, the physical limit (a T1 drop can push a stored T2 past it)."""
        return tuple(min(t2, 2 * t1) for t1, t2 in zip(self.t1, self.t2, strict=True))


def choose_chain(backend, length: int = CHAIN_LENGTH) -> tuple[int, ...]:
    """The connected line of `length` physical qubits with the lowest summed cz error plus readout error."""
    target = backend.target
    readout = {qubit: target["measure"][(qubit,)].error for qubit in range(backend.num_qubits)}
    cz = {}
    for (a, b), properties in target["cz"].items():
        if properties is not None and properties.error is not None:
            cz[frozenset((a, b))] = min(properties.error, cz.get(frozenset((a, b)), 1.0))
    neighbours: dict[int, list[int]] = {}
    for edge in cz:
        a, b = tuple(edge)
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)

    best, best_score = None, np.inf
    stack = [(qubit,) for qubit in neighbours]
    while stack:
        path = stack.pop()
        if len(path) == length:
            if path[0] > path[-1]:
                continue                                    # each line once, not once per direction
            score = sum(readout[q] for q in path) + sum(cz[frozenset(edge)] for edge in pairwise(path))
            if score < best_score:
                best, best_score = path, score
            continue
        stack.extend(path + (n,) for n in neighbours[path[-1]] if n not in path)
    if best is None:
        raise ValueError(f"no connected chain of {length} qubits on {backend.name}")
    return best


def load_calibration(backend=None, physical_qubits: tuple[int, ...] | None = None) -> DeviceCalibration:
    """Read one chain's calibration from a fake backend snapshot (FakeFez by default)."""
    if backend is None:
        from qiskit_ibm_runtime.fake_provider import FakeFez
        backend = FakeFez()
    chain = tuple(physical_qubits) if physical_qubits is not None else choose_chain(backend)
    target, properties = backend.target, backend.properties()
    edges = list(pairwise(chain))

    def cz_property(a: int, b: int) -> InstructionProperties:
        return target["cz"].get((a, b)) or target["cz"][(b, a)]

    return DeviceCalibration(
        backend_name=backend.name,
        physical_qubits=chain,
        t1=tuple(target.qubit_properties[q].t1 for q in chain),
        t2=tuple(target.qubit_properties[q].t2 for q in chain),
        readout_p01=tuple(float(properties.qubit_property(q)["prob_meas1_prep0"][0]) for q in chain),
        readout_p10=tuple(float(properties.qubit_property(q)["prob_meas0_prep1"][0]) for q in chain),
        sx_error=tuple(target["sx"][(q,)].error for q in chain),
        x_error=tuple(target["x"][(q,)].error for q in chain),
        cz_error=tuple(cz_property(a, b).error for a, b in edges),
        sx_duration=tuple(target["sx"][(q,)].duration for q in chain),
        x_duration=tuple(target["x"][(q,)].duration for q in chain),
        cz_duration=tuple(cz_property(a, b).duration for a, b in edges),
    )


def transpile_to_device(circuit: QuantumCircuit) -> QuantumCircuit:
    """Rewrite into native gates on a line of qubits, with no optimisation.

    The random circuits only use CX between neighbours on a line, so this matches transpiling onto the chosen
    physical chain (no swaps), and a target and its twin get the same layout. Level 0 keeps every gate in place:
    nothing is merged, so a twin's count of non-Clifford rotations survives.
    """
    return transpile(circuit, basis_gates=list(NATIVE_GATES), coupling_map=CouplingMap.from_line(circuit.num_qubits),
                     initial_layout=list(range(circuit.num_qubits)), optimization_level=0)


def _inverse(operation) -> list:
    """Native-gate inverse. SX_dagger = RZ(pi) SX RZ(pi) up to a global phase, as IBM hardware does it."""
    name = operation.name
    if name == "rz":
        return [RZGate(-float(operation.params[0]))]
    if name in ("x", "cz"):
        return [operation]
    if name == "sx":
        return [RZGate(np.pi), SXGate(), RZGate(np.pi)]
    raise ValueError(f"cannot fold non-native gate {name!r}")


def fold_gates(circuit: QuantumCircuit, scale: float) -> QuantumCircuit:
    """Local unitary folding: every gate G becomes G (G_dagger G)^n with n = (scale - 1) / 2.

    Same unitary, `scale` times as many noisy gates. Run it at optimization_level 0 or the folds cancel.
    """
    folds = (scale - 1) / 2
    if scale < 1 or folds != int(folds):
        raise ValueError(f"fold scale must be an odd integer >= 1, got {scale}")
    folded = QuantumCircuit(*circuit.qregs, *circuit.cregs, global_phase=circuit.global_phase)
    for instruction in circuit.data:
        operation, qubits = instruction.operation, instruction.qubits
        folded.append(operation, qubits)
        for _ in range(int(folds)):
            for inverse_operation in _inverse(operation):
                folded.append(inverse_operation, qubits)
            folded.append(operation, qubits)
    return folded


def _relaxation(t1: tuple, t2: tuple, duration: float, qubits: tuple[int, ...]) -> QuantumError:
    """T1/T2 decay over one gate on each of its qubits; the first qubit is the lowest tensor factor."""
    error = thermal_relaxation_error(t1[qubits[0]], t2[qubits[0]], duration)
    for qubit in qubits[1:]:
        error = error.expand(thermal_relaxation_error(t1[qubit], t2[qubit], duration))
    return error


def _gate_error(gate_error: float, relaxation: QuantumError, qubit_count: int) -> QuantumError:
    """Depolarizing noise sized so that, composed with relaxation, the average gate infidelity equals the
    calibrated gate error. Same recipe as Aer's NoiseModel.from_backend."""
    relax_fidelity = average_gate_fidelity(relaxation)
    dim = 2 ** qubit_count
    error = min(gate_error, dim / (dim + 1))
    if error <= 1 - relax_fidelity:
        return relaxation
    depol = dim * (error - (1 - relax_fidelity)) / (dim * relax_fidelity - 1)
    return depolarizing_error(min(depol, 4 ** qubit_count / (4 ** qubit_count - 1)), qubit_count).compose(relaxation)


def build_device_noise_model(calibration: DeviceCalibration) -> NoiseModel:
    """Per-qubit sx and x errors, per-edge cz errors (both directions), and asymmetric readout errors."""
    t1, t2 = calibration.t1, calibration.truncated_t2
    noise_model = NoiseModel(basis_gates=list(NATIVE_GATES))
    for qubit in range(len(t1)):
        for name, errors, durations in (("sx", calibration.sx_error, calibration.sx_duration),
                                        ("x", calibration.x_error, calibration.x_duration)):
            relaxation = _relaxation(t1, t2, durations[qubit], (qubit,))
            noise_model.add_quantum_error(_gate_error(errors[qubit], relaxation, 1), name, [qubit])
        p01, p10 = calibration.readout_p01[qubit], calibration.readout_p10[qubit]
        noise_model.add_readout_error(ReadoutError([[1 - p01, p01], [p10, 1 - p10]]), [qubit])
    for edge, error in enumerate(calibration.cz_error):
        for pair in ((edge, edge + 1), (edge + 1, edge)):
            relaxation = _relaxation(t1, t2, calibration.cz_duration[edge], pair)
            noise_model.add_quantum_error(_gate_error(error, relaxation, 2), "cz", list(pair))
    return noise_model


def build_timing_target(calibration: DeviceCalibration) -> Target:
    """Gate durations on the compact chain, for scheduling idle periods."""
    count = len(calibration.t1)
    target = Target(num_qubits=count)
    target.add_instruction(SXGate(), {(q,): InstructionProperties(duration=calibration.sx_duration[q])
                                      for q in range(count)})
    target.add_instruction(XGate(), {(q,): InstructionProperties(duration=calibration.x_duration[q])
                                     for q in range(count)})
    target.add_instruction(RZGate(Parameter("theta")), {(q,): InstructionProperties(duration=0.0)
                                                        for q in range(count)})
    cz_properties = {}
    for edge, duration in enumerate(calibration.cz_duration):
        cz_properties[(edge, edge + 1)] = InstructionProperties(duration=duration)
        cz_properties[(edge + 1, edge)] = InstructionProperties(duration=duration)
    target.add_instruction(CZGate(), cz_properties)
    target.add_instruction(Delay(Parameter("duration")), {(q,): None for q in range(count)})
    return target


def add_idle_relaxation(circuit: QuantumCircuit, calibration: DeviceCalibration) -> QuantumCircuit:
    """Schedule as late as possible, fill idle gaps with delays, and attach T1/T2 decay to each delay.

    Gate errors already include decay during the gate; this adds the decay of qubits waiting for others.
    """
    target = build_timing_target(calibration)
    scheduled = PassManager([ALAPScheduleAnalysis(target=target), PadDelay(target=target)]).run(circuit)
    return RelaxationNoisePass(list(calibration.t1), list(calibration.truncated_t2), op_types=Delay,
                               target=target)(scheduled)


@dataclass(frozen=True)
class DeviceCondition:
    """One device state, with the same interface as noise.NoiseCondition.

    Every fold scale uses the same noise model; the circuit, not the model, carries the noise amplification.
    """

    name: str
    calibration: DeviceCalibration
    idle_relaxation: bool = True

    def build_simulators(self, config: ExperimentConfig) -> dict[float, AerSimulator]:
        """One density-matrix simulator, shared by every fold scale."""
        simulator = AerSimulator(method="density_matrix", noise_model=build_device_noise_model(self.calibration))
        return {scale: simulator for scale in config.noise_scale_factors}

    def prepare_circuit(self, circuit: QuantumCircuit, scale: float) -> QuantumCircuit:
        """Native gates, folded to `scale`, with idle decay attached if enabled."""
        folded = fold_gates(transpile_to_device(circuit), scale)
        return add_idle_relaxation(folded, self.calibration) if self.idle_relaxation else folded


def scale_coherence(calibration: DeviceCalibration, factor: float) -> DeviceCalibration:
    """T1 and T2 multiplied by `factor` on every qubit."""
    return replace(calibration, t1=tuple(t * factor for t in calibration.t1),
                   t2=tuple(t * factor for t in calibration.t2))


def scale_readout(calibration: DeviceCalibration, factor: float) -> DeviceCalibration:
    """Both readout flip probabilities multiplied by `factor` (capped at 0.5) on every qubit."""
    return replace(calibration, readout_p01=tuple(min(p * factor, 0.5) for p in calibration.readout_p01),
                   readout_p10=tuple(min(p * factor, 0.5) for p in calibration.readout_p10))


def scale_gate_errors(calibration: DeviceCalibration, factor: float) -> DeviceCalibration:
    """sx, x and cz errors multiplied by `factor` on every qubit and edge."""
    return replace(calibration, sx_error=tuple(e * factor for e in calibration.sx_error),
                   x_error=tuple(e * factor for e in calibration.x_error),
                   cz_error=tuple(e * factor for e in calibration.cz_error))


def degrade_qubit(calibration: DeviceCalibration, qubit: int, t1_factor: float,
                  cz_factor: float) -> DeviceCalibration:
    """One qubit goes bad: its T1 drops (a defect comes into resonance) and the cz gates touching it get worse."""
    t1 = tuple(t * t1_factor if index == qubit else t for index, t in enumerate(calibration.t1))
    cz = tuple(e * cz_factor if qubit in (edge, edge + 1) else e for edge, e in enumerate(calibration.cz_error))
    return replace(calibration, t1=t1, cz_error=cz)
