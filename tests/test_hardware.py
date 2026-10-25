"""Unit tests for the hardware path: session files, mapping onto physical qubits, counts, and the budget guard."""

import json
from functools import cache

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp, Statevector

from trustqem.circuits import CLIFFORD_ANGLES, build_random_records
from trustqem.hardware import (
    HardwareSession,
    build_session_records,
    load_manifest,
    load_probabilities,
    load_records,
    map_to_device,
    prepare_session,
    submit_session,
)
from trustqem.pool import pool_from_probabilities
from trustqem.simulate import build_observable_labels, build_sign_table, ideal_expectation_values

SMALL = {"test_circuits": 2, "oracle_circuits": 2, "twin_circuits": 2}


@cache
def _backend():
    from qiskit_ibm_runtime.fake_provider import FakeFez
    return FakeFez()


def _spec(**changes) -> HardwareSession:
    return HardwareSession(session="S1", backend_name="fake_fez", physical_qubits=(136, 143, 142, 141),
                           **{**SMALL, **changes})


def test_roles_partition_the_session() -> None:
    """Test, oracle and twin ids are consecutive, disjoint and cover every circuit."""
    spec = _spec(test_circuits=3, oracle_circuits=4, twin_circuits=5)
    ids = np.concatenate([spec.role_ids(role) for role in ("test", "oracle", "twin")])
    assert ids.tolist() == list(range(spec.circuit_count))


def test_session_records_have_near_clifford_twins() -> None:
    """Twins keep at most k non-Clifford rotations; the same seed gives the same circuits."""
    spec = _spec(twin_non_clifford_count=2)
    records = build_session_records(spec)
    assert len(records) == spec.circuit_count
    for index in spec.role_ids("twin"):
        angles = [float(i.operation.params[0]) % (2 * np.pi) for i in records[index].circuit.data
                  if i.operation.name in ("rx", "ry", "rz")]
        off_grid = sum(not any(np.isclose(a, c) for c in (*CLIFFORD_ANGLES, 2 * np.pi)) for a in angles)
        assert off_grid <= 2
    again = build_session_records(spec)
    assert all(a.circuit == b.circuit for a, b in zip(records, again, strict=True))


@pytest.mark.parametrize("scale", [1.0, 3.0, 5.0])
def test_mapping_to_device_keeps_every_fold(scale: float) -> None:
    """On the physical chain, at optimisation level 0, the sx/x/cz counts equal the folded counts."""
    from trustqem.device import fold_gates, transpile_to_device
    circuit = build_random_records(1, 4, 6, 0.5, np.random.default_rng(1))[0].circuit
    expected = fold_gates(transpile_to_device(circuit), scale).count_ops()
    physical = map_to_device(circuit, scale, _backend(), (136, 143, 142, 141))
    for name in ("sx", "x", "cz"):
        assert physical.count_ops().get(name, 0) == expected.get(name, 0)
    used = {physical.find_bit(q).index for i in physical.data for q in i.qubits if i.operation.name != "barrier"}
    assert used == {136, 143, 142, 141}


def test_pool_from_ideal_probabilities_recovers_ideal_values() -> None:
    """Noiseless fractions give noisy values equal to the ideal ones at every scale."""
    records = build_random_records(3, 4, 5, 0.5, np.random.default_rng(2))
    labels = build_observable_labels(4)
    observables = [SparsePauliOp(label) for label in labels]
    probabilities = np.array([[Statevector(r.circuit).probabilities()] * 3 for r in records])
    pool = pool_from_probabilities(records, "ideal", probabilities, 1000, observables, labels,
                                   build_sign_table(labels, 4))
    for scale in range(3):
        assert np.allclose(pool.row_noisy_values[:, scale], pool.row_ideal_values)
    assert np.allclose(pool.row_ideal_values[:len(labels)], ideal_expectation_values(records[0].circuit, observables))


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    """A tiny dry-run session on FakeFez."""
    session_dir = tmp_path_factory.mktemp("hardware") / "S1"
    prepare_session(session_dir, "S1", "ibm_fez", dry_run=True, **SMALL)
    return session_dir


def test_prepare_round_trips_manifest_and_circuits(prepared) -> None:
    """The manifest and QPY files reload into the same spec and circuits."""
    spec = load_manifest(prepared)
    assert spec.dry_run and spec.circuit_count == 6 and len(spec.physical_qubits) == 4
    assert [r.circuit for r in load_records(prepared)] == [r.circuit for r in build_session_records(spec)]
    calibration = json.loads((prepared / "calibration.json").read_text())
    assert list(calibration["physical_qubits"]) == list(spec.physical_qubits)


def test_budget_guard_refuses_expensive_jobs(prepared) -> None:
    """Above the cap, submit stops before contacting any device."""
    with pytest.raises(RuntimeError, match="over the"):
        submit_session(prepared, budget_cap_seconds=0.1)


def test_dry_run_submit_saves_counts_in_order(prepared) -> None:
    """One count dictionary per circuit and scale; fractions per circuit sum to 1."""
    submit_session(prepared)
    probabilities = load_probabilities(prepared)
    assert probabilities.shape == (6, 3, 16)
    assert np.allclose(probabilities.sum(axis=2), 1)
