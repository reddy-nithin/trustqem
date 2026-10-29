# Verdict, hardware track (Amendment 3, docs/HYPOTHESES.md)

Monday simulated from the calibration of S1.

- **H2-hw** frozen coverage below 0.87 in: S1, S2

## S1

- frozen coverage 0.667 (95% CI 0.614 to 0.717); below 0.87: True
- **H3-hw** R1W K=60: coverage 0.902 (95% CI 0.855 to 0.931), width 0.157 vs oracle 0.175 (0.90x): PASS; CI contains 0.90: True
- test MAE 0.0382; drift alarm p-value (Monday simulated twins vs hardware twins) 1.11e-12

## S2

- frozen coverage 0.648 (95% CI 0.590 to 0.702); below 0.87: True
- **H3-hw** R1W K=60: coverage 0.905 (95% CI 0.864 to 0.952), width 0.166 vs oracle 0.169 (0.98x): PASS; CI contains 0.90: True
- test MAE 0.0389; drift alarm p-value (Monday simulated twins vs hardware twins) 5.74e-12

