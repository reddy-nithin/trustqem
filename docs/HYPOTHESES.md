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

### Amendment 2 (2026-10-25, Stage 3, before the device pilot)

**Question.** Do H2 and H3 still hold, with R1W exactly as frozen in Amendment 1, when (a) the noise is a per-qubit
model of a real IBM Heron device and (b) noise is amplified by gate folding, which is what hardware allows, instead
of by scaling error rates inside the simulator?

**Device (Monday).** The FakeFez snapshot in qiskit-ibm-runtime 0.51.0 (Heron r2, 156 qubits, calibration dated
2025-02-26). We use the connected line of 4 physical qubits with the lowest summed cz error plus readout error:
physical qubits 136, 143, 142, 141. Their calibration: T1 96, 150, 166, 168 µs; T2 94, 123, 145, 91 µs; sx error
2.1e-4, 1.0e-4, 3.1e-4, 1.4e-4; cz error 2.4e-3, 3.3e-3, 2.9e-3 on the three edges; readout P(1|0) 0 to 0.003 and
P(0|1) 0.007 to 0.011; sx 24 ns, cz 84 ns. Noise model: each gate gets T1/T2 relaxation over its duration plus
depolarizing noise sized so the total matches the calibrated gate error (the recipe of Aer's
NoiseModel.from_backend; a test checks every gate channel matches it exactly); readout keeps IBM's asymmetric flip
probabilities; idle qubits decay through ALAP scheduling and Aer's RelaxationNoisePass. rz is virtual and noiseless.

**Circuits and folding.** Same random-circuit recipe and twins as before (4 qubits, 1 to 12 layers). Circuits and
twins are transpiled to the native gates (cz, rz, sx, x) on the line with optimization level 0, so twin and target
keep the same layout and gates are not merged. Noise is amplified by local unitary folding, G to G (G† G)^n, at
scales 1, 3, 5. The learned model's inputs are the noisy values at fold scales 1, 3, 5 plus the same four circuit
features. Shots stay at 1000 per circuit per scale.

**Tuesday scenarios (frozen here).** Applied to Monday's calibration of the four chain qubits:

| scenario | change | basis |
|---|---|---|
| E0 no drift | none (control) | |
| E1 coherence drop | T1 and T2 x0.5 on all four qubits | T1 of one transmon varies by more than 2x over days (Burnett et al., npj Quantum Inf. 2019, doi 10.1038/s41534-019-0168-5); all four at once is a pessimistic day |
| E2 bad qubit | chain qubit 1 (physical 143): T1 x0.2; cz error on its two edges x3 | a defect coming into resonance can change T1 by up to 10x within 15 minutes (Klimov et al., PRL 121, 090502, 2018; on IBM qubits, Carroll et al., npj Quantum Inf. 2022, doi 10.1038/s41534-022-00643-y); gate errors of single ibm_kyiv qubits fluctuated by up to 300% over 12 days (arXiv 2505.06165) |
| E3 readout | readout flip probabilities x2 | assumption: no published day-to-day readout figure was found; on FakeFez the 90th-percentile readout error is 3.5x the median, so x2 is inside the spread of one chip |
| E4 gate errors | sx, x, cz errors x1.5 | stale calibration; inside the 300% range above; on FakeFez the 90th-percentile sx and cz errors are 2.0x and 3.7x the median |
| E5 combined | T1/T2 x0.7, gate errors x1.3, readout x1.5, plus chain qubit 1 at T1 x0.5 and cz x1.5 | milder versions of all of the above on one day |

**Hypotheses and pass rules (unchanged in substance).**
- H1 check: Monday conformal coverage within 0.90 ± 0.02.
- H2: frozen Monday intervals lose 10 or more points of coverage in at least 2 of the 5 drift scenarios (E1 to E5).
- H3, judged per scenario including E0: R1W with near-Clifford twins (k ≥ 2) at some K ≤ 100 reaches coverage
  within 3 points of 0.90 with mean width under 2x the oracle at the same K. This is the rule Amendment 1's verdict
  code applies. The fixed cell k = 4, K = 100 is reported next to it for every scenario, so the reader can see the
  result without the choice of k and K.
- H4 (drift alarm) is reported as secondary and not judged.

**R1W is unchanged.** Same shift features (|noisy value| at each scale, decay from the lowest to the highest scale,
circuit features), degree-2 polynomial logistic regression, weights clipped to [0.05, 20]. The only difference is
that the scale columns now hold fold scales 1, 3, 5 instead of rate scales 1, 2, 3, because that is what the
hardware gives. Nothing about R1W will be tuned on Stage 3 results; any change would need a new amendment and fresh
pools with another seed.

**Methods reported.** R0 frozen, ZNE (linear, scales 1, 3, 5) with bootstrap intervals, R1, R2, R1W (k = 0, 2, 4, 8),
R3 oracle, and R4 retrain.

**Runs.** Pilot: seed 3003, 500 Monday circuits, 300 Tuesday circuits per scenario, K in {25, 50, 100}, 5 repeats,
R4 with N in {50, 100}. Full: seed 3030, 400 Tuesday circuits per scenario, K in {10, 25, 50, 100, 200}, 20
repeats, R4 with N in {50, 100, 200}. The full run goes ahead if the pilot finishes without errors and the full run
is projected to take under 3 hours, whatever the pilot's verdict. If it runs, the full run is the Stage 3 verdict
and the pilot is reported alongside; otherwise the pilot is the verdict.

**Disclosure.** Before this amendment a smoke run (60 Monday circuits, scenarios E0 and E5, 2 repeats) checked that
the code runs. Its numbers were seen. Nothing above was changed because of them.

**Correction to the basis column (2026-10-26, after checking the full papers).** The scenarios, magnitudes and rules
above are unchanged; only the cited support is corrected.
- Burnett et al. 2019: supported. T1 "can vary by more than a factor 2" for both qubits, over about 60 hours of
  repeated measurement (standard deviation about 20% of the mean).
- Klimov et al. 2018: supported. T1 "can fluctuate by an order of magnitude on 15 minute timescales". These are
  Google (Xmon) qubits, not IBM qubits.
- Carroll et al. 2022: shows on IBM transmons that T1 dips when a defect (two-level system) drifts into resonance,
  tracked over 272 hours, but gives no size such as 10x. It supports that the mechanism occurs on IBM devices, not the
  magnitude.
- arXiv 2505.06165 (Das and Ghosh): the "up to 300%" figure is not in the paper. It shows qualitatively that single
  qubits on ibm_kyiv (for example its qubit 8) have large day-to-day X-gate error swings over 12 days, and that some
  CNOT links spike on certain days, with most CNOT errors between 1e-2 and 1e-1. The E2 cz x3 and E4 x1.5 multipliers
  therefore rest on this qualitative evidence and on the FakeFez spread (90th-percentile cz error 3.7x the median),
  and should be read as assumptions.

### Amendment 3 (2026-10-25, Stage 4, before any hardware job)

**Question.** Do the error bars restored by R1W hold on a real IBM device, when the model was trained only on
simulated data?

**Setup.**
- Device: an IBM Heron device available on the Open Plan (`ibm_fez` by default; the device used is recorded in each
  session's `manifest.json`). The 4-qubit line is chosen on session 1's day as the connected line with the lowest
  summed cz error plus readout error (`device.choose_chain`), and kept for session 2.
- Monday: simulated with the Stage 3 device model (per-qubit gate, relaxation, idle and readout noise) from the
  device's calibration recorded at session 1's `prepare`. 300 training and 100 calibration random circuits, 200
  twins with k = 8. The learned model, its conformal quantile and the Monday twin scores come only from this
  simulation.
- Tuesdays: two hardware sessions, S1 and S2, at least 3 days apart, on the same qubits and the same circuits: 60
  test, 60 oracle and 60 twin circuits (k = 8), fold scales 1, 3, 5, 1000 shots, SamplerV2 with dynamical decoupling
  and twirling off, optimization level 0. Seed 4004. The shift the method must repair is the simulator-to-hardware
  gap (both sessions) plus day-to-day drift (S2).
- Methods: R0 frozen, ZNE (linear, scales 1, 3, 5) with shot bootstrap, R1, R2, R1W, and R3 oracle, at K = 25 and
  K = 60. R4 is not run: retraining needs N + 100 labeled hardware circuits and the sessions have 60.
- Uncertainty: estimates average 200 random draws of the calibration circuits on the full test set; 95% intervals
  come from 1000 circuit-level bootstrap resamples (test circuits resampled with replacement, and the twin and
  oracle sets resampled or subsampled).

**Hypotheses and rules.**
- H2-hw: frozen intervals cover less than 0.87 on hardware in at least one session.
- H3-hw (primary), judged per session: R1W at K = 60 reaches coverage within 3 points of 0.90, with mean width under
  2x the oracle's at K = 60. Also reported for each session: whether the 95% interval of R1W's coverage contains
  0.90, and the same numbers at K = 25. With 60 test circuits (420 rows) the 95% interval is about ±5 points wide, so
  a pass is evidence, not proof, and a fail by less than that margin is reported as inconclusive rather than as a
  clear failure.
- R1W is exactly as frozen in Amendment 1 (shift features, degree-2 logistic regression, weights clipped to
  [0.05, 20]); only k = 8 twins are run, the setting that held in every Stage 3 scenario.
- Reported, not judged: the fold-scaling diagnostic (measured attenuation at each fold scale against the
  simulator's prediction for the same calibration, and the linearity ratio ln(a5/a1) / ln(a3/a1), which is 2.0 when
  each fold adds the same noise), the drift alarm, and the QPU time IBM charges against our estimate.

**Data rules.** No circuit or session is excluded. A failed or cancelled job is re-run once with the same circuits
and noted in the log. The qubits stay fixed for S2 even if their calibration got worse; that change is part of what
is tested. If only S1 completes before the poster deadline, S1 alone is reported and labelled as one session.

**Disclosure.** Before this amendment the full pipeline was rehearsed on FakeFez in local mode (results in the
git-ignored `results/hardware/dryrun/`) to check that every step runs. Its numbers are simulated, not hardware
data. One descriptive number was corrected from it: the expected width of R1W's 95% coverage interval, first
written as ±4 points, is ±5 in the rehearsal (0.833 to 0.931). No rule, method or threshold changed.
