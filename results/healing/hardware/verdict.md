# Self-healing loop replayed on IBM hardware (Amendment 4, reported, not judged)

Monday is simulated; then S1, S2 in order. 200 random canary orders.

| session | alarm rate | median martingale | never | healing | daily |
|---|---|---|---|---|---|
| S1 | 1.00 | 2.9e+15 | 0.667 / 0.087 | 0.902 / 0.157 | 0.902 / 0.157 |
| S2 | 0.00 | 0.0772 | 0.648 / 0.087 | 0.890 / 0.158 | 0.905 / 0.166 |

Cells are test coverage / mean interval width.
