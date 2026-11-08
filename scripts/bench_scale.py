"""Speed test for Amendment 4: seconds per circuit at one qubit count, on whatever simulator the env selects.

Prints the time per (circuit, scale) and the exact noisy values, so CPU and GPU runs can be compared.
Usage: uv run python scripts/bench_scale.py <qubits> <circuits> <output.json>
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from trustqem.circuits import build_random_records
from trustqem.config import ExperimentConfig
from trustqem.noise import MONDAY
from trustqem.simulate import aer_device_options, build_observable_labels, exact_noisy_expectation_values


def main() -> None:
    qubits, circuits, output = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    config = ExperimentConfig(qubit_count=qubits)
    records = build_random_records(circuits, qubits, config.max_layers, config.cx_probability_per_pair,
                                   np.random.default_rng(99))
    observables = [SparsePauliOp(label) for label in build_observable_labels(qubits)]
    simulators = MONDAY.build_simulators(config)
    exact_noisy_expectation_values(records[0].circuit, simulators[1.0], observables)   # warm-up
    values, start = [], time.time()
    for record in records:
        for scale in config.noise_scale_factors:
            values.append(exact_noisy_expectation_values(record.circuit, simulators[scale], observables).tolist())
    seconds = (time.time() - start) / (circuits * len(config.noise_scale_factors))
    output.write_text(json.dumps({"qubits": qubits, "options": aer_device_options(),
                                  "seconds_per_circuit_scale": seconds, "values": values}))
    print(f"{qubits} qubits, {aer_device_options() or 'CPU double'}: {seconds:.3f} s per circuit and scale")


if __name__ == "__main__":
    main()
