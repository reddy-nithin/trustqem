"""Recalibrating conformal intervals after drift, with the learned model frozen.

Every method returns a new half-width q. The interval for a test circuit is always prediction +/- q.
"""

import numpy as np
from scipy.stats import ks_2samp

from trustqem.conformal import conformal_quantile


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
