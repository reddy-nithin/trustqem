"""Noise models and drift scenarios.

A NoiseCondition is one state of the device ("Monday", "Tuesday after drift", ...). It builds a noise model at any
noise scale factor, because ZNE needs the same device at 1x, 2x and 3x noise.
"""

from collections.abc import Callable
from dataclasses import dataclass

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error, thermal_relaxation_error

from trustqem.circuits import ONE_QUBIT_GATE_NAMES, TWO_QUBIT_GATE_NAMES
from trustqem.config import ExperimentConfig
from trustqem.simulate import aer_device_options

# Thermal relaxation parameters for the drift scenarios, in microseconds. These are pessimistic (older-generation
# hardware, or a bad day) so the effect is visible next to 3% two-qubit depolarizing noise.
T1_MICROSECONDS = 30.0
T2_MICROSECONDS = 20.0
ONE_QUBIT_GATE_MICROSECONDS = 0.05
TWO_QUBIT_GATE_MICROSECONDS = 0.4


@dataclass(frozen=True)
class NoiseCondition:
    """One device state. Every field multiplies or adds to Monday's depolarizing noise."""

    name: str
    depolarizing_multiplier: float = 1.0
    bad_qubit: int | None = None               # CX gates touching this qubit get extra depolarizing noise
    bad_qubit_multiplier: float = 1.0
    thermal_relaxation: bool = False           # add T1/T2 decay during every gate (pulls qubits toward |0>)
    readout_flip_probability: float = 0.0      # chance each measured bit is misread

    def build_noise_model(self, scale_factor: float, config: ExperimentConfig) -> NoiseModel:
        """Noise model at a ZNE scale factor. Gate noise scales; readout noise does not (ZNE can't amplify it)."""
        noise_model = NoiseModel()
        one_rate = scale_factor * self.depolarizing_multiplier * config.one_qubit_depolarizing_rate
        two_rate = scale_factor * self.depolarizing_multiplier * config.two_qubit_depolarizing_rate

        one_qubit_error = depolarizing_error(one_rate, 1)
        if self.thermal_relaxation:
            one_qubit_error = one_qubit_error.compose(_thermal_error(scale_factor * ONE_QUBIT_GATE_MICROSECONDS, 1))
        noise_model.add_all_qubit_quantum_error(one_qubit_error, list(ONE_QUBIT_GATE_NAMES))

        for control in range(config.qubit_count - 1):
            pair = [control, control + 1]
            pair_rate = two_rate * (self.bad_qubit_multiplier if self.bad_qubit in pair else 1.0)
            two_qubit_error = depolarizing_error(min(pair_rate, 1.0), 2)
            if self.thermal_relaxation:
                two_qubit_error = two_qubit_error.compose(
                    _thermal_error(scale_factor * TWO_QUBIT_GATE_MICROSECONDS, 2))
            noise_model.add_quantum_error(two_qubit_error, list(TWO_QUBIT_GATE_NAMES), pair)

        if self.readout_flip_probability > 0:
            flip = self.readout_flip_probability
            noise_model.add_all_qubit_readout_error(ReadoutError([[1 - flip, flip], [flip, 1 - flip]]))
        return noise_model

    def build_simulators(self, config: ExperimentConfig) -> dict[float, AerSimulator]:
        """One density-matrix simulator per ZNE scale factor."""
        return {scale: AerSimulator(method="density_matrix", noise_model=self.build_noise_model(scale, config),
                                     **aer_device_options())
                for scale in config.noise_scale_factors}

    def prepare_circuit(self, circuit: QuantumCircuit, scale: float) -> QuantumCircuit:
        """The circuit runs as written: here the noise model, not the circuit, carries the noise scale."""
        return circuit


def _thermal_error(gate_microseconds: float, qubit_count: int):
    """T1/T2 relaxation over one gate's duration, on 1 or 2 qubits."""
    single = thermal_relaxation_error(T1_MICROSECONDS, T2_MICROSECONDS, gate_microseconds)
    return single if qubit_count == 1 else single.expand(single)


MONDAY = NoiseCondition(name="monday")

DRIFT_SCENARIOS: dict[str, NoiseCondition] = {
    "D0_no_drift": NoiseCondition(name="D0_no_drift"),
    "D1_depolarizing_x1.5": NoiseCondition(name="D1_depolarizing_x1.5", depolarizing_multiplier=1.5),
    "D2_depolarizing_x2": NoiseCondition(name="D2_depolarizing_x2", depolarizing_multiplier=2.0),
    "D3_bad_qubit": NoiseCondition(name="D3_bad_qubit", bad_qubit=2, bad_qubit_multiplier=4.0),
    "D4_thermal_relaxation": NoiseCondition(name="D4_thermal_relaxation", thermal_relaxation=True),
    "D5_readout": NoiseCondition(name="D5_readout", readout_flip_probability=0.03),
    "D6_combined": NoiseCondition(name="D6_combined", depolarizing_multiplier=1.25, bad_qubit=2,
                                  bad_qubit_multiplier=3.0, thermal_relaxation=True, readout_flip_probability=0.02),
}

SimulatorFactory = Callable[[ExperimentConfig], dict[float, AerSimulator]]


def build_depolarizing_noise_model(scale_factor: float, one_qubit_rate: float, two_qubit_rate: float) -> NoiseModel:
    """Luke's original model: depolarizing noise after every gate, both rates multiplied by scale_factor.

    Kept separately (rather than through NoiseCondition) so notebook 00 reproduces his numbers bit for bit.
    """
    noise_model = NoiseModel()
    noise_model.add_all_qubit_quantum_error(
        depolarizing_error(scale_factor * one_qubit_rate, 1), list(ONE_QUBIT_GATE_NAMES))
    noise_model.add_all_qubit_quantum_error(
        depolarizing_error(scale_factor * two_qubit_rate, 2), list(TWO_QUBIT_GATE_NAMES))
    return noise_model


def build_noisy_simulators(config: ExperimentConfig) -> dict[float, AerSimulator]:
    """Luke's simulators: one density-matrix simulator per noise scale factor."""
    return {
        scale_factor: AerSimulator(
            method="density_matrix",
            noise_model=build_depolarizing_noise_model(
                scale_factor, config.one_qubit_depolarizing_rate, config.two_qubit_depolarizing_rate),
        )
        for scale_factor in config.noise_scale_factors
    }
