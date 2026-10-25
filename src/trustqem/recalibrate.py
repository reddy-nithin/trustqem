"""Recalibrating conformal intervals after drift, with the learned model frozen.

Every method returns a new half-width q. The interval for a test circuit is always prediction +/- q.
"""

from collections.abc import Callable

import numpy as np
from scipy.stats import ks_2samp
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from trustqem.conformal import conformal_quantile, weighted_conformal_quantiles

WEIGHT_CLIP = (0.05, 20.0)     # keeps a few extreme likelihood ratios from deciding the quantile alone


def shift_features(noisy_values: np.ndarray, row_features: np.ndarray) -> np.ndarray:
    """What the weighting sees, all measurable on hardware: |noisy value| per scale, how fast it decays with noise,
    and the circuit features. Sign is dropped because the residual distribution is symmetric in it."""
    magnitude = np.abs(noisy_values)
    decay = magnitude[:, :1] - magnitude[:, -1:]
    return np.hstack([magnitude, decay, row_features])


def fit_shift_weigher(source_features: np.ndarray, target_features: np.ndarray,
                      degree: int = 2) -> Callable[[np.ndarray], np.ndarray]:
    """Estimate the likelihood ratio w(x) = p_target(x) / p_source(x) with a classifier that tells the sets apart.

    If the classifier says P(target | x) = p, then w(x) = p / (1 - p) * n_source / n_target. Weights are clipped to
    WEIGHT_CLIP. Here source = Clifford twin rows (labels known), target = the circuits we want intervals for.
    """
    features = np.vstack([source_features, target_features])
    labels = np.r_[np.zeros(len(source_features)), np.ones(len(target_features))]
    classifier = make_pipeline(StandardScaler(), PolynomialFeatures(degree), StandardScaler(),
                               LogisticRegression(C=1.0, max_iter=2000))
    classifier.fit(features, labels)
    prior_odds = len(source_features) / len(target_features)

    def weigh(rows: np.ndarray) -> np.ndarray:
        target_probability = np.clip(classifier.predict_proba(rows)[:, 1], 1e-6, 1 - 1e-6)
        return np.clip(target_probability / (1 - target_probability) * prior_odds, *WEIGHT_CLIP)

    return weigh


def clifford_weighted_quantiles(
    clifford_scores_after_drift: np.ndarray,
    clifford_shift_features: np.ndarray,
    target_shift_features: np.ndarray,
    alpha: float,
) -> np.ndarray:
    """R1W: Clifford-direct, with twin rows reweighted to look like the target rows. One half-width per target row."""
    weigh = fit_shift_weigher(clifford_shift_features, target_shift_features)
    return weighted_conformal_quantiles(clifford_scores_after_drift, weigh(clifford_shift_features),
                                        weigh(target_shift_features), alpha)


def clifford_direct_quantile(clifford_scores_after_drift: np.ndarray, alpha: float) -> float:
    """R1: calibrate on the drifted device's Clifford circuits as if they were ordinary calibration circuits."""
    return conformal_quantile(clifford_scores_after_drift, alpha)


def clifford_ratio_quantile(
    random_quantile_before: float,
    clifford_scores_before: np.ndarray,
    clifford_scores_after_drift: np.ndarray,
    alpha: float,
) -> float:
    """R2: scale Monday's random-circuit quantile by how much the Clifford quantile grew.

    Uses Monday's measured gap between Clifford and random circuits, so it doesn't need Clifford circuits to look
    like random ones, only to drift the same way.
    """
    before = conformal_quantile(clifford_scores_before, alpha)
    after = conformal_quantile(clifford_scores_after_drift, alpha)
    if before <= 0:
        raise ValueError("Monday Clifford quantile is zero, ratio undefined")
    return random_quantile_before * after / before


def drift_alarm_p_value(clifford_scores_before: np.ndarray, clifford_scores_after: np.ndarray) -> float:
    """Two-sample Kolmogorov-Smirnov test: small p-value = the Clifford residuals changed = the device drifted.

    Pass one score per circuit (e.g. the circuit mean), so the samples are independent.
    """
    return float(ks_2samp(clifford_scores_before, clifford_scores_after).pvalue)


def per_circuit_mean(scores: np.ndarray, row_circuit_index: np.ndarray) -> np.ndarray:
    """Average score per circuit, for tests that need independent samples."""
    circuit_ids = np.unique(row_circuit_index)
    return np.array([scores[row_circuit_index == circuit_id].mean() for circuit_id in circuit_ids])
