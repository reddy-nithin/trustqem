"""Simulate a pool of circuits on one device state, keeping everything the methods need."""

import logging
import multiprocessing
import os
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp
from qiskit_aer import AerSimulator

from trustqem.circuits import CircuitRecord
from trustqem.config import ExperimentConfig
from trustqem.simulate import ideal_expectation_values, sampled_probabilities

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimulatedPool:
    """Circuits run on one device state. Row arrays have one row per (circuit, observable)."""

    condition_name: str
    records: list[CircuitRecord]
    probabilities: np.ndarray       # (circuits, scales, 2**n) measured fractions, kept for bootstrap resampling
    row_circuit_index: np.ndarray
    row_features: np.ndarray        # layer_count, one_qubit_gate_count, cx_count, observable_weight
    row_noisy_values: np.ndarray    # (rows, scales)
    row_ideal_values: np.ndarray
    shots: int

    @property
    def circuit_count(self) -> int:
        """How many circuits are in the pool."""
        return len(self.records)

    def rows_of(self, circuit_ids: np.ndarray) -> np.ndarray:
        """Boolean row mask for the given circuits."""
        return np.isin(self.row_circuit_index, circuit_ids)

    def model_inputs(self) -> np.ndarray:
        """What the learned model sees: noisy value per scale, then circuit features (Luke's column order)."""
        return np.hstack([self.row_noisy_values, self.row_features])


def worker_count() -> int:
    """How many processes simulate circuits at once (env TRUSTQEM_WORKERS, default 1 = no extra processes)."""
    value = int(os.environ.get("TRUSTQEM_WORKERS", "1"))
    if value < 1:
        raise ValueError(f"TRUSTQEM_WORKERS must be at least 1, got {value}")
    return value


_worker_simulators: dict[float, AerSimulator] = {}
_UNUSED_RNG = np.random.default_rng(0)   # sampled_probabilities needs one; the explicit seed is used instead


def _init_worker(simulators: dict[float, AerSimulator], counter, gpus: list[str]) -> None:
    """Each worker keeps its own copy of the simulators and runs Aer on one thread (the workers are the parallelism).

    With TRUSTQEM_GPUS="0,1", workers are dealt round-robin onto those GPUs before any CUDA call.
    """
    global _worker_simulators
    if gpus:
        with counter.get_lock():
            index = counter.value
            counter.value += 1
        os.environ["CUDA_VISIBLE_DEVICES"] = gpus[index % len(gpus)]
    for simulator in simulators.values():     # these are this worker's own unpickled copies
        simulator.set_options(max_parallel_threads=1)
    _worker_simulators = simulators


def _sample_task(task: tuple[QuantumCircuit, float, int, int]) -> np.ndarray:
    circuit, scale, shots, seed = task
    return sampled_probabilities(circuit, _worker_simulators[scale], shots, _UNUSED_RNG,
                                 seed_simulator=seed)


def run_sampling_tasks(tasks: list[tuple[QuantumCircuit, float]], seeds: list[int],
                       simulators: dict[float, AerSimulator], shots: int) -> list[np.ndarray]:
    """Measured fractions for every (circuit, scale) task, in task order, on `worker_count()` processes."""
    workers = worker_count()
    if workers == 1:
        return [sampled_probabilities(circuit, simulators[scale], shots, _UNUSED_RNG,
                                      seed_simulator=seed)
                for (circuit, scale), seed in zip(tasks, seeds, strict=True)]
    # spawn, not fork: Aer starts OpenMP threads, and forking a process that has them can hang
    context = multiprocessing.get_context("spawn")
    payload = [(circuit, scale, shots, seed) for (circuit, scale), seed in zip(tasks, seeds, strict=True)]
    gpus = [gpu for gpu in os.environ.get("TRUSTQEM_GPUS", "").split(",") if gpu.strip()]
    counter = context.Value("i", 0)
    with ProcessPoolExecutor(workers, mp_context=context, initializer=_init_worker,
                             initargs=(simulators, counter, gpus)) as executor:
        return list(executor.map(_sample_task, payload, chunksize=max(1, len(payload) // (workers * 8))))


def simulate_pool(
    records: list[CircuitRecord],
    condition_name: str,
    simulators: dict[float, AerSimulator],
    config: ExperimentConfig,
    observables: list[SparsePauliOp],
    observable_labels: list[str],
    sign_table: np.ndarray,
    random_generator: np.random.Generator,
    prepare: Callable[[QuantumCircuit, float], QuantumCircuit] | None = None,
) -> SimulatedPool:
    """Ideal values from the statevector; shot-sampled values at every noise scale from the noisy simulators.

    `prepare(circuit, scale)` turns the logical circuit into what actually runs at that scale (e.g. transpiled and
    gate-folded). Ideal values always come from the logical circuit.
    """
    start_time = time.time()
    tasks = [(record.circuit if prepare is None else prepare(record.circuit, scale), scale)
             for record in records for scale in config.noise_scale_factors]
    # one seed per (circuit, scale), drawn in the same order as the old loop, so any worker count gives the same pool
    seeds = [int(random_generator.integers(0, 2**31)) for _ in tasks]
    flat = run_sampling_tasks(tasks, seeds, simulators, config.shots_per_circuit)
    # shape (circuits, scales, 2**n)
    probabilities = np.array(flat).reshape(len(records), len(config.noise_scale_factors), -1)
    logger.info("pool %s: %d circuits in %.0fs", condition_name, len(records), time.time() - start_time)
    return pool_from_probabilities(records, condition_name, probabilities, config.shots_per_circuit, observables,
                                   observable_labels, sign_table)


def pool_from_probabilities(
    records: list[CircuitRecord],
    condition_name: str,
    probabilities: np.ndarray,
    shots: int,
    observables: list[SparsePauliOp],
    observable_labels: list[str],
    sign_table: np.ndarray,
) -> SimulatedPool:
    """Turn measured fractions (circuits, scales, 2**n), from a simulator or real hardware, into a pool's rows."""
    observable_weights = [sum(1 for character in label if character != "I") for label in observable_labels]
    row_index, row_features, row_noisy, row_ideal = [], [], [], []
    for circuit_index, record in enumerate(records):
        ideal_values = ideal_expectation_values(record.circuit, observables)
        noisy_values = probabilities[circuit_index] @ sign_table.T              # (scales, observables)
        for observable_index, weight in enumerate(observable_weights):
            row_index.append(circuit_index)
            row_features.append([record.layer_count, record.one_qubit_gate_count, record.cx_count, weight])
            row_noisy.append(noisy_values[:, observable_index])
            row_ideal.append(ideal_values[observable_index])
    return SimulatedPool(
        condition_name=condition_name,
        records=records,
        probabilities=np.asarray(probabilities, dtype=float),
        row_circuit_index=np.array(row_index),
        row_features=np.array(row_features, dtype=float),
        row_noisy_values=np.array(row_noisy),
        row_ideal_values=np.array(row_ideal),
        shots=shots,
    )
