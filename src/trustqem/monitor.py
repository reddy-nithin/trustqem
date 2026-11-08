"""Self-healing loop (Amendment 4): watch Clifford canaries with a conformal test martingale, recalibrate on alarm.

The idea in one line: while the device is unchanged, each canary's score looks like one more draw from the reference
scores, so its conformal p-value is uniform. A betting martingale on those p-values stays small; Ville's inequality
says it reaches 1/alpha with probability at most alpha. When the device drifts, canary scores get larger, p-values
get small, the martingale grows, and crossing 1/alpha is the alarm.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from scipy.special import logsumexp

EPSILON_GRID = np.linspace(0.01, 0.99, 99)   # betting strengths averaged by the simple-mixture martingale


def conformal_p_value(bag: np.ndarray, score: float, rng: np.random.Generator) -> float:
    """Smoothed conformal p-value of `score` against `bag` (larger score = stranger), ties broken at random."""
    greater = np.count_nonzero(bag > score)
    equal = np.count_nonzero(bag == score) + 1           # the new score ties with itself
    return float((greater + rng.uniform() * equal) / (bag.size + 1))


@dataclass
class SimpleMixtureMartingale:
    """Power martingale prod(eps * p**(eps - 1)) averaged over eps (Vovk, Gammerman and Shafer). Kept in logs."""

    log_products: np.ndarray = field(default_factory=lambda: np.zeros(EPSILON_GRID.size))

    def update(self, p_value: float) -> float:
        """Bet on one p-value and return the new martingale value."""
        p_value = max(p_value, 1e-12)
        self.log_products = self.log_products + np.log(EPSILON_GRID) + (EPSILON_GRID - 1) * np.log(p_value)
        return self.value

    @property
    def value(self) -> float:
        return float(np.exp(logsumexp(self.log_products) - np.log(EPSILON_GRID.size)))


@dataclass
class CanaryMonitor:
    """Sequential conformal test of 'canaries still look like the reference'. Each canary joins the bag after use."""

    reference: np.ndarray
    rng: np.random.Generator
    threshold: float = 20.0
    martingale: SimpleMixtureMartingale = field(default_factory=SimpleMixtureMartingale)

    def __post_init__(self) -> None:
        self.bag = np.asarray(self.reference, dtype=float).copy()

    def observe(self, scores: np.ndarray) -> tuple[float, bool]:
        """Feed one session's canary scores in random order. Returns (martingale value, alarm)."""
        for score in self.rng.permutation(np.asarray(scores, dtype=float)):
            self.martingale.update(conformal_p_value(self.bag, score, self.rng))
            self.bag = np.append(self.bag, score)
        return self.martingale.value, self.martingale.value >= self.threshold


@dataclass(frozen=True)
class Session:
    """One day: per-circuit canary scores, and what to do with them."""

    canary_scores: np.ndarray                              # one score per canary circuit (frozen model)
    evaluate: Callable[[object], tuple[float, float]]      # state -> (coverage, mean width) on today's test rows
    heal: Callable[[], object]                             # recalibrate on today's canaries; returns the new state


@dataclass(frozen=True)
class DayLog:
    day: int
    martingale: float
    alarm: bool
    healed: bool
    coverage: float
    mean_width: float


def run_self_healing(reference_scores: np.ndarray, sessions: list[Session], start_state: object,
                     rng: np.random.Generator, threshold: float = 20.0) -> list[DayLog]:
    """Day loop: watch canaries; on alarm, heal with today's canaries, make them the new reference, start over."""
    monitor, state, logs = CanaryMonitor(reference_scores, rng, threshold), start_state, []
    for day, session in enumerate(sessions, start=1):
        value, alarm = monitor.observe(session.canary_scores)
        if alarm:
            state = session.heal()
            monitor = CanaryMonitor(session.canary_scores, rng, threshold)
        coverage, width = session.evaluate(state)
        logs.append(DayLog(day, value, alarm, alarm, coverage, width))
    return logs
