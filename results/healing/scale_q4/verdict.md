# Verdict, self-healing loop (Amendment 4, H6)

| scenario | false alarm (days 1-5) | detected | delay (days) | coverage after alarm | coverage day 10: never / healing / daily |
|---|---|---|---|---|---|
| D0_no_drift | 0.000 | 0.00 | n/a | n/a | 0.876 / 0.876 / 0.909 |
| D1_depolarizing_x1.5 | 0.000 | 0.63 | 3.9 | 0.912 | 0.757 / 0.852 / 0.910 |
| D2_depolarizing_x2 | 0.000 | 0.99 | 2.3 | 0.913 | 0.643 / 0.917 / 0.909 |
| D3_bad_qubit | 0.000 | 1.00 | 1.5 | 0.913 | 0.536 / 0.912 / 0.906 |
| D4_thermal_relaxation | 0.000 | 1.00 | 1.8 | 0.902 | 0.658 / 0.903 / 0.905 |
| D5_readout | 0.000 | 0.99 | 3.1 | 0.938 | 0.790 / 0.936 / 0.938 |
| D6_combined | 0.000 | 1.00 | 1.0 | 0.910 | 0.415 / 0.910 / 0.908 |

- **H6a** false alarms at most 5% in every scenario: PASS
- **H6b** coverage within 3 points of 0.90 after a correct alarm, in every scenario with one: FAIL
