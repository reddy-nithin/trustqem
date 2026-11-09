"""Poster figures (C1 to C8), each read straight from a results file. Writes PNG (300 dpi) and SVG to results/poster/.

Usage: uv run python scripts/poster_figures.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from trustqem.experiments.report import METHOD_STYLE

OUT = Path("results/poster")
TARGET, BAND = 0.90, 0.03
GREY, ZNE, OURS, ORACLE, RETRAIN = (METHOD_STYLE[m][0] for m in
                                    ("R0_frozen", "zne_bootstrap", "R1W_clifford_weighted", "R3_oracle", "R4_retrain"))
ALARM = "#c44e52"
DRIFTS = ("D1_depolarizing_x1.5", "D2_depolarizing_x2", "D3_bad_qubit", "D4_thermal_relaxation", "D5_readout",
          "D6_combined")
SHORT = {"D1_depolarizing_x1.5": "gate noise x1.5", "D2_depolarizing_x2": "gate noise x2", "D3_bad_qubit": "bad qubit",
         "D4_thermal_relaxation": "thermal relaxation", "D5_readout": "readout", "D6_combined": "combined"}

plt.rcParams.update({"font.size": 16, "axes.titlesize": 18, "axes.labelsize": 16, "legend.fontsize": 14,
                     "xtick.labelsize": 14, "ytick.labelsize": 14, "axes.spines.top": False,
                     "axes.spines.right": False, "font.family": "DejaVu Sans"})


def load(path: str):
    return json.loads(Path(path).read_text())


def entry(intervals: list, scenario: str, method: str, count: int, keep: int, field: str = "coverage") -> float:
    for e in intervals:
        if (e["scenario"], e["method"], e["K"], e["k"]) == (scenario, method, count, keep):
            return e[field]["mean"]
    raise KeyError((scenario, method, count, keep))


def band(axis) -> None:
    axis.axhspan(TARGET - BAND, TARGET + BAND, color="#e6e6e6", zorder=0)
    axis.axhline(TARGET, color="black", lw=1, zorder=1)


def save(fig, name: str, sources: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)
    print(f"{name}: {', '.join(sources)}")


def c1_hardware() -> None:
    """Hero: real-hardware coverage, 4 methods per session, 95% circuit-bootstrap whiskers."""
    sessions = {"Session 1\n4 qubits": "results/hardware/S1/summary.json",
                "Session 2\n4 qubits": "results/hardware/S2/summary.json",
                "Session 3\n12 qubits": "results/q12/hardware/S3/summary.json"}
    sessions = {name: path for name, path in sessions.items() if Path(path).exists()}
    methods = (("R0_frozen", "no fix (frozen)", GREY), ("zne_bootstrap", "standard (ZNE)", ZNE),
               ("R1W_clifford_weighted_K60", "TrustQEM", OURS), ("R3_oracle_K60", "ideal yardstick", ORACLE))
    fig, axis = plt.subplots(figsize=(10, 6))
    band(axis)
    width = 0.8 / len(methods)
    for i, (key, label, colour) in enumerate(methods):
        estimates, errors = [], []
        for path in sessions.values():
            cov = load(path)["methods"][key]["coverage"]
            estimates.append(cov["estimate"])
            errors.append([cov["estimate"] - cov["ci95"][0], cov["ci95"][1] - cov["estimate"]])
        x = np.arange(len(sessions)) + (i - 1.5) * width
        axis.bar(x, estimates, width * 0.92, color=colour, label=label, yerr=np.array(errors).T, capsize=4,
                 error_kw={"lw": 1.2})
        for xi, value in zip(x, estimates, strict=True):
            axis.text(xi, 0.405, f"{value:.2f}", ha="center", va="bottom", fontsize=13, color="white",
                      fontweight="bold")
    axis.set_xticks(np.arange(len(sessions)), list(sessions))
    axis.set_ylim(0.4, 1.0)
    axis.set_ylabel("how often the error bar\ncontains the true answer")
    axis.text(-0.48, TARGET + 0.005, "target 90%", ha="left", va="bottom", fontsize=13)
    axis.legend(loc="upper left", ncol=4, frameon=False, bbox_to_anchor=(0, 1.13), fontsize=13)
    axis.set_title("Real IBM quantum computer (ibm_fez)", pad=40)
    save(fig, "C1_hardware_coverage", list(sessions.values()))


def c2_scaling() -> None:
    """Two drift types against qubit count, plus IBM chip noise (FakeFez device track, 4 and 12 qubits only)."""
    qubits = (4, 6, 8, 10, 12)
    data = {n: load(f"results/drift/scale_q{n}/summary.json")["intervals"] for n in qubits}
    rich = load("results/twins_k16/scale_q12/summary.json")["intervals"]
    panels = ("D4_thermal_relaxation", "D2_depolarizing_x2")
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), sharey=True)
    for axis, scenario in zip(axes[:2], panels, strict=True):
        band(axis)
        for method, count, keep, colour, label in (("R0_frozen", 0, -1, GREY, "no fix"),
                                                   ("R1W_clifford_weighted", 100, 4, OURS, "TrustQEM"),
                                                   ("R3_oracle", 100, -1, ORACLE, "ideal yardstick")):
            axis.plot(qubits, [entry(data[n], scenario, method, count, keep) for n in qubits], "o-", color=colour,
                      lw=2.5, ms=8, label=label)
        axis.plot([12], [entry(rich, scenario, "R1W_clifford_weighted", 100, 16)], "*", ms=20, mfc="none",
                  mec=OURS, mew=2, label="TrustQEM, richer checks")
        axis.set_title(SHORT[scenario])
        axis.set_xticks(qubits)
        axis.set_xlabel("qubits")
    device_panel(axes[2], qubits)
    axes[0].set_ylabel("coverage after drift")
    axes[0].set_ylim(0.5, 0.97)
    axes[0].legend(loc="lower left", frameon=False, fontsize=12)
    save(fig, "C2_scaling_three_drifts", ["results/drift/scale_q{4..12}/summary.json",
                                          "results/twins_k16/scale_q12/summary.json",
                                          "results/device/full/summary.json",
                                          "results/device/scale_q12/summary.json"])


def device_panel(axis, ticks: tuple[int, ...]) -> None:
    """IBM chip noise (FakeFez): mean over drifts E1 to E5 at 4 and 12 qubits, shaded min to max."""
    device = {4: load("results/device/full/summary.json")["intervals"],
              12: load("results/device/scale_q12/summary.json")["intervals"]}
    drifts = ("E1_coherence_drop", "E2_bad_qubit", "E3_readout", "E4_gate_errors", "E5_combined")
    sizes = sorted(device)
    band(axis)
    for method, count, keep, colour in (("R0_frozen", 0, -1, GREY), ("R1W_clifford_weighted", 100, 4, OURS),
                                        ("R3_oracle", 100, -1, ORACLE)):
        values = np.array([[entry(device[n], d, method, count, keep) for d in drifts] for n in sizes])
        axis.fill_between(sizes, values.min(axis=1), values.max(axis=1), color=colour, alpha=0.15, lw=0)
        axis.plot(sizes, values.mean(axis=1), "o-", color=colour, lw=2.5, ms=8)
    axis.set_title("IBM chip noise")
    axis.set_xticks(sizes)
    axis.set_xlim(ticks[0] - 0.4, ticks[-1] + 0.4)
    axis.set_xlabel("qubits")


def c3_healing_timeline() -> None:
    """Ten simulated days, drift after day 5: the alarm score and coverage with and without self-healing."""
    summary = load("results/healing/scale_q4/summary.json")["D6_combined"]
    days = np.arange(1, 11)
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True, gridspec_kw={"height_ratios": [1, 1.4]})
    top.semilogy(days, summary["median_martingale_by_day"], "o-", color=ALARM, lw=2.5, ms=8)
    top.axhline(20, color=ALARM, ls="--", lw=1.5)
    top.text(1, 26, "alarm line (20)", color=ALARM, fontsize=13)
    top.set_ylabel("alarm score")
    band(bottom)
    for key, colour, label in (("never", GREY, "never fixed"), ("healing", OURS, "self-healing (TrustQEM)")):
        bottom.plot(days, summary["coverage_by_day"][key], "o-", color=colour, lw=2.5, ms=8, label=label)
    for axis in (top, bottom):
        axis.axvspan(5.5, 10.5, color="#fbe9ee", zorder=0)
    bottom.text(8, 0.6, "machine drifted", ha="center", fontsize=14, color="#8a3d5f")
    bottom.set_ylim(0.35, 1.0)
    bottom.set_xticks(days)
    bottom.set_xlabel("day")
    bottom.set_ylabel("coverage")
    bottom.legend(loc="lower left", frameon=False)
    top.set_title("Self-healing, 200 simulated runs (median), 4 qubits, combined drift")
    save(fig, "C3_self_healing_timeline", ["results/healing/scale_q4/summary.json"])


def c4_hardware_replay() -> None:
    """The loop replayed on ibm_fez: alarm on S1, quiet on S2 with the repair holding; S3 (12 q) is its own replay."""
    summary = load("results/healing/hardware/summary.json") + load("results/q12/healing/hardware/summary.json")
    labels = {"S1": "Session 1\n4 qubits", "S2": "Session 2\n3 days later", "S3": "Session 3\n12 qubits*"}
    names = [labels.get(s["session"], s["session"]) for s in summary]
    fig, (top, bottom) = plt.subplots(1, 2, figsize=(14, 5.5))
    top.bar(names, [s["median_martingale"] for s in summary], color=ALARM, width=0.5)
    top.set_yscale("log")
    top.axhline(20, color="black", ls="--", lw=1.5)
    top.text(0.5, 40, "alarm line (20)", ha="center", fontsize=13)
    top.set_ylabel("alarm score (log)")
    top.set_title("Alarm", pad=34)
    band(bottom)
    x, w = np.arange(len(names)), 0.35
    bottom.bar(x - w / 2, [s["never"]["coverage"] for s in summary], w, color=GREY, label="never fixed")
    bottom.bar(x + w / 2, [s["healing"]["coverage"] for s in summary], w, color=OURS, label="self-healing")
    for xi, s in zip(x, summary, strict=True):
        bottom.text(xi + w / 2, s["healing"]["coverage"] + 0.01, f"{s['healing']['coverage']:.2f}", ha="center")
        bottom.text(xi - w / 2, s["never"]["coverage"] + 0.01, f"{s['never']['coverage']:.2f}", ha="center")
    bottom.set_xticks(x, names)
    bottom.set_ylim(0.4, 1.0)
    bottom.set_ylabel("coverage")
    bottom.set_title("Error bars", pad=34)
    bottom.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False, fontsize=13)
    fig.suptitle("Self-healing on the real IBM chip", y=1.1)
    note = "* Session 3 is a separate replay: simulated Monday, then session 3."
    fig.text(0.5, -0.08, note, ha="center", fontsize=12)
    save(fig, "C4_hardware_healing_replay",
         ["results/healing/hardware/summary.json", "results/q12/healing/hardware/summary.json"])


def c5_alarm_156() -> None:
    """How many days the alarm needs on a simulated 156-qubit chip."""
    summary = load("results/canary_scale/q156/summary.json")
    delays = {int(k): v for k, v in summary["delay_counts"].items()}
    fig, axis = plt.subplots(figsize=(9, 5.5))
    axis.bar(list(delays), list(delays.values()), color=ALARM, width=0.65)
    axis.set_xlabel("days after the drift until the alarm")
    axis.set_ylabel(f"runs (of {summary['sequences']})")
    axis.set_xticks(list(delays))
    false = round(summary["false_alarm_rate_quiet_days"] * summary["sequences"])
    axis.text(0.98, 0.95, f"{summary['qubits']} qubits\n{false} false alarms in {summary['sequences']} runs\n"
              f"drift caught in {summary['detection_rate']:.0%}\n{summary['seconds_per_canary']:.1f} s per check",
              transform=axis.transAxes, ha="right", va="top", fontsize=14,
              bbox={"boxstyle": "round", "fc": "white", "ec": "#cccccc"})
    axis.set_title(f"The alarm at chip scale (mean {summary['mean_delay_days']:.1f} days)")
    save(fig, "C5_alarm_156_qubits", ["results/canary_scale/q156/summary.json"])


def c6_cost() -> None:
    """Coverage against the number of circuits whose true answer must be known (simulation, Stage 2)."""
    intervals = load("results/drift/full/summary.json")["intervals"]
    ours_k = (10, 25, 50, 100, 200)
    retrain_k = (50, 100, 200)
    calibration = 100          # R4 also needs 100 labeled circuits to calibrate (drift.py retrain_calibration_circuits)

    def mean_over_drifts(method: str, count: int, keep: int, field: str) -> float:
        return float(np.mean([entry(intervals, s, method, count, keep, field) for s in DRIFTS]))

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))
    for axis, field, label in ((axes[0], "coverage", "coverage (mean of 6 drifts)"),
                               (axes[1], "mean_width", "error bar width")):
        if field == "coverage":
            band(axis)
        axis.plot(ours_k, [mean_over_drifts("R1W_clifford_weighted", k, 4, field) for k in ours_k], "o-",
                  color=OURS, lw=2.5, ms=9, label="TrustQEM: check circuits\n(a laptop knows the answer)")
        axis.plot([k + calibration for k in retrain_k],
                  [mean_over_drifts("R4_retrain", k, -1, field) for k in retrain_k], "s-", color=RETRAIN, lw=2.5,
                  ms=9, label="retrain: labeled circuits\n(answer needs a quantum-hard sum)")
        axis.set_xscale("log")
        axis.set_xticks([10, 25, 50, 100, 200, 300], ["10", "25", "50", "100", "200", "300"])
        axis.set_xlabel("circuits with a known answer")
        axis.set_ylabel(label)
    axes[0].set_ylim(0.8, 0.97)
    axes[0].legend(loc="lower right", frameon=False, fontsize=12)
    fig.suptitle("Same honesty, far cheaper labels (simulation, 4 qubits)", y=1.02)
    save(fig, "C6_cost_vs_retraining", ["results/drift/full/summary.json"])


def c7_realism_ladder() -> None:
    """Frozen against TrustQEM in every setting, one dot per drift scenario or hardware session."""
    sim = load("results/drift/full/summary.json")["intervals"]
    device = load("results/device/full/summary.json")["intervals"]
    rows = [("simulation\n(6 drifts)", [entry(sim, s, "R0_frozen", 0, -1) for s in DRIFTS],
             [entry(sim, s, "R1W_clifford_weighted", 100, 4) for s in DRIFTS])]
    device_drifts = sorted({e["scenario"] for e in device} - {"E0_no_drift", "monday"})
    rows.append(("IBM chip model\n(5 drifts)", [entry(device, s, "R0_frozen", 0, -1) for s in device_drifts],
                 [entry(device, s, "R1W_clifford_weighted", 100, 4) for s in device_drifts]))
    hardware = [load(f"results/hardware/{s}/summary.json")["methods"] for s in ("S1", "S2")]
    rows.append(("real IBM chip\n(2 sessions)", [h["R0_frozen"]["coverage"]["estimate"] for h in hardware],
                 [h["R1W_clifford_weighted_K60"]["coverage"]["estimate"] for h in hardware]))
    fig, axis = plt.subplots(figsize=(11, 4))
    axis.axvspan(TARGET - BAND, TARGET + BAND, color="#e6e6e6", zorder=0)
    axis.axvline(TARGET, color="black", lw=1)
    for y, (_label, frozen, ours) in enumerate(reversed(rows)):
        for f, o in zip(frozen, ours, strict=True):
            axis.annotate("", xy=(o, y), xytext=(f, y), arrowprops={"arrowstyle": "->", "color": "#c9a3b8", "lw": 1.2})
        axis.scatter(frozen, [y] * len(frozen), s=110, color=GREY, zorder=3, label="no fix" if y == 0 else None)
        axis.scatter(ours, [y] * len(ours), s=110, color=OURS, zorder=4, label="TrustQEM" if y == 0 else None)
    axis.set_yticks(range(len(rows)), [r[0] for r in reversed(rows)])
    axis.set_xlabel("coverage after drift (target 0.90)")
    axis.set_xlim(0.4, 1.0)
    axis.legend(loc="lower left", frameon=False)
    axis.set_title("Every setting, 4 qubits: drift breaks the bars, TrustQEM repairs them")
    save(fig, "C7_realism_ladder", ["results/drift/full", "results/device/full", "results/hardware/S1,S2"])


def c8_zeros() -> None:
    """Why bigger chips are harder: most check-circuit answers are 0, and noise cannot move a 0.
    Numbers from docs/RESEARCH_LOG.md (H5 diagnosis): share of observables with |ideal| > 0.1."""
    shares = {"4 qubits": (0.71, 0.32), "12 qubits": (0.52, 0.16)}
    fig, axis = plt.subplots(figsize=(8.5, 5.2))
    x, w = np.arange(len(shares)), 0.36
    real = [v[0] for v in shares.values()]
    twin = [v[1] for v in shares.values()]
    axis.bar(x - w / 2, real, w, color="#56b4e9", label="real circuits")
    axis.bar(x + w / 2, twin, w, color=OURS, label="check circuits (k = 4)")
    for xi, r, t in zip(x, real, twin, strict=True):
        axis.text(xi - w / 2, r + 0.015, f"{r:.0%}", ha="center")
        axis.text(xi + w / 2, t + 0.015, f"{t:.0%}", ha="center")
    axis.set_xticks(x, list(shares))
    axis.set_ylim(0, 0.85)
    axis.set_ylabel("answers clearly away from 0\n(|value| > 0.1)")
    axis.legend(frameon=False, loc="upper right")
    axis.set_title("Bigger chip, emptier check circuits")
    save(fig, "C8_why_scaling_is_hard", ["docs/RESEARCH_LOG.md (H5 diagnosis)"])


if __name__ == "__main__":
    for make in (c1_hardware, c2_scaling, c3_healing_timeline, c4_hardware_replay, c5_alarm_156, c6_cost,
                 c7_realism_ladder, c8_zeros):
        make()
