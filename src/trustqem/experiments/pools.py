"""Build and cache the simulated circuit pools an experiment needs (Monday, Monday twins, Tuesday per scenario)."""

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from trustqem.circuits import CircuitRecord, build_clifford_twin, build_random_records
from trustqem.config import ExperimentConfig
from trustqem.noise import DRIFT_SCENARIOS, MONDAY, NoiseCondition
from trustqem.pool import SimulatedPool, simulate_pool
from trustqem.simulate import build_observable_labels, build_sign_table

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PoolSizes:
    """How many circuits of each kind to simulate."""

    monday_circuits: int            # split into train / calibration / test per repeat
    monday_twin_sources: int        # fresh Monday circuits whose Clifford twins give the Monday Clifford baseline
    tuesday_circuits: int           # per scenario: split into test and oracle-calibration pools per repeat
    twin_non_clifford_counts: tuple[int, ...]
    scenarios: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentPools:
    """Everything simulated for one experiment. Tuesday twin i is the twin of Tuesday circuit i."""

    config: ExperimentConfig
    sizes: PoolSizes
    sign_table: np.ndarray
    monday: SimulatedPool
    monday_twins: dict[int, SimulatedPool]                 # by non-Clifford count
    tuesday: dict[str, SimulatedPool]                      # by scenario
    tuesday_twins: dict[tuple[str, int], SimulatedPool]    # by (scenario, non-Clifford count)


def _twins(records: list[CircuitRecord], keep: int, rng: np.random.Generator) -> list[CircuitRecord]:
    """One twin per record with `keep` non-Clifford rotations."""
    return [build_clifford_twin(record, keep, rng) for record in records]


def build_pools(config: ExperimentConfig, sizes: PoolSizes) -> ExperimentPools:
    """Simulate every pool. The same Tuesday circuits are used in every scenario, so scenarios are paired."""
    rng = np.random.default_rng(config.random_seed)
    labels = build_observable_labels(config.qubit_count)
    observables = [SparsePauliOp(label) for label in labels]
    sign_table = build_sign_table(labels, config.qubit_count)

    def run(records: list[CircuitRecord], condition: NoiseCondition, tag: str) -> SimulatedPool:
        return simulate_pool(records, tag, condition.build_simulators(config), config, observables, labels,
                             sign_table, rng)

    def random_records(count: int) -> list[CircuitRecord]:
        return build_random_records(count, config.qubit_count, config.max_layers, config.cx_probability_per_pair,
                                    rng)

    monday = run(random_records(sizes.monday_circuits), MONDAY, "monday")
    twin_sources = random_records(sizes.monday_twin_sources)
    monday_twins = {keep: run(_twins(twin_sources, keep, rng), MONDAY, f"monday_twins_k{keep}")
                    for keep in sizes.twin_non_clifford_counts}

    tuesday_records = random_records(sizes.tuesday_circuits)
    tuesday_twin_records = {keep: _twins(tuesday_records, keep, rng) for keep in sizes.twin_non_clifford_counts}
    tuesday, tuesday_twins = {}, {}
    for scenario in sizes.scenarios:
        condition = DRIFT_SCENARIOS[scenario]
        tuesday[scenario] = run(tuesday_records, condition, f"tuesday_{scenario}")
        for keep, twin_records in tuesday_twin_records.items():
            tuesday_twins[(scenario, keep)] = run(twin_records, condition, f"tuesday_{scenario}_twins_k{keep}")
    return ExperimentPools(config, sizes, sign_table, monday, monday_twins, tuesday, tuesday_twins)


def load_or_build_pools(config: ExperimentConfig, sizes: PoolSizes, cache_path: Path) -> ExperimentPools:
    """Reuse cached pools if they were built with the same settings, otherwise simulate and cache."""
    if cache_path.exists():
        with open(cache_path, "rb") as cache_file:
            cached: ExperimentPools = pickle.load(cache_file)
        if cached.config == config and cached.sizes == sizes:
            logger.info("loaded cached pools from %s", cache_path)
            return cached
        logger.info("cache settings differ, rebuilding pools")
    pools = build_pools(config, sizes)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as cache_file:
        pickle.dump(pools, cache_file)
    return pools
