"""Self-healing loop: the alarm is quiet when nothing changes, fires on drift, and healing resets it."""

import numpy as np

from trustqem.monitor import CanaryMonitor, Session, SimpleMixtureMartingale, conformal_p_value, run_self_healing


def test_p_values_are_uniform_when_scores_are_exchangeable() -> None:
    rng = np.random.default_rng(0)
    p_values = [conformal_p_value(rng.normal(size=50), rng.normal(), rng) for _ in range(4000)]
    assert abs(np.mean(p_values) - 0.5) < 0.02
    assert abs(np.mean(np.array(p_values) < 0.1) - 0.1) < 0.02


def test_martingale_shrinks_on_large_p_values_and_grows_on_small_ones() -> None:
    martingale = SimpleMixtureMartingale()
    for _ in range(20):
        martingale.update(0.9)
    assert martingale.value < 1
    for _ in range(20):
        martingale.update(0.01)
    assert martingale.value > 20


def test_false_alarm_rate_is_at_most_alpha_without_drift() -> None:
    rng = np.random.default_rng(1)
    alarms = 0
    for _ in range(1000):
        monitor = CanaryMonitor(rng.exponential(size=60), rng)
        fired = any(monitor.observe(rng.exponential(size=30))[1] for _ in range(10))
        alarms += fired
    assert alarms / 1000 <= 0.05 + 0.015          # Ville bound plus Monte Carlo slack


def test_alarm_fires_soon_after_a_clear_shift() -> None:
    rng = np.random.default_rng(2)
    monitor = CanaryMonitor(rng.exponential(size=60), rng)
    for _ in range(3):
        monitor.observe(rng.exponential(size=30))
    value, alarm = monitor.observe(2.0 * rng.exponential(size=30) + 0.5)
    assert alarm and value >= 20


def test_healing_runs_once_and_the_monitor_restarts_from_the_new_reference() -> None:
    rng = np.random.default_rng(3)
    healed_days = []

    def session(scale: float, day: int) -> Session:
        return Session(canary_scores=scale * rng.exponential(size=30) + (scale - 1),
                       evaluate=lambda state: (1.0 if state == "healed" else 0.5, 1.0),
                       heal=lambda: healed_days.append(day) or "healed")

    sessions = [session(1.0, d) for d in range(1, 4)] + [session(3.0, d) for d in range(4, 9)]
    logs = run_self_healing(rng.exponential(size=60), sessions, "monday", rng)
    assert healed_days == [4]                       # one alarm at the drift, none after re-referencing
    assert [log.coverage for log in logs] == [0.5] * 3 + [1.0] * 5
