"""Amendment 5, fix 1 (exploratory): rerun the drift study on its cached pools with R1N added.

Same seeds and splits as the drift run, so every other method reproduces it; outputs go to results/nonzero/.
"""

from pathlib import Path

from trustqem.experiments import drift


def run(profile_name: str, results_root: Path) -> Path:
    return drift.run(profile_name, results_root, output_dir=results_root / "nonzero" / profile_name)
