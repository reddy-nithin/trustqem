"""Ways to get an expectation value: ideal (statevector), exact noisy (density matrix), and shot-sampled noisy."""

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import DensityMatrix, SparsePauliOp, Statevector
from qiskit_aer import AerSimulator


def build_observable_labels(qubit_count: int) -> list[str]:
    """Z on each qubit, then ZZ on each neighboring pair. Qiskit order: the rightmost character is qubit 0."""
    labels = []
    for qubit_index in range(qubit_count):
        label = ["I"] * qubit_count
        label[qubit_count - 1 - qubit_index] = "Z"
        labels.append("".join(label))
    for qubit_index in range(qubit_count - 1):
        label = ["I"] * qubit_count
        label[qubit_count - 1 - qubit_index] = "Z"
        label[qubit_count - 2 - qubit_index] = "Z"
        labels.append("".join(label))
    return labels


def build_sign_table(observable_labels: list[str], qubit_count: int) -> np.ndarray:
    """sign_table[observable, basis_state] is the +1/-1 value that Z-string observable takes on that basis state.

    Multiplying it by measured probabilities turns counts into expectation values.
    """
    state_indices = np.arange(2 ** qubit_count)
    sign_table = np.zeros((len(observable_labels), 2 ** qubit_count))
    for observable_index, label in enumerate(observable_labels):
        parity = np.zeros(2 ** qubit_count, dtype=int)
        for qubit_index, character in enumerate(reversed(label)):
            if character == "Z":
                parity += (state_indices >> qubit_index) & 1
        sign_table[observable_index] = 1 - 2 * (parity % 2)
    return sign_table


def ideal_expectation_values(circuit: QuantumCircuit, observables: list[SparsePauliOp]) -> np.ndarray:
    """Exact noiseless expectation of every observable, from the statevector."""
    statevector = Statevector(circuit)
    return np.array([statevector.expectation_value(observable).real for observable in observables])


def exact_noisy_expectation_values(
    circuit: QuantumCircuit,
    simulator: AerSimulator,
    observables: list[SparsePauliOp],
) -> np.ndarray:
    """Exact noisy expectation of every observable (infinite shots), from the simulated density matrix."""
    circuit_with_save = circuit.copy()
    circuit_with_save.save_density_matrix()
    # optimization_level=0 keeps the gate names the noise model is attached to
    transpiled = transpile(circuit_with_save, simulator, optimization_level=0)
    density_matrix = DensityMatrix(simulator.run(transpiled).result().data()["density_matrix"])
    return np.array([density_matrix.expectation_value(observable).real for observable in observables])


def sampled_probabilities(
    circuit: QuantumCircuit,
    simulator: AerSimulator,
    shots: int,
    random_generator: np.random.Generator,
) -> np.ndarray:
    """Measure `shots` times in the Z basis and return the fraction of shots that landed on each basis state."""
    qubit_count = circuit.num_qubits
    circuit_with_measurement = circuit.copy()
    circuit_with_measurement.measure_all()
    transpiled = transpile(circuit_with_measurement, simulator, optimization_level=0)
    counts = simulator.run(
        transpiled, shots=shots, seed_simulator=int(random_generator.integers(0, 2**31))).result().get_counts()
    probabilities = np.zeros(2 ** qubit_count)
    for bitstring, count in counts.items():
        probabilities[int(bitstring, 2)] = count / shots
    if abs(probabilities.sum() - 1) > 1e-9:
        raise RuntimeError(f"measured probabilities sum to {probabilities.sum()}, expected 1")
    return probabilities


def sampled_expectation_values(
    circuit: QuantumCircuit,
    simulator: AerSimulator,
    shots: int,
    sign_table: np.ndarray,
    random_generator: np.random.Generator,
) -> np.ndarray:
    """Shot estimate of every observable. This is what real hardware gives you."""
    return sign_table @ sampled_probabilities(circuit, simulator, shots, random_generator)
