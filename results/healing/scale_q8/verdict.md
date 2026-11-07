# Verdict, self-healing loop (Amendment 4, H6)

| scenario | false alarm (days 1-5) | detected | delay (days) | coverage after alarm | coverage day 10: never / healing / daily |
|---|---|---|---|---|---|
| D0_no_drift | 0.000 | 0.00 | n/a | n/a | 0.888 / 0.888 / 0.886 |
| D1_depolarizing_x1.5 | 0.000 | 0.24 | 4.0 | 0.871 | 0.793 / 0.814 / 0.854 |
| D2_depolarizing_x2 | 0.000 | 0.98 | 2.9 | 0.838 | 0.712 / 0.840 / 0.824 |
| D3_bad_qubit | 0.000 | 0.97 | 3.2 | 0.810 | 0.728 / 0.810 / 0.815 |
| D4_thermal_relaxation | 0.000 | 1.00 | 1.5 | 0.882 | 0.701 / 0.882 / 0.883 |
| D5_readout | 0.000 | 1.00 | 3.0 | 0.928 | 0.816 / 0.928 / 0.918 |
| D6_combined | 0.000 | 1.00 | 1.0 | 0.846 | 0.554 / 0.847 / 0.847 |

- **H6a** false alarms at most 5% in every scenario: PASS
- **H6b** coverage within 3 points of 0.90 after a correct alarm, in every scenario with one: FAIL
