"""Experiment: do conformal intervals on learned mitigation survive drift, and does Clifford recalibration fix them?

One repeat = a fresh random split of Monday circuits into train / calibration / test, a freshly trained model, and
fresh random draws of the Tuesday test set and of the K recalibration circuits.
"""

import json
import logging
from dataclasses import asdict, dataclass
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
from trustqem.experiments.report import plot_coverage_by_scenario, summarize, write_verdict
from trustqem.mitigation import learned_predictions, train_learned_mitigator
from trustqem.pool import SimulatedPool
from trustqem.recalibrate import (
    clifford_direct_quantile,
    clifford_ratio_quantile,
    drift_alarm_p_value,
    per_circuit_mean,
)

logger = logging.getLogger(__name__)


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
    model = train_learned_mitigator(monday.model_inputs()[train_rows], monday.row_ideal_values[train_rows], config)
    monday_predictions, monday_scores = _scores(model, monday)
    monday_quantile = conformal_quantile(monday_scores[monday.rows_of(calibration_ids)], profile.alpha)

    rows = _evaluate_test_set(repeat, "monday", monday, monday_predictions, monday_scores, test_ids,
                              monday_quantile, bootstrap["monday"])
    monday_twin_scores = {keep: _scores(model, pool)[1] for keep, pool in pools.monday_twins.items()}
    alarms = []
    for scenario in pools.tuesday:
        scenario_rows, scenario_alarms = _evaluate_scenario(
            pools, profile, repeat, scenario, model, monday_quantile, monday_twin_scores, bootstrap[scenario], rng)
        rows.extend(scenario_rows)
        alarms.extend(scenario_alarms)
    return rows, alarms


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


def _evaluate_scenario(pools: ExperimentPools, profile: DriftProfile, repeat: int, scenario: str, model,
                       monday_quantile: float, monday_twin_scores: dict[int, np.ndarray], bootstrap: tuple,
                       rng: np.random.Generator) -> tuple[list[ResultRow], list[dict]]:
    """All recalibration methods, K values and twin types for one drift scenario."""
    tuesday = pools.tuesday[scenario]
    predictions, scores = _scores(model, tuesday)
    order = rng.permutation(tuesday.circuit_count)
    test_ids, oracle_source = order[:profile.test_circuits], order[profile.test_circuits:]
    rows = _evaluate_test_set(repeat, scenario, tuesday, predictions, scores, test_ids, monday_quantile, bootstrap)
    test_rows = tuesday.rows_of(test_ids)
    truths, test_predictions = tuesday.row_ideal_values[test_rows], predictions[test_rows]
    mae = float(scores[test_rows].mean())
    alarms = []

    def add(method: str, count: int, keep: int, quantile: float) -> None:
        report = evaluate_symmetric_intervals(test_predictions, truths, quantile)
        rows.append(ResultRow(repeat, scenario, method, count, keep, report.coverage, report.mean_width, mae))

    for count in profile.recalibration_counts:
        oracle_ids = rng.choice(oracle_source, size=count, replace=False)
        add("R3_oracle", count, -1, conformal_quantile(scores[tuesday.rows_of(oracle_ids)], profile.alpha))
        for keep in pools.sizes.twin_non_clifford_counts:
            twin_pool = pools.tuesday_twins[(scenario, keep)]
            _, twin_scores = _scores(model, twin_pool)
            twin_ids = rng.choice(test_ids, size=min(count, test_ids.size), replace=False)   # twins of test circuits
            twin_rows = twin_pool.rows_of(twin_ids)
            monday_pool = pools.monday_twins[keep]
            monday_ids = rng.choice(monday_pool.circuit_count, size=min(count, monday_pool.circuit_count),
                                    replace=False)
            monday_rows = monday_pool.rows_of(monday_ids)
            before, after = monday_twin_scores[keep][monday_rows], twin_scores[twin_rows]
            add("R1_clifford_direct", count, keep, clifford_direct_quantile(after, profile.alpha))
            add("R2_clifford_ratio", count, keep,
                clifford_ratio_quantile(monday_quantile, before, after, profile.alpha))
            alarms.append({"repeat": repeat, "scenario": scenario, "recalibration_count": count,
                           "non_clifford_count": keep, "p_value": drift_alarm_p_value(
                               per_circuit_mean(before, monday_pool.row_circuit_index[monday_rows]),
                               per_circuit_mean(after, twin_pool.row_circuit_index[twin_rows]))})
    return rows, alarms


def run(profile_name: str, results_root: Path) -> Path:
    """Run every repeat of the drift experiment and write results, figures and the verdict."""
    profile = PROFILES[profile_name]
    config = ExperimentConfig()
    output_dir = results_root / "drift" / profile_name
    pools = load_or_build_pools(config, profile.sizes, output_dir / "pools.pkl")
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
    plot_coverage_by_scenario(summary, profile.alpha, max(profile.recalibration_counts)).savefig(
        output_dir / "coverage_by_scenario.png", dpi=200)
    write_verdict(summary, profile.alpha, output_dir / "verdict.md")
    return output_dir
