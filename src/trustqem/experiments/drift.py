"""Experiment: do conformal intervals on learned mitigation survive drift, and does Clifford recalibration fix them?

One repeat = a fresh random split of Monday circuits into train / calibration / test, a freshly trained model, and
fresh random draws of the Tuesday test set and of the K recalibration circuits.
"""

import json
import logging
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from trustqem.baselines import bootstrap_zne_intervals
from trustqem.config import ExperimentConfig
from trustqem.conformal import (
    absolute_residual_scores,
    conformal_quantile,
    evaluate_intervals,
    evaluate_symmetric_intervals,
)
from trustqem.experiments.pools import ExperimentPools, PoolSizes, load_or_build_pools
from trustqem.experiments.report import (
    plot_coverage_by_scenario,
    plot_recalibration_budget,
    summarize,
    write_verdict,
)
from trustqem.mitigation import learned_predictions, train_learned_mitigator
from trustqem.noise import DRIFT_SCENARIOS
from trustqem.pool import SimulatedPool
from trustqem.recalibrate import (
    clifford_direct_quantile,
    clifford_ratio_quantile,
    clifford_weighted_quantiles,
    drift_alarm_p_value,
    per_circuit_mean,
    shift_features,
)

logger = logging.getLogger(__name__)

NONZERO_IDEAL, NONZERO_MIN_ROWS = 0.1, 20       # Amendment 5, R1N


@dataclass(frozen=True)
class DriftProfile:
    """Sizes for one run of the drift experiment."""

    sizes: PoolSizes
    train_circuits: int
    calibration_circuits: int
    test_circuits: int              # Monday test, and Tuesday test per scenario
    recalibration_counts: tuple[int, ...]   # K values
    repeats: int
    alpha: float = 0.1
    bootstrap_resamples: int = 200
    random_seed: int = 42
    retrain_counts: tuple[int, ...] = ()        # N labeled drifted circuits for R4; empty skips R4
    retrain_calibration_circuits: int = 100
    qubit_count: int = 4


def scale_profile(qubit_count: int) -> DriftProfile:
    """Amendment 4 scaling study: doubled sizes, twins k in {2, 4} (plus 0 and 8 at 4 qubits), seed 5050 + n."""
    keeps = (0, 2, 4, 8) if qubit_count == 4 else (2, 4)
    return DriftProfile(
        sizes=PoolSizes(monday_circuits=1000, monday_twin_sources=400, tuesday_circuits=800,
                        twin_non_clifford_counts=keeps, scenarios=tuple(DRIFT_SCENARIOS)),
        train_circuits=600, calibration_circuits=200, test_circuits=200,
        recalibration_counts=(10, 25, 50, 100, 200), repeats=20, random_seed=5050 + qubit_count,
        qubit_count=qubit_count)


SCALE_QUBIT_COUNTS = (4, 6, 8, 10, 12)


PROFILES = {
    "smoke": DriftProfile(
        sizes=PoolSizes(monday_circuits=60, monday_twin_sources=20, tuesday_circuits=40,
                        twin_non_clifford_counts=(0, 2), scenarios=("D0_no_drift", "D2_depolarizing_x2")),
        train_circuits=30, calibration_circuits=15, test_circuits=15, recalibration_counts=(10,), repeats=2,
        bootstrap_resamples=50),
    "pilot": DriftProfile(
        sizes=PoolSizes(monday_circuits=500, monday_twin_sources=150, tuesday_circuits=300,
                        twin_non_clifford_counts=(0, 2, 4),
                        scenarios=("D0_no_drift", "D2_depolarizing_x2", "D4_thermal_relaxation", "D6_combined")),
        train_circuits=300, calibration_circuits=100, test_circuits=100, recalibration_counts=(25, 50, 100),
        repeats=5),
    # confirmation run for Amendment 1 (docs/HYPOTHESES.md): fresh seed, every scenario, 20 repeats
    "full": DriftProfile(
        sizes=PoolSizes(monday_circuits=500, monday_twin_sources=200, tuesday_circuits=400,
                        twin_non_clifford_counts=(0, 2, 4, 8), scenarios=tuple(DRIFT_SCENARIOS)),
        train_circuits=300, calibration_circuits=100, test_circuits=100,
        recalibration_counts=(10, 25, 50, 100, 200), repeats=20, random_seed=2026, retrain_counts=(50, 100, 200)),
    **{f"scale_q{n}": scale_profile(n) for n in SCALE_QUBIT_COUNTS},
}


@dataclass(frozen=True)
class ResultRow:
    """One method's intervals on one test set in one repeat."""

    repeat: int
    scenario: str
    method: str
    recalibration_count: int        # K, 0 when not applicable
    non_clifford_count: int         # k, -1 when not applicable
    coverage: float
    mean_width: float
    model_mae: float


def _scores(model, pool: SimulatedPool) -> tuple[np.ndarray, np.ndarray]:
    """Frozen-model predictions and absolute residual scores for every row of a pool."""
    predictions = learned_predictions(model, pool.model_inputs())
    return predictions, absolute_residual_scores(predictions, pool.row_ideal_values)


def _bootstrap_by_pool(pools: ExperimentPools, profile: DriftProfile) -> dict[str, tuple]:
    """ZNE bootstrap intervals for Monday and every Tuesday pool, computed once."""
    rng = np.random.default_rng(pools.config.random_seed + 7)
    targets = {"monday": pools.monday, **pools.tuesday}
    return {name: bootstrap_zne_intervals(pool.probabilities, pools.sign_table, pools.config.noise_scale_factors,
                                          pool.shots, profile.alpha, profile.bootstrap_resamples, rng)
            for name, pool in targets.items()}


def run_repeat(pools: ExperimentPools, profile: DriftProfile, repeat: int,
               bootstrap: dict[str, tuple]) -> tuple[list[ResultRow], list[dict]]:
    """Train on a fresh Monday split, then score every method on Monday test and on every Tuesday scenario."""
    config, rng = pools.config, np.random.default_rng(pools.config.random_seed + 1000 + repeat)
    order = rng.permutation(pools.monday.circuit_count)
    train_ids = order[:profile.train_circuits]
    calibration_ids = order[profile.train_circuits:profile.train_circuits + profile.calibration_circuits]
    test_ids = order[profile.train_circuits + profile.calibration_circuits:][:profile.test_circuits]

    monday = pools.monday
    train_rows = monday.rows_of(train_ids)
    training = (monday.model_inputs()[train_rows], monday.row_ideal_values[train_rows])
    model = train_learned_mitigator(*training, config)
    monday_predictions, monday_scores = _scores(model, monday)
    monday_quantile = conformal_quantile(monday_scores[monday.rows_of(calibration_ids)], profile.alpha)

    rows = _evaluate_test_set(repeat, "monday", monday, monday_predictions, monday_scores, test_ids,
                              monday_quantile, bootstrap["monday"])
    context = _RepeatContext(pools, profile, repeat, model, monday_quantile, training,
                             {keep: _scores(model, pool)[1] for keep, pool in pools.monday_twins.items()})
    alarms = []
    for scenario in pools.tuesday:
        scenario_rows, scenario_alarms = _evaluate_scenario(context, scenario, bootstrap[scenario], rng)
        rows.extend(scenario_rows)
        alarms.extend(scenario_alarms)
    return rows, alarms


@dataclass(frozen=True)
class _RepeatContext:
    """What every scenario in one repeat shares: the frozen Monday model and its calibration."""

    pools: ExperimentPools
    profile: DriftProfile
    repeat: int
    model: object
    monday_quantile: float
    training: tuple[np.ndarray, np.ndarray]         # Monday training inputs and ideal values, reused by R4
    monday_twin_scores: dict[int, np.ndarray]


def _evaluate_test_set(repeat: int, scenario: str, pool: SimulatedPool, predictions: np.ndarray,
                       scores: np.ndarray, test_ids: np.ndarray, frozen_quantile: float,
                       bootstrap: tuple) -> list[ResultRow]:
    """Frozen conformal intervals and the ZNE bootstrap baseline on one test set."""
    test_rows = pool.rows_of(test_ids)
    truths = pool.row_ideal_values[test_rows]
    mae = float(scores[test_rows].mean())
    frozen = evaluate_symmetric_intervals(predictions[test_rows], truths, frozen_quantile)
    zne_point, zne_lower, zne_upper = bootstrap
    zne = evaluate_intervals(zne_lower[test_rows], zne_upper[test_rows], truths)
    zne_mae = float(np.abs(zne_point[test_rows] - truths).mean())
    method = "conformal_monday" if scenario == "monday" else "R0_frozen"
    return [ResultRow(repeat, scenario, method, 0, -1, frozen.coverage, frozen.mean_width, mae),
            ResultRow(repeat, scenario, "zne_bootstrap", 0, -1, zne.coverage, zne.mean_width, zne_mae)]


def _evaluate_scenario(context: _RepeatContext, scenario: str, bootstrap: tuple,
                       rng: np.random.Generator) -> tuple[list[ResultRow], list[dict]]:
    """All recalibration methods, K values and twin types for one drift scenario."""
    pools, profile, repeat = context.pools, context.profile, context.repeat
    tuesday = pools.tuesday[scenario]
    predictions, scores = _scores(context.model, tuesday)
    order = rng.permutation(tuesday.circuit_count)
    test_ids, oracle_source = order[:profile.test_circuits], order[profile.test_circuits:]
    rows = _evaluate_test_set(repeat, scenario, tuesday, predictions, scores, test_ids, context.monday_quantile,
                              bootstrap)
    test_rows = tuesday.rows_of(test_ids)
    truths, test_predictions = tuesday.row_ideal_values[test_rows], predictions[test_rows]
    test_shift = shift_features(tuesday.row_noisy_values[test_rows], tuesday.row_features[test_rows])
    mae = float(scores[test_rows].mean())
    twin_scores = {keep: _scores(context.model, pools.tuesday_twins[(scenario, keep)])[1]
                   for keep in pools.sizes.twin_non_clifford_counts}
    alarms = []

    def add(method: str, count: int, keep: int, quantile: float | np.ndarray) -> None:
        report = evaluate_symmetric_intervals(test_predictions, truths, quantile)
        rows.append(ResultRow(repeat, scenario, method, count, keep, report.coverage, report.mean_width, mae))

    for count in profile.recalibration_counts:
        if count <= oracle_source.size:
            oracle_ids = rng.choice(oracle_source, size=count, replace=False)
            add("R3_oracle", count, -1, conformal_quantile(scores[tuesday.rows_of(oracle_ids)], profile.alpha))
        for keep in pools.sizes.twin_non_clifford_counts:
            twin_pool, monday_pool = pools.tuesday_twins[(scenario, keep)], pools.monday_twins[keep]
            twin_rows = twin_pool.rows_of(rng.choice(twin_pool.circuit_count, size=count, replace=False))
            monday_rows = monday_pool.rows_of(rng.choice(monday_pool.circuit_count,
                                                         size=min(count, monday_pool.circuit_count), replace=False))
            before, after = context.monday_twin_scores[keep][monday_rows], twin_scores[keep][twin_rows]
            twin_shift = shift_features(twin_pool.row_noisy_values[twin_rows], twin_pool.row_features[twin_rows])
            add("R1_clifford_direct", count, keep, clifford_direct_quantile(after, profile.alpha))
            add("R2_clifford_ratio", count, keep,
                clifford_ratio_quantile(context.monday_quantile, before, after, profile.alpha))
            add("R1W_clifford_weighted", count, keep,
                clifford_weighted_quantiles(after, twin_shift, test_shift, profile.alpha))
            nonzero = np.abs(twin_pool.row_ideal_values[twin_rows]) > NONZERO_IDEAL
            if nonzero.sum() >= NONZERO_MIN_ROWS:           # Amendment 5, R1N: only twin rows with signal
                add("R1N_nonzero_weighted", count, keep,
                    clifford_weighted_quantiles(after[nonzero], twin_shift[nonzero], test_shift, profile.alpha))
            alarms.append({"repeat": repeat, "scenario": scenario, "recalibration_count": count,
                           "non_clifford_count": keep, "p_value": drift_alarm_p_value(
                               per_circuit_mean(before, monday_pool.row_circuit_index[monday_rows]),
                               per_circuit_mean(after, twin_pool.row_circuit_index[twin_rows]))})
    rows.extend(_retrain_rows(context, scenario, tuesday, test_ids, oracle_source, rng))
    return rows, alarms


def _retrain_rows(context: _RepeatContext, scenario: str, tuesday: SimulatedPool, test_ids: np.ndarray,
                  oracle_source: np.ndarray, rng: np.random.Generator) -> list[ResultRow]:
    """R4: retrain on Monday plus N labeled drifted circuits, then calibrate on more labeled drifted circuits."""
    profile, rows = context.profile, []
    test_rows = tuesday.rows_of(test_ids)
    for count in profile.retrain_counts:
        labeled = rng.choice(oracle_source, size=count + profile.retrain_calibration_circuits, replace=False)
        fit_rows, calibration_rows = tuesday.rows_of(labeled[:count]), tuesday.rows_of(labeled[count:])
        model = train_learned_mitigator(
            np.vstack([context.training[0], tuesday.model_inputs()[fit_rows]]),
            np.concatenate([context.training[1], tuesday.row_ideal_values[fit_rows]]), context.pools.config)
        predictions, scores = _scores(model, tuesday)
        report = evaluate_symmetric_intervals(predictions[test_rows], tuesday.row_ideal_values[test_rows],
                                              conformal_quantile(scores[calibration_rows], profile.alpha))
        rows.append(ResultRow(context.repeat, scenario, "R4_retrain", count, -1, report.coverage,
                              report.mean_width, float(scores[test_rows].mean())))
    return rows


def run(profile_name: str, results_root: Path, output_dir: Path | None = None) -> Path:
    """Run every repeat of the drift experiment and write results, figures and the verdict.

    Pools always come from (or go to) the drift cache; `output_dir` only moves the outputs (Amendment 5 reruns)."""
    profile = PROFILES[profile_name]
    config = replace(ExperimentConfig(), random_seed=profile.random_seed, qubit_count=profile.qubit_count)
    pools_path = results_root / "drift" / profile_name / "pools.pkl"
    output_dir = output_dir or pools_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    pools_path.parent.mkdir(parents=True, exist_ok=True)
    pools = load_or_build_pools(config, profile.sizes, pools_path)
    bootstrap = _bootstrap_by_pool(pools, profile)

    all_rows, all_alarms = [], []
    for repeat in range(profile.repeats):
        rows, alarms = run_repeat(pools, profile, repeat, bootstrap)
        all_rows.extend(rows)
        all_alarms.extend(alarms)
        logger.info("repeat %d/%d done", repeat + 1, profile.repeats)

    summary = summarize([asdict(row) for row in all_rows], all_alarms, profile.alpha)
    (output_dir / "config.json").write_text(json.dumps(
        {"config": config.to_dict(), "profile": asdict(profile)}, indent=2, default=str))
    (output_dir / "rows.json").write_text(json.dumps([asdict(row) for row in all_rows]))
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    headline_count = 100 if 100 in profile.recalibration_counts else max(profile.recalibration_counts)
    plot_coverage_by_scenario(summary, profile.alpha, headline_count).savefig(
        output_dir / "coverage_by_scenario.png", dpi=200)
    plot_recalibration_budget(summary, profile.alpha).savefig(output_dir / "recalibration_budget.png", dpi=200)
    write_verdict(summary, profile.alpha, output_dir / "verdict.md")
    return output_dir
