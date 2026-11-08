# Verdict (pre-registered rules and Amendment 1, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.891 (holds: True); ZNE bootstrap 0.833 (under 0.85: True)
- **H2** scenarios losing >= 10 points: 5 of 6
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - D0_no_drift: frozen 0.886; R1W (k >= 2): R1W_clifford_weighted k=2 K=25 (coverage 0.878, width 0.143 vs oracle 0.146); R1/R2: R2_clifford_ratio k=4 K=50 (coverage 0.879, width 0.136 vs oracle 0.140)
  - D1_depolarizing_x1.5: frozen 0.794; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D2_depolarizing_x2: frozen 0.708; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D3_bad_qubit: frozen 0.729; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D4_thermal_relaxation: frozen 0.702; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.880, width 0.397 vs oracle 0.247); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.888, width 0.253 vs oracle 0.247)
  - D5_readout: frozen 0.811; R1W (k >= 2): R1W_clifford_weighted k=2 K=25 (coverage 0.918, width 0.217 vs oracle 0.185); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.902, width 0.203 vs oracle 0.186)
  - D6_combined: frozen 0.551; R1W (k >= 2): NOT restored; R1/R2: NOT restored
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - D0_no_drift: false-alarm rate 0.00 to 0.05
  - D1_depolarizing_x1.5: power 0.20 to 0.35
  - D2_depolarizing_x2: power 0.85 to 0.90
  - D3_bad_qubit: power 0.80 to 0.90
  - D4_thermal_relaxation: power 1.00 to 1.00
  - D5_readout: power 1.00 to 1.00
  - D6_combined: power 1.00 to 1.00
