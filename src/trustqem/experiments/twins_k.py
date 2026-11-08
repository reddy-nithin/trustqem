"""Amendment 5, fix 2 (exploratory): twins with k = 16 non-Clifford rotations at 12 qubits.

k = 16 was fixed before any coverage was seen: it matches the 4-qubit twin-to-real share of observables with
|ideal| > 0.1 (RESEARCH_LOG 2026-11-06). The other pools are the Amendment 4 drift pools, reused unchanged.
Profile "scale_q12" (or any drift profile); outputs go to results/twins_k16/<profile>/.
"""

import os
from dataclasses import replace
from pathlib import Path

from trustqem.config import ExperimentConfig

from trustqem.experiments import drift
from trustqem.experiments.pools import add_twin_pools, load_or_build_pools

KEEP = 16


def run(profile_name: str, results_root: Path, keep: int = KEEP) -> Path:
    profile = drift.PROFILES[profile_name]
    config = replace(ExperimentConfig(), random_seed=profile.random_seed, qubit_count=profile.qubit_count)
    pools = load_or_build_pools(config, profile.sizes, results_root / "drift" / profile_name / "pools.pkl")
    root = Path(os.environ.get("TRUSTQEM_CACHE", results_root / "drift" / profile_name))
    parts = root / f"twins_k{keep}_{profile_name}"
    extended = add_twin_pools(pools, keep, profile.random_seed + 16_000, parts)
    return drift.analyze(extended, profile, results_root / f"twins_k{keep}" / profile_name)
