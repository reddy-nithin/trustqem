# Verdict, device track (Amendment 2, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.894 (holds: True); ZNE bootstrap 0.855 (under 0.85: False)
- **H2** scenarios losing >= 10 points: 2 of 5
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - E0_no_drift: frozen 0.890; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.899, width 0.102 vs oracle 0.083); R1/R2: R1_clifford_direct k=8 K=25 (coverage 0.898, width 0.084 vs oracle 0.083)
  - E1_coherence_drop: frozen 0.859; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.905, width 0.133 vs oracle 0.094); R1/R2: R2_clifford_ratio k=8 K=25 (coverage 0.898, width 0.092 vs oracle 0.094)
  - E2_bad_qubit: frozen 0.721; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.916, width 0.180 vs oracle 0.137); R1/R2: R2_clifford_ratio k=4 K=25 (coverage 0.886, width 0.134 vs oracle 0.137)
  - E3_readout: frozen 0.849; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.916, width 0.119 vs oracle 0.102); R1/R2: R2_clifford_ratio k=4 K=25 (coverage 0.899, width 0.096 vs oracle 0.102)
  - E4_gate_errors: frozen 0.832; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.913, width 0.110 vs oracle 0.102); R1/R2: R2_clifford_ratio k=8 K=25 (coverage 0.897, width 0.102 vs oracle 0.102)
  - E5_combined: frozen 0.760; R1W (k >= 2): R1W_clifford_weighted k=8 K=25 (coverage 0.886, width 0.128 vs oracle 0.117); R1/R2: R2_clifford_ratio k=8 K=25 (coverage 0.879, width 0.119 vs oracle 0.117)
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - E0_no_drift: false-alarm rate 0.00 to 0.20
  - E1_coherence_drop: power 0.40 to 1.00
  - E2_bad_qubit: power 1.00 to 1.00
  - E3_readout: power 0.60 to 1.00
  - E4_gate_errors: power 0.60 to 1.00
  - E5_combined: power 1.00 to 1.00

## Fixed cells at K = 100 (coverage / mean width)

| scenario | MAE | frozen | ZNE+bootstrap | R1 k=4 | R2 k=4 | R1W k=4 | R1W k=8 | oracle |
|---|---|---|---|---|---|---|---|---|
| E0_no_drift | 0.0201 | 0.890 / 0.082 | 0.864 / 0.111 | 0.882 / 0.080 | 0.896 / 0.084 | 0.912 / 0.089 | 0.906 / 0.086 | 0.897 / 0.084 |
| E1_coherence_drop | 0.0222 | 0.859 / 0.082 | 0.845 / 0.112 | 0.867 / 0.084 | 0.885 / 0.089 | 0.874 / 0.087 | 0.915 / 0.098 | 0.897 / 0.092 |
| E2_bad_qubit | 0.0315 | 0.721 / 0.082 | 0.841 / 0.112 | 0.851 / 0.118 | 0.865 / 0.124 | 0.915 / 0.149 | 0.897 / 0.137 | 0.905 / 0.141 |
| E3_readout | 0.0226 | 0.849 / 0.082 | 0.819 / 0.112 | 0.881 / 0.091 | 0.901 / 0.095 | 0.906 / 0.097 | 0.897 / 0.094 | 0.913 / 0.099 |
| E4_gate_errors | 0.0231 | 0.832 / 0.082 | 0.852 / 0.111 | 0.865 / 0.090 | 0.879 / 0.094 | 0.902 / 0.103 | 0.909 / 0.104 | 0.891 / 0.098 |
| E5_combined | 0.0281 | 0.760 / 0.082 | 0.817 / 0.112 | 0.852 / 0.107 | 0.865 / 0.112 | 0.879 / 0.117 | 0.893 / 0.123 | 0.874 / 0.115 |

## Hardware budget (IBM Open Plan: 240 s per day, 600 s per month)

- stage4_day_test_plus_twins: 80 circuits x 3 fold scales x 1000 shots = 240000 shots, about 63.2 s of QPU time
- monday_training_on_hardware: 400 circuits x 3 fold scales x 1000 shots = 1200000 shots, about 308.1 s of QPU time
