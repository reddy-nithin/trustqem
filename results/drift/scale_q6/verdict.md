# Verdict (pre-registered rules and Amendment 1, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.893 (holds: True); ZNE bootstrap 0.826 (under 0.85: True)
- **H2** scenarios losing >= 10 points: 4 of 6
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - D0_no_drift: frozen 0.895; R1W (k >= 2): R1W_clifford_weighted k=4 K=25 (coverage 0.904, width 0.155 vs oracle 0.141); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.887, width 0.153 vs oracle 0.139)
  - D1_depolarizing_x1.5: frozen 0.811; R1W (k >= 2): R1W_clifford_weighted k=2 K=25 (coverage 0.887, width 0.245 vs oracle 0.194); R1/R2: NOT restored
  - D2_depolarizing_x2: frozen 0.712; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.872, width 0.507 vs oracle 0.263); R1/R2: NOT restored
  - D3_bad_qubit: frozen 0.674; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D4_thermal_relaxation: frozen 0.712; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.883, width 0.478 vs oracle 0.245); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.877, width 0.241 vs oracle 0.245)
  - D5_readout: frozen 0.817; R1W (k >= 2): R1W_clifford_weighted k=2 K=25 (coverage 0.918, width 0.212 vs oracle 0.192); R1/R2: R1_clifford_direct k=4 K=10 (coverage 0.896, width 0.193 vs oracle 0.182)
  - D6_combined: frozen 0.520; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.891, width 0.604 vs oracle 0.420); R1/R2: NOT restored
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - D0_no_drift: false-alarm rate 0.00 to 0.00
  - D1_depolarizing_x1.5: power 0.05 to 0.35
  - D2_depolarizing_x2: power 0.60 to 0.95
  - D3_bad_qubit: power 0.75 to 0.95
  - D4_thermal_relaxation: power 1.00 to 1.00
  - D5_readout: power 0.95 to 0.95
  - D6_combined: power 1.00 to 1.00
