# Round 5 Panels Backtest Log

Final command:

```bash
cd /Users/giordanmasen/Desktop/projects/prosperity/prosperity_rust_backtester
/Users/giordanmasen/Library/Caches/rust_backtester/target/release/rust_backtester --trader ../research/round5/panels/panel_trader.py --dataset round5 --products full --artifact-mode none
```

Final result:

| Day | Own Trades | PnL |
|---:|---:|---:|
| 2 | 15 | 83,687 |
| 3 | 14 | 77,081 |
| 4 | 10 | 40,832 |
| Total | 39 | 201,600 |

Final PnL by product:

| Product | Day 2 | Day 3 | Day 4 | Total |
|---|---:|---:|---:|---:|
| `PANEL_1X2` | 31,518 | 4,425 | 8,110 | 44,053 |
| `PANEL_1X4` | -2,030 | 30,502 | 10,405 | 38,877 |
| `PANEL_2X2` | 0 | 16,386 | 10,260 | 26,646 |
| `PANEL_2X4` | 29,077 | 13,301 | 4,984 | 47,362 |
| `PANEL_4X4` | 25,122 | 12,467 | 7,073 | 44,662 |

## Strategy Iteration

| Variant | PnL | Notes |
|---|---:|---|
| No lag signals | 168,080 | Static anchors alone positive but weaker |
| Only two largest lag hooks | 195,016 | Most edge recovered, but full set better |
| Original full lag set, no imbalance | 200,524 | Strong baseline |
| Original full lag set with tiny imbalance | 200,534 | +10 only, treated as noise |
| Add `PANEL_1X2 -> PANEL_2X4` lag, weight 0.25 | 201,018 | Improvement |
| Add `PANEL_1X2 -> PANEL_2X4` lag, weight 0.20 | 201,600 | Selected |
| Add `PANEL_1X2 -> PANEL_2X4` lag, weight 0.10 | 200,352 | Worse |
| Add `PANEL_1X2 -> PANEL_2X4` lag, weight 0.50 | 199,417 | Worse |
| Add extra `PANEL_2X4 -> PANEL_1X2` lag | 201,475 | Worse than selected |
| Soften `PANEL_4X4` main lag weight to -0.75 | 185,092 | Lost too much day 2 edge |
| Flat 10,000 anchors | 9,148 | Rejects area/generic anchor hypothesis |
| Anchor +50 perturbation | 173,230 | Positive but worse |
| Anchor -50 perturbation | 147,868 | Positive but worse |
| Crossing threshold 20% lower | 139,237 | Over-aggressive |
| Crossing threshold 20% higher | 87,983 | Too few high-edge fills |
| Improve one tick inside spread | 89,845 | Overtrades and loses edge |

## Validation Notes

- Day-by-day final PnL is positive across all public days.
- Product-level final PnL is positive for all five products.
- No exact timestamp hard-coding.
- The strategy starts from empty `traderData` and uses only online mid histories.
- Relationship models were checked out-of-sample by day; basket/pair regressions were rejected due negative holdout R² and unstable residuals.
- Parameter perturbation passed in the sense that nearby conservative variants remain positive, while the selected constants are best among tested variants.

Recommendation: include this category strategy in the final combined Round 5 submission, with care to preserve the position limit 10 and avoid adding unrelated panel basket trades.
