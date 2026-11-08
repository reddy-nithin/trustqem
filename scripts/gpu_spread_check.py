"""Check that TRUSTQEM_GPUS spreads pool workers over several GPUs (watch nvidia-smi while it runs)."""

import time

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from trustqem.circuits import build_random_records
from trustqem.config import ExperimentConfig
from trustqem.noise import MONDAY
from trustqem.pool import simulate_pool
from trustqem.simulate import build_observable_labels, build_sign_table


def main() -> None:
    config = ExperimentConfig(qubit_count=12)
    labels = build_observable_labels(12)
    records = build_random_records(32, 12, config.max_layers, config.cx_probability_per_pair,
                                   np.random.default_rng(5))
    start = time.time()
    simulate_pool(records, "spread", MONDAY.build_simulators(config), config, [SparsePauliOp(l) for l in labels],
                  labels, build_sign_table(labels, 12), np.random.default_rng(6))
    print(f"{len(records) * 3 / (time.time() - start):.2f} simulations per second")


if __name__ == "__main__":
    main()
