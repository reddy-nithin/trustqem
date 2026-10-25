"""Experiment (Stage 4): do Clifford-recalibrated error bars hold on a real IBM device? (Amendment 3)

Monday is simulated from the device's calibration on the first session's day, so the model never sees hardware
data. Each hardware session (a "Tuesday") runs test, oracle and near-Clifford twin circuits at fold scales 1, 3, 5.
The shift the twins must repair is simulator-to-hardware plus day-to-day drift. Hardware data are fixed, so
uncertainty comes from a circuit-level bootstrap rather than repeated simulation.
"""

import json
import logging
import pickle
from dataclasses import dataclass, replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from qiskit.quantum_info import SparsePauliOp

from trustqem.baselines import bootstrap_zne_intervals
from trustqem.circuits import build_clifford_twin, build_random_records
from trustqem.config import ExperimentConfig
from trustqem.conformal import absolute_residual_scores, conformal_quantile, evaluate_symmetric_intervals
from trustqem.device import DeviceCalibration, DeviceCondition
from trustqem.hardware import HardwareSession, load_manifest, load_probabilities, load_records
from trustqem.mitigation import learned_predictions, train_learned_mitigator
from trustqem.pool import SimulatedPool, pool_from_probabilities, simulate_pool
from trustqem.recalibrate import (
    clifford_direct_quantile,
    clifford_ratio_quantile,
    clifford_weighted_quantiles,
    drift_alarm_p_value,
    per_circuit_mean,
    shift_features,
)
from trustqem.simulate import build_observable_labels, build_sign_table

logger = logging.getLogger(__name__)

ALPHA = 0.1
TOLERANCE = 0.03
FROZEN_BREAK_THRESHOLD = 0.87          # H2-hw: frozen intervals cover less than this in at least one session
MONDAY_TRAIN, MONDAY_CALIBRATION, MONDAY_TWIN_SOURCES = 300, 100, 200
CALIBRATION_DRAWS, BOOTSTRAP_RESAMPLES = 200, 1000
SMALL_K = 25


@dataclass(frozen=True)
class Monday:
    """The frozen model trained on simulated Monday data, and what recalibration needs from Monday."""

    key: str
    config: ExperimentConfig
    model: object
    quantile: float
    twin_scores: np.ndarray
    twin_circuit_index: np.ndarray


def _observables(qubit_count: int) -> tuple[list[str], list[SparsePauliOp], np.ndarray]:
    labels = build_observable_labels(qubit_count)
    return labels, [SparsePauliOp(label) for label in labels], build_sign_table(labels, qubit_count)


def experiment_config(spec: HardwareSession) -> ExperimentConfig:
    """The session's circuit recipe, shots and fold scales as an ExperimentConfig."""
    return replace(ExperimentConfig(), random_seed=spec.seed, qubit_count=spec.qubit_count, max_layers=spec.max_layers,
                   cx_probability_per_pair=spec.cx_probability_per_pair, noise_scale_factors=spec.fold_scales,
                   shots_per_circuit=spec.shots)


def build_monday(calibration: DeviceCalibration, spec: HardwareSession, cache_path: Path) -> Monday:
    """Simulate Monday on this calibration, train the model, calibrate it. Cached by calibration and spec."""
    key = json.dumps([calibration.to_dict(), spec.seed, spec.twin_non_clifford_count, list(spec.fold_scales)])
    if cache_path.exists():
        with open(cache_path, "rb") as file:
            cached: Monday = pickle.load(file)
        if cached.key == key:
            return cached
    config = experiment_config(spec)
    labels, observables, sign_table = _observables(spec.qubit_count)
    rng = np.random.default_rng(spec.seed + 1)
    condition = DeviceCondition("monday", calibration)
    simulators = condition.build_simulators(config)

    def simulate(records, tag: str) -> SimulatedPool:
        return simulate_pool(records, tag, simulators, config, observables, labels, sign_table, rng,
                             prepare=condition.prepare_circuit)

    def random_records(count: int):
        return build_random_records(count, spec.qubit_count, spec.max_layers, spec.cx_probability_per_pair, rng)

    pool = simulate(random_records(MONDAY_TRAIN + MONDAY_CALIBRATION), "monday")
    twins = simulate([build_clifford_twin(record, spec.twin_non_clifford_count, rng)
                      for record in random_records(MONDAY_TWIN_SOURCES)], "monday_twins")
    train_rows = pool.rows_of(np.arange(MONDAY_TRAIN))
    model = train_learned_mitigator(pool.model_inputs()[train_rows], pool.row_ideal_values[train_rows], config)
    calibration_rows = pool.rows_of(np.arange(MONDAY_TRAIN, MONDAY_TRAIN + MONDAY_CALIBRATION))
    quantile = conformal_quantile(_scores(model, pool)[calibration_rows], ALPHA)
    monday = Monday(key, config, model, quantile, _scores(model, twins), twins.row_circuit_index)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as file:
        pickle.dump(monday, file)
    return monday


def _scores(model, pool: SimulatedPool) -> np.ndarray:
    return absolute_residual_scores(learned_predictions(model, pool.model_inputs()), pool.row_ideal_values)


def session_pools(session_dir: Path) -> dict[str, SimulatedPool]:
    """The session's measured counts as one pool per role (test, oracle, twin)."""
    spec = load_manifest(session_dir)
    records, probabilities = load_records(session_dir), load_probabilities(session_dir)
    labels, observables, sign_table = _observables(spec.qubit_count)
    pools = {}
    for role in ("test", "oracle", "twin"):
        ids = spec.role_ids(role)
        pools[role] = pool_from_probabilities([records[i] for i in ids], f"{spec.session}_{role}",
                                              probabilities[ids], spec.shots, observables, labels, sign_table)
    return pools


def _row_index(pool: SimulatedPool) -> list[np.ndarray]:
    """Row indices of each circuit, so circuit-level resamples can repeat a circuit."""
    return [np.flatnonzero(pool.row_circuit_index == c) for c in range(pool.circuit_count)]


@dataclass(frozen=True)
class _SessionData:
    """Everything one resample needs, computed once."""

    test: SimulatedPool
    test_predictions: np.ndarray
    test_shift: np.ndarray
    zne_bounds: tuple[np.ndarray, np.ndarray]
    twin_scores: np.ndarray
    twin_shift: np.ndarray
    oracle_scores: np.ndarray
    rows: dict[str, list[np.ndarray]]


def _prepare(monday: Monday, pools: dict[str, SimulatedPool], rng: np.random.Generator) -> _SessionData:
    test, twin = pools["test"], pools["twin"]
    sign_table = _observables(monday.config.qubit_count)[2]
    _, lower, upper = bootstrap_zne_intervals(test.probabilities, sign_table, monday.config.noise_scale_factors,
                                              test.shots, ALPHA, 200, rng)
    return _SessionData(
        test=test, test_predictions=learned_predictions(monday.model, test.model_inputs()),
        test_shift=shift_features(test.row_noisy_values, test.row_features), zne_bounds=(lower, upper),
        twin_scores=_scores(monday.model, twin), twin_shift=shift_features(twin.row_noisy_values, twin.row_features),
        oracle_scores=_scores(monday.model, pools["oracle"]),
        rows={role: _row_index(pool) for role, pool in pools.items()})


def _draw(count: int, size: int, rng: np.random.Generator, resample: bool) -> np.ndarray:
    """Circuit ids: all of them (or a bootstrap of all), or a random subset of `size`."""
    if size >= count:
        return rng.integers(0, count, count) if resample else np.arange(count)
    return rng.choice(count, size=size, replace=False)


def evaluate_once(monday: Monday, data: _SessionData, counts: tuple[int, ...], rng: np.random.Generator,
                  resample_test: bool) -> dict[str, tuple[float, float]]:
    """Coverage and mean width of every method for one draw of test, twin and oracle circuits."""
    test_ids = _draw(len(data.rows["test"]), len(data.rows["test"]), rng, resample_test)
    test_rows = np.concatenate([data.rows["test"][i] for i in test_ids])
    truths, predictions = data.test.row_ideal_values[test_rows], data.test_predictions[test_rows]
    shift = data.test_shift[test_rows]

    def report(half_width) -> tuple[float, float]:
        result = evaluate_symmetric_intervals(predictions, truths, half_width)
        return result.coverage, result.mean_width

    lower, upper = data.zne_bounds[0][test_rows], data.zne_bounds[1][test_rows]
    results = {"R0_frozen": report(monday.quantile),
               "zne_bootstrap": (float(((truths >= lower) & (truths <= upper)).mean()), float((upper - lower).mean()))}
    monday_ids = np.unique(monday.twin_circuit_index)
    for count in counts:
        twin_rows = np.concatenate([data.rows["twin"][i] for i in
                                    _draw(len(data.rows["twin"]), count, rng, resample_test)])
        oracle_rows = np.concatenate([data.rows["oracle"][i] for i in
                                      _draw(len(data.rows["oracle"]), count, rng, resample_test)])
        monday_rows = np.isin(monday.twin_circuit_index, rng.choice(monday_ids, size=min(count, monday_ids.size),
                                                                     replace=False))
        after = data.twin_scores[twin_rows]
        results[f"R1_clifford_direct_K{count}"] = report(clifford_direct_quantile(after, ALPHA))
        results[f"R2_clifford_ratio_K{count}"] = report(clifford_ratio_quantile(
            monday.quantile, monday.twin_scores[monday_rows], after, ALPHA))
        results[f"R1W_clifford_weighted_K{count}"] = report(clifford_weighted_quantiles(
            after, data.twin_shift[twin_rows], shift, ALPHA))
        results[f"R3_oracle_K{count}"] = report(conformal_quantile(data.oracle_scores[oracle_rows], ALPHA))
    return results


def summarize_session(monday: Monday, pools: dict[str, SimulatedPool], seed: int) -> dict:
    """Estimates (averaged over calibration draws on the full test set) and circuit-bootstrap 95% CIs."""
    rng = np.random.default_rng(seed)
    data = _prepare(monday, pools, rng)
    counts = tuple(sorted({SMALL_K, pools["twin"].circuit_count}))
    draws = [evaluate_once(monday, data, counts, rng, resample_test=False) for _ in range(CALIBRATION_DRAWS)]
    boots = [evaluate_once(monday, data, counts, rng, resample_test=True) for _ in range(BOOTSTRAP_RESAMPLES)]
    methods = {}
    for name in draws[0]:
        entry = {}
        for index, field in enumerate(("coverage", "mean_width")):
            values = np.array([b[name][index] for b in boots])
            entry[field] = {"estimate": float(np.mean([d[name][index] for d in draws])),
                            "ci95": [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]}
        methods[name] = entry
    test_mae = float(np.abs(data.test_predictions - data.test.row_ideal_values).mean())
    alarm = drift_alarm_p_value(per_circuit_mean(monday.twin_scores, monday.twin_circuit_index),
                                per_circuit_mean(data.twin_scores, pools["twin"].row_circuit_index))
    return {"counts": list(counts), "methods": methods, "test_mae": test_mae, "drift_alarm_p_value": alarm,
            "test_rows": int(data.test.row_ideal_values.size)}


def fold_diagnostic(pools: dict[str, SimulatedPool], simulated: dict[str, SimulatedPool]) -> dict:
    """How much folding attenuates signals on the device versus in the simulator (rows with |ideal| > 0.3).

    linearity = ln(a5 / a1) / ln(a3 / a1): 2.0 if each fold adds the same noise; less if folds partly cancel.
    """
    def attenuation(group: dict[str, SimulatedPool]) -> list[float]:
        noisy = np.vstack([group[r].row_noisy_values for r in ("test", "oracle")])
        ideal = np.concatenate([group[r].row_ideal_values for r in ("test", "oracle")])
        keep = np.abs(ideal) > 0.3
        return [float((noisy[keep, s] * np.sign(ideal[keep])).sum() / np.abs(ideal[keep]).sum())
                for s in range(noisy.shape[1])]

    result = {}
    for name, group in (("hardware", pools), ("simulator", simulated)):
        a = attenuation(group)
        linearity = float(np.log(a[2] / a[0]) / np.log(a[1] / a[0])) if min(a) > 0 and a[1] < a[0] else float("nan")
        result[name] = {"attenuation_by_scale": a, "linearity": linearity}
    return result


def simulate_session(session_dir: Path, monday: Monday) -> dict[str, SimulatedPool]:
    """The session's test and oracle circuits simulated on that day's calibration, for the fold diagnostic."""
    spec = load_manifest(session_dir)
    condition = DeviceCondition("simulated", load_calibration_file(session_dir))
    labels, observables, sign_table = _observables(spec.qubit_count)
    records, rng = load_records(session_dir), np.random.default_rng(spec.seed + 2)
    return {role: simulate_pool([records[i] for i in spec.role_ids(role)], f"{spec.session}_sim_{role}",
                                condition.build_simulators(monday.config), monday.config, observables, labels,
                                sign_table, rng, prepare=condition.prepare_circuit)
            for role in ("test", "oracle")}


def load_calibration_file(session_dir: Path) -> DeviceCalibration:
    """The calibration recorded when the session was prepared."""
    data = json.loads((session_dir / "calibration.json").read_text())
    return DeviceCalibration(**{k: tuple(v) if isinstance(v, list) else v for k, v in data.items()})


def session_verdict(name: str, summary: dict) -> list[str]:
    """Amendment 3 rules for one session."""
    methods, large = summary["methods"], max(summary["counts"])
    frozen = methods["R0_frozen"]["coverage"]
    weighted, oracle = methods[f"R1W_clifford_weighted_K{large}"], methods[f"R3_oracle_K{large}"]
    coverage, width = weighted["coverage"]["estimate"], weighted["mean_width"]["estimate"]
    oracle_width = oracle["mean_width"]["estimate"]
    low, high = weighted["coverage"]["ci95"]
    passes = abs(coverage - (1 - ALPHA)) <= TOLERANCE and width < 2 * oracle_width
    return [f"## {name}", "",
            f"- frozen coverage {frozen['estimate']:.3f} (95% CI {frozen['ci95'][0]:.3f} to {frozen['ci95'][1]:.3f}); "
            f"below {FROZEN_BREAK_THRESHOLD}: {frozen['estimate'] < FROZEN_BREAK_THRESHOLD}",
            f"- **H3-hw** R1W K={large}: coverage {coverage:.3f} (95% CI {low:.3f} to {high:.3f}), width {width:.3f} "
            f"vs oracle {oracle_width:.3f} ({width / oracle_width:.2f}x): "
            f"{'PASS' if passes else 'FAIL'}; CI contains 0.90: {low <= 1 - ALPHA <= high}",
            f"- test MAE {summary['test_mae']:.4f}; drift alarm p-value (Monday simulated twins vs hardware twins) "
            f"{summary['drift_alarm_p_value']:.3g}", ""]


def plot_sessions(summaries: dict[str, dict]) -> Figure:
    """Coverage and width with 95% CIs for every method, one group of bars per session."""
    names = list(next(iter(summaries.values()))["methods"])
    figure, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    bar = 0.8 / len(summaries)
    for index, (session, summary) in enumerate(summaries.items()):
        positions = np.arange(len(names)) + index * bar
        for axis, field in zip(axes, ("coverage", "mean_width"), strict=True):
            entries = [summary["methods"][n][field] for n in names]
            estimates = np.array([e["estimate"] for e in entries])
            errors = np.abs(np.array([e["ci95"] for e in entries]).T - estimates)
            axis.bar(positions, estimates, bar, yerr=errors, label=session)
    axes[0].axhline(1 - ALPHA, color="black", linestyle="--", linewidth=1)
    axes[0].set_ylabel("test coverage (target dashed)")
    axes[1].set_ylabel("mean interval width")
    axes[1].set_xticks(np.arange(len(names)) + 0.4 - bar / 2)
    axes[1].set_xticklabels([n.replace("_clifford", "").replace("_", " ") for n in names], rotation=30, ha="right")
    axes[0].legend()
    figure.suptitle("Hardware sessions: coverage and width (95% circuit-bootstrap CIs)")
    figure.tight_layout()
    return figure


def run(root: Path) -> Path:
    """Analyse every session folder under `root` (S1, S2, ...) against one simulated Monday."""
    session_dirs = sorted(d for d in root.iterdir() if (d / "counts.json").exists())
    if not session_dirs:
        raise FileNotFoundError(f"no session with counts.json under {root}")
    first = min(session_dirs, key=lambda d: json.loads((d / "manifest.json").read_text())["prepared_at"])
    monday = build_monday(load_calibration_file(first), load_manifest(first), root / "monday.pkl")
    summaries, lines = {}, ["# Verdict, hardware track (Amendment 3, docs/HYPOTHESES.md)", "",
                            f"Monday simulated from the calibration of {first.name}.", ""]
    for session_dir in session_dirs:
        pools = session_pools(session_dir)
        summary = summarize_session(monday, pools, load_manifest(session_dir).seed + 3)
        summary["fold_diagnostic"] = fold_diagnostic(pools, simulate_session(session_dir, monday))
        (session_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        summaries[session_dir.name] = summary
        lines += session_verdict(session_dir.name, summary)
    broken = [s for s, summary in summaries.items()
              if summary["methods"]["R0_frozen"]["coverage"]["estimate"] < FROZEN_BREAK_THRESHOLD]
    lines.insert(4, f"- **H2-hw** frozen coverage below {FROZEN_BREAK_THRESHOLD} in: {', '.join(broken) or 'none'}")
    lines.insert(5, "")
    (root / "verdict.md").write_text("\n".join(lines) + "\n")
    plot_sessions(summaries).savefig(root / "coverage_by_session.png", dpi=200)
    return root
