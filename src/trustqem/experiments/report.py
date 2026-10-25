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
    "R3_oracle": ("#009e73", "oracle (labeled drifted circuits)"),
}
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


def plot_coverage_by_scenario(summary: dict, alpha: float, count: int) -> Figure:
    """Coverage (left) and width (right) per scenario at the largest K, best k shown per Clifford method."""
    scenarios = sorted({entry["scenario"] for entry in summary["intervals"] if entry["scenario"] != "monday"})
    keeps = sorted({entry["k"] for entry in summary["intervals"] if entry["k"] >= 0})
    series = [("R0_frozen", 0, -1), ("zne_bootstrap", 0, -1), ("R3_oracle", count, -1)]
    series += [(method, count, keep) for method in ("R1_clifford_direct", "R2_clifford_ratio") for keep in keeps]
    figure, (coverage_axis, width_axis) = plt.subplots(1, 2, figsize=(15, 5.5))
    bar_width = 0.8 / len(series)
    for index, (method, method_count, keep) in enumerate(series):
        colour, label = METHOD_STYLE[method]
        label = f"{label} (k={keep})" if keep >= 0 else label
        alpha_shade = 1.0 if keep <= 0 else max(0.35, 1 - 0.2 * keeps.index(keep))
        entries = [_lookup(summary, scenario, method, method_count, keep) for scenario in scenarios]
        positions = np.arange(len(scenarios)) + index * bar_width
        for axis, field in ((coverage_axis, "coverage"), (width_axis, "mean_width")):
            axis.bar(positions, [e[field]["mean"] for e in entries], bar_width,
                     yerr=[e[field]["ci95"] for e in entries], color=colour, alpha=alpha_shade, label=label)
    for axis in (coverage_axis, width_axis):
        axis.set_xticks(np.arange(len(scenarios)) + 0.4 - bar_width / 2)
        axis.set_xticklabels([s.split("_", 1)[1].replace("_", " ") for s in scenarios], rotation=15)
    coverage_axis.axhline(1 - alpha, color="black", linestyle="--", linewidth=1)
    coverage_axis.set_ylim(0, 1.05)
    coverage_axis.set_ylabel("test coverage (target dashed)")
    width_axis.set_ylabel("mean interval width")
    width_axis.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8)
    figure.suptitle(f"Do the error bars survive drift? K = {count} recalibration circuits")
    figure.tight_layout()
    return figure


def write_verdict(summary: dict, alpha: float, path: Path) -> None:
    """Apply the pre-registered pilot rules and write a short markdown verdict."""
    target = 1 - alpha
    lines = ["# Verdict (pre-registered rules, docs/HYPOTHESES.md)", ""]
    monday = _lookup(summary, "monday", "conformal_monday", 0, -1)
    zne = _lookup(summary, "monday", "zne_bootstrap", 0, -1)
    lines.append(f"- **H1** Monday conformal coverage {monday['coverage']['mean']:.3f} "
                 f"(holds: {abs(monday['coverage']['mean'] - target) <= 0.02}); ZNE bootstrap "
                 f"{zne['coverage']['mean']:.3f} (under 0.85: {zne['coverage']['mean'] < 0.85})")
    counts = sorted({e["K"] for e in summary["intervals"] if e["method"] == "R3_oracle"})
    for scenario in sorted({e["scenario"] for e in summary["intervals"]} - {"monday"}):
        frozen = _lookup(summary, scenario, "R0_frozen", 0, -1)["coverage"]["mean"]
        best = _best_recalibration(summary, scenario, counts, target)
        lines.append(f"- **{scenario}** frozen coverage {frozen:.3f} (drop {target - frozen:+.3f}); "
                     + (f"restored by {best}" if best else "NOT restored by any Clifford method"))
    path.write_text("\n".join(lines) + "\n")


def _best_recalibration(summary: dict, scenario: str, counts: list[int], target: float) -> str | None:
    """Smallest K whose Clifford method lands within tolerance and under 2x oracle width."""
    for count in counts:
        oracle_width = _lookup(summary, scenario, "R3_oracle", count, -1)["mean_width"]["mean"]
        for entry in summary["intervals"]:
            if entry["scenario"] != scenario or entry["K"] != count or not entry["method"].startswith(("R1", "R2")):
                continue
            close = abs(entry["coverage"]["mean"] - target) <= TOLERANCE
            if close and entry["mean_width"]["mean"] <= 2 * oracle_width:
                return (f"{entry['method']} k={entry['k']} K={count} "
                        f"(coverage {entry['coverage']['mean']:.3f}, width {entry['mean_width']['mean']:.3f} "
                        f"vs oracle {oracle_width:.3f})")
    return None
