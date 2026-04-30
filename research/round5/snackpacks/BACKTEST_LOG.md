# Snack Packs Backtest Log

All exact scores below use the Rust backtester with Round 5 public days 2, 3, and 4.

Final command:

```bash
cd prosperity_rust_backtester
/Users/giordanmasen/Library/Caches/rust_backtester/target/release/rust_backtester --trader ../research/round5/snackpacks/snackpack_strategy.py --dataset round5 --products full --artifact-mode full --flat --run-id snackpack_final_edge_tight
```

## Strategy Bake-Off

| strategy | total PnL | day 2 | day 3 | day 4 | trades | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline market making around current mid | 55,447.5 | 15,372.0 | 21,799.5 | 18,276.0 | 3,215 | positive but low edge |
| Static anchored fair, no relationships | 167,845.0 | 77,508.0 | 53,461.0 | 36,876.0 | 126 | strong baseline |
| Own-product momentum overlay | 153,670.0 | 64,440.0 | 51,139.0 | 38,091.0 | 127 | rejected |
| Own-product reversion overlay | 170,713.0 | 76,211.0 | 56,726.0 | 37,776.0 | 149 | rejected versus lead-lag |
| Pair fair-value blend | 129,460.0 | 50,281.0 | 54,948.0 | 24,231.0 | 107 | rejected |
| Basket residual blend | 126,096.0 | 57,966.0 | 36,050.0 | 32,080.0 | 131 | rejected |
| Book imbalance overlay | 75,057.0 | 45,524.0 | 26,629.0 | 2,904.0 | 450 | rejected |
| Lead-lag hybrid before quote-edge perturbation | 187,238.0 | 83,683.0 | 62,119.0 | 41,436.0 | 155 | best structural signal |
| Final lead-lag hybrid | 187,420.0 | 83,799.0 | 62,185.0 | 41,436.0 | 152 | selected |

The relationship layer adds 19,575 PnL over static anchoring and is positive on every day.

## Perturbation Checks

| perturbation | total PnL | day 2 | day 3 | day 4 | read |
| --- | ---: | ---: | ---: | ---: | --- |
| Lead-lag weights x 0.75 | 172,967.0 | 78,857.0 | 52,225.0 | 41,885.0 | still positive, weaker |
| Lead-lag weights x 1.25 | 154,042.0 | 65,724.0 | 48,184.0 | 40,134.0 | too aggressive |
| Looser quote edges | 187,330.0 | 83,683.0 | 62,099.0 | 41,548.0 | comparable |
| Mid-tight quote edges | 187,372.0 | 83,799.0 | 62,137.0 | 41,436.0 | comparable |
| Tighter quote edges | 187,420.0 | 83,799.0 | 62,185.0 | 41,436.0 | selected |
| Very tight quote edges | 187,393.0 | 83,799.0 | 62,281.0 | 41,313.0 | comparable but slightly worse |

The small quote-edge change is not a fragile single-day jump: it improves or matches each day versus the prior hybrid. The signal-weight tests show that pushing the lead-lag coefficients harder is not robust.

## Final Backtest

| day | PnL | own trades |
| --- | ---: | ---: |
| 2 | 83,799.0 | 45 |
| 3 | 62,185.0 | 57 |
| 4 | 41,436.0 | 50 |
| Total | 187,420.0 | 152 |

PnL by product:

| product | day 2 | day 3 | day 4 | total |
| --- | ---: | ---: | ---: | ---: |
| SNACKPACK_RASPBERRY | 29,811.0 | 15,655.0 | 16,985.0 | 62,451.0 |
| SNACKPACK_STRAWBERRY | 4,280.0 | 20,688.0 | 13,230.0 | 38,198.0 |
| SNACKPACK_VANILLA | 16,495.0 | 9,586.0 | 6,240.0 | 32,321.0 |
| SNACKPACK_CHOCOLATE | 18,845.0 | 10,155.0 | 2,060.0 | 31,060.0 |
| SNACKPACK_PISTACHIO | 14,368.0 | 6,101.0 | 2,921.0 | 23,390.0 |

No position-limit breaches or runtime errors appeared in the final run.

## Walk-Forward Notes

Available public days are 2, 3, and 4, so I treated them as D1/D2/D3:

- Lead-lag signs were checked by day before adding anything new to the final strategy.
- Extra predictive-looking overlays from the day-by-day scan were exact-backtested and rejected because they lowered all-day Rust PnL to 170,278.
- Leave-one-day-out basket models were rejected because most targets failed at least one held-out day.
- The selected fixed strategy was exact-backtested day-by-day; all five products and all three days are positive.

## Include Decision

Include this category strategy in the final combined submission. It is compact, dependency-free, below the 100KB budget, and uses only causal same-category state.
