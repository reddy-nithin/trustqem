"""Amendment 4, hardware replay of the self-healing loop: simulated Monday, then each IBM session in order.

Day 1 is the first session, day 2 the next, and so on. The canaries are that session's k = 8 twins. On an alarm
the loop recalibrates with R1W on those canaries and keeps that recalibration on later days until the next alarm.
Reported per session: the martingale value, whether it alarmed, and test coverage and width for "never"
(frozen Monday), "healing" and "daily" (R1W on every session's own twins). Reported, not judged.
"""

import json
import pickle
from pathlib import Path

import numpy as np

from trustqem.conformal import evaluate_symmetric_intervals
from trustqem.experiments.hardware import ALPHA, Monday, _scores, session_pools
from trustqem.hardware import load_manifest
from trustqem.mitigation import learned_predictions
from trustqem.monitor import CanaryMonitor
from trustqem.recalibrate import clifford_weighted_quantiles, per_circuit_mean, shift_features

ORDERINGS = 200          # the martingale sees canaries in random order; repeat to report how often it alarms
THRESHOLD = 20.0


def _session_data(monday: Monday, session_dir: Path) -> dict:
    pools = session_pools(session_dir)
    test, twin = pools["test"], pools["twin"]
    twin_scores = _scores(monday.model, twin)
    return {"name": session_dir.name,
            "canaries": per_circuit_mean(twin_scores, twin.row_circuit_index),
            "heal": (twin_scores, shift_features(twin.row_noisy_values, twin.row_features)),
            "predictions": learned_predictions(monday.model, test.model_inputs()),
            "truths": test.row_ideal_values,
            "test_shift": shift_features(test.row_noisy_values, test.row_features)}


def _report(day: dict, state) -> dict:
    half = state if isinstance(state, float) else clifford_weighted_quantiles(*state, day["test_shift"], ALPHA)
    result = evaluate_symmetric_intervals(day["predictions"], day["truths"], half)
    return {"coverage": float(result.coverage), "mean_width": float(result.mean_width)}


def replay(monday: Monday, days: list[dict], rng: np.random.Generator) -> list[dict]:
    """One pass of the loop over the sessions in order."""
    monitor = CanaryMonitor(per_circuit_mean(monday.twin_scores, monday.twin_circuit_index), rng, THRESHOLD)
    state, log = float(monday.quantile), []
    for day in days:
        value, alarm = monitor.observe(day["canaries"])
        if alarm:
            state = day["heal"]
            monitor = CanaryMonitor(day["canaries"], rng, THRESHOLD)
        log.append({"session": day["name"], "martingale": value, "alarm": bool(alarm),
                    "healing": _report(day, state)})
    return log


def run(root: Path, output_dir: Path, seed: int = 4040) -> Path:
    """`root` holds monday.pkl and the session folders (results/hardware)."""
    with open(root / "monday.pkl", "rb") as file:
        monday: Monday = pickle.load(file)
    session_dirs = sorted((d for d in root.iterdir() if (d / "counts.json").exists()),
                          key=lambda d: load_manifest(d).session)
    days = [_session_data(monday, d) for d in session_dirs]
    rng = np.random.default_rng(seed)
    runs = [replay(monday, days, rng) for _ in range(ORDERINGS)]
    summary = []
    for index, day in enumerate(days):
        alarms = [run_log[index]["alarm"] for run_log in runs]
        first_alarm_here = [run_log[index]["alarm"] and not any(r["alarm"] for r in run_log[:index])
                            for run_log in runs]
        healing = [run_log[index]["healing"] for run_log in runs]
        summary.append({
            "session": day["name"],
            "alarm_rate": float(np.mean(alarms)), "first_alarm_rate": float(np.mean(first_alarm_here)),
            "median_martingale": float(np.median([run_log[index]["martingale"] for run_log in runs])),
            "never": _report(day, float(monday.quantile)), "daily": _report(day, day["heal"]),
            "healing": {field: float(np.mean([h[field] for h in healing])) for field in ("coverage", "mean_width")}})
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    lines = ["# Self-healing loop replayed on IBM hardware (Amendment 4, reported, not judged)", "",
             f"Monday is simulated; then {', '.join(d['name'] for d in days)} in order. {ORDERINGS} random canary "
             "orders.", "",
             "| session | alarm rate | median martingale | never | healing | daily |", "|---|---|---|---|---|---|"]
    for entry in summary:
        cells = [f"{entry[p]['coverage']:.3f} / {entry[p]['mean_width']:.3f}" for p in ("never", "healing", "daily")]
        lines.append(f"| {entry['session']} | {entry['alarm_rate']:.2f} | {entry['median_martingale']:.3g} | "
                     + " | ".join(cells) + " |")
    lines += ["", "Cells are test coverage / mean interval width."]
    (output_dir / "verdict.md").write_text("\n".join(lines) + "\n")
    return output_dir
