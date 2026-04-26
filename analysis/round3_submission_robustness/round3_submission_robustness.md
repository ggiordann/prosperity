# Round 3 Submission Robustness

This ranking is designed for the case where the Prosperity website and the local Rust backtester disagree.
It intentionally favors strategies that are not just locally profitable, but also stable, simple, and less sensitive to nearby tweaks.

## Top Picks

- Best overall robustness score: `v25_worst_mid_fair`
- Raw PnL leader in this set: `v19_vfe_mr_3000`
- Strongest simple baseline: `hybrid`

## Ranking

| Rank | Strategy | Robustness | Total PnL | Min Day | Day Std | Sharpe-like | Sensitivity Gap | Baseline Proximity |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `v25_worst_mid_fair` | 0.552 | 714,323.00 | 168,298.50 | 60,873.48 | 3.912 | 1,046.33 | 0.714 |
| 2 | `hybrid` | 0.550 | 666,607.00 | 208,328.50 | 14,460.11 | 15.367 | 44,844.33 | 1.000 |
| 3 | `v19_vfe_mr_3000` | 0.540 | 716,239.00 | 168,655.50 | 61,348.04 | 3.892 | 2,363.50 | 0.714 |
| 4 | `v26_worst_mid_target` | 0.527 | 713,544.00 | 166,594.50 | 62,462.28 | 3.808 | 1,565.67 | 0.714 |
| 5 | `v16_hp_smaller_mr` | 0.521 | 714,767.00 | 168,772.50 | 60,612.02 | 3.931 | 3,202.50 | 0.714 |
| 6 | `v18_both_mr_smaller` | 0.517 | 712,868.00 | 168,809.50 | 59,699.00 | 3.980 | 2,978.67 | 0.714 |
| 7 | `v17_hp_mr500` | 0.473 | 709,202.00 | 167,708.50 | 59,391.30 | 3.980 | 4,615.50 | 0.714 |
| 8 | `30u30` | 0.437 | 714,767.00 | 168,772.50 | 60,612.02 | 3.931 | 4,725.67 | 0.714 |
| 9 | `v24_partial_hedge` | 0.277 | 706,155.00 | 170,047.50 | 56,365.29 | 4.176 | 17,711.50 | 0.625 |
| 10 | `v22_negskew_stable` | 0.265 | 696,163.00 | 167,053.50 | 57,856.85 | 4.011 | 25,338.00 | 0.625 |

## Reading It

- `Total PnL`: what the local Rust backtester says.
- `Min Day`: worst single public round-3 day. Higher is better.
- `Day Std`: lower means less day-to-day swing.
- `Sharpe-like`: mean day PnL divided by day PnL standard deviation.
- `Sensitivity Gap`: average PnL gap to nearby family variants. Lower is better.
- `Baseline Proximity`: feature similarity to the simpler `hybrid.py` baseline. Higher is usually safer.

## Files

- CSV: `C:\Users\josh\Documents\GitHub\prosperity\analysis\round3_submission_robustness\round3_submission_robustness.csv`
