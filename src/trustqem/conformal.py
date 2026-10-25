"""Split conformal prediction for regression: error bars with a finite-sample coverage guarantee.

The guarantee: if calibration and test points are exchangeable (drawn the same way), an interval
prediction +/- q covers the truth with probability at least 1 - alpha. Drift breaks exchangeability, which is the
whole point of this project.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class IntervalReport:
    """How a set of intervals did on test points."""

    coverage: float          # fraction of test truths inside their interval
    mean_width: float        # average interval width (upper - lower)
    count: int               # number of test points scored


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """The ceil((n+1)(1-alpha))-th smallest score. Returns inf if n is too small to promise 1 - alpha."""
    scores = np.asarray(scores, dtype=float)
    count = scores.size
    if count == 0:
        raise ValueError("need at least one calibration score")
    rank = int(np.ceil((count + 1) * (1 - alpha)))
    if rank > count:
        return float("inf")
    return float(np.sort(scores)[rank - 1])


def absolute_residual_scores(predictions: np.ndarray, truths: np.ndarray) -> np.ndarray:
    """Nonconformity score |truth - prediction|. Big score = the model was far off."""
    return np.abs(np.asarray(truths) - np.asarray(predictions))


def per_circuit_max_scores(scores: np.ndarray, row_circuit_index: np.ndarray) -> np.ndarray:
    """One score per circuit: the worst row. Calibrating on these covers all of a circuit's rows at once,
    and keeps the guarantee exact even though rows of one circuit are correlated."""
    circuit_ids = np.unique(row_circuit_index)
    return np.array([scores[row_circuit_index == circuit_id].max() for circuit_id in circuit_ids])


def evaluate_symmetric_intervals(
    predictions: np.ndarray,
    truths: np.ndarray,
    half_width: float,
) -> IntervalReport:
    """Score intervals prediction +/- half_width, clipped to the physical range [-1, 1]."""
    lower = np.clip(predictions - half_width, -1, 1)
    upper = np.clip(predictions + half_width, -1, 1)
    return evaluate_intervals(lower, upper, truths)


def evaluate_intervals(lower: np.ndarray, upper: np.ndarray, truths: np.ndarray) -> IntervalReport:
    """Coverage and mean width of arbitrary intervals [lower, upper]."""
    covered = (truths >= lower) & (truths <= upper)
    return IntervalReport(coverage=float(covered.mean()), mean_width=float((upper - lower).mean()),
                          count=int(truths.size))
