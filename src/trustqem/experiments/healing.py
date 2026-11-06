"""Experiment (Amendment 4, H6): the self-healing loop over 10-day sequences, resampled from the drift pools.

Days 1 to 5 run under D0 (no drift), days 6 to 10 under one drift scenario. Each day has 30 canary circuits
(near-Clifford twins, k = 4) and 30 test circuits. Three policies share the same days:
  never   keep the Monday intervals forever
  healing watch the canaries; on alarm, recalibrate with R1W on that day's canaries (monitor.run_self_healing)
  daily   recalibrate with R1W on every day's canaries, alarm or not
"""

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from trustqem.config import ExperimentConfig
from trustqem.conformal import conformal_quantile, evaluate_symmetric_intervals
from trustqem.experiments.drift import PROFILES, _scores
from trustqem.experiments.pools import ExperimentPools, load_or_build_pools
from trustqem.mitigation import train_learned_mitigator
from trustqem.monitor import Session, run_self_healing
from trustqem.recalibrate import clifford_weighted_quantiles, per_circuit_mean, shift_features

logger = logging.getLogger(__name__)

KEEP = 4                  # non-Clifford rotations per canary
CANARIES_PER_DAY = 30
TEST_PER_DAY = 30
QUIET_DAYS, DRIFT_DAYS = 5, 5
SEQUENCES_PER_REPEAT = 10
THRESHOLD = 20.0
CONTROL = "D0_no_drift"


@dataclass(frozen=True)
class Healed:
    """Recalibration state: the canary rows R1W reweights for each new day's test rows."""

    scores: np.ndarray
    shift: np.ndarray


@dataclass(frozen=True)
class Day:
    """Everything one simulated session needs, already scored by the frozen model."""

    canary_circuit_scores: np.ndarray
    canary: Healed
    predictions: np.ndarray
    truths: np.ndarray
    test_shift: np.ndarray


def _draw_day(pools: ExperimentPools, scored: dict, scenario: str, rng: np.random.Generator) -> Day:
    """30 test circuits and 30 canaries that are twins of other circuits (twin i is the twin of circuit i)."""
    tuesday, twins = pools.tuesday[scenario], pools.tuesday_twins[(scenario, KEEP)]
    order = rng.permutation(tuesday.circuit_count)
    test_ids, canary_ids = order[:TEST_PER_DAY], order[TEST_PER_DAY:TEST_PER_DAY + CANARIES_PER_DAY]
    predictions, _ = scored[("test", scenario)]
    _, twin_scores = scored[("twin", scenario)]
    test_rows, canary_rows = tuesday.rows_of(test_ids), twins.rows_of(canary_ids)
    return Day(
        canary_circuit_scores=per_circuit_mean(twin_scores[canary_rows], twins.row_circuit_index[canary_rows]),
        canary=Healed(twin_scores[canary_rows],
                      shift_features(twins.row_noisy_values[canary_rows], twins.row_features[canary_rows])),
        predictions=predictions[test_rows], truths=tuesday.row_ideal_values[test_rows],
        test_shift=shift_features(tuesday.row_noisy_values[test_rows], tuesday.row_features[test_rows]))


def _evaluate(day: Day, state: float | Healed, alpha: float) -> tuple[float, float]:
    half = state if isinstance(state, float) else clifford_weighted_quantiles(state.scores, state.shift,
                                                                              day.test_shift, alpha)
    report = evaluate_symmetric_intervals(day.predictions, day.truths, half)
    return report.coverage, report.mean_width


def _sequence(days: list[Day], reference: np.ndarray, monday_quantile: float, alpha: float,
              rng: np.random.Generator) -> dict:
    sessions = [Session(day.canary_circuit_scores, lambda state, day=day: _evaluate(day, state, alpha),
                        lambda day=day: day.canary) for day in days]
    healing = run_self_healing(reference, sessions, monday_quantile, rng, THRESHOLD)
    never = [_evaluate(day, monday_quantile, alpha) for day in days]
    daily = [_evaluate(day, day.canary, alpha) for day in days]
    return {"healing": [asdict(log) for log in healing], "never": never, "daily": daily}


def run_sequences(pools: ExperimentPools, profile, repeat: int) -> dict[str, list[dict]]:
    """Train the frozen Monday model as in the drift experiment, then 10 sequences per drift scenario."""
    config, rng = pools.config, np.random.default_rng(pools.config.random_seed + 7000 + repeat)
    order = rng.permutation(pools.monday.circuit_count)
    train_ids = order[:profile.train_circuits]
    calibration_ids = order[profile.train_circuits:profile.train_circuits + profile.calibration_circuits]
    monday = pools.monday
    train_rows = monday.rows_of(train_ids)
    model = train_learned_mitigator(monday.model_inputs()[train_rows], monday.row_ideal_values[train_rows], config)
    monday_quantile = float(conformal_quantile(_scores(model, monday)[1][monday.rows_of(calibration_ids)],
                                               profile.alpha))
    monday_twins = pools.monday_twins[KEEP]
    reference = per_circuit_mean(_scores(model, monday_twins)[1], monday_twins.row_circuit_index)
    scored = {}
    for scenario in pools.tuesday:
        scored[("test", scenario)] = _scores(model, pools.tuesday[scenario])
        scored[("twin", scenario)] = _scores(model, pools.tuesday_twins[(scenario, KEEP)])
    results = {}
    for scenario in pools.tuesday:      # the D0 entry is the all-quiet control: 10 days with no drift
        results[scenario] = []
        for _ in range(SEQUENCES_PER_REPEAT):
            days = ([_draw_day(pools, scored, CONTROL, rng) for _ in range(QUIET_DAYS)]
                    + [_draw_day(pools, scored, scenario, rng) for _ in range(DRIFT_DAYS)])
            results[scenario].append(_sequence(days, reference, monday_quantile, profile.alpha, rng))
    return results


def summarize_healing(sequences: dict[str, list[dict]]) -> dict:
    """False alarms on quiet days, detection, delay, and coverage per day for each policy."""
    summary = {}
    for scenario, runs in sequences.items():
        first_alarm = [next((log["day"] for log in run["healing"] if log["alarm"]), None) for run in runs]
        false = [day is not None and day <= QUIET_DAYS for day in first_alarm]
        detected = [day for day in first_alarm if day is not None and day > QUIET_DAYS]
        after = [log["coverage"] for run, day in zip(runs, first_alarm, strict=True)
                 if day is not None and day > QUIET_DAYS for log in run["healing"] if log["day"] > day]
        per_day = {policy: [float(np.mean([(run[policy][d]["coverage"] if policy == "healing"
                                            else run[policy][d][0]) for run in runs]))
                            for d in range(QUIET_DAYS + DRIFT_DAYS)] for policy in ("never", "healing", "daily")}
        width = {policy: float(np.mean([(log["mean_width"] if policy == "healing" else log[1])
                                        for run in runs for log in run[policy]]))
                 for policy in ("never", "healing", "daily")}
        martingale = [float(np.median([run["healing"][d]["martingale"] for run in runs]))
                      for d in range(QUIET_DAYS + DRIFT_DAYS)]
        summary[scenario] = {
            "sequences": len(runs), "false_alarm_rate_quiet_days": float(np.mean(false)),
            "detection_rate": len(detected) / len(runs),
            "mean_delay_days": float(np.mean(np.array(detected) - QUIET_DAYS)) if detected else None,
            "coverage_after_correct_alarm": float(np.mean(after)) if after else None,
            "coverage_by_day": per_day, "mean_width": width, "median_martingale_by_day": martingale}
    return summary


def plot_timeline(summary: dict, scenario: str, alpha: float):
    """Median martingale (log scale, with the alarm line) above coverage per day for the three policies."""
    entry, days = summary[scenario], np.arange(1, QUIET_DAYS + DRIFT_DAYS + 1)
    figure, (top, bottom) = plt.subplots(2, 1, figsize=(7, 5.5), sharex=True)
    top.semilogy(days, entry["median_martingale_by_day"], "o-", color="#4C72B0", label="alarm score (median)")
    top.axhline(THRESHOLD, color="#C44E52", linestyle="--", label=f"alarm at {THRESHOLD:.0f}")
    top.axvspan(QUIET_DAYS + 0.5, days[-1] + 0.5, color="#DDDDDD", alpha=0.5, label="device drifted")
    top.set_ylabel("canary martingale")
    top.legend(fontsize=8)
    for policy, color in (("never", "#C44E52"), ("healing", "#55A868"), ("daily", "#8172B2")):
        bottom.plot(days, entry["coverage_by_day"][policy], "o-", color=color, label=policy)
    bottom.axhline(1 - alpha, color="black", linewidth=0.8)
    bottom.axvspan(QUIET_DAYS + 0.5, days[-1] + 0.5, color="#DDDDDD", alpha=0.5)
    bottom.set_xlabel("day")
    bottom.set_ylabel("test coverage")
    bottom.legend(fontsize=8)
    figure.suptitle(f"Self-healing loop, {scenario}")
    figure.tight_layout()
    return figure


def run(profile_name: str, results_root: Path) -> Path:
    """Reuse the drift pools of `profile_name`, run every repeat, write summary, figures and the verdict."""
    profile = PROFILES[profile_name]
    config = ExperimentConfig(random_seed=profile.random_seed, qubit_count=profile.qubit_count)
    pools = load_or_build_pools(config, profile.sizes, results_root / "drift" / profile_name / "pools.pkl")
    if KEEP not in pools.sizes.twin_non_clifford_counts:
        raise ValueError(f"profile {profile_name} has no k = {KEEP} twins")
    sequences: dict[str, list[dict]] = {}
    for repeat in range(profile.repeats):
        for scenario, runs in run_sequences(pools, profile, repeat).items():
            sequences.setdefault(scenario, []).extend(runs)
        logger.info("healing repeat %d/%d done", repeat + 1, profile.repeats)
    summary = summarize_healing(sequences)
    output_dir = results_root / "healing" / profile_name
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    for scenario in summary:
        plot_timeline(summary, scenario, profile.alpha).savefig(output_dir / f"timeline_{scenario}.png", dpi=200)
        plt.close("all")
    write_healing_verdict(summary, profile.alpha, output_dir / "verdict.md")
    return output_dir


def write_healing_verdict(summary: dict, alpha: float, path: Path) -> None:
    """H6 as pre-registered: false alarms at most 5% of sequences; coverage within 3 points after a correct alarm."""
    lines = ["# Verdict, self-healing loop (Amendment 4, H6)", "",
             "| scenario | false alarm (days 1-5) | detected | delay (days) | coverage after alarm | "
             "coverage day 10: never / healing / daily |", "|---|---|---|---|---|---|"]
    passes_a, passes_b = [], []
    for scenario, entry in summary.items():
        after = entry["coverage_after_correct_alarm"]
        last = {policy: entry["coverage_by_day"][policy][-1] for policy in ("never", "healing", "daily")}
        delay = "n/a" if entry["mean_delay_days"] is None else f"{entry['mean_delay_days']:.1f}"
        lines.append(f"| {scenario} | {entry['false_alarm_rate_quiet_days']:.3f} | {entry['detection_rate']:.2f} | "
                     f"{delay} | {'n/a' if after is None else f'{after:.3f}'} | "
                     f"{last['never']:.3f} / {last['healing']:.3f} / {last['daily']:.3f} |")
        passes_a.append(entry["false_alarm_rate_quiet_days"] <= 0.05)
        if after is not None and scenario != CONTROL:
            passes_b.append(abs(after - (1 - alpha)) <= 0.03)
    lines += ["", f"- **H6a** false alarms at most 5% in every scenario: {'PASS' if all(passes_a) else 'FAIL'}",
              f"- **H6b** coverage within 3 points of {1 - alpha:.2f} after a correct alarm, in every scenario with "
              f"one: {'PASS' if passes_b and all(passes_b) else 'FAIL' if passes_b else 'n/a'}"]
    path.write_text("\n".join(lines) + "\n")
