# Verdict, device track (Amendment 2, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.889 (holds: True); ZNE bootstrap 0.855 (under 0.85: False)
- **H2** scenarios losing >= 10 points: 2 of 5
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - E0_no_drift: frozen 0.886; R1W (k >= 2): R1W_clifford_weighted k=4 K=25 (coverage 0.885, width 0.119 vs oracle 0.085); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.898, width 0.087 vs oracle 0.082)
  - E1_coherence_drop: frozen 0.866; R1W (k >= 2): R1W_clifford_weighted k=4 K=25 (coverage 0.880, width 0.103 vs oracle 0.091); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.900, width 0.095 vs oracle 0.093)
  - E2_bad_qubit: frozen 0.714; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.902, width 0.156 vs oracle 0.138); R1/R2: R1_clifford_direct k=8 K=25 (coverage 0.878, width 0.131 vs oracle 0.138)
  - E3_readout: frozen 0.864; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.897, width 0.100 vs oracle 0.092); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.909, width 0.098 vs oracle 0.094)
  - E4_gate_errors: frozen 0.847; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.903, width 0.118 vs oracle 0.099); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.875, width 0.095 vs oracle 0.100)
  - E5_combined: frozen 0.775; R1W (k >= 2): R1W_clifford_weighted k=4 K=25 (coverage 0.903, width 0.140 vs oracle 0.122); R1/R2: R1_clifford_direct k=8 K=10 (coverage 0.874, width 0.110 vs oracle 0.115)
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - E0_no_drift: false-alarm rate 0.00 to 0.00
  - E1_coherence_drop: power 0.00 to 0.20
  - E2_bad_qubit: power 0.55 to 1.00
  - E3_readout: power 0.15 to 0.60
  - E4_gate_errors: power 0.00 to 0.30
  - E5_combined: power 0.50 to 0.95

## Fixed cells at K = 100 (coverage / mean width)

| scenario | MAE | frozen | ZNE+bootstrap | R1 k=4 | R2 k=4 | R1W k=4 | R1W k=8 | oracle |
|---|---|---|---|---|---|---|---|---|
| E0_no_drift | 0.0204 | 0.886 / 0.082 | 0.860 / 0.111 | 0.863 / 0.077 | 0.885 / 0.082 | 0.884 / 0.082 | 0.901 / 0.087 | 0.892 / 0.084 |
| E1_coherence_drop | 0.0214 | 0.866 / 0.082 | 0.852 / 0.111 | 0.874 / 0.084 | 0.896 / 0.090 | 0.907 / 0.093 | 0.914 / 0.095 | 0.895 / 0.089 |
| E2_bad_qubit | 0.0317 | 0.714 / 0.082 | 0.838 / 0.112 | 0.813 / 0.106 | 0.836 / 0.113 | 0.907 / 0.141 | 0.899 / 0.137 | 0.896 / 0.135 |
| E3_readout | 0.0222 | 0.864 / 0.082 | 0.811 / 0.111 | 0.892 / 0.090 | 0.913 / 0.096 | 0.917 / 0.098 | 0.904 / 0.093 | 0.902 / 0.092 |
| E4_gate_errors | 0.0227 | 0.847 / 0.082 | 0.868 / 0.112 | 0.863 / 0.086 | 0.883 / 0.092 | 0.902 / 0.098 | 0.903 / 0.098 | 0.895 / 0.096 |
| E5_combined | 0.0271 | 0.775 / 0.082 | 0.834 / 0.111 | 0.845 / 0.099 | 0.872 / 0.106 | 0.909 / 0.120 | 0.909 / 0.121 | 0.899 / 0.116 |

## Hardware budget (IBM Open Plan: 240 s per day, 600 s per month)

- stage4_day_test_plus_twins: 80 circuits x 3 fold scales x 1000 shots = 240000 shots, about 63.2 s of QPU time
- monday_training_on_hardware: 400 circuits x 3 fold scales x 1000 shots = 1200000 shots, about 308.1 s of QPU time
