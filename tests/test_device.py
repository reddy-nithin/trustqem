"""Unit tests for the device-realistic track: calibration, transpiling, gate folding and drift helpers."""

from functools import cache

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, SparsePauliOp, SuperOp
from qiskit_aer.noise import NoiseModel

from trustqem.circuits import CLIFFORD_ANGLES, build_clifford_twin, build_random_records, is_clifford
from trustqem.device import (
    DeviceCondition,
    build_device_noise_model,
    choose_chain,
    degrade_qubit,
    fold_gates,
    load_calibration,
    scale_coherence,
    scale_gate_errors,
    scale_readout,
    transpile_to_device,
)
from trustqem.simulate import build_observable_labels, ideal_expectation_values

NOISY_GATES = ("sx", "x", "cz")


@cache
def _backend():
    from qiskit_ibm_runtime.fake_provider import FakeFez
    return FakeFez()


@cache
def _calibration():
    return load_calibration(_backend())


def _records(count: int, seed: int = 0):
    return build_random_records(count, 4, 8, 0.5, np.random.default_rng(seed))


def _observables():
    return [SparsePauliOp(label) for label in build_observable_labels(4)]


@pytest.mark.parametrize("scale", [3, 5])
def test_folding_multiplies_noisy_gate_counts(scale: int) -> None:
    """Each sx, x and cz appears exactly `scale` times as often; rz is virtual and not counted."""
    native = transpile_to_device(_records(1)[0].circuit)
    native.x(0)                                   # random circuits never transpile to x, so add one
    before, after = native.count_ops(), fold_gates(native, scale).count_ops()
    for name in NOISY_GATES:
        assert after.get(name, 0) == scale * before.get(name, 0)


@pytest.mark.parametrize("scale", [3, 5])
def test_folding_keeps_the_unitary(scale: int) -> None:
    """Folded and unfolded circuits are the same operation (up to a global phase)."""
    native = transpile_to_device(_records(1, seed=1)[0].circuit)
    assert Operator(fold_gates(native, scale)).equiv(Operator(native))


@pytest.mark.parametrize("seed", range(3))
def test_transpiled_folded_circuit_keeps_noiseless_expectations(seed: int) -> None:
    """Transpiling (trivial layout, no swaps) and folding leave every ideal expectation value unchanged."""
    circuit = _records(1, seed)[0].circuit
    folded = fold_gates(transpile_to_device(circuit), 5)
    assert np.allclose(ideal_expectation_values(folded, _observables()),
                       ideal_expectation_values(circuit, _observables()), atol=1e-9)


@pytest.mark.parametrize("scale", [0, 2, 2.5])
def test_folding_rejects_even_or_fractional_scales(scale: float) -> None:
    """Unitary folding only reaches odd integer scales."""
    with pytest.raises(ValueError):
        fold_gates(QuantumCircuit(1), scale)


def _non_clifford_rz_count(circuit: QuantumCircuit) -> int:
    """rz gates whose angle is not a multiple of pi/2."""
    angles = [float(i.operation.params[0]) % (2 * np.pi) for i in circuit.data if i.operation.name == "rz"]
    return sum(not np.isclose(min(abs(a - c) for c in (*CLIFFORD_ANGLES, 2 * np.pi)), 0, atol=1e-9) for a in angles)


def _cz_pairs(circuit: QuantumCircuit) -> list[tuple[int, ...]]:
    return [tuple(circuit.find_bit(q).index for q in i.qubits) for i in circuit.data if i.operation.name == "cz"]


@pytest.mark.parametrize("keep", [0, 2, 4, 8])
def test_twins_stay_near_clifford_after_transpiling(keep: int) -> None:
    """A twin with k kept rotations has at most k non-Clifford rz after transpiling; k = 0 stays Clifford.
    Twin and target keep the same two-qubit gate layout."""
    rng = np.random.default_rng(3)
    for record in _records(5, seed=4):
        twin = transpile_to_device(build_clifford_twin(record, keep, rng).circuit)
        assert _non_clifford_rz_count(twin) <= keep
        assert _cz_pairs(twin) == _cz_pairs(transpile_to_device(record.circuit))
        if keep == 0:
            assert is_clifford(twin)
            assert is_clifford(fold_gates(twin, 3))


def test_choose_chain_returns_a_connected_line() -> None:
    """Four distinct qubits, each neighbouring pair joined by a cz."""
    chain = choose_chain(_backend())
    assert len(set(chain)) == 4
    cz_pairs = set(_backend().target["cz"].keys())
    assert all((a, b) in cz_pairs or (b, a) in cz_pairs for a, b in zip(chain, chain[1:], strict=False))


def test_calibration_fields_are_physical() -> None:
    """One value per qubit (or edge), all in plausible ranges for a Heron device."""
    calibration = _calibration()
    assert len(calibration.t1) == len(calibration.readout_p01) == len(calibration.sx_error) == 4
    assert len(calibration.cz_error) == len(calibration.cz_duration) == 3
    assert all(1e-6 < t < 1e-3 for t in calibration.t1)
    assert all(0 <= p < 0.1 for p in calibration.readout_p01 + calibration.readout_p10)
    assert all(0 < e < 0.05 for e in calibration.cz_error)


def test_drift_helpers_change_only_their_fields() -> None:
    """Each perturbation touches the fields it names and nothing else."""
    base = _calibration()
    coherence = scale_coherence(base, 0.5)
    assert coherence.t1 == pytest.approx([t / 2 for t in base.t1]) and coherence.cz_error == base.cz_error
    readout = scale_readout(base, 2.0)
    assert readout.readout_p10 == pytest.approx([2 * p for p in base.readout_p10]) and readout.t1 == base.t1
    gates = scale_gate_errors(base, 1.5)
    assert gates.cz_error == pytest.approx([1.5 * e for e in base.cz_error]) and gates.readout_p01 == base.readout_p01
    bad = degrade_qubit(base, 1, t1_factor=0.2, cz_factor=3.0)
    assert bad.t1[1] == pytest.approx(0.2 * base.t1[1]) and bad.t1[0] == base.t1[0]
    assert bad.cz_error[:2] == pytest.approx([3 * e for e in base.cz_error[:2]]) and bad.cz_error[2] == base.cz_error[2]


def test_condition_shares_one_noise_model_across_scales() -> None:
    """Folding, not the noise model, carries the noise amplification."""
    from trustqem.config import ExperimentConfig
    simulators = DeviceCondition("monday", _calibration()).build_simulators(
        ExperimentConfig(noise_scale_factors=(1.0, 3.0, 5.0)))
    assert len({id(simulator) for simulator in simulators.values()}) == 1


def _same_channel(first, second) -> bool:
    """Two noise errors act identically (compared as superoperators)."""
    return np.allclose(SuperOp(first.to_quantumchannel()).data, SuperOp(second.to_quantumchannel()).data, atol=1e-9)


@pytest.mark.slow
def test_gate_noise_matches_aer_from_backend() -> None:
    """Every gate and readout error on the chain equals the one Aer's NoiseModel.from_backend builds for the
    same physical qubits. Two deliberate differences: we add idle decay, and readout keeps IBM's asymmetric flip
    probabilities where Aer uses their average."""
    calibration = _calibration()
    theirs = NoiseModel.from_backend(_backend())
    ours = build_device_noise_model(calibration)
    physical = calibration.physical_qubits
    for compact, qubit in enumerate(physical):
        for name in ("sx", "x"):
            assert _same_channel(ours._local_quantum_errors[name][(compact,)],
                                 theirs._local_quantum_errors[name][(qubit,)])
        our_flips = np.diag(np.fliplr(ours._local_readout_errors[(compact,)].probabilities))
        their_flips = np.diag(np.fliplr(theirs._local_readout_errors[(qubit,)].probabilities))
        assert our_flips.mean() == pytest.approx(their_flips.mean(), abs=1e-9)
    for edge in range(3):
        pair = (physical[edge], physical[edge + 1])
        their_pair = pair if pair in theirs._local_quantum_errors["cz"] else pair[::-1]
        our_pair = (edge, edge + 1) if their_pair == pair else (edge + 1, edge)
        assert _same_channel(ours._local_quantum_errors["cz"][our_pair], theirs._local_quantum_errors["cz"][their_pair])
