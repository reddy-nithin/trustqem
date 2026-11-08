# Verdict, device track (Amendment 2, docs/HYPOTHESES.md)

- **H1** Monday conformal coverage 0.893 (holds: True); ZNE bootstrap 0.855 (under 0.85: False)
- **H2** scenarios losing >= 10 points: 0 of 5
- **H3** per scenario (frozen coverage; smallest K <= 100 that restores it):
  - E0_no_drift: frozen 0.895; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.892, width 0.123 vs oracle 0.079); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.900, width 0.085 vs oracle 0.079)
  - E1_coherence_drop: frozen 0.854; R1W (k >= 2): R1W_clifford_weighted k=4 K=25 (coverage 0.906, width 0.099 vs oracle 0.091); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.886, width 0.092 vs oracle 0.091)
  - E2_bad_qubit: frozen 0.854; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.889, width 0.150 vs oracle 0.094); R1/R2: R2_clifford_ratio k=4 K=10 (coverage 0.883, width 0.093 vs oracle 0.094)
  - E3_readout: frozen 0.858; R1W (k >= 2): R1W_clifford_weighted k=2 K=25 (coverage 0.920, width 0.103 vs oracle 0.092); R1/R2: R2_clifford_ratio k=2 K=10 (coverage 0.899, width 0.097 vs oracle 0.093)
  - E4_gate_errors: frozen 0.854; R1W (k >= 2): R1W_clifford_weighted k=2 K=25 (coverage 0.904, width 0.099 vs oracle 0.092); R1/R2: R2_clifford_ratio k=4 K=50 (coverage 0.877, width 0.088 vs oracle 0.091)
  - E5_combined: frozen 0.825; R1W (k >= 2): R1W_clifford_weighted k=4 K=10 (coverage 0.876, width 0.153 vs oracle 0.100); R1/R2: R2_clifford_ratio k=4 K=25 (coverage 0.886, width 0.100 vs oracle 0.101)
- **H4** drift alarm at K = 100 (detection rate over repeats, best and worst k):
  - E0_no_drift: false-alarm rate 0.00 to 0.00
  - E1_coherence_drop: power 0.45 to 0.70
  - E2_bad_qubit: power 0.35 to 0.55
  - E3_readout: power 0.90 to 0.95
  - E4_gate_errors: power 0.05 to 0.55
  - E5_combined: power 0.85 to 1.00

## Fixed cells at K = 100 (coverage / mean width)

| scenario | MAE | frozen | ZNE+bootstrap | R1 k=4 | R2 k=4 | R1W k=4 | R1W k=8 | oracle |
|---|---|---|---|---|---|---|---|---|
| E0_no_drift | 0.0195 | 0.895 / 0.082 | 0.852 / 0.115 | 0.828 / 0.068 | 0.896 / 0.082 | 0.895 / 0.082 | n/a | 0.889 / 0.081 |
| E1_coherence_drop | 0.0220 | 0.854 / 0.082 | 0.851 / 0.115 | 0.826 / 0.076 | 0.895 / 0.093 | 0.896 / 0.094 | n/a | 0.893 / 0.093 |
| E2_bad_qubit | 0.0220 | 0.854 / 0.082 | 0.856 / 0.115 | 0.817 / 0.074 | 0.882 / 0.090 | 0.885 / 0.091 | n/a | 0.893 / 0.093 |
| E3_readout | 0.0219 | 0.858 / 0.082 | 0.811 / 0.115 | 0.843 / 0.079 | 0.906 / 0.097 | 0.930 / 0.107 | n/a | 0.894 / 0.092 |
| E4_gate_errors | 0.0221 | 0.854 / 0.082 | 0.853 / 0.115 | 0.798 / 0.071 | 0.876 / 0.088 | 0.881 / 0.090 | n/a | 0.889 / 0.092 |
| E5_combined | 0.0237 | 0.825 / 0.082 | 0.831 / 0.115 | 0.814 / 0.080 | 0.886 / 0.098 | 0.900 / 0.105 | n/a | 0.890 / 0.100 |

## Hardware budget (IBM Open Plan: 600 s per rolling 28 days)

- stage4_day_test_plus_twins: 80 circuits x 3 fold scales x 1000 shots = 240000 shots, about 63.6 s of QPU time
- monday_training_on_hardware: 400 circuits x 3 fold scales x 1000 shots = 1200000 shots, about 310.0 s of QPU time
