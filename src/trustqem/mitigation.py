"""Mitigation methods: zero-noise extrapolation (ZNE) and the learned gradient-boosting mitigator."""

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split

from trustqem.config import ExperimentConfig
from trustqem.dataset import MitigationDataset


def zne_extrapolate(noisy_values_at_scales: np.ndarray, scale_factors: tuple[float, ...], degree: int) -> float:
    """Fit a polynomial through (scale, noisy value) points and read it off at scale 0 (zero noise)."""
    coefficients = np.polyfit(scale_factors, noisy_values_at_scales, degree)
    return float(np.polyval(coefficients, 0.0))


def zne_all_rows(noisy_values: np.ndarray, scale_factors: tuple[float, ...], degree: int) -> np.ndarray:
    """ZNE on every row, clipped to [-1, 1] because Pauli expectation values can't leave that range."""
    extrapolated = np.array([zne_extrapolate(row, scale_factors, degree) for row in noisy_values])
    return np.clip(extrapolated, -1, 1)


def split_circuits(
    number_of_circuits: int,
    test_fraction: float,
    random_seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Split circuit ids (not rows) so every observable of a test circuit is unseen."""
    train_circuits, test_circuits = train_test_split(
        np.arange(number_of_circuits), test_size=test_fraction, random_state=random_seed)
    return train_circuits, test_circuits


def rows_of(dataset: MitigationDataset, circuit_ids: np.ndarray) -> np.ndarray:
    """Boolean mask of the rows that belong to the given circuits."""
    return np.isin(dataset.row_circuit_index, circuit_ids)


def build_model_inputs(dataset: MitigationDataset) -> np.ndarray:
    """What the learned model sees: the noisy value at each scale, then the cheap circuit features."""
    return np.hstack([dataset.row_noisy_values, dataset.row_features])


def train_learned_mitigator(
    model_inputs: np.ndarray,
    ideal_values: np.ndarray,
    config: ExperimentConfig,
) -> GradientBoostingRegressor:
    """Gradient boosting from (noisy values, features) to the ideal value."""
    model = GradientBoostingRegressor(
        n_estimators=config.gradient_boosting_trees,
        max_depth=config.gradient_boosting_depth,
        random_state=config.random_seed,
    )
    model.fit(model_inputs, ideal_values)
    return model


def learned_predictions(model: GradientBoostingRegressor, model_inputs: np.ndarray) -> np.ndarray:
    """Model predictions, clipped to [-1, 1]."""
    return np.clip(model.predict(model_inputs), -1, 1)
