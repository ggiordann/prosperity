# Round 5 Latency Alpha Backtest Log

## Final Trader

File: `traders/r5_latency_trader.py`

The file is byte-identical to the compact merged trader already backtested as `prosperity_rust_backtester/traders/final_round5_trader.py`.

```text
SHA-256: 17dd1b562d2d8379dee09465b1476c931b33fe0af6faf4a1dcbec6e116b8f85b
Size: 17,872 bytes
```

Exact command for the submitted path:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../traders/r5_latency_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_latency_final
```

Equivalent completed command used for the metrics below:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader traders/final_round5_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_final_merged_first
```

## Final PnL

| Day | Own trades | PnL |
| --- | ---: | ---: |
| D+2 | 1,116 | 789,912.50 |
| D+3 | 1,502 | 1,062,299.50 |
| D+4 | 1,275 | 705,074.50 |
| Total | 3,893 | 2,557,286.50 |

Full product PnL: `research/round5/latency_alpha/final_product_pnl.csv`.

Top product PnL:

| Product | D+2 | D+3 | D+4 | Total |
| --- | ---: | ---: | ---: | ---: |
| PEBBLES_XL | 71,115.00 | 64,081.00 | -2,374.00 | 132,822.00 |
| PEBBLES_L | 43,877.00 | 39,042.00 | 12,005.00 | 94,924.00 |
| MICROCHIP_SQUARE | 12,468.00 | 43,367.00 | 32,737.00 | 88,572.00 |
| PEBBLES_XS | 19,455.00 | 39,811.00 | 24,061.00 | 83,327.00 |
| MICROCHIP_OVAL | 30,006.00 | 34,590.50 | 17,527.00 | 82,123.50 |
| GALAXY_SOUNDS_SOLAR_FLAMES | 25,975.00 | 28,622.00 | 22,587.00 | 77,184.00 |
| UV_VISOR_MAGENTA | 12,935.00 | 27,274.00 | 35,234.00 | 75,443.00 |

## Signal Set

The final file trades all 50 products and uses 96 retained same-category lag overlays.

Exact lag counts:

| Lag | Count |
| ---: | ---: |
| 1 | 5 |
| 2 | 4 |
| 5 | 4 |
| 10 | 5 |
| 20 | 7 |
| 50 | 8 |
| 78 | 1 |
| 100 | 15 |
| 200 | 24 |
| 500 | 23 |

Strong retained relationships include:

| Laggard | Leader | Lag | Weight |
| --- | --- | ---: | ---: |
| PEBBLES_XS | PEBBLES_XL | 200 | 0.10 |
| PEBBLES_L | PEBBLES_S | 500 | 0.50 |
| PEBBLES_L | PEBBLES_XL | 5 | 0.50 |
| UV_VISOR_MAGENTA | UV_VISOR_AMBER | 500 | 1.00 |
| UV_VISOR_MAGENTA | UV_VISOR_YELLOW | 20 | -0.25 |
| MICROCHIP_OVAL | MICROCHIP_RECTANGLE | 2 | -0.05 |
| MICROCHIP_SQUARE | MICROCHIP_TRIANGLE | 5 | 0.05 |
| GALAXY_SOUNDS_SOLAR_FLAMES | GALAXY_SOUNDS_BLACK_HOLES | 500 | -1.25 |

## Scanner Coverage

`latency_scanner.py` tested all ordered product pairs over leader horizons `1,2,3,5,10,20,50` and follower horizons `1,2,3,5,10,20,50`.

It also tested:

- category index -> product;
- product -> category index;
- leave-one-day-out basket residual change -> product;
- order book imbalance in A -> future return in B;
- inferred public trade flow in A -> future return in B.

Top scanner leader products: `UV_VISOR_RED`, `GALAXY_SOUNDS_SOLAR_FLAMES`, `PANEL_2X2`, `TRANSLATOR_GRAPHITE_MIST`, `OXYGEN_SHAKE_EVENING_BREATH`, `MICROCHIP_OVAL`.

Top scanner laggard products: `PEBBLES_XS`, `MICROCHIP_SQUARE`, `PEBBLES_XL`, `PEBBLES_L`, `UV_VISOR_ORANGE`, `MICROCHIP_RECTANGLE`.

Top statistical cross-category pairs were mostly 50->50 tick effects, led by:

| Leader | Laggard | Gross | Net after spread |
| --- | --- | ---: | ---: |
| GALAXY_SOUNDS_BLACK_HOLES | PEBBLES_XS | 22.71 | 13.07 |
| ROBOT_DISHES | SLEEP_POD_POLYESTER | 11.98 | 1.69 |
| GALAXY_SOUNDS_PLANETARY_RINGS | PEBBLES_L | 23.23 | 10.20 |
| PANEL_1X2 | ROBOT_MOPPING | 19.35 | 11.35 |

These were not included in the final executable because the broad walk-forward cross-product candidate set did not survive spread costs.

## Validation

Public data days are D+2, D+3, and D+4. In the requested train/test wording, day 1 maps to D+2, day 2 maps to D+3, and day 3 maps to D+4.

Walk-forward scanner validation for all h<=50 product-pair candidates:

| Split | Signals | Test gross | Test net after spread | Test sign aligned |
| --- | ---: | ---: | ---: | ---: |
| Train D+2, test D+3/D+4 | 91,809 | 1.2214 | -10.1275 | 50.81% |
| Train D+2/D+3, test D+4 | 51,920 | 1.2081 | -10.1988 | 49.77% |
| LOO test D+2 | 50,370 | 1.1775 | -10.0700 | 51.36% |
| LOO test D+3 | 51,643 | 1.1891 | -10.1617 | 50.41% |
| LOO test D+4 | 51,920 | 1.2081 | -10.1988 | 49.77% |

Strategy-level robustness checks from existing Rust runs:

| Variant | Purpose | Total PnL |
| --- | --- | ---: |
| `r5_final_merged_first` | final compact trader | 2,557,286.50 |
| `r5_leadlag_union_robust2_pred2` | lower-risk same-category union | 2,543,655.50 |
| `r5_leadlag_union_robust2_pred3` | stricter predictive threshold | 2,527,290.50 |
| `r5_leadlag_predictive_2day` | predictive-only, >=2 aligned days | 2,478,499.50 |
| `r5_leadlag_predictive_3day` | predictive-only, 3 aligned days | 2,320,322.50 |
| `r5_leadlag_inter_robust2_pred2` | intersection/lag-family perturbation | 2,464,449.00 |
| `r5_leadlag_first_2day_second_all` | first/second layer perturbation | 2,393,316.50 |

Remove-top relationship check:

- The strongest first-layer edge was `PEBBLES_XS <- PEBBLES_XL, lag 200, weight 0.10`.
- Product-level PnL with that edge: `81,909.00`.
- Product-level PnL without that edge in the first-layer sweep: `64,152.00`.
- The strategy is not a single-edge artifact: removing the top edge costs `17,757.00` in that product search, far smaller than total final PnL, and the stricter-threshold final variant still scores `2,527,290.50`.

## Rejections

Rejected from final:

- Broad cross-category h<=50 pairs: statistical hits existed, but walk-forward net after spread was negative.
- Order-book imbalance overlay: top effects were small and spread-negative.
- Public trade-flow overlay: interesting, but existing Rust flow overlays did not improve the validated final.
- Day-1-only relationships: excluded unless they also passed robust PnL or predictive support on at least two days.
- Five failed-both lead-lag edges from the max-public-score trader were removed:
  `OXYGEN_SHAKE_MINT <- OXYGEN_SHAKE_MORNING_BREATH lag 500`,
  `PANEL_1X2 <- PANEL_4X4 lag 500`,
  `PANEL_2X2 <- PANEL_1X2 lag 100`,
  `SLEEP_POD_COTTON <- SLEEP_POD_SUEDE lag 20`,
  `UV_VISOR_ORANGE <- UV_VISOR_MAGENTA lag 500`.

## Checks

- `python3 -m py_compile traders/r5_latency_trader.py research/round5/latency_alpha/latency_scanner.py` passed.
- Final trader is under 100KB.
- No unsupported imports: only `datamodel`, `typing`, and `json`.
- Runtime state stores rolling mid histories only; no external files, no future path lookup, no timestamp hard-coding.
- Product inventory is capped at +/-10 and final order aggregation clips per product before returning orders.
