# Verdict (pre-registered rules and Amendment 1, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.889 (holds: True); ZNE bootstrap 0.838 (under 0.85: True)
- **H2** scenarios losing >= 10 points: 4 of 6
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - D0_no_drift: frozen 0.890; R1W (k >= 2): R1W_clifford_weighted k=2 K=25 (coverage 0.882, width 0.144 vs oracle 0.144); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.902, width 0.148 vs oracle 0.145)
  - D1_depolarizing_x1.5: frozen 0.807; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.873, width 0.340 vs oracle 0.187); R1/R2: NOT restored
  - D2_depolarizing_x2: frozen 0.717; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D3_bad_qubit: frozen 0.767; R1W (k >= 2): NOT restored; R1/R2: NOT restored
  - D4_thermal_relaxation: frozen 0.711; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.895, width 0.416 vs oracle 0.237); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.889, width 0.244 vs oracle 0.237)
  - D5_readout: frozen 0.818; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.910, width 0.361 vs oracle 0.182); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.906, width 0.196 vs oracle 0.182)
  - D6_combined: frozen 0.586; R1W (k >= 2): NOT restored; R1/R2: NOT restored
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - D0_no_drift: false-alarm rate 0.05 to 0.10
  - D1_depolarizing_x1.5: power 0.15 to 0.55
  - D2_depolarizing_x2: power 0.80 to 0.95
  - D3_bad_qubit: power 0.30 to 0.40
  - D4_thermal_relaxation: power 1.00 to 1.00
  - D5_readout: power 0.95 to 1.00
  - D6_combined: power 1.00 to 1.00
