"""Unit tests for the parts copied from Luke's notebook."""

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp, Statevector

from trustqem.circuits import build_random_circuit
from trustqem.config import ExperimentConfig
from trustqem.mitigation import zne_extrapolate
from trustqem.simulate import build_observable_labels, build_sign_table, ideal_expectation_values

SCALES = (1.0, 2.0, 3.0)


def test_observable_labels_for_four_qubits() -> None:
    """Four single Z's then three neighboring ZZ's, rightmost character is qubit 0."""
    assert build_observable_labels(4) == ["IIIZ", "IIZI", "IZII", "ZIII", "IIZZ", "IZZI", "ZZII"]


@pytest.mark.parametrize("seed", range(5))
def test_sign_table_matches_exact_expectations(seed: int) -> None:
    """Sign table times ideal probabilities must equal qiskit's exact Pauli expectations."""
    rng = np.random.default_rng(seed)
    circuit, _ = build_random_circuit(4, 4, 0.5, rng)
    labels = build_observable_labels(4)
    observables = [SparsePauliOp(label) for label in labels]
    from_table = build_sign_table(labels, 4) @ Statevector(circuit).probabilities()
    assert np.allclose(from_table, ideal_expectation_values(circuit, observables))


def test_linear_zne_weights() -> None:
    """With scales 1, 2, 3 linear ZNE is (4/3) y1 + (1/3) y2 - (2/3) y3, as Luke's notebook states."""
    y = np.array([0.6, 0.45, 0.33])
    assert zne_extrapolate(y, SCALES, 1) == pytest.approx(4 / 3 * y[0] + 1 / 3 * y[1] - 2 / 3 * y[2])


def test_quadratic_zne_weights() -> None:
    """Quadratic ZNE is 3 y1 - 3 y2 + y3."""
    y = np.array([0.6, 0.45, 0.33])
    assert zne_extrapolate(y, SCALES, 2) == pytest.approx(3 * y[0] - 3 * y[1] + y[2])


def test_zne_recovers_a_straight_line_exactly() -> None:
    """If the noisy values really lie on a line, linear ZNE returns its intercept."""
    y = 0.8 - 0.1 * np.array(SCALES)
    assert zne_extrapolate(y, SCALES, 1) == pytest.approx(0.8)


def test_config_rejects_bad_first_scale() -> None:
    """Downstream code treats column 0 as the base noise, so the first scale must be 1.0."""
    with pytest.raises(ValueError):
        ExperimentConfig(noise_scale_factors=(2.0, 3.0))
