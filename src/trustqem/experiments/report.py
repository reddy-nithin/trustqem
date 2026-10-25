"""Aggregate repeats, plot, and apply the pre-registered verdict rules (docs/HYPOTHESES.md)."""

from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

METHOD_STYLE = {
    "R0_frozen": ("#9a9a9a", "frozen Monday intervals"),
    "zne_bootstrap": ("#e69f00", "ZNE + bootstrap"),
    "R1_clifford_direct": ("#56b4e9", "Clifford direct"),
    "R2_clifford_ratio": ("#0072b2", "Clifford ratio"),
    "R1W_clifford_weighted": ("#cc79a7", "Clifford weighted (ours)"),
    "R3_oracle": ("#009e73", "oracle (labeled drifted circuits)"),
    "R4_retrain": ("#d55e00", "retrain on labeled drifted circuits"),
}
MAIN_SERIES_K = 4          # twin type shown in the main figure (Amendment 1: judged on k >= 2)
TOLERANCE = 0.03


def _mean_and_ci(values: list[float]) -> dict:
    """Mean with a normal-approximation 95% interval across repeats."""
    array = np.asarray(values, dtype=float)
    half = 1.96 * array.std(ddof=1) / np.sqrt(array.size) if array.size > 1 else float("nan")
    return {"mean": float(array.mean()), "ci95": float(half), "n": int(array.size)}


def summarize(rows: list[dict], alarms: list[dict], alpha: float) -> dict:
    """Group result rows by (scenario, method, K, k) and alarm p-values by (scenario, K, k)."""
    groups: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        key = (row["scenario"], row["method"], row["recalibration_count"], row["non_clifford_count"])
        for field in ("coverage", "mean_width", "model_mae"):
            groups[key][field].append(row[field])
    intervals = [{"scenario": s, "method": m, "K": count, "k": keep,
                  **{field: _mean_and_ci(values) for field, values in fields.items()}}
                 for (s, m, count, keep), fields in sorted(groups.items())]

    alarm_groups: dict[tuple, list] = defaultdict(list)
    for alarm in alarms:
        alarm_groups[(alarm["scenario"], alarm["recalibration_count"], alarm["non_clifford_count"])].append(
            alarm["p_value"])
    alarm_summary = [{"scenario": s, "K": count, "k": keep,
                      "detection_rate": float(np.mean(np.asarray(p_values) < 0.05)), "n": len(p_values)}
                     for (s, count, keep), p_values in sorted(alarm_groups.items())]
    return {"alpha": alpha, "intervals": intervals, "alarms": alarm_summary}


def _lookup(summary: dict, scenario: str, method: str, count: int, keep: int) -> dict | None:
    """Find one aggregated entry."""
    for entry in summary["intervals"]:
        if (entry["scenario"], entry["method"], entry["K"], entry["k"]) == (scenario, method, count, keep):
            return entry
    return None


def _scenario_label(scenario: str) -> str:
    """'D4_thermal_relaxation' -> 'D4 thermal relaxation'."""
    return scenario.replace("_", " ")


def plot_coverage_by_scenario(summary: dict, alpha: float, count: int) -> Figure:
    """Coverage (top) and width (bottom) per scenario at one K, for the headline methods."""
    scenarios = sorted({entry["scenario"] for entry in summary["intervals"] if entry["scenario"] != "monday"})
    keeps = {entry["k"] for entry in summary["intervals"] if entry["k"] >= 0}
    keep = MAIN_SERIES_K if MAIN_SERIES_K in keeps else max(keeps)
    series = [("R0_frozen", 0, -1), ("zne_bootstrap", 0, -1), ("R1_clifford_direct", count, keep),
              ("R2_clifford_ratio", count, keep), ("R1W_clifford_weighted", count, keep), ("R3_oracle", count, -1)]
    series = [s for s in series if _lookup(summary, scenarios[0], *s) is not None]
    figure, (coverage_axis, width_axis) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    bar_width = 0.8 / len(series)
    for index, (method, method_count, method_keep) in enumerate(series):
        colour, label = METHOD_STYLE[method]
        label = f"{label}, k={method_keep}" if method_keep >= 0 else label
        entries = [_lookup(summary, scenario, method, method_count, method_keep) for scenario in scenarios]
        positions = np.arange(len(scenarios)) + index * bar_width
        for axis, field in ((coverage_axis, "coverage"), (width_axis, "mean_width")):
            axis.bar(positions, [e[field]["mean"] for e in entries], bar_width,
                     yerr=[e[field]["ci95"] for e in entries], color=colour, label=label)
    width_axis.set_xticks(np.arange(len(scenarios)) + 0.4 - bar_width / 2)
    width_axis.set_xticklabels([_scenario_label(s) for s in scenarios], rotation=15)
    coverage_axis.axhline(1 - alpha, color="black", linestyle="--", linewidth=1)
    coverage_axis.set_ylim(0.3, 1.02)
    coverage_axis.set_ylabel("test coverage (target dashed)")
    width_axis.set_ylabel("mean interval width")
    coverage_axis.legend(loc="lower left", fontsize=8, ncol=3)
    figure.suptitle(f"Do the error bars survive drift? K = {count} recalibration circuits")
    figure.tight_layout()
    return figure


def plot_recalibration_budget(summary: dict, alpha: float) -> Figure:
    """Coverage vs K for Clifford-weighted (each k) against the oracle, one panel per drifted scenario."""
    scenarios = sorted({e["scenario"] for e in summary["intervals"]} - {"monday"})
    keeps = sorted({e["k"] for e in summary["intervals"] if e["method"] == "R1W_clifford_weighted"})
    columns = 4
    figure, axes = plt.subplots(-(-len(scenarios) // columns), columns, figsize=(16, 4 * -(-len(scenarios) // columns)),
                                sharey=True, squeeze=False)
    for axis, scenario in zip(axes.flat, scenarios, strict=False):
        for method, keep, style in [("R3_oracle", -1, "-"), *[("R1W_clifford_weighted", k, "--") for k in keeps]]:
            entries = sorted((e for e in summary["intervals"] if (e["scenario"], e["method"], e["k"])
                              == (scenario, method, keep)), key=lambda e: e["K"])
            if not entries:
                continue
            colour, label = METHOD_STYLE[method]
            shade = 1.0 if keep < 0 else 0.3 + 0.7 * (keeps.index(keep) + 1) / len(keeps)
            axis.errorbar([e["K"] for e in entries], [e["coverage"]["mean"] for e in entries],
                          yerr=[e["coverage"]["ci95"] for e in entries], color=colour, alpha=shade, linestyle=style,
                          marker="o", markersize=3, label=label if keep < 0 else f"{label}, k={keep}")
        axis.axhspan(1 - alpha - TOLERANCE, 1 - alpha + TOLERANCE, color="black", alpha=0.07)
        axis.axhline(1 - alpha, color="black", linestyle=":", linewidth=1)
        axis.set_xscale("log")
        axis.set_title(_scenario_label(scenario), fontsize=10)
        axis.set_xlabel("K recalibration circuits")
    for axis in axes.flat[len(scenarios):]:
        axis.set_visible(False)
    axes[0, 0].set_ylabel("test coverage")
    axes[0, 0].legend(fontsize=7, loc="lower right")
    figure.suptitle("How many recalibration circuits are enough? (grey band: target ± 3 points)")
    figure.tight_layout()
    return figure


def write_verdict(summary: dict, alpha: float, path: Path,
                  title: str = "Verdict (pre-registered rules and Amendment 1, docs/HYPOTHESES.md)") -> None:
    """Apply the pre-registered rules (with Amendment 1) and write a short markdown verdict."""
    target = 1 - alpha
    lines = [f"# {title}", ""]
    monday = _lookup(summary, "monday", "conformal_monday", 0, -1)
    zne = _lookup(summary, "monday", "zne_bootstrap", 0, -1)
    lines.append(f"- **H1** Monday conformal coverage {monday['coverage']['mean']:.3f} "
                 f"(holds: {abs(monday['coverage']['mean'] - target) <= 0.02}); ZNE bootstrap "
                 f"{zne['coverage']['mean']:.3f} (under 0.85: {zne['coverage']['mean'] < 0.85})")
    counts = sorted({e["K"] for e in summary["intervals"] if e["method"] == "R3_oracle" and e["K"] <= 100})
    drifted = sorted({e["scenario"] for e in summary["intervals"]} - {"monday", "D0_no_drift"})
    drops = {s: target - _lookup(summary, s, "R0_frozen", 0, -1)["coverage"]["mean"] for s in drifted}
    lines.append(f"- **H2** scenarios losing >= 10 points: {sum(d >= 0.10 for d in drops.values())} of {len(drops)}")
    lines.append("- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):")
    for scenario in sorted({e["scenario"] for e in summary["intervals"]} - {"monday"}):
        frozen = _lookup(summary, scenario, "R0_frozen", 0, -1)["coverage"]["mean"]
        weighted = _best_recalibration(summary, scenario, counts, target, ("R1W",), minimum_keep=2)
        unweighted = _best_recalibration(summary, scenario, counts, target, ("R1_", "R2_"), minimum_keep=0)
        lines.append(f"  - {scenario}: frozen {frozen:.3f}; R1W (k >= 2): {weighted or 'NOT restored'}; "
                     f"R1/R2: {unweighted or 'NOT restored'}")
    lines.append("- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):")
    for scenario in sorted({a["scenario"] for a in summary["alarms"]}):
        rates = [a["detection_rate"] for a in summary["alarms"] if a["scenario"] == scenario and a["K"] == 100]
        if rates:
            kind = "false-alarm rate" if scenario == "D0_no_drift" else "power"
            lines.append(f"  - {scenario}: {kind} {min(rates):.2f} to {max(rates):.2f}")
    path.write_text("\n".join(lines) + "\n")


def _best_recalibration(summary: dict, scenario: str, counts: list[int], target: float, prefixes: tuple[str, ...],
                        minimum_keep: int) -> str | None:
    """Smallest K whose method lands within tolerance and under 2x oracle width."""
    for count in counts:
        oracle = _lookup(summary, scenario, "R3_oracle", count, -1)
        if oracle is None:
            continue
        oracle_width = oracle["mean_width"]["mean"]
        candidates = [e for e in summary["intervals"]
                      if e["scenario"] == scenario and e["K"] == count and e["method"].startswith(prefixes)
                      and e["k"] >= minimum_keep and abs(e["coverage"]["mean"] - target) <= TOLERANCE
                      and e["mean_width"]["mean"] <= 2 * oracle_width]
        if candidates:
            entry = min(candidates, key=lambda e: abs(e["coverage"]["mean"] - target))
            return (f"{entry['method']} k={entry['k']} K={count} (coverage {entry['coverage']['mean']:.3f}, "
                    f"width {entry['mean_width']['mean']:.3f} vs oracle {oracle_width:.3f})")
    return None
