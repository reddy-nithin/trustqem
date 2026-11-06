# Verdict (pre-registered rules and Amendment 1, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.888 (holds: True); ZNE bootstrap 0.815 (under 0.85: True)
- **H2** scenarios losing >= 10 points: 6 of 6
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - D0_no_drift: frozen 0.882; R1W (k >= 2): R1W_clifford_weighted k=4 K=25 (coverage 0.903, width 0.173 vs oracle 0.148); R1/R2: R2_clifford_ratio k=8 K=10 (coverage 0.900, width 0.164 vs oracle 0.142)
  - D1_depolarizing_x1.5: frozen 0.759; R1W (k >= 2): R1W_clifford_weighted k=8 K=10 (coverage 0.913, width 0.442 vs oracle 0.227); R1/R2: R2_clifford_ratio k=8 K=25 (coverage 0.873, width 0.201 vs oracle 0.207)
  - D2_depolarizing_x2: frozen 0.643; R1W (k >= 2): R1W_clifford_weighted k=8 K=10 (coverage 0.901, width 0.558 vs oracle 0.307); R1/R2: R2_clifford_ratio k=8 K=10 (coverage 0.880, width 0.321 vs oracle 0.307)
  - D3_bad_qubit: frozen 0.532; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.892, width 0.687 vs oracle 0.456); R1/R2: NOT restored
  - D4_thermal_relaxation: frozen 0.671; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.909, width 0.319 vs oracle 0.287); R1/R2: R2_clifford_ratio k=8 K=10 (coverage 0.893, width 0.314 vs oracle 0.286)
  - D5_readout: frozen 0.793; R1W (k >= 2): R1W_clifford_weighted k=2 K=25 (coverage 0.929, width 0.312 vs oracle 0.192); R1/R2: R1_clifford_direct k=4 K=10 (coverage 0.897, width 0.200 vs oracle 0.189)
  - D6_combined: frozen 0.413; R1W (k >= 2): R1W_clifford_weighted k=2 K=10 (coverage 0.904, width 0.958 vs oracle 0.537); R1/R2: R1_clifford_direct k=8 K=10 (coverage 0.895, width 0.551 vs oracle 0.537)
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - D0_no_drift: false-alarm rate 0.00 to 0.10
  - D1_depolarizing_x1.5: power 0.50 to 0.95
  - D2_depolarizing_x2: power 0.85 to 1.00
  - D3_bad_qubit: power 0.85 to 1.00
  - D4_thermal_relaxation: power 1.00 to 1.00
  - D5_readout: power 1.00 to 1.00
  - D6_combined: power 1.00 to 1.00
