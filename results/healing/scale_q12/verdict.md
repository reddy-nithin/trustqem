# Verdict, self-healing loop (Amendment 4, H6)

| scenario | false alarm (days 1-5) | detected | delay (days) | coverage after alarm | coverage day 10: never / healing / daily |
|---|---|---|---|---|---|
| D0_no_drift | 0.000 | 0.00 | n/a | n/a | 0.894 / 0.894 / 0.881 |
| D1_depolarizing_x1.5 | 0.000 | 0.23 | 4.5 | 0.854 | 0.809 / 0.817 / 0.837 |
| D2_depolarizing_x2 | 0.000 | 0.99 | 3.0 | 0.815 | 0.730 / 0.815 / 0.812 |
| D3_bad_qubit | 0.005 | 0.67 | 3.9 | 0.827 | 0.787 / 0.815 / 0.817 |
| D4_thermal_relaxation | 0.000 | 1.00 | 1.2 | 0.871 | 0.705 / 0.871 / 0.874 |
| D5_readout | 0.000 | 1.00 | 2.5 | 0.915 | 0.822 / 0.916 / 0.915 |
| D6_combined | 0.000 | 1.00 | 1.0 | 0.839 | 0.595 / 0.838 / 0.840 |

- **H6a** false alarms at most 5% in every scenario: PASS
- **H6b** coverage within 3 points of 0.90 after a correct alarm, in every scenario with one: FAIL
