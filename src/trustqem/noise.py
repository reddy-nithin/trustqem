"""Noise models. Drift scenarios get added here in Phase 2."""

from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

from trustqem.circuits import ONE_QUBIT_GATE_NAMES, TWO_QUBIT_GATE_NAMES
from trustqem.config import ExperimentConfig


def build_depolarizing_noise_model(
    scale_factor: float,
    one_qubit_rate: float,
    two_qubit_rate: float,
) -> NoiseModel:
    """Depolarizing noise after every gate, with both rates multiplied by scale_factor.

    Scaling the rate is the simulator's shortcut for "more noise". Real hardware can't do this
    and uses gate folding instead (Phase 4).
    """
    noise_model = NoiseModel()
    noise_model.add_all_qubit_quantum_error(
        depolarizing_error(scale_factor * one_qubit_rate, 1), list(ONE_QUBIT_GATE_NAMES))
    noise_model.add_all_qubit_quantum_error(
        depolarizing_error(scale_factor * two_qubit_rate, 2), list(TWO_QUBIT_GATE_NAMES))
    return noise_model


def build_noisy_simulators(config: ExperimentConfig) -> dict[float, AerSimulator]:
    """One density-matrix simulator per noise scale factor."""
    return {
        scale_factor: AerSimulator(
            method="density_matrix",
            noise_model=build_depolarizing_noise_model(
                scale_factor, config.one_qubit_depolarizing_rate, config.two_qubit_depolarizing_rate),
        )
        for scale_factor in config.noise_scale_factors
    }
