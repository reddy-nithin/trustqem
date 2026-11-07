# Research log

Dated lab notebook: what was done, what was found, what went wrong. Newest entries at the bottom.

## 2026-10-24 · Baseline reproduced

Repo and uv environment set up with the package versions Luke Miller's starter notebook was tested on
(qiskit 2.6.1, qiskit-aer 0.18.0, scikit-learn 1.9.1). His notebook #4 code was split into `src/trustqem/` modules.
`notebooks/00_reproduce_baseline.ipynb` reproduces his held-out results exactly (same seed, same order of random
draws), 4 qubits, depolarizing noise, 1000 shots per scale, 100 unseen test circuits:

| method | test MAE |
|---|---|
| unmitigated | 0.0526 |
| unmitigated, 3x shots | 0.0502 |
| ZNE linear | 0.0426 |
| ZNE quadratic | 0.0991 |
| **learned (gradient boosting)** | **0.0339** |
| ZNE linear, exact values (reference) | 0.0157 |
| ZNE quadratic, exact values (reference) | 0.0033 |

Pain point: enabling INFO logging globally also turned on qiskit's transpiler logs (a 2.4 MB notebook). Fixed by
enabling INFO for the `trustqem` logger only.

## 2026-10-25 · Pilot (profile `pilot`, 5 repeats, 4 qubits, α = 0.1)

Run: `uv run trustqem run drift --profile pilot` (3.5 min on an M2). Results: `results/drift/pilot/`.

**H1 holds.** Monday conformal coverage 0.888 ± 0.010 (target 0.90). ZNE + bootstrap covers 0.822 ± 0.015.

**H2 holds, strongly.** Frozen Monday intervals under drift: depolarizing ×2 → 0.668, thermal relaxation → 0.684,
combined → 0.463. ZNE + bootstrap collapses just as badly (0.673, 0.693, 0.486), so today's standard practice has the
same problem. The learned model's MAE roughly doubles (0.034 → 0.066, 0.119 in the combined scenario).

**H3 is mixed: Clifford recalibration closes most of the gap but systematically falls short.** At K = 100:

| scenario | frozen | best Clifford (method, k) | oracle |
|---|---|---|---|
| depolarizing ×2 | 0.668 | 0.811 (ratio, k=0 or 4) | 0.903 |
| thermal relaxation | 0.684 | 0.853 (ratio, k=0) | 0.887 |
| combined | 0.463 | 0.869 (ratio, k=4) | 0.894 |

The pre-registered rule technically passes on the combined scenario (ratio, k=4, K=50: 0.876, width 0.505 vs
oracle 0.532), but not on depolarizing ×2 or thermal relaxation. Read honestly, the result is **partial**: about 60%
to 90% of the lost coverage comes back, and the intervals stay too narrow.

**H4 looks promising.** The KS alarm fired 0 of 5 times without drift. At K = 100 it fired 80 to 100% of the time on
every drift scenario; at K = 25 it was weak on depolarizing ×2 (0 to 20%). Only 5 repeats, so this is not a rate
estimate yet.

**Diagnosis (exploratory, not pre-registered).** 81% of Clifford twin rows (k = 0) have ideal value exactly 0, against
15% of random-circuit rows. Noise barely moves a value that is already 0, so those rows carry almost no drift
signal and pull the quantile down. Calibrating on nonzero-ideal Clifford rows only overshoots (0.95 to 0.99
coverage). The Clifford set is a covariate-shifted calibration set. Proposed fix for Stage 2: weighted conformal
prediction under covariate shift (Tibshirani et al., 2019), reweighting Clifford rows so their distribution of
observed features (noisy values, depth) matches the target circuits'. Those features are available on hardware.

## 2026-10-25 · Weighted recalibration (Amendment 1) and the confirmation run (profile `full`)

R1W was developed on the pilot pools and frozen in Amendment 1 (commit `90bb355`) before this run. Fresh pools,
seed 2026: 500 Monday circuits, 400 Tuesday circuits per scenario, all seven scenarios, twins with k = 0, 2, 4, 8,
20 repeats. About 15 minutes on an M2. Results: `results/drift/full/`.

**H1 holds.** Monday conformal 0.894 ± 0.013 (MAE 0.033). ZNE + bootstrap 0.833.

**H2 holds in 6 of 6 drift scenarios.** Frozen coverage: depolarizing ×1.5 0.776, ×2 0.663, bad qubit 0.574,
thermal 0.674, readout 0.788, combined 0.446. ZNE + bootstrap also fails everywhere (0.51 to 0.76).

**H3 holds for R1W in all 7 scenarios.** At K = 100 with k = 4 or 8, coverage is 0.881 to 0.915 and width is 1.0 to
1.1× oracle:

| scenario | frozen | R1 k=4 | R2 k=4 | **R1W k=4** | **R1W k=8** | oracle |
|---|---|---|---|---|---|---|
| no drift | 0.887 | 0.866 | 0.904 | 0.904 / 0.15 | 0.898 / 0.15 | 0.897 / 0.15 |
| depol. ×1.5 | 0.776 | 0.825 | 0.851 | 0.890 / 0.22 | 0.902 / 0.23 | 0.894 / 0.22 |
| depol. ×2 | 0.663 | 0.829 | 0.859 | 0.893 / 0.31 | 0.895 / 0.31 | 0.889 / 0.30 |
| bad qubit | 0.574 | 0.833 | 0.860 | 0.905 / 0.44 | 0.915 / 0.46 | 0.902 / 0.43 |
| thermal | 0.674 | 0.839 | 0.865 | 0.881 / 0.27 | 0.888 / 0.28 | 0.884 / 0.27 |
| readout | 0.788 | 0.892 | 0.922 | 0.913 / 0.21 | 0.912 / 0.21 | 0.894 / 0.19 |
| combined | 0.446 | 0.830 | 0.866 | 0.903 / 0.56 | 0.909 / 0.57 | 0.893 / 0.54 |

(R1W and oracle cells: coverage / mean width. 95% CIs on coverage are ±0.007 to ±0.015.)

- Unweighted R1 and R2 confirm the pilot: they recover most of the loss but sit 3 to 7 points low.
- **k matters.** With pure Clifford twins (k = 0), R1W over-covers (0.90 to 0.98) with widths up to 2.35× oracle,
  because no pure Clifford row resembles a mid-valued random row. k = 2 is in between and noisier. k = 4 to 8 works.
  These twins stay classically simulable: stabilizer-rank simulation cost grows exponentially in k but only
  polynomially in qubit count.
- **Budget.** With k = 8, K = 25 already restores coverage in every scenario (0.894 to 0.915), at widths up to 1.3×
  oracle. Widths reach the oracle's by K = 50 to 100. At K = 10 coverage is fine but widths are 1.3 to 2.3× oracle.

**R4 (retrain) comparison.** Retraining on N = 50 to 200 labeled drifted circuits, plus 100 more for calibration,
also gives 0.88 to 0.90 coverage, with widths 10 to 25% narrower than R1W, because the retrained model is more
accurate (combined scenario MAE 0.117 → 0.088). The honest trade-off is that R4 needs 150 to 300 circuits with known
ideal values. For non-Clifford circuits at scale, no classical computer can supply those. R1W needs 25 to 100
near-Clifford circuits, which it can.

**H4 is partial.** False-alarm rate on no drift ≤ 0.05 at every K and k except k = 8 at K = 25 (0.10). At K = 100,
power ≥ 0.80 for at least one k in all six drift scenarios, and for every k in four of them. The mildest drifts are
the hardest to detect: depolarizing ×1.5 reaches 0.85 only with k = 8 (0.15 to 0.50 otherwise) and needs K = 200 for
0.9 to 1.0 at k ≥ 2. Pure Clifford twins detect worst.

**Caveats.**
- All 20 repeats share one simulated pool per scenario, so the CIs reflect resampling variation and understate
  pool-to-pool variation.
- The oracle itself averages 0.884 on thermal relaxation, slightly under 0.90. Row-level calibration on correlated
  rows is the likely cause; per-circuit (max-score) calibration would test that.
- Simulation only, 4 qubits. Stage 3 adds device-realistic noise and gate folding.

## 2026-10-25 · Stage 3: device-realistic noise and gate folding (Amendment 2)

**What changed.** Monday is now the FakeFez calibration (IBM Heron r2 snapshot dated 2025-02-26, from
qiskit-ibm-runtime 0.51.0) on the best 4-qubit line, physical qubits 136, 143, 142, 141. Each qubit has its own T1,
T2, gate errors and asymmetric readout errors, and idle qubits decay while they wait. Circuits and twins are
transpiled to the native gates (cz, rz, sx, x) and noise is amplified by folding every gate (G to G G† G) to scales
1, 3, 5, instead of scaling error rates. Tuesday scenarios perturb Monday's calibration: E1 T1/T2 x0.5, E2 one bad
qubit (T1 x0.2, its cz errors x3), E3 readout x2, E4 gate errors x1.5, E5 a milder mix, E0 no drift. Magnitudes,
sources and pass rules were frozen in Amendment 2 (commit `33c061c`) before the pilot ran. R1W was not changed.

Checks before running: every gate error channel of our 4-qubit model equals the one Aer's `NoiseModel.from_backend`
builds for the same physical qubits (a slow test); folding multiplies the sx, x and cz counts by exactly the scale
and leaves the unitary unchanged; pure Clifford twins stay Clifford after transpiling, and a twin with k kept
rotations has at most k non-Clifford rz gates; the drift smoke run gives byte-identical results before and after
the shared-code changes; notebook 00 still reproduces Luke's seven numbers.

**Runs.** Pilot: seed 3003, 5 repeats, 65 minutes. Full: seed 3030, 500 Monday circuits, 400 Tuesday circuits per
scenario, twins with k = 0, 2, 4, 8, K in {10, 25, 50, 100, 200}, 20 repeats, 86 minutes (4-core container).
Results: `results/device/pilot/` and `results/device/full/`. The full run is the Stage 3 verdict.

**H1 holds.** Monday conformal coverage 0.889 ± 0.010 (MAE 0.020). ZNE + bootstrap covers 0.855 ± 0.005, so the
second half of the original H1 (under 0.85) narrowly fails on this noise: with Heron-level noise, linear ZNE is less
biased than on the toy model.

**H2 holds, but only just: 2 of 5 drift scenarios lose 10 or more points.** Frozen coverage: E2 bad qubit 0.714 and
E5 combined 0.775 (18.6 and 12.5 points under 0.90). The other three lose 3.4 to 5.3 points against 0.90 (E1 0.866,
E3 0.864, E4 0.847), or 2.0 to 3.9 points against the no-drift control's 0.886.
Realistic day-to-day drift on a good chain of a Heron device is milder than the toy scenarios of Stage 2, except
when one qubit goes bad.

**H3 holds for R1W in all 6 scenarios.** By the pre-registered rule, R1W restores every scenario already at K = 25
(coverage 0.880 to 0.903, width 1.09 to 1.39x oracle). At the fixed cell K = 100:

| scenario | frozen | ZNE+boot | R1 k=4 | R2 k=4 | **R1W k=4** | **R1W k=8** | oracle | R4 N=100 |
|---|---|---|---|---|---|---|---|---|
| E0 no drift | 0.886 | 0.860 | 0.863 | 0.885 | 0.884 / 0.082 | 0.901 / 0.087 | 0.892 / 0.084 | 0.896 / 0.083 |
| E1 coherence x0.5 | 0.866 | 0.852 | 0.874 | 0.896 | 0.907 / 0.093 | 0.914 / 0.095 | 0.895 / 0.089 | 0.894 / 0.087 |
| E2 bad qubit | 0.714 | 0.838 | 0.813 | 0.836 | 0.907 / 0.141 | 0.899 / 0.137 | 0.896 / 0.135 | 0.901 / 0.117 |
| E3 readout x2 | 0.864 | 0.811 | 0.892 | 0.913 | 0.917 / 0.098 | 0.904 / 0.093 | 0.902 / 0.092 | 0.894 / 0.088 |
| E4 gate errors x1.5 | 0.847 | 0.868 | 0.863 | 0.883 | 0.902 / 0.098 | 0.903 / 0.098 | 0.895 / 0.096 | 0.893 / 0.090 |
| E5 combined | 0.775 | 0.834 | 0.845 | 0.872 | 0.909 / 0.120 | 0.909 / 0.121 | 0.899 / 0.116 | 0.896 / 0.104 |

(Coverage, or coverage / mean width. 95% CIs on coverage are ±0.005 to ±0.017. Frozen width is 0.082 in
every scenario.)

- R1W with k = 4 or 8 at K = 100: coverage 0.884 to 0.917, width 0.98 to 1.07x oracle, in every scenario.
- **Unweighted recalibration is enough for mild drift but not for a bad qubit.** R2 (k = 4, K = 100) is within 3
  points in E0, E1, E3, E4 and E5 (0.872), but covers only 0.836 in E2. R1 sits 1 to 9 points low. The verdict line
  for R1/R2 passes everywhere only because the rule may pick the best k and K; at fixed cells R1W is the method that
  holds across scenarios.
- **Pure Clifford twins (k = 0) fail in both directions.** At K ≤ 50 the weighted quantile is often infinite (no twin
  looks like the target), so intervals span the whole [-1, 1] range: coverage 0.96 to 0.99 at widths 9 to 18x
  oracle. At K = 200 in E2 the same method under-covers (0.847). Near-Clifford twins are needed, as in Stage 2.
- **Budget.** At K = 10, R1W with k ≥ 2 covers 0.895 to 0.941 but at widths 3 to 11x oracle (fails the width rule).
  K = 25 is the smallest passing K; with k = 4 or 8, widths are 0.93 to 1.09x oracle by K = 50.
- **R4 (retrain)** covers 0.890 to 0.902 everywhere. Its intervals are 5 to 15% narrower than R1W k = 8 at
  N = 100 (20% in E2 at N = 200), using 150 to 300 labeled drifted circuits against R1W's 25 to 100 twins.
- **ZNE + bootstrap** is steadier under drift than the frozen conformal intervals (0.811 to 0.868), because its
  bootstrap width (0.111) is set by shot noise, but it never reaches 0.90 and its MAE is 0.028 to 0.032 against the
  learned model's 0.020 to 0.032.

**Pilot agrees on coverage.** Pilot frozen: E2 0.721, E5 0.760, others 0.832 to 0.890 (H2: 2 of 5). R1W at K = 100:
k = 4 0.874 to 0.915, k = 8 0.893 to 0.915. The pilot's k = 4 cells in E1 (0.874) and E5 (0.879) are 2.6 and 2.1 points
low; the full run's are not.

**H4 (secondary) is weak on realistic drift.** At K = 100 the false-alarm rate is 0.00 at every k. Power: E2 0.55 to
1.00, E5 0.50 to 0.95, E3 0.15 to 0.60, E4 0.00 to 0.30, E1 0.00 to 0.20. The pilot showed much higher power on the
same scenarios (E1 0.40 to 1.00, E3 0.60 to 1.00), which says the alarm rate depends heavily on the particular
simulated pools: repeats reuse one pool, and the Monday and Tuesday twins come from different circuits.

**Hardware budget (for Stage 4).** IBM's documented estimate is about 2 s per sub-job plus (rep_delay + circuit
time) per shot. FakeFez's default rep_delay is 250 µs, while the folded circuits last 1.2 µs (scale 1) to 5.9 µs
(scale 5) on average, so the shot count, not the folding, sets the cost.

| run | circuits | executions (x3 scales) | shots | estimated QPU time |
|---|---|---|---|---|
| one Tuesday: 40 test + 40 twins (one k) | 80 | 240 | 240,000 | 63 s |
| Monday training set on hardware (300 train + 100 calibration) | 400 | 1,200 | 1,200,000 | 308 s |

One Tuesday fits easily in the Open Plan's 600 s per rolling 28-day window. A hardware-trained Monday would take half
of that allowance. (Corrected 2026-10-26: this entry first described the plan as 240 s per day and 600 s per month.
IBM's plans overview gives 10 minutes per 28-day rolling window and no daily limit. The budget lines in
results/device/*/verdict.md and budget.json were written with the old wording and were not regenerated.) Training on a simulator with the device's calibration, or halving shots, are the
obvious options to weigh.

**Caveats.**
- One fake snapshot, one (best) chain, 4 qubits. The noise is Markovian per gate: no crosstalk, leakage, coherent
  over-rotations or drift within a run. Coherent errors matter for folding on hardware, because G† G can partly
  cancel them, so real folded noise may grow less than 3x and 5x.
- Readout error is not amplified by folding; both ZNE and the learned model see it as a fixed bias.
- The E3 readout multiplier is an assumption (no published day-to-day readout figure was found). The other
  magnitudes rest on Klimov et al. 2018, Burnett et al. 2019, Carroll et al. 2022 and arXiv 2505.06165. Checked
  against the full papers on 2026-10-26: Burnett (T1 varies by more than 2x over about 60 hours) and Klimov (an
  order of magnitude within 15 minutes, on Google qubits) hold; Carroll shows the mechanism on IBM qubits but no
  magnitude; the "300%" attributed to 2505.06165 is not in that paper. The gate-error multipliers in E2 and E4 are
  therefore assumptions. See the correction under Amendment 2 in HYPOTHESES.md.
- All repeats share one simulated pool per scenario, so CIs understate pool-to-pool variation (the H4 gap between
  pilot and full is an example).
- The H3 rule lets the best k and smallest K be chosen after the fact; the fixed cells (k = 4 and 8 at K = 100) are
  the fairer summary and agree.

**Pain points.** The verdict code recognised only `D0_no_drift` as the control, so the first pilot verdict counted
E0 as a drift scenario ("2 of 6"). Fixed to treat any `*_no_drift` as the control; the drift verdicts regenerate
unchanged. Adding qiskit-ibm-runtime moved python-dateutil from 3.0.0 to 2.9.0.post0 in the lockfile (the qiskit,
qiskit-aer and scikit-learn pins did not move). The full run was restarted once because a background job limit of
2 hours was too close to its 86-minute runtime.

## 2026-10-26: Stage 4 interim look at hardware session 1

Declared in HYPOTHESES.md (after Amendment 3) before it ran. Session 1: ibm_fez, qubits 144 to 147, job
dbfn4hfpc3tc739nr2hg, 540 executions at 1000 shots, 145 s charged against a 140 s estimate. Analysed on a copy under
`results/interim/hardware/`; `results/hardware/` is untouched and session 2 is unchanged.

**Data checks.** Measured values track the ideal ones: correlation 0.992 (oracle), 0.995 (test) and 0.995 (twins) at
fold scale 1, falling to 0.96 to 0.97 at scale 5, and 0.991 to 0.995 for each of the seven observables. Reversing the
bit order drops the oracle correlation to 0.083, so counts are read in the right order. Folding behaves as modelled:
attenuation 0.930, 0.864, 0.809 at scales 1, 3, 5 (simulator 0.955, 0.911, 0.869), linearity 1.89 (simulator 2.01).
The device is noisier than the simulated Monday at every scale.

**Interim result (one session, 60 test circuits, 95% circuit-bootstrap CIs).**

| method | coverage | mean width |
|---|---|---|
| R0 frozen | 0.667 (0.614 to 0.717) | 0.087 |
| ZNE + bootstrap | 0.774 (0.736 to 0.814) | 0.113 |
| R1 K = 60 | 0.914 (0.867 to 0.940) | 0.167 |
| R2 K = 60 | 0.918 (0.871 to 0.948) | 0.178 |
| R1W K = 60 | 0.902 (0.855 to 0.931) | 0.157 |
| R3 oracle K = 60 | 0.917 (0.879 to 0.945) | 0.175 |

H2-hw holds for S1 (frozen 0.667 < 0.87). H3-hw passes for S1: R1W at K = 60 covers 0.902 at 0.90x the oracle's
width; at K = 25 it covers 0.897. Test MAE 0.038 (Stage 3 simulation about 0.02). The drift alarm fires
(p = 1.1e-12). Unweighted R1 and R2 also restore coverage here, so on this session the weighting buys narrower bars
(0.157 against 0.167 and 0.178), not coverage. One session; the verdict waits for session 2.

## 2026-10-29: Stage 4 hardware session 2 and verdict

Session 2: ibm_fez, same qubits (144 to 147) and same 180 circuits as session 1, prepared with `--pair-with S1`,
job dbhlojmne4hc73bd5htg, 540 executions at 1000 shots, 145 s charged against a 140 s estimate (290 s used in total
for both sessions). Nothing was changed after the interim look.

**Calibration change from S1.** cz error fell on all three links (0.0028, 0.0020, 0.0025 to 0.0016, 0.0018, 0.0024)
and readout error fell on qubits 144 and 146. Qubit 147 got worse (T1 189 to 128 µs, T2 150 to 116 µs) and qubit
145's p10 readout error rose from 1.3% to 1.9%. Single-qubit gate errors reported by IBM were identical on both
days. Folding behaved as on S1: attenuation 0.928, 0.869, 0.817 at scales 1, 3, 5 (simulator 0.961, 0.925, 0.891),
linearity 1.93 (simulator 1.99).

**Result (S2, 60 test circuits, 420 rows, 95% circuit-bootstrap CIs).**

| method | coverage | mean width |
|---|---|---|
| R0 frozen | 0.648 (0.590 to 0.702) | 0.087 |
| ZNE + bootstrap | 0.717 (0.669 to 0.762) | 0.114 |
| R1 K = 60 | 0.900 (0.840 to 0.955) | 0.165 |
| R2 K = 60 | 0.920 (0.852 to 0.962) | 0.175 |
| R1W K = 60 | 0.905 (0.864 to 0.952) | 0.166 |
| R3 oracle K = 60 | 0.914 (0.852 to 0.950) | 0.169 |
| R1W K = 25 | 0.911 (0.829 to 0.955) | 0.176 |

S1 rescored in the final run gives the same numbers as the interim look (R1W K = 60: 0.902, width 0.157, 0.90x
oracle).

**Verdict (Amendment 3).** H2-hw holds in both sessions (frozen 0.667 and 0.648, both below 0.87). H3-hw passes in
both sessions: R1W at K = 60 covers 0.902 (S1) and 0.905 (S2), each 95% CI contains 0.90, at 0.90x and 0.98x the
oracle's width. Test MAE 0.038 and 0.039. The drift alarm fires in both (p = 1.1e-12 and 5.7e-12). As on S1,
unweighted R1 and R2 also restore coverage on S2, and on S2 the weighting no longer buys narrower bars (0.166
against R1's 0.165). So the hardware evidence supports Clifford recalibration in general; it does not single out
the weighted version. With 60 test circuits per session the CIs are about ±5 points, so this is evidence, not proof.
Outputs: `results/hardware/verdict.md`, `results/hardware/S{1,2}/summary.json`,
`results/hardware/coverage_by_session.png`.

## 2026-11-06: Amendment 4 setup, reproducibility check, self-healing results

**Moving to the lab server.** Simulations for Amendment 4 run on the UMKC lab server (Ubuntu, Xeon Silver 4210R,
4x RTX A4000) in tmux, each from a frozen git worktree of one commit. Speed at 12 qubits: 17.4 s per simulation on
one CPU core, 0.62 s on one GPU, about 2.7 per second with four jobs sharing one GPU, about 10 per second on all four
GPUs. GPU single precision was slower (1.0 s) and is not used.

**Does the parallel code change anything?** No. The first 40 Monday circuits of the `full` profile and their
measured probabilities are bit-identical between the Mac (one worker) and the server (24 workers). The full 4-qubit
`full` run on the server does not reproduce the committed Mac numbers byte for byte (e.g. ZNE bootstrap coverage
0.831 vs 0.833, D0 frozen 0.891 vs 0.887). Running the original code (commit c2fe941) on the server with the same
pools gives a summary identical to the new code, so the gap comes from the platform (floating point in model
training on Linux vs macOS), not from the changes. No verdict changes. Committed results stay the Mac originals.

**H6, self-healing loop, 4 qubits** (`results/healing/scale_q4/`, profile `scale_q4` pools, 200 ten-day sequences
per scenario, 30 canaries and 30 test circuits per day, k = 4, alarm at 20). H6a passes: no false alarm on any quiet
day in any scenario. H6b fails as written: after a correct alarm, coverage is 0.902 to 0.913 in five scenarios but
0.938 under D5 readout drift, more than 3 points above 0.90 (over-coverage). Detection: 99 to 100% within 1.0 to
3.1 days for D2 to D6; D1 (depolarizing x1.5) is caught in 63% of sequences after 3.9 days on average. On day 10
the healed intervals cover 0.85 to 0.94 against 0.42 to 0.79 for never recalibrating.

**Self-healing replayed on hardware** (`results/healing/hardware/`, 200 canary orders). S1: the alarm fires in all
200 (median martingale about 3e15) and healing lifts coverage from 0.667 to 0.902. S2, three days later: no alarm in
any order (median 0.08); S1's recalibration still covers 0.890, against 0.905 for recalibrating on S2's own twins.

**Scale of the alarm, 156 qubits** (`results/canary_scale/q156/`, reported, not judged). Pure Clifford canaries on a
simulated 156-qubit chip (stabilizer method, depolarizing 0.001 / 0.01 plus 1% readout flips; drift = gate errors
x1.5), 311 Z and ZZ observables, 1,000 shots, 5.7 s per canary on one server core. Raw canary error 0.0294 before
and 0.0316 after the drift. With 60 reference canaries and 30 per day, the alarm never fired on quiet days in 200
sequences and caught the drift in all 200, after 2.6 days on average. Caveat: days are resampled from pools of 150
canaries per condition, so sequences share circuits. This shows the alarm runs at chip size; it says nothing about
coverage at 156 qubits.

**H5 scaling, 4 to 12 qubits (pre-registered in Amendment 4): FAILS from 6 qubits on.** `scripts/scaling_table.py`
reads `results/drift/scale_q{n}/summary.json` and checks R1W (k = 2 and 4, K = 100) against 0.90 ± 0.03 and width
under 2x oracle. At 4 qubits every scenario passes except D5 readout, which over-covers (0.93). At 6, 8 and 12 qubits,
R1W still passes D0 and D5 but under-covers the gate-noise drifts, with intervals narrower than the oracle's:

| scenario | frozen, 12 q | R1W k=4, 12 q | width / oracle |
|---|---|---|---|
| D1 depolarizing x1.5 | 0.805 | 0.832 | 0.81 |
| D2 depolarizing x2 | 0.725 | 0.806 | 0.74 |
| D3 bad qubit | 0.789 | 0.816 | 0.72 |
| D4 thermal relaxation | 0.699 | 0.867 | 0.93 |
| D6 combined | 0.590 | 0.830 | 0.79 |

R1W closes about a third to two thirds of the gap, not all of it. The 10-qubit run is still going.

Signal check (reported): the share of rows with |ideal| > 0.1 is 0.71, 0.62, 0.58 and 0.52 at 4, 6, 8 and 12 qubits,
well above the 20% flag. The signal is fine.

Likely cause (diagnostic, after looking): with k fixed at 2 or 4, the twins get more Clifford as circuits grow. At 12
qubits only 14% (k = 2) and 16% (k = 4) of twin observables have |ideal| > 0.1, against 52% of the real circuits; at 4
qubits k = 4 gave 32% against 71%. A Clifford observable with ideal value 0 stays at 0 under depolarizing noise, so
most twin rows carry no information about gate-noise drift. That matches the pattern: the drifts that move zeros
(readout, thermal relaxation) are repaired; the ones that only shrink nonzero values are not.

**Amendment 5, fix 1 (R1N, exploratory): FAILS the other way.** `results/nonzero/` reruns the drift study on the
cached pools with R1N added. Every other method reproduces the Amendment 4 summaries exactly at all five sizes
(checked entry by entry). R1N over-corrects: at n = 12, k = 4, coverage is 0.96 to 0.99 in every scenario, with
widths 1.8 to 5.6x the oracle's (D0 2.1x, D2 3.8x, D6 4.4x). It fails the width rule everywhere except D0 at 4 qubits.
Reading: the nonzero twin rows have larger residuals than typical test rows, many of which have ideal values near 0,
so dropping the zeros swaps "twins too easy" for "twins too hard". The weighting cannot undo a shift this large.
Fix 1 is dropped; fix 2 (k = 16 twins, Amendment 5) is next, which changes the twins themselves.

**Amendment 5, fix 2 (k = 16 twins at 12 qubits, exploratory): FAILS.** `results/twins_k16/scale_q12/` adds k = 16
twins to the 12-qubit pools (fresh Monday twin sources, Tuesday twins paired with the same test circuits) and reruns
the analysis. At K = 100, R1W with k = 16 gains 1 to 3 points over k = 4 under gate-noise drift but still misses the
band, with widths below the oracle's:

| scenario | frozen | R1W k=4 | R1W k=16 | width / oracle, k=16 |
|---|---|---|---|---|
| D1 depolarizing x1.5 | 0.809 | 0.830 | 0.849 | 0.84 |
| D2 depolarizing x2 | 0.729 | 0.798 | 0.836 | 0.81 |
| D3 bad qubit | 0.786 | 0.830 | 0.833 | 0.78 |
| D4 thermal relaxation | 0.699 | 0.866 | 0.870 | 0.93 |
| D6 combined | 0.588 | 0.836 | 0.848 | 0.85 |

D0, D4 and D5 pass; D1, D2, D3 and D6 fail, the same set as k = 4. (The k = 2 and 4 numbers here differ from the
Amendment 4 run by up to 0.01 because this analysis draws its own repeats.) Reading: richer twins help a little, so the
mostly-zero diagnosis is part of the story but not all of it. Gate-noise drift on 144-rotation circuits is not fully
seen by circuits with 16 rotations. Coverage at 6 to 12 qubits under gate-noise drift stays an open problem.

**Device track at 12 qubits (Amendment 2 rules, FakeFez-derived noise): repair works.** `results/device/scale_q12/`.
The device-style drifts are milder at 12 qubits (frozen loses 4 to 7 points, so H2 counts 0 of 5). R1W k = 4 at K = 100
gives 0.896, 0.885, 0.930, 0.881 and 0.900 for E1 to E5 against an oracle of 0.89, with widths within 1.2x the oracle's.
E3 readout over-covers at the edge of the band, as at 4 qubits.

**H6 self-healing at 8 and 12 qubits: H6a passes, H6b fails** (`results/healing/scale_q{8,12}/`). False alarms 0 to
0.5% on quiet days. Detection: D2, D4, D5, D6 caught in 98 to 100% of sequences after 1 to 3 days; D3 in 67% (12 q) and
97% (8 q); mild D1 in about 23%. After an alarm, coverage at 12 q is 0.82 to 0.92 (never-fix 0.60 to 0.82), so healing
recovers what R1W can recover and inherits its H5 shortfall. Healing matches daily recalibration within 0.02.
