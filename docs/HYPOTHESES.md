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

### Amendment 1 (2026-10-25, after the pilot, before the confirmation run)

**What the pilot showed.** Clifford-direct (R1) and Clifford-ratio (R2) recovered most of the lost coverage but
stayed 3 to 9 points short on two of three drift scenarios. Diagnosis: 81% of Clifford twin rows (k = 0) have ideal
value exactly 0, against 15% of random-circuit rows, so the twins are a covariate-shifted calibration set.

**New method, R1W (Clifford-weighted).** Weighted split conformal prediction under covariate shift (Tibshirani,
Barber, Candès and Ramdas, NeurIPS 2019). A degree-2 polynomial logistic regression separates twin rows from the
target rows using only quantities measurable on hardware: |noisy value| at each noise scale, its decay from the
lowest to the highest scale, and the circuit features. The odds become likelihood-ratio weights, clipped to
[0.05, 20]. The target rows are the unlabeled test circuits themselves, which are run on the device anyway. These
settings were chosen once, on the pilot pools, and are frozen from here.

**Exploration that led to it, on the pilot pools only (K = 100, 5 repeats):** R1W reached 0.88 to 0.94 coverage on
all four pilot scenarios with near-Clifford twins (k = 2 or 4), at widths 1.0 to 1.2× oracle. With pure Clifford
twins (k = 0) it over-covered (0.98 to 0.99) with widths up to 2.4× oracle, because no pure Clifford row resembles a
random row with a mid-range value.

**Confirmation design.** The pilot pools are now development data. All Stage 2 claims come from fresh pools simulated
with a different seed (2026), all seven scenarios D0 to D6, 20 repeats, K in {10, 25, 50, 100, 200}, twins with
k in {0, 2, 4, 8}. H3 is judged on R1W with k ≥ 2 by the original rule (within 3 points of 90%, width under 2× oracle),
per scenario. R1 and R2 are still reported. Twins are now drawn from all Tuesday circuits rather than only the test
circuits, so K can exceed the test-set size.

**Added comparison, R4 (retrain).** IBM-style fix (Liao et al., 2023): retrain the model on Monday data plus N
labeled drifted random circuits, N in {50, 100, 200}, then calibrate on 100 more labeled drifted circuits. This
measures what our method saves: R4 needs N + 100 circuits with known ideal values, which a classical computer cannot
supply for large non-Clifford circuits.
