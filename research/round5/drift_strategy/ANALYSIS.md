# Round 5 Drift Strategy Analysis

Round 5 public files are `prices_round_5_day_2.csv`, `day_3.csv`, and `day_4.csv`. In this note, "Day 1/2/3" means those three chronological public files: file days 2/3/4.

## Data And Tests

Command:

```bash
python3 research/round5/drift_strategy/analyze_drift.py
```

Generated artifacts:

- `product_day_metrics.csv`
- `product_drift_summary.csv`
- `step_events.csv`
- `category_drift.csv`
- `category_leadership.csv`
- `validation_summary.csv`

Tests run for every product:

- close-to-open drift, OLS trend R2, up/down/zero tick rates
- monotonic trend consistency across public days
- persistent step jumps: absolute return above `max(4 * robust_sigma, 2.5 * average_spread, 25)` and still directionally persistent after 50 or 200 ticks
- opening 100-tick move and final 100-tick move
- buy-and-hold long and buy-and-hold short with cap 10 and spread crossing
- momentum, breakout, and trend-following variants with cap 10
- static mean-reversion/opposite-direction comparison
- category drift and cross-category lead-lag
- movement after step events in another product
- Day 1 step-repeat check on Days 2/3

## Drift Products Found

Only 12 products had the same drift sign on all three public days. These are the only products used in `traders/r5_drift_trader.py`.

| Product | Direction | Mean Move | Worst Day Move | Best Day Move | Rust PnL |
| --- | ---: | ---: | ---: | ---: | ---: |
| OXYGEN_SHAKE_GARLIC | long | 1299.3 | 111.0 | 1958.5 | 38,770 |
| GALAXY_SOUNDS_BLACK_HOLES | long | 1151.8 | 688.5 | 1446.5 | 34,340 |
| PANEL_2X4 | long | 790.2 | 738.0 | 894.5 | 23,580 |
| UV_VISOR_RED | long | 574.0 | 182.0 | 842.0 | 17,015 |
| SNACKPACK_STRAWBERRY | long | 297.0 | 97.5 | 436.0 | 8,655 |
| SLEEP_POD_LAMB_WOOL | long | 272.0 | 16.0 | 404.5 | 8,000 |
| MICROCHIP_OVAL | short | -1488.5 | -1897.5 | -744.0 | 44,646 |
| PEBBLES_XS | short | -1326.2 | -1951.5 | -823.5 | 39,630 |
| UV_VISOR_AMBER | short | -954.5 | -1499.5 | -255.0 | 28,465 |
| PEBBLES_S | short | -651.3 | -937.0 | -177.0 | 19,365 |
| SNACKPACK_PISTACHIO | short | -298.2 | -489.0 | -123.5 | 8,700 |
| SNACKPACK_CHOCOLATE | short | -113.7 | -181.5 | -75.0 | 3,160 |

Total Rust PnL from these static directional positions: `274,326`.

## Products To Avoid Mean Reverting

These same 12 products should not be mean reverted on the public evidence. Reversing the final drift direction has negative expected value after spread cost. The strongest avoid-mean-reversion names are:

- Short-biased products: `MICROCHIP_OVAL`, `PEBBLES_XS`, `UV_VISOR_AMBER`, `PEBBLES_S`, `SNACKPACK_PISTACHIO`, `SNACKPACK_CHOCOLATE`
- Long-biased products: `OXYGEN_SHAKE_GARLIC`, `GALAXY_SOUNDS_BLACK_HOLES`, `PANEL_2X4`, `UV_VISOR_RED`, `SNACKPACK_STRAWBERRY`, `SLEEP_POD_LAMB_WOOL`

Tempting but rejected static drift names because they reverse by day:

- `PEBBLES_XL`: +3674.5, -1552.5, +4014.0
- `MICROCHIP_SQUARE`: +2455.5, +3438.5, -2278.0
- `SLEEP_POD_POLYESTER`: +1765.5, +1118.5, -917.0
- `SLEEP_POD_SUEDE`: +1099.0, +1048.0, -338.0
- `ROBOT_MOPPING`: -179.5, +2352.5, -582.5
- `UV_VISOR_YELLOW`: +1567.5, +466.0, -1985.5
- `TRANSLATOR_GRAPHITE_MIST`: -662.5, +1713.0, -1260.5

## Step Functions

Persistent step-heavy products:

| Product | Persistent Step Count | Days | Max Jump |
| --- | ---: | --- | ---: |
| OXYGEN_SHAKE_CHOCOLATE | 47 | 2,3,4 | 100.0 |
| OXYGEN_SHAKE_EVENING_BREATH | 44 | 2 | 100.0 |
| ROBOT_IRONING | 33 | 2 | 102.0 |
| MICROCHIP_OVAL | 5 | 2,3,4 | 60.0 |
| GALAXY_SOUNDS_BLACK_HOLES | 4 | 3,4 | 51.5 |
| MICROCHIP_SQUARE | 3 | 3,4 | 98.5 |
| MICROCHIP_TRIANGLE | 3 | 2,3,4 | 65.0 |
| MICROCHIP_RECTANGLE | 3 | 2,3 | 61.0 |
| SLEEP_POD_LAMB_WOOL | 3 | 2,4 | 52.0 |
| UV_VISOR_MAGENTA | 3 | 2,3,4 | 49.0 |

Day 1 step functions did not repeat at the same timestamp on Day 2 or Day 3 within a 100-timestamp tolerance. Step behaviour exists, but the timestamp schedule is not stable enough for a hardcoded step strategy.

## Category Drift

Category-level drift is weaker than product-level drift:

| Category | Day 2 | Day 3 | Day 4 | Mean |
| --- | ---: | ---: | ---: | ---: |
| sleep | 653.8 | 893.2 | -200.5 | 448.8 |
| galaxy | 808.3 | 358.2 | -277.3 | 296.4 |
| oxygen | 170.9 | -180.9 | 759.5 | 249.8 |
| snack | 30.9 | 4.2 | 23.5 | 19.5 |
| pebbles | 0.1 | 0.1 | 0.2 | 0.1 |
| panel | 4.9 | -303.8 | 261.5 | -12.5 |
| visor | 472.8 | -18.6 | -507.9 | -17.9 |
| translator | 64.8 | 55.3 | -432.9 | -104.3 |
| robot | -86.5 | -329.4 | 59.3 | -118.9 |
| microchip | 142.2 | -402.0 | -491.8 | -250.5 |

No category drift was robust enough to trade directly. `snack` is all-days positive but too small, and `pebbles` is category-flat because the internal products offset each other.

## Cross-Category Leadership

The strongest consistent category-level leadership correlations were:

- `sleep -> translator`, lag 500, mean corr `0.259`
- `translator -> visor`, lag 500, mean corr `0.249`
- `visor -> sleep`, lag 500, mean corr `0.204`
- `snack -> oxygen`, lag 200, mean corr `0.185`
- `robot -> panel`, lag 500, mean corr `0.181`

The strongest negative leadership correlations were:

- `microchip -> oxygen`, lag 500, mean corr `-0.203`
- `galaxy -> visor`, lag 500, mean corr `-0.195`
- `microchip -> visor`, lag 500, mean corr `-0.192`
- `snack -> galaxy`, lag 500, mean corr `-0.190`
- `microchip -> snack`, lag 500, mean corr `-0.165`

These are real enough to note, but they are weaker than same-category lead-lag already explored elsewhere in Round 5 and were not used in this pure drift trader.

## Momentum And Breakout Tests

Naive momentum and breakout entries overtraded once spread crossing was included. A live dynamic-momentum prototype with cap 10 and spread thresholds lost `-411,735` on Day 2 with `13,957` own trades. This confirmed the risk called out in the prompt: drift products can be profitable, but noisy momentum over many products can be worse than doing nothing.

Final decision:

- Use static directional drift only where all three days agree.
- Reject Day 1-only drift.
- Reject products where drift reverses by day.
- Do not add dynamic momentum unless the signal exceeds spread by a very large margin and survives out-of-sample validation. No tested dynamic momentum rule did.
- Do not close at end of day; the Rust backtester marks inventory to market, and forced liquidation spends spread without improving expected value.

## Final Strategy Logic

For each tick:

1. If product is in the long set, target position `+10`.
2. If product is in the short set, target position `-10`.
3. Otherwise, target position `0`.
4. If current position is below target, buy up to target at the current best ask.
5. If current position is above target, sell down to target at the current best bid.
6. Return no `traderData`; no timestamp hardcoding or future data.

Final long set:

```text
OXYGEN_SHAKE_GARLIC
GALAXY_SOUNDS_BLACK_HOLES
PANEL_2X4
UV_VISOR_RED
SNACKPACK_STRAWBERRY
SLEEP_POD_LAMB_WOOL
```

Final short set:

```text
MICROCHIP_OVAL
PEBBLES_XS
UV_VISOR_AMBER
PEBBLES_S
SNACKPACK_PISTACHIO
SNACKPACK_CHOCOLATE
```
