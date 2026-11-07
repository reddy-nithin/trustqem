# Verdict (pre-registered rules and Amendment 1, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.896 (holds: True); ZNE bootstrap 0.852 (under 0.85: False)
- **H2** scenarios losing >= 10 points: 4 of 6
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - D0_no_drift: frozen 0.892; R1W (k >= 2): R1W_clifford_weighted k=16 K=10 (coverage 0.887, width 0.174 vs oracle 0.128); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.897, width 0.139 vs oracle 0.128)
  - D1_depolarizing_x1.5: frozen 0.809; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D2_depolarizing_x2: frozen 0.729; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D3_bad_qubit: frozen 0.786; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D4_thermal_relaxation: frozen 0.699; R1W (k >= 2): R1W_clifford_weighted k=2 K=10 (coverage 0.913, width 0.435 vs oracle 0.225); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.896, width 0.248 vs oracle 0.225)
  - D5_readout: frozen 0.817; R1W (k >= 2): R1W_clifford_weighted k=16 K=10 (coverage 0.910, width 0.204 vs oracle 0.182); R1/R2: R2_clifford_ratio k=16 K=10 (coverage 0.905, width 0.188 vs oracle 0.182)
  - D6_combined: frozen 0.588; R1W (k >= 2): R1W_clifford_weighted k=16 K=10 (coverage 0.876, width 0.362 vs oracle 0.321); R1/R2: R2_clifford_ratio k=16 K=10 (coverage 0.879, width 0.311 vs oracle 0.321)
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - D0_no_drift: false-alarm rate 0.00 to 0.10
  - D1_depolarizing_x1.5: power 0.15 to 0.85
  - D2_depolarizing_x2: power 0.95 to 1.00
  - D3_bad_qubit: power 0.40 to 1.00
  - D4_thermal_relaxation: power 1.00 to 1.00
  - D5_readout: power 1.00 to 1.00
  - D6_combined: power 1.00 to 1.00
