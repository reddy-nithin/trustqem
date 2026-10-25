"""Build the (circuit, observable) table the mitigation methods learn from and are scored on."""

import logging
import time
from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp
from qiskit_aer import AerSimulator

from trustqem.circuits import build_random_circuit
from trustqem.config import ExperimentConfig
from trustqem.simulate import (
    exact_noisy_expectation_values,
    ideal_expectation_values,
    sampled_expectation_values,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MitigationDataset:
    """One row per (circuit, observable). Arrays are row-aligned."""

    circuits: list[QuantumCircuit]
    row_circuit_index: np.ndarray        # which circuit each row came from, so splits can be by circuit
    row_features: np.ndarray             # config.feature_names values
    row_noisy_values: np.ndarray         # shot-sampled noisy value per noise scale. What the methods see.
    row_matched_budget_values: np.ndarray  # base-scale value with all the shots the scales would have used
    row_exact_noisy_values: np.ndarray   # exact noisy value per noise scale. Reference only.
    row_ideal_values: np.ndarray         # the truth

    @property
    def row_layer_counts(self) -> np.ndarray:
        """Circuit depth (layers) of each row."""
        return self.row_features[:, 0]


def generate_dataset(
    config: ExperimentConfig,
    simulators: dict[float, AerSimulator],
    observables: list[SparsePauliOp],
    observable_labels: list[str],
    sign_table: np.ndarray,
    random_generator: np.random.Generator,
    progress_every: int = 50,
) -> MitigationDataset:
    """Simulate config.number_of_circuits random circuits at every noise scale.

    The order of random draws matches Luke's notebook, so the same seed gives the same dataset.
    """
    rows: dict[str, list] = {name: [] for name in (
        "circuit_index", "features", "noisy", "matched", "exact", "ideal")}
    circuits = []
    base_scale = config.noise_scale_factors[0]
    start_time = time.time()

    for circuit_index in range(config.number_of_circuits):
        layer_count = int(random_generator.integers(1, config.max_layers + 1))
        circuit, cx_count = build_random_circuit(
            layer_count, config.qubit_count, config.cx_probability_per_pair, random_generator)
        one_qubit_gate_count = layer_count * config.qubit_count

        ideal_values = ideal_expectation_values(circuit, observables)
        sampled_per_scale = np.array([
            sampled_expectation_values(circuit, simulators[scale], config.shots_per_circuit, sign_table,
                                       random_generator)
            for scale in config.noise_scale_factors])                       # (scales, observables)
        matched_budget_values = sampled_expectation_values(
            circuit, simulators[base_scale], config.matched_budget_multiplier * config.shots_per_circuit,
            sign_table, random_generator)
        exact_per_scale = np.array([
            exact_noisy_expectation_values(circuit, simulators[scale], observables)
            for scale in config.noise_scale_factors])                       # (scales, observables)

        circuits.append(circuit)
        for observable_index, label in enumerate(observable_labels):
            observable_weight = sum(1 for character in label if character != "I")
            rows["circuit_index"].append(circuit_index)
            rows["features"].append([layer_count, one_qubit_gate_count, cx_count, observable_weight])
            rows["noisy"].append(sampled_per_scale[:, observable_index])
            rows["matched"].append(matched_budget_values[observable_index])
            rows["exact"].append(exact_per_scale[:, observable_index])
            rows["ideal"].append(ideal_values[observable_index])

        if (circuit_index + 1) % progress_every == 0:
            elapsed = time.time() - start_time
            logger.info("simulated %d/%d circuits in %.0fs", circuit_index + 1, config.number_of_circuits, elapsed)

    return MitigationDataset(
        circuits=circuits,
        row_circuit_index=np.array(rows["circuit_index"]),
        row_features=np.array(rows["features"], dtype=float),
        row_noisy_values=np.array(rows["noisy"]),
        row_matched_budget_values=np.array(rows["matched"]),
        row_exact_noisy_values=np.array(rows["exact"]),
        row_ideal_values=np.array(rows["ideal"]),
    )
