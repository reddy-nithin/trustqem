"""Baseline error bars: ZNE with bootstrap intervals from resampled shots.

This is what a careful hardware user would do today. It captures shot noise but not extrapolation bias.
"""

import numpy as np


def linear_zne_weights(scale_factors: tuple[float, ...]) -> np.ndarray:
    """Weights w so that linear ZNE = w @ (values at each scale). For scales 1, 2, 3 this is (4/3, 1/3, -2/3)."""
    design = np.column_stack([np.ones(len(scale_factors)), np.asarray(scale_factors)])
    return np.linalg.pinv(design)[0]


def bootstrap_zne_intervals(
    probabilities: np.ndarray,
    sign_table: np.ndarray,
    scale_factors: tuple[float, ...],
    shots: int,
    alpha: float,
    resamples: int,
    random_generator: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Percentile bootstrap for linear ZNE on every (circuit, observable).

    probabilities: (circuits, scales, 2**n) measured fractions. Each resample redraws `shots` outcomes per scale
    from the measured fractions, recomputes the expectation values and the ZNE estimate.
    Returns (point, lower, upper), each of shape (circuits * observables,) in the pool's row order.
    """
    weights = linear_zne_weights(scale_factors)
    points, lowers, uppers = [], [], []
    for circuit_probabilities in probabilities:
        point = np.clip(weights @ (circuit_probabilities @ sign_table.T), -1, 1)       # (observables,)
        resampled = np.stack([
            random_generator.multinomial(shots, scale_probabilities / scale_probabilities.sum(), size=resamples)
            / shots
            for scale_probabilities in circuit_probabilities], axis=1)                # (resamples, scales, 2**n)
        estimates = np.clip(np.einsum("s,rso->ro", weights, resampled @ sign_table.T), -1, 1)
        points.append(point)
        lowers.append(np.quantile(estimates, alpha / 2, axis=0))
        uppers.append(np.quantile(estimates, 1 - alpha / 2, axis=0))
    return np.concatenate(points), np.concatenate(lowers), np.concatenate(uppers)
