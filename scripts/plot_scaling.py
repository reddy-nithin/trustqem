"""Scaling figure (Amendment 4): coverage and width against qubit count at K = 100, k = 4, per drift scenario.

Amendment 5 fix 2 adds one point: R1W with k = 16 twins at 12 qubits (hollow star).
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt

from trustqem.experiments.report import METHOD_STYLE

QUBITS, K, KEEP = (4, 6, 8, 10, 12), 100, 4
RICH_KEEP, RICH_RESULTS = 16, Path("results/twins_k16/scale_q12/summary.json")
SCENARIOS = ("D1_depolarizing_x1.5", "D2_depolarizing_x2", "D3_bad_qubit", "D4_thermal_relaxation", "D5_readout",
             "D6_combined")


def _value(entries, scenario, method, count, keep, field):
    for e in entries:
        if (e["scenario"], e["method"], e["K"], e["k"]) == (scenario, method, count, keep):
            return e[field]["mean"]
    return None


def main(results: Path = Path("results/drift"), out: Path = Path("results/drift/scaling.png")) -> None:
    summaries = {n: json.loads((results / f"scale_q{n}" / "summary.json").read_text())["intervals"] for n in QUBITS}
    fig, axes = plt.subplots(2, len(SCENARIOS), figsize=(16, 5.5), sharex=True, sharey="row")
    rich = json.loads(RICH_RESULTS.read_text())["intervals"] if RICH_RESULTS.exists() else None
    series = (("R0_frozen", 0, -1), ("R1W_clifford_weighted", K, KEEP), ("R3_oracle", K, -1))
    for column, scenario in enumerate(SCENARIOS):
        top, bottom = axes[0, column], axes[1, column]
        top.axhspan(0.87, 0.93, color="#dddddd", zorder=0)
        top.axhline(0.90, color="black", lw=0.8)
        for method, count, keep in series:
            colour, label = METHOD_STYLE[method]
            coverage = [_value(summaries[n], scenario, method, count, keep, "coverage") for n in QUBITS]
            top.plot(QUBITS, coverage, "o-", color=colour, label=label)
            if method != "R0_frozen":
                width = [_value(summaries[n], scenario, method, count, keep, "mean_width") for n in QUBITS]
                bottom.plot(QUBITS, width, "o-", color=colour)
        if rich is not None:
            colour = METHOD_STYLE["R1W_clifford_weighted"][0]
            for axis, field in ((top, "coverage"), (bottom, "mean_width")):
                axis.plot([12], [_value(rich, scenario, "R1W_clifford_weighted", K, RICH_KEEP, field)], "*",
                          markersize=13, markerfacecolor="none", markeredgecolor=colour, markeredgewidth=1.5,
                          label=f"ours, k = {RICH_KEEP} twins (12 q)" if field == "coverage" else None)
        top.set_title(scenario.replace("_", " "), fontsize=9)
        bottom.set_xlabel("qubits")
        bottom.set_xticks(QUBITS)
    axes[0, 0].set_ylabel("test coverage")
    axes[1, 0].set_ylabel("mean interval width")
    axes[0, 0].legend(fontsize=7, loc="lower left")
    fig.suptitle(f"Coverage after drift, K = {K} recalibration circuits, twins k = {KEEP}, star k = {RICH_KEEP} (band: 0.90 ± 0.03)")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    print(out)


if __name__ == "__main__":
    main()
