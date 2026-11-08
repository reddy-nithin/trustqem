# Verdict (pre-registered rules and Amendment 1, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.896 (holds: True); ZNE bootstrap 0.852 (under 0.85: False)
- **H2** scenarios losing >= 10 points: 4 of 6
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - D0_no_drift: frozen 0.892; R1W (k >= 2): R1W_clifford_weighted k=2 K=25 (coverage 0.878, width 0.131 vs oracle 0.134); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.897, width 0.139 vs oracle 0.128)
  - D1_depolarizing_x1.5: frozen 0.805; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.872, width 0.254 vs oracle 0.191); R1/R2: NOT restored
  - D2_depolarizing_x2: frozen 0.725; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D3_bad_qubit: frozen 0.789; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D4_thermal_relaxation: frozen 0.699; R1W (k >= 2): R1W_clifford_weighted k=2 K=10 (coverage 0.889, width 0.367 vs oracle 0.236); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.899, width 0.247 vs oracle 0.236)
  - D5_readout: frozen 0.819; R1W (k >= 2): R1W_clifford_weighted k=4 K=25 (coverage 0.915, width 0.197 vs oracle 0.177); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.912, width 0.198 vs oracle 0.180)
  - D6_combined: frozen 0.590; R1W (k >= 2): NOT restored; R1/R2: NOT restored
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - D0_no_drift: false-alarm rate 0.00 to 0.00
  - D1_depolarizing_x1.5: power 0.45 to 0.50
  - D2_depolarizing_x2: power 0.95 to 1.00
  - D3_bad_qubit: power 0.45 to 0.70
  - D4_thermal_relaxation: power 1.00 to 1.00
  - D5_readout: power 1.00 to 1.00
  - D6_combined: power 1.00 to 1.00
