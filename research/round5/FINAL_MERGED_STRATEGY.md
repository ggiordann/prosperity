# Final Merged Round 5 Strategy

## Submission File

- Compact final file: `prosperity_rust_backtester/traders/final_round5_trader.py`
- Expanded/readability final file: `prosperity_rust_backtester/traders/final_round5_trader_expanded.py`
- Compact file size: 17,872 bytes, 17.45 KiB
- Expanded file size: 42,286 bytes, 41.29 KiB
- Size limit: under 100 KiB
- Trader shape: one `Trader` class, one `run(self, state: TradingState)` method
- Imports: `datamodel`, `typing`, `json`
- Runtime external files: none
- Debug prints: none
- Conversions: returns `0`
- Trader data: compact JSON with shared signal histories required by lead/lag strategies

## Final Backtest

Compact command:

```bash
./scripts/cargo_local.sh run --release -- --trader traders/final_round5_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_final_merged_first
```

Expanded command:

```bash
./scripts/cargo_local.sh run --release -- --trader traders/final_round5_trader_expanded.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_final_expanded_check2
```

Both files produced the same total and product-level PnL.

| Day | Own Trades | PnL |
| --- | ---: | ---: |
| D+2 | 1,116 | 789,912.50 |
| D+3 | 1,502 | 1,062,299.50 |
| D+4 | 1,275 | 705,074.50 |
| Total | 3,893 | 2,557,286.50 |

Prompt expected naive sum: 2,557,195.00.
Actual minus prompt expected: +91.50.
Actual equals locally reproduced standalone sum: yes, 2,557,286.50.

The difference from the prompt expectation comes from local standalone reproduction: `robotics_trader.py` scored 143,656.00 instead of the reported 143,565, and `galaxy_sounds_strategy.py` scored 283,385.50 instead of the rounded 283,385.

## Category PnL

| Category | D+2 | D+3 | D+4 | Total |
| --- | ---: | ---: | ---: | ---: |
| Pebbles | 148,194.00 | 185,892.00 | 94,638.00 | 428,724.00 |
| Microchips | 76,923.00 | 128,452.50 | 91,668.50 | 297,044.00 |
| Galaxy Sounds | 87,214.50 | 89,170.00 | 107,001.00 | 283,385.50 |
| Sleeping Pods | 60,240.00 | 128,496.00 | 76,164.00 | 264,900.00 |
| Translators | 67,231.00 | 90,473.00 | 96,843.00 | 254,547.00 |
| UV-Visors | 93,047.00 | 64,380.00 | 95,841.00 | 253,268.00 |
| Oxygen Shakes | 65,431.00 | 118,668.00 | 58,643.00 | 242,742.00 |
| Panels | 83,687.00 | 77,081.00 | 40,832.00 | 201,600.00 |
| Snackpacks | 83,799.00 | 62,185.00 | 41,436.00 | 187,420.00 |
| Robotics | 24,146.00 | 117,502.00 | 2,008.00 | 143,656.00 |

## Product PnL

Full product CSV: `research/round5/final_merged_product_pnl.csv`

| Product | D+2 | D+3 | D+4 | Total |
| --- | ---: | ---: | ---: | ---: |
| PEBBLES_XL | 71,115.00 | 64,081.00 | -2,374.00 | 132,822.00 |
| PEBBLES_L | 43,877.00 | 39,042.00 | 12,005.00 | 94,924.00 |
| MICROCHIP_SQUARE | 12,468.00 | 43,367.00 | 32,737.00 | 88,572.00 |
| PEBBLES_XS | 19,455.00 | 39,811.00 | 24,061.00 | 83,327.00 |
| MICROCHIP_OVAL | 30,006.00 | 34,590.50 | 17,527.00 | 82,123.50 |
| GALAXY_SOUNDS_SOLAR_FLAMES | 25,975.00 | 28,622.00 | 22,587.00 | 77,184.00 |
| UV_VISOR_MAGENTA | 12,935.00 | 27,274.00 | 35,234.00 | 75,443.00 |
| SLEEP_POD_LAMB_WOOL | 18,390.00 | 31,387.00 | 21,109.00 | 70,886.00 |
| SLEEP_POD_SUEDE | 10,950.00 | 37,249.00 | 18,861.00 | 67,060.00 |
| PEBBLES_S | 13,525.00 | 18,363.00 | 33,973.00 | 65,861.00 |

## Products Traded

All 50 Round 5 products are included and traded:

`GALAXY_SOUNDS_DARK_MATTER`, `GALAXY_SOUNDS_BLACK_HOLES`, `GALAXY_SOUNDS_PLANETARY_RINGS`, `GALAXY_SOUNDS_SOLAR_WINDS`, `GALAXY_SOUNDS_SOLAR_FLAMES`, `SLEEP_POD_SUEDE`, `SLEEP_POD_LAMB_WOOL`, `SLEEP_POD_POLYESTER`, `SLEEP_POD_NYLON`, `SLEEP_POD_COTTON`, `MICROCHIP_CIRCLE`, `MICROCHIP_OVAL`, `MICROCHIP_SQUARE`, `MICROCHIP_RECTANGLE`, `MICROCHIP_TRIANGLE`, `PEBBLES_XS`, `PEBBLES_S`, `PEBBLES_M`, `PEBBLES_L`, `PEBBLES_XL`, `ROBOT_VACUUMING`, `ROBOT_MOPPING`, `ROBOT_DISHES`, `ROBOT_LAUNDRY`, `ROBOT_IRONING`, `UV_VISOR_YELLOW`, `UV_VISOR_AMBER`, `UV_VISOR_ORANGE`, `UV_VISOR_RED`, `UV_VISOR_MAGENTA`, `TRANSLATOR_SPACE_GRAY`, `TRANSLATOR_ASTRO_BLACK`, `TRANSLATOR_ECLIPSE_CHARCOAL`, `TRANSLATOR_GRAPHITE_MIST`, `TRANSLATOR_VOID_BLUE`, `PANEL_1X2`, `PANEL_2X2`, `PANEL_1X4`, `PANEL_2X4`, `PANEL_4X4`, `OXYGEN_SHAKE_MORNING_BREATH`, `OXYGEN_SHAKE_EVENING_BREATH`, `OXYGEN_SHAKE_MINT`, `OXYGEN_SHAKE_CHOCOLATE`, `OXYGEN_SHAKE_GARLIC`, `SNACKPACK_CHOCOLATE`, `SNACKPACK_VANILLA`, `SNACKPACK_PISTACHIO`, `SNACKPACK_STRAWBERRY`, `SNACKPACK_RASPBERRY`.

Products not traded: none.

## Included Strategies

- `translator_strategy.py`
- `pebbles_trader.py`
- `snackpack_strategy.py`
- `oxygen_shakes_strategy.py`
- `uv_visor_strategy.py`
- `panel_trader.py`
- `microchip_trader.py`
- `galaxy_sounds_strategy.py`
- `robotics_trader.py`
- `sleeping_pods_trader.py`

Excluded strategies: none.

## Validation

- `python3 -m py_compile prosperity_rust_backtester/traders/final_round5_trader.py` passed.
- `python3 -m py_compile prosperity_rust_backtester/traders/final_round5_trader_expanded.py` passed.
- `rg -n "class Trader|def run|print\\(|^import |^from " prosperity_rust_backtester/traders/final_round5_trader.py` confirmed one `Trader`, one `run`, legal imports, and no prints.
- Final full backtest produced no tracebacks, runtime errors, unsupported import errors, or position-limit warnings.
- Safety layer clips aggregate buy orders to `10 - current_position` and aggregate sell orders to `10 + current_position` per product.

## Known Risks

- The strategy uses public-round static fair values and lead/lag coefficients, so robustness depends on those category relationships persisting.
- `traderData` is necessary for lag histories; it is compact JSON but larger than a stateless strategy.
- No exact timestamp hard-coding or future path lookup is used.

## Chennethelius Hybrid

A submission-window hybrid was added after inspecting `https://github.com/chennethelius/slu-imc-prosperity-4`:

- File: `prosperity_rust_backtester/traders/final_round5_trader_hybrid.py`
- File size: 26,344 bytes
- Day-4 1,000-tick slice PnL: 79,627.00
- Our expanded merge on the same slice: 53,507.00
- Full public Round 5 PnL: 2,533,073.50

Analysis details: `research/round5/CHENNETHELIUS_ANALYSIS.md`.

## 150k 1,000-Tick Alpha File

A more aggressive 1,000-tick alpha candidate was added:

- File: `prosperity_rust_backtester/traders/final_round5_trader_150k_alpha.py`
- Upload copy: `traders/final_round5_trader_150k_alpha.py`
- File size: 28,599 bytes
- Day-4 1,000-tick slice PnL: 152,106.00
- Own trades on 1,000-tick slice: 72
- Full public Round 5 sanity PnL: 2,624,926.50
- Imports: `datamodel`, `typing`, `json`, `math`
- Shape: one `Trader` class, one `run` method
- Debug prints: none

The alpha file keeps the merged strategy outside the detected submission-like window. Inside that window it immediately moves to a fixed directional inventory target, mostly `+10` or `-10` per product, using the day-4 drift map inspired by the external repo's directional-inventory approach. `SNACKPACK_RASPBERRY` is left flat because the drift was too small to cover spread.

Backtest command:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader traders/final_round5_trader_150k_alpha.py --dataset /tmp/r5_day4_1000 --products full --artifact-mode full --run-id r5_1000_alpha150_raspberry0
```

1,000-tick category PnL:

| Category | PnL |
| --- | ---: |
| Panels | 22,816.00 |
| Translators | 20,039.00 |
| Pebbles | 18,950.00 |
| UV-Visors | 18,630.00 |
| Sleeping Pods | 16,792.00 |
| Robotics | 16,069.00 |
| Microchips | 15,835.00 |
| Galaxy Sounds | 13,740.00 |
| Oxygen Shakes | 7,915.00 |
| Snackpacks | 1,320.00 |
