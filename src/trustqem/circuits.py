"""Circuit generators.

The random-circuit recipe is Luke Miller's, unchanged. Clifford twins are new: same layout as a target circuit, with
rotation angles snapped to multiples of pi/2 so a classical computer can compute their ideal output at any size.
"""

from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit
from qiskit.exceptions import QiskitError
from qiskit.quantum_info import Clifford

ONE_QUBIT_GATE_NAMES = ("rx", "ry", "rz")
TWO_QUBIT_GATE_NAMES = ("cx",)
CLIFFORD_ANGLES = (0.0, np.pi / 2, np.pi, 3 * np.pi / 2)


@dataclass(frozen=True)
class CircuitRecord:
    """A circuit plus the structural facts the learned model uses as features."""

    circuit: QuantumCircuit
    layer_count: int
    cx_count: int
    non_clifford_count: int

    @property
    def one_qubit_gate_count(self) -> int:
        """Number of rotation gates (one per qubit per layer)."""
        return self.layer_count * self.circuit.num_qubits


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


def build_random_records(
    number_of_circuits: int,
    qubit_count: int,
    max_layers: int,
    cx_probability_per_pair: float,
    random_generator: np.random.Generator,
) -> list[CircuitRecord]:
    """A pool of Luke-style random circuits with random depth in [1, max_layers]."""
    records = []
    for _ in range(number_of_circuits):
        layer_count = int(random_generator.integers(1, max_layers + 1))
        circuit, cx_count = build_random_circuit(layer_count, qubit_count, cx_probability_per_pair, random_generator)
        records.append(CircuitRecord(circuit, layer_count, cx_count, non_clifford_count=layer_count * qubit_count))
    return records


def build_clifford_twin(
    target: CircuitRecord,
    non_clifford_keep: int,
    random_generator: np.random.Generator,
) -> CircuitRecord:
    """Copy the target's gate layout, replacing rotation angles with random multiples of pi/2.

    `non_clifford_keep` rotations (chosen at random) keep their original angle, making a near-Clifford circuit.
    With 0 kept, the twin is exactly Clifford. Classical simulation cost grows with the kept count, so on
    hardware-sized circuits only small values stay checkable. This is the training-circuit idea of Clifford
    Data Regression (Czarnik et al.).
    """
    source = target.circuit
    rotation_positions = [index for index, instruction in enumerate(source.data)
                          if instruction.operation.name in ONE_QUBIT_GATE_NAMES]
    keep_count = min(non_clifford_keep, len(rotation_positions))
    kept_positions = set(random_generator.choice(rotation_positions, size=keep_count, replace=False).tolist())

    twin = QuantumCircuit(source.num_qubits)
    for index, instruction in enumerate(source.data):
        name = instruction.operation.name
        qubits = [source.find_bit(qubit).index for qubit in instruction.qubits]
        if name in ONE_QUBIT_GATE_NAMES:
            angle = (float(instruction.operation.params[0]) if index in kept_positions
                     else float(random_generator.choice(CLIFFORD_ANGLES)))
            getattr(twin, name)(angle, qubits[0])
        elif name in TWO_QUBIT_GATE_NAMES:
            twin.cx(qubits[0], qubits[1])
        else:
            raise ValueError(f"unexpected gate {name!r} in target circuit")
    return CircuitRecord(twin, target.layer_count, target.cx_count, non_clifford_count=keep_count)


def is_clifford(circuit: QuantumCircuit) -> bool:
    """True if qiskit can represent the circuit as a Clifford (every gate is Clifford)."""
    try:
        Clifford(circuit)
    except QiskitError:
        return False
    return True
