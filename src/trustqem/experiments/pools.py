"""Build and cache the simulated circuit pools an experiment needs (Monday, Monday twins, Tuesday per scenario)."""

import logging
import os
import pickle
from collections.abc import Mapping
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
    conditions: str = ""                                    # description of the device states, to validate caches


def _conditions(monday_condition: NoiseCondition, scenarios: Mapping[str, NoiseCondition],
                sizes: PoolSizes) -> str:
    """Text description of every device state the pools are simulated on."""
    return repr((monday_condition, [scenarios[name] for name in sizes.scenarios]))


def _twins(records: list[CircuitRecord], keep: int, rng: np.random.Generator) -> list[CircuitRecord]:
    """One twin per record with `keep` non-Clifford rotations."""
    return [build_clifford_twin(record, keep, rng) for record in records]


def _skip_pool(rng: np.random.Generator, circuit_count: int, scale_count: int) -> None:
    """Advance the generator exactly as simulate_pool would (one seed per circuit and scale), without simulating."""
    for _ in range(circuit_count * scale_count):
        rng.integers(0, 2**31)


def build_pools(config: ExperimentConfig, sizes: PoolSizes, monday_condition: NoiseCondition = MONDAY,
                scenarios: Mapping[str, NoiseCondition] = DRIFT_SCENARIOS,
                parts_dir: Path | None = None) -> ExperimentPools:
    """Simulate every pool. The same Tuesday circuits are used in every scenario, so scenarios are paired.

    Any condition with `build_simulators` and `prepare_circuit` works (noise.NoiseCondition, device.DeviceCondition).
    """
    rng = np.random.default_rng(config.random_seed)
    labels = build_observable_labels(config.qubit_count)
    observables = [SparsePauliOp(label) for label in labels]
    sign_table = build_sign_table(labels, config.qubit_count)

    def run(records: list[CircuitRecord], condition: NoiseCondition, tag: str) -> SimulatedPool:
        key = repr((config, sizes, condition, tag, len(records)))
        part = parts_dir / f"{tag}.pkl" if parts_dir is not None else None
        if part is not None and part.exists():
            with open(part, "rb") as file:
                saved_key, saved_pool = pickle.load(file)
            if saved_key == key:
                _skip_pool(rng, len(records), len(config.noise_scale_factors))
                logger.info("pool %s: loaded finished part %s", tag, part)
                return saved_pool
        pool = simulate_pool(records, tag, condition.build_simulators(config), config, observables, labels,
                             sign_table, rng, prepare=condition.prepare_circuit)
        if part is not None:
            part.parent.mkdir(parents=True, exist_ok=True)
            temporary = part.with_suffix(".tmp")
            with open(temporary, "wb") as file:
                pickle.dump((key, pool), file)
            temporary.replace(part)       # atomic, so a crash mid-write never leaves a broken part
        return pool

    def random_records(count: int) -> list[CircuitRecord]:
        return build_random_records(count, config.qubit_count, config.max_layers, config.cx_probability_per_pair,
                                    rng)

    monday = run(random_records(sizes.monday_circuits), monday_condition, "monday")
    twin_sources = random_records(sizes.monday_twin_sources)
    monday_twins = {keep: run(_twins(twin_sources, keep, rng), monday_condition, f"monday_twins_k{keep}")
                    for keep in sizes.twin_non_clifford_counts}

    tuesday_records = random_records(sizes.tuesday_circuits)
    tuesday_twin_records = {keep: _twins(tuesday_records, keep, rng) for keep in sizes.twin_non_clifford_counts}
    tuesday, tuesday_twins = {}, {}
    for scenario in sizes.scenarios:
        condition = scenarios[scenario]
        tuesday[scenario] = run(tuesday_records, condition, f"tuesday_{scenario}")
        for keep, twin_records in tuesday_twin_records.items():
            tuesday_twins[(scenario, keep)] = run(twin_records, condition, f"tuesday_{scenario}_twins_k{keep}")
    return ExperimentPools(config, sizes, sign_table, monday, monday_twins, tuesday, tuesday_twins,
                           _conditions(monday_condition, scenarios, sizes))


def _parts_dir(cache_path: Path) -> Path:
    """Where finished pools are saved one by one, so an interrupted run resumes."""
    return cache_path.parent / "pool_parts"


def load_or_build_pools(config: ExperimentConfig, sizes: PoolSizes, cache_path: Path,
                        monday_condition: NoiseCondition = MONDAY,
                        scenarios: Mapping[str, NoiseCondition] = DRIFT_SCENARIOS) -> ExperimentPools:
    """Reuse cached pools if they were built with the same settings, otherwise simulate and cache."""
    root = os.environ.get("TRUSTQEM_CACHE")
    if root:        # big caches live outside the repo (server: lab storage)
        cache_path = Path(root) / f"{cache_path.parent.parent.name}_{cache_path.parent.name}" / cache_path.name
    if cache_path.exists():
        with open(cache_path, "rb") as cache_file:
            cached: ExperimentPools = pickle.load(cache_file)
        expected = _conditions(monday_condition, scenarios, sizes)
        if cached.config == config and cached.sizes == sizes and getattr(cached, "conditions", "") == expected:
            logger.info("loaded cached pools from %s", cache_path)
            return cached
        logger.info("cache settings differ, rebuilding pools")
    pools = build_pools(config, sizes, monday_condition, scenarios, parts_dir=_parts_dir(cache_path))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as cache_file:
        pickle.dump(pools, cache_file)
    return pools
