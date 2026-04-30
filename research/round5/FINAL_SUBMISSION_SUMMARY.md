# Round 5 Final Submission Summary

## Ready File

- Final file: `traders/final_round5_trader.py`
- File size: 32,642 bytes, 31.88 KiB
- Size limit: under 100 KiB
- Imports: `datamodel`, `typing`, `json`
- Runtime external files: none
- Debug prints: none
- Conversions: returns `0`
- Shape: exactly one `Trader` class with `run(self, state: TradingState)`
- Position limit: shared final safety pass clips buy orders to `10 - position` and sell orders to `10 + position` per product.

## Backtest Command

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../traders/final_round5_trader.py --dataset round5 --products off --artifact-mode none --flat --run-id r5_final_integrated
```

## Final PnL

| Day | Own trades | PnL |
| --- | ---: | ---: |
| D+2 | 1,266 | 878,480.50 |
| D+3 | 1,564 | 1,050,127.50 |
| D+4 | 1,365 | 726,296.50 |
| Total | 4,195 | 2,654,904.50 |

Leave-one-day-out totals:

- D+2 + D+3: 1,928,608.00
- D+2 + D+4: 1,604,777.00
- D+3 + D+4: 1,776,424.00

No-Day-1 variant, treating D+2 as public day 1: D+3 + D+4 = 1,776,424.00.

## PnL By Strategy Family

| Family | D+2 | D+3 | D+4 | Total |
| --- | ---: | ---: | ---: | ---: |
| Lead-lag/static core | 735,911.50 | 904,906.50 | 631,904.50 | 2,272,722.50 |
| Basket product slice | 92,050.00 | 73,426.00 | 66,726.00 | 232,202.00 |
| Regime product slice | 50,519.00 | 71,795.00 | 27,666.00 | 149,980.00 |

## PnL By Product

| Product | D+2 | D+3 | D+4 | Total |
| --- | ---: | ---: | ---: | ---: |
| PEBBLES_XL | 71,115.0 | 64,081.0 | -2,374.0 | 132,822.0 |
| PEBBLES_L | 43,877.0 | 39,042.0 | 12,005.0 | 94,924.0 |
| MICROCHIP_SQUARE | 12,468.0 | 43,367.0 | 32,737.0 | 88,572.0 |
| PEBBLES_XS | 19,455.0 | 39,811.0 | 24,061.0 | 83,327.0 |
| MICROCHIP_OVAL | 30,006.0 | 34,590.5 | 17,527.0 | 82,123.5 |
| PEBBLES_M | 28,454.0 | 31,409.0 | 21,652.0 | 81,515.0 |
| GALAXY_SOUNDS_SOLAR_FLAMES | 25,975.0 | 28,622.0 | 22,587.0 | 77,184.0 |
| UV_VISOR_MAGENTA | 12,935.0 | 27,274.0 | 35,234.0 | 75,443.0 |
| SLEEP_POD_LAMB_WOOL | 18,390.0 | 31,387.0 | 21,109.0 | 70,886.0 |
| SLEEP_POD_SUEDE | 10,950.0 | 39,119.0 | 20,188.0 | 70,257.0 |
| PEBBLES_S | 13,525.0 | 18,363.0 | 33,973.0 | 65,861.0 |
| GALAXY_SOUNDS_DARK_MATTER | 14,473.0 | 31,791.0 | 18,118.0 | 64,382.0 |
| TRANSLATOR_GRAPHITE_MIST | 22,948.0 | 21,218.0 | 19,195.0 | 63,361.0 |
| SNACKPACK_RASPBERRY | 29,811.0 | 15,655.0 | 16,985.0 | 62,451.0 |
| TRANSLATOR_VOID_BLUE | 14,490.0 | 26,576.0 | 19,470.0 | 60,536.0 |
| OXYGEN_SHAKE_EVENING_BREATH | 361.0 | 32,473.0 | 25,966.0 | 58,800.0 |
| PANEL_2X2 | 28,961.0 | 11,839.0 | 17,265.0 | 58,065.0 |
| SLEEP_POD_POLYESTER | 17,615.0 | 30,609.0 | 9,113.0 | 57,337.0 |
| TRANSLATOR_ECLIPSE_CHARCOAL | 10,036.0 | 17,447.0 | 28,622.0 | 56,105.0 |
| ROBOT_MOPPING | 19,268.0 | 19,550.0 | 13,412.0 | 52,230.0 |
| MICROCHIP_RECTANGLE | 5,750.0 | 25,458.0 | 20,905.0 | 52,113.0 |
| OXYGEN_SHAKE_MINT | 31,847.0 | 4,000.0 | 15,805.0 | 51,652.0 |
| UV_VISOR_AMBER | 14,935.0 | 11,030.0 | 24,436.0 | 50,401.0 |
| GALAXY_SOUNDS_BLACK_HOLES | 14,658.5 | 14,142.0 | 21,124.0 | 49,924.5 |
| UV_VISOR_RED | 39,387.0 | 17,201.0 | -7,055.0 | 49,533.0 |
| GALAXY_SOUNDS_PLANETARY_RINGS | 13,200.0 | -1,655.0 | 37,537.0 | 49,082.0 |
| PANEL_2X4 | 28,152.0 | 13,832.0 | 6,037.0 | 48,021.0 |
| SLEEP_POD_COTTON | 11,190.0 | 15,009.0 | 20,490.0 | 46,689.0 |
| OXYGEN_SHAKE_CHOCOLATE | 12,416.0 | 15,986.0 | 17,908.0 | 46,310.0 |
| UV_VISOR_YELLOW | 18,145.0 | 0.0 | 26,860.0 | 45,005.0 |
| PANEL_4X4 | 25,122.0 | 12,467.0 | 7,073.0 | 44,662.0 |
| OXYGEN_SHAKE_GARLIC | 19,232.0 | 30,159.0 | -4,761.0 | 44,630.0 |
| PANEL_1X2 | 31,518.0 | 4,425.0 | 8,110.0 | 44,053.0 |
| GALAXY_SOUNDS_SOLAR_WINDS | 18,908.0 | 16,270.0 | 7,635.0 | 42,813.0 |
| MICROCHIP_CIRCLE | 27,668.0 | 9,057.0 | 5,613.0 | 42,338.0 |
| OXYGEN_SHAKE_MORNING_BREATH | 1,575.0 | 36,050.0 | 3,725.0 | 41,350.0 |
| ROBOT_IRONING | 15,367.0 | 10,628.0 | 14,397.0 | 40,392.0 |
| TRANSLATOR_ASTRO_BLACK | -1,590.0 | 16,787.0 | 24,388.0 | 39,585.0 |
| PANEL_1X4 | -2,030.0 | 30,502.0 | 10,405.0 | 38,877.0 |
| SNACKPACK_STRAWBERRY | 4,280.0 | 20,688.0 | 13,230.0 | 38,198.0 |
| ROBOT_DISHES | 10,068.0 | 36,978.0 | -10,374.0 | 36,672.0 |
| TRANSLATOR_SPACE_GRAY | 21,347.0 | 8,445.0 | 5,168.0 | 34,960.0 |
| UV_VISOR_ORANGE | 7,645.0 | 8,875.0 | 16,366.0 | 32,886.0 |
| SNACKPACK_VANILLA | 16,495.0 | 9,586.0 | 6,240.0 | 32,321.0 |
| MICROCHIP_TRIANGLE | 1,031.0 | 15,980.0 | 14,886.5 | 31,897.5 |
| ROBOT_LAUNDRY | 11,417.0 | 18,844.0 | 1,441.0 | 31,702.0 |
| SNACKPACK_CHOCOLATE | 18,845.0 | 10,155.0 | 2,060.0 | 31,060.0 |
| SNACKPACK_PISTACHIO | 14,368.0 | 6,101.0 | 2,921.0 | 23,390.0 |
| SLEEP_POD_NYLON | 2,095.0 | 14,242.0 | 6,591.0 | 22,928.0 |
| ROBOT_VACUUMING | 326.0 | 14,662.0 | 290.0 | 15,278.0 |

No product has negative total PnL. No product loses on two or more days.

## Included Strategy Modules

- Core from `r5_latency_trader.py` / duplicate family.
- Basket slice from `r5_basket_trader.py`: `PANEL_2X2`, `PEBBLES_M`, `ROBOT_MOPPING`, `ROBOT_IRONING`.
- Regime slice from `r5_regime_filter_trader.py`: `SLEEP_POD_SUEDE`, `ROBOT_LAUNDRY`, `PANEL_2X4`.

## Excluded Strategy Modules

- `r5_ml_distilled_trader.py`: byte-identical to latency.
- `r5_participant_trader.py`: byte-identical to latency.
- `r5_orderbook_trader.py`: same PnL as latency, larger file.
- `r5_strategy_tournament_trader.py`: lower PnL than latency.
- Full `r5_basket_trader.py`: lower standalone PnL; only selected products added robust value.
- Full `r5_regime_filter_trader.py`: lower standalone PnL; only selected products added robust value.
- `r5_drift_trader.py`: low total and conflicts with stronger fair-value core.
- `r5_mean_reversion_trader.py`: weak total, near-flat D+2.

## Robustness Checks

- Standalone candidate backtests across D+2, D+3, D+4.
- Incremental routed merge probes for basket top 3, basket top 4, basket top 7, regime stable, and basket top 4 + regime stable.
- Product-level cleanup: rejected basket top 7 additions with weaker day split despite higher public total.
- Day-by-day validation from full round run.
- Leave-one-day-out arithmetic on final day results.
- No-Day-1 arithmetic check.
- File size check under 100 KiB.
- Import/debug scan.
- `py_compile` check.

## Risks

- Public data is only three days; static fair values and lead-lag coefficients can still overfit public matching.
- Local backtester PnL may diverge from the website.
- Final uses rolling JSON `traderData`; runtime is acceptable locally at about 153 seconds for the 30k-tick full public backtest, but it is not stateless.
- Some products have one negative day, but none have negative total or lose on two days.

Ready to submit locally: yes.
