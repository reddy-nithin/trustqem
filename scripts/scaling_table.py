"""H5 table: R1W, or another method (argv[2]), with k in {2, 4} at K = 100 against the oracle, per qubit count and drift scenario."""

import json
import sys
from pathlib import Path

K, TARGET, SLACK = 100, 0.90, 0.03


def table(results: Path, qubit_counts: list[int], method: str = "R1W_clifford_weighted") -> list[dict]:
    rows = []
    for n in qubit_counts:
        path = results / f"scale_q{n}" / "summary.json"
        if not path.exists():
            continue
        entries = json.loads(path.read_text())["intervals"]
        oracle = {e["scenario"]: e["mean_width"]["mean"] for e in entries if e["method"] == "R3_oracle"}
        frozen = {e["scenario"]: e["coverage"]["mean"] for e in entries if e["method"] == "R0_frozen"}
        for e in entries:
            if e["method"] != method or e["K"] != K or e["k"] not in (2, 4):
                continue
            coverage, width = e["coverage"]["mean"], e["mean_width"]["mean"]
            ratio = width / oracle[e["scenario"]]
            rows.append({"n": n, "scenario": e["scenario"], "k": e["k"], "frozen": frozen[e["scenario"]],
                         "coverage": coverage, "width_ratio": ratio,
                         "pass": abs(coverage - TARGET) <= SLACK and ratio < 2})
    return rows


if __name__ == "__main__":
    results = Path(sys.argv[1] if len(sys.argv) > 1 else "results/drift")
    rows = table(results, [4, 6, 8, 10, 12], sys.argv[2] if len(sys.argv) > 2 else "R1W_clifford_weighted")
    for r in rows:
        print(f"n={r['n']:2d} {r['scenario']:24s} k={r['k']} frozen {r['frozen']:.3f} repaired {r["coverage"]:.3f} "
              f"width/oracle {r['width_ratio']:.2f} {'PASS' if r['pass'] else 'FAIL'}")
