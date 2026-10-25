"""Circuit generators. The random-circuit recipe is Luke Miller's, unchanged."""

import numpy as np
from qiskit import QuantumCircuit

ONE_QUBIT_GATE_NAMES = ("rx", "ry", "rz")
TWO_QUBIT_GATE_NAMES = ("cx",)


def build_random_circuit(
    layer_count: int,
    qubit_count: int,
    cx_probability_per_pair: float,
    random_generator: np.random.Generator,
) -> tuple[QuantumCircuit, int]:
    """Random rotations on every qubit, then CX on random neighboring pairs, repeated layer_count times.

    Returns the circuit and how many CX gates it has.
    """
    circuit = QuantumCircuit(qubit_count)
    cx_count = 0
    for _ in range(layer_count):
        for qubit_index in range(qubit_count):
            rotation_name = random_generator.choice(ONE_QUBIT_GATE_NAMES)
            rotation_angle = random_generator.uniform(0, 2 * np.pi)
            getattr(circuit, rotation_name)(rotation_angle, qubit_index)
        for qubit_index in range(qubit_count - 1):
            if random_generator.uniform() < cx_probability_per_pair:
                circuit.cx(qubit_index, qubit_index + 1)
                cx_count += 1
    return circuit, cx_count
