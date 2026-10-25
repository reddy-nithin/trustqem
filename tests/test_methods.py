"""Unit tests for conformal intervals, Clifford twins, drift scenarios and baselines."""

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp, Statevector

from trustqem.baselines import bootstrap_zne_intervals, linear_zne_weights
from trustqem.circuits import build_clifford_twin, build_random_records, is_clifford
from trustqem.config import ExperimentConfig
from trustqem.conformal import (
    absolute_residual_scores,
    conformal_quantile,
    evaluate_symmetric_intervals,
    per_circuit_max_scores,
    weighted_conformal_quantiles,
)
from trustqem.noise import DRIFT_SCENARIOS, MONDAY
from trustqem.recalibrate import (
    clifford_ratio_quantile,
    clifford_weighted_quantiles,
    drift_alarm_p_value,
    fit_shift_weigher,
)
from trustqem.simulate import build_observable_labels, build_sign_table, ideal_expectation_values


def test_conformal_quantile_hand_example() -> None:
    """n=9, alpha=0.1: rank ceil(10*0.9)=9, so the largest score."""
    assert conformal_quantile(np.arange(1, 10), 0.1) == 9.0
    # n=19: rank ceil(20*0.9)=18
    assert conformal_quantile(np.arange(1, 20), 0.1) == 18.0


def test_conformal_quantile_too_few_points_is_infinite() -> None:
    """With 5 points you can't promise 90%, so the honest interval is infinite."""
    assert conformal_quantile(np.ones(5), 0.1) == float("inf")


def test_conformal_coverage_on_exchangeable_data() -> None:
    """Averaged over many draws, coverage is at least 1 - alpha when calibration and test match."""
    rng = np.random.default_rng(0)
    coverages = []
    for _ in range(200):
        calibration = np.abs(rng.standard_t(3, size=200))
        test = np.abs(rng.standard_t(3, size=200))
        coverages.append((test <= conformal_quantile(calibration, 0.1)).mean())
    assert np.mean(coverages) >= 0.895


def test_symmetric_intervals_clip_to_physical_range() -> None:
    """Pauli expectations live in [-1, 1], so an interval never extends past it."""
    report = evaluate_symmetric_intervals(np.array([0.95]), np.array([1.0]), half_width=0.2)
    assert report.coverage == 1.0
    assert report.mean_width == pytest.approx(0.25)


def test_per_circuit_max_scores() -> None:
    """One score per circuit, the worst of its rows."""
    scores = np.array([0.1, 0.5, 0.2, 0.3])
    assert per_circuit_max_scores(scores, np.array([0, 0, 1, 1])).tolist() == [0.5, 0.3]


def test_absolute_residual_scores() -> None:
    """Scores are distances, never negative."""
    assert absolute_residual_scores(np.array([0.2, -0.1]), np.array([0.5, -0.4])).tolist() == pytest.approx([0.3, 0.3])


@pytest.mark.parametrize("seed", range(5))
def test_clifford_twin_is_clifford_and_keeps_layout(seed: int) -> None:
    """A k=0 twin is Clifford, has the same gate sequence names and CX pairs, and the same features."""
    rng = np.random.default_rng(seed)
    target = build_random_records(1, 4, 8, 0.5, rng)[0]
    twin = build_clifford_twin(target, non_clifford_keep=0, random_generator=rng)
    assert is_clifford(twin.circuit)
    assert not is_clifford(target.circuit)
    target_layout = [(i.operation.name, tuple(target.circuit.find_bit(q).index for q in i.qubits))
                     for i in target.circuit.data]
    twin_layout = [(i.operation.name, tuple(twin.circuit.find_bit(q).index for q in i.qubits))
                   for i in twin.circuit.data]
    assert twin_layout == target_layout
    assert (twin.layer_count, twin.cx_count) == (target.layer_count, target.cx_count)


def test_clifford_twin_ideal_values_are_zero_or_plus_minus_one() -> None:
    """Pauli expectations of a Clifford state are always 0, +1 or -1."""
    rng = np.random.default_rng(3)
    labels = build_observable_labels(4)
    observables = [SparsePauliOp(label) for label in labels]
    target = build_random_records(1, 4, 6, 0.5, rng)[0]
    values = ideal_expectation_values(build_clifford_twin(target, 0, rng).circuit, observables)
    assert np.all(np.isclose(values, 0) | np.isclose(np.abs(values), 1))


def test_near_clifford_twin_keeps_requested_rotations() -> None:
    """k kept rotations means the twin is no longer Clifford (for a random angle) and records k."""
    rng = np.random.default_rng(1)
    target = build_random_records(1, 4, 6, 0.5, rng)[0]
    twin = build_clifford_twin(target, non_clifford_keep=2, random_generator=rng)
    assert twin.non_clifford_count == 2
    assert not is_clifford(twin.circuit)


def test_no_drift_condition_matches_luke_noise_on_a_circuit() -> None:
    """D0 builds the same physics as Luke's all-qubit depolarizing model (exact noisy values agree)."""
    from trustqem.noise import build_noisy_simulators
    from trustqem.simulate import exact_noisy_expectation_values

    config = ExperimentConfig()
    rng = np.random.default_rng(5)
    observables = [SparsePauliOp(label) for label in build_observable_labels(4)]
    circuit = build_random_records(1, 4, 5, 0.5, rng)[0].circuit
    luke = exact_noisy_expectation_values(circuit, build_noisy_simulators(config)[2.0], observables)
    ours = exact_noisy_expectation_values(circuit, DRIFT_SCENARIOS["D0_no_drift"].build_simulators(config)[2.0],
                                          observables)
    assert np.allclose(luke, ours)


def test_every_drift_scenario_builds() -> None:
    """Each scenario produces a noise model at every scale without errors."""
    config = ExperimentConfig()
    for condition in [MONDAY, *DRIFT_SCENARIOS.values()]:
        for scale in config.noise_scale_factors:
            condition.build_noise_model(scale, config)


def test_bootstrap_interval_shrinks_with_shots() -> None:
    """More shots, tighter bootstrap intervals."""
    labels = build_observable_labels(2)
    sign_table = build_sign_table(labels, 2)
    probabilities = np.tile(np.array([0.4, 0.1, 0.2, 0.3]), (1, 3, 1))     # one circuit, three scales
    widths = []
    for shots in (100, 10000):
        _, lower, upper = bootstrap_zne_intervals(probabilities, sign_table, (1.0, 2.0, 3.0), shots, 0.1, 300,
                                                  np.random.default_rng(0))
        widths.append((upper - lower).mean())
    assert widths[1] < widths[0] / 5


def test_linear_zne_weights_match_formula() -> None:
    """Scales 1, 2, 3 give (4/3, 1/3, -2/3)."""
    assert linear_zne_weights((1.0, 2.0, 3.0)) == pytest.approx([4 / 3, 1 / 3, -2 / 3])


def test_clifford_ratio_quantile_scales_by_growth() -> None:
    """If Clifford residuals double, the random-circuit quantile doubles."""
    before = np.linspace(0, 1, 99)
    after = 2 * before
    assert clifford_ratio_quantile(0.3, before, after, 0.1) == pytest.approx(0.6)


def test_drift_alarm_quiet_on_same_distribution_and_loud_on_shift() -> None:
    """KS p-value is large for matching samples and tiny for shifted ones."""
    rng = np.random.default_rng(0)
    base = rng.normal(size=100)
    assert drift_alarm_p_value(base, rng.normal(size=100)) > 0.05
    assert drift_alarm_p_value(base, rng.normal(loc=1.0, size=100)) < 0.01


def test_sign_table_for_clifford_state() -> None:
    """Sanity: |00> has Z=+1 on both qubits and ZZ=+1."""
    sign_table = build_sign_table(build_observable_labels(2), 2)
    assert np.allclose(sign_table @ Statevector.from_label("00").probabilities(), [1, 1, 1])


def test_weighted_quantile_with_equal_weights_matches_plain_quantile() -> None:
    """Equal weights are ordinary split conformal."""
    rng = np.random.default_rng(0)
    for count in (9, 19, 50, 137):
        scores = rng.exponential(size=count)
        weighted = weighted_conformal_quantiles(scores, np.ones(count), np.ones(3), 0.1)
        assert np.all(weighted == conformal_quantile(scores, 0.1))


def test_weighted_quantile_is_infinite_when_test_weight_dominates() -> None:
    """A test point unlike every calibration point gets an honest infinite interval."""
    assert weighted_conformal_quantiles(np.arange(10.0), np.ones(10), np.array([100.0]), 0.1)[0] == np.inf


def test_weighted_quantile_rejects_negative_weights() -> None:
    """Weights are likelihood ratios, never negative."""
    with pytest.raises(ValueError):
        weighted_conformal_quantiles(np.ones(3), np.array([1.0, -1.0, 1.0]), np.ones(1), 0.1)


def test_shift_weigher_upweights_rows_that_look_like_the_target() -> None:
    """Source rows from the target's region get larger weights than rows from elsewhere."""
    rng = np.random.default_rng(1)
    source = rng.normal(0, 1, size=(500, 1))
    target = rng.normal(1, 1, size=(500, 1))
    weigh = fit_shift_weigher(source, target)
    assert weigh(np.array([[1.5]]))[0] > 1 > weigh(np.array([[-1.5]]))[0]


def test_weighted_recalibration_restores_coverage_under_covariate_shift() -> None:
    """Noise grows with |x|; calibration mostly near 0, test spread out. Plain conformal under-covers, weighted does
    not, averaged over draws."""
    rng = np.random.default_rng(2)
    plain, weighted = [], []
    for _ in range(40):
        calibration_x = rng.normal(0, 0.5, size=(400, 1))
        test_x = rng.normal(0, 1.5, size=(300, 1))
        calibration_scores = np.abs(rng.normal(size=400) * (0.1 + np.abs(calibration_x[:, 0])))
        test_scores = np.abs(rng.normal(size=300) * (0.1 + np.abs(test_x[:, 0])))
        plain.append((test_scores <= conformal_quantile(calibration_scores, 0.1)).mean())
        quantiles = clifford_weighted_quantiles(calibration_scores, calibration_x, test_x, 0.1)
        weighted.append((test_scores <= quantiles).mean())
    assert np.mean(plain) < 0.85
    assert np.mean(weighted) > np.mean(plain) + 0.03
