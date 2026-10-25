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
