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
