# Verdict (pre-registered rules and Amendment 1, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.894 (holds: True); ZNE bootstrap 0.833 (under 0.85: True)
- **H2** scenarios losing >= 10 points: 6 of 6
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - D0_no_drift: frozen 0.887; R1W (k >= 2): R1W_clifford_weighted k=4 K=25 (coverage 0.895, width 0.204 vs oracle 0.149); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.895, width 0.168 vs oracle 0.158)
  - D1_depolarizing_x1.5: frozen 0.776; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.898, width 0.267 vs oracle 0.221); R1/R2: NOT restored
  - D2_depolarizing_x2: frozen 0.663; R1W (k >= 2): R1W_clifford_weighted k=8 K=10 (coverage 0.914, width 0.515 vs oracle 0.309); R1/R2: NOT restored
  - D3_bad_qubit: frozen 0.574; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.912, width 0.760 vs oracle 0.431); R1/R2: R2_clifford_ratio k=8 K=25 (coverage 0.879, width 0.408 vs oracle 0.428)
  - D4_thermal_relaxation: frozen 0.674; R1W (k >= 2): R1W_clifford_weighted k=8 K=10 (coverage 0.905, width 0.482 vs oracle 0.265); R1/R2: R2_clifford_ratio k=8 K=25 (coverage 0.873, width 0.267 vs oracle 0.280)
  - D5_readout: frozen 0.788; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.910, width 0.222 vs oracle 0.193); R1/R2: R1_clifford_direct k=0 K=10 (coverage 0.894, width 0.210 vs oracle 0.196)
  - D6_combined: frozen 0.446; R1W (k >= 2): R1W_clifford_weighted k=8 K=10 (coverage 0.909, width 0.696 vs oracle 0.541); R1/R2: R2_clifford_ratio k=8 K=25 (coverage 0.875, width 0.524 vs oracle 0.533)
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - D0_no_drift: false-alarm rate 0.00 to 0.05
  - D1_depolarizing_x1.5: power 0.15 to 0.85
  - D2_depolarizing_x2: power 0.75 to 1.00
  - D3_bad_qubit: power 0.80 to 1.00
  - D4_thermal_relaxation: power 1.00 to 1.00
  - D5_readout: power 0.90 to 0.95
  - D6_combined: power 1.00 to 1.00
