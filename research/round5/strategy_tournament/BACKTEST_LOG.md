# Round 5 Strategy Tournament Backtest Log

## Files

- Selected trader: `traders/r5_strategy_tournament_trader.py`
- Tournament harness: `research/round5/strategy_tournament/run_tournament.py`
- Candidate CSV: `research/round5/strategy_tournament/candidate_results.csv`
- Product PnL: `research/round5/strategy_tournament/selected_product_pnl.csv`
- Category/family PnL: `research/round5/strategy_tournament/selected_family_pnl.csv`

## Exact Commands

Full selected backtest:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../traders/r5_strategy_tournament_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_strategy_tournament_selected_full
```

Metrics-only runtime check:

```bash
cd prosperity_rust_backtester
/usr/bin/time -p ./scripts/cargo_local.sh run --release -- --trader ../traders/r5_strategy_tournament_trader.py --dataset round5 --products summary --artifact-mode none --run-id r5_strategy_tournament_selected_metrics
```

Selected-only versus all-candidates:

```bash
cd prosperity_rust_backtester
/usr/bin/time -p ./scripts/cargo_local.sh run --release -- --trader ../research/round5/strategy_tournament/all_candidates_trader.py --dataset round5 --products summary --artifact-mode none --run-id r5_strategy_tournament_all_candidates_metrics
```

## Selected Trader Result

| day | ticks | own_trades | pnl |
| ---: | ---: | ---: | ---: |
| 2 | 10,000 | 1,112 | 787,022.50 |
| 3 | 10,000 | 1,498 | 1,058,008.50 |
| 4 | 10,000 | 1,281 | 698,624.50 |
| total | 30,000 | 3,891 | 2,543,655.50 |

Runtime check under heavy concurrent local backtests:

- selected metrics-only: `real 436.56`, `user 330.41`, `sys 5.28`
- all-candidates metrics-only: `real 266.44`, `user 252.59`, `sys 2.97`

## Selected-Only Versus All-Candidates

The all-candidates comparator is the selected core plus the best anonymous participant-flow overlay candidate. It lost PnL versus the selected-only trader.

| trader | day_2 | day_3 | day_4 | total | own_trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| selected-only | 787,022.50 | 1,058,008.50 | 698,624.50 | 2,543,655.50 | 3,891 |
| all-candidates flow overlay | 787,022.50 | 1,055,944.50 | 698,091.50 | 2,541,058.50 | 3,891 |
| difference | 0.00 | 2,064.00 | 533.00 | 2,597.00 | 0 |

## PnL By Product

Top products:

| product | day_2 | day_3 | day_4 | total | positive_days |
| --- | ---: | ---: | ---: | ---: | ---: |
| PEBBLES_XL | 71,115.00 | 64,081.00 | -2,374.00 | 132,822.00 | 2 |
| PEBBLES_L | 43,877.00 | 39,042.00 | 12,005.00 | 94,924.00 | 3 |
| MICROCHIP_SQUARE | 12,468.00 | 43,367.00 | 32,737.00 | 88,572.00 | 3 |
| PEBBLES_XS | 19,455.00 | 39,811.00 | 24,061.00 | 83,327.00 | 3 |
| MICROCHIP_OVAL | 30,006.00 | 34,590.50 | 17,527.00 | 82,123.50 | 3 |
| UV_VISOR_MAGENTA | 12,935.00 | 27,274.00 | 35,234.00 | 75,443.00 | 3 |
| GALAXY_SOUNDS_SOLAR_FLAMES | 25,942.00 | 27,554.00 | 20,434.00 | 73,930.00 | 3 |
| SLEEP_POD_LAMB_WOOL | 18,390.00 | 31,387.00 | 21,109.00 | 70,886.00 | 3 |

Lowest positive products:

| product | day_2 | day_3 | day_4 | total | positive_days |
| --- | ---: | ---: | ---: | ---: | ---: |
| ROBOT_VACUUMING | 326.00 | 14,662.00 | 290.00 | 15,278.00 | 3 |
| SLEEP_POD_NYLON | 2,095.00 | 14,242.00 | 6,591.00 | 22,928.00 | 3 |
| SNACKPACK_PISTACHIO | 14,252.00 | 6,053.00 | 2,921.00 | 23,226.00 | 3 |
| PANEL_2X2 | 0.00 | 16,422.00 | 10,260.00 | 26,682.00 | 2 |
| ROBOT_IRONING | 4,860.00 | 20,290.00 | 3,679.00 | 28,829.00 | 3 |

Full table: `selected_product_pnl.csv`.

## PnL By Category Proxy

The live strategy families interact through one fair-value/order layer, so exact strategy-family attribution is not separable from one run. This category proxy is the realized Rust PnL grouped by product family.

| category | day_2 | day_3 | day_4 | total |
| --- | ---: | ---: | ---: | ---: |
| pebbles | 148,718.00 | 183,483.00 | 92,386.00 | 424,587.00 |
| microchip | 76,923.00 | 128,452.50 | 91,668.50 | 297,044.00 |
| galaxy | 87,181.50 | 88,102.00 | 104,848.00 | 280,131.50 |
| sleep | 60,240.00 | 128,496.00 | 76,164.00 | 264,900.00 |
| visor | 92,987.00 | 64,380.00 | 95,849.00 | 253,216.00 |
| translator | 65,246.00 | 88,940.00 | 94,839.00 | 249,025.00 |
| oxygen | 65,431.00 | 118,668.00 | 58,643.00 | 242,742.00 |
| panel | 82,467.00 | 77,866.00 | 40,783.00 | 201,116.00 |
| snack | 83,683.00 | 62,119.00 | 41,436.00 | 187,238.00 |
| robot | 24,146.00 | 117,502.00 | 2,008.00 | 143,656.00 |

## Strategy-Family Attribution

These are Rust-validated tournament/ablation totals used for family decisions. Incremental attribution is approximate because lead-lag, crossing, and quoting share the same fair-value and order layer.

| strategy family | Rust total | decision |
| --- | ---: | --- |
| static/crossing/passive anchor base | 2,182,319.00 | Selected base. |
| selected lead-lag overlays | +361,336.50 incremental | Selected; brings final to 2,543,655.50. |
| anonymous participant flow overlay | -2,597.00 incremental | Rejected. |
| basket residual overlays | negative/fragile in Rust overlay tests | Rejected. |
| order book imbalance | failed offline robust score | Rejected. |
| broad momentum/drift | failed offline robust score | Rejected except microchip lag filters. |

## Leave-One-Day-Out Screen

The vectorized offline LOO screen was intentionally harsher than the final Rust union. Standalone offline winners did not generalize, so they were rejected instead of merged.

| holdout_day | selected_candidates | holdout_pnl | holdout_positive_candidates | holdout_negative_candidates |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 15 | -15,120.50 | 6 | 9 |
| 3 | 20 | -16,306.00 | 7 | 13 |
| 4 | 19 | -53,549.00 | 7 | 12 |

## File Size

`traders/r5_strategy_tournament_trader.py`: `17,744` bytes.

## Use As Final Base?

Yes. Use this as the final merge base. It is compact, Rust-validated, day-stable, and beats the broader all-candidates overlay. The next merge should add nothing unless a new module proves positive by robust objective and by Rust selected-only delta.
