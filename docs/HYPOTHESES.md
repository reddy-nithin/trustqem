# Hypotheses (written before any experiment in this repo was run)

Committed on 2026-10-25, before the pilot. Results are reported against these as written, including the ones that
fail. Changes after this date are listed at the bottom with a reason.

## Setup

- **Learned mitigator:** gradient boosting from (noisy expectation values at noise scales 1, 2, 3, cheap circuit
  features) to the ideal expectation value, trained on "Monday" noise (Luke Miller's starter notebook #4).
- **Intervals:** split conformal prediction at miscoverage α = 0.1 (target coverage 90%), calibrated on held-out
  Monday circuits.
- **Drift ("Tuesday"):** the device noise changes after training. The model stays frozen.
- **Clifford recalibration:** run K Clifford or near-Clifford circuits on the drifted device. Their ideal values are
  classically computable at any size, which is the property that matters on hardware. Recompute the conformal quantile
  from the frozen model's residuals on those circuits, without retraining.

## Hypotheses

- **H1 (no drift).** Split-conformal intervals on the learned mitigator reach 90% ± 2 test coverage. ZNE (linear)
  with bootstrap intervals from resampled shots covers less than 85%, because bootstrap captures shot noise but not
  extrapolation bias.
- **H2 (drift breaks it).** Under at least 2 of the drift scenarios, the frozen Monday intervals lose 10 or more
  points of coverage.
- **H3 (Clifford fix).** Recalibrating on K ≤ 100 Clifford or near-Clifford circuits restores coverage to within 3
  points of 90%, with mean interval width below 2× that of an oracle recalibration on K labeled drifted random
  circuits.
- **H4 (drift alarm).** A test comparing Monday and Tuesday Clifford residuals detects each drift scenario with power
  of 80% or more, at a false-alarm rate of 5% or less on the no-drift control.

## Pilot verdict rules

- **Works:** H2 holds on a non-depolarizing drift, and Clifford-direct or Clifford-ratio recalibration restores
  coverage to within ±3 points with K ≤ 100 and width within 2× oracle.
- **Partial:** that only holds for depolarizing drift.
- **Fails:** neither recalibration restores coverage. Pivot options: re-centering, more non-Clifford gates per twin,
  or a different conformity score.

## Changes after pre-registration

(none yet)
