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
