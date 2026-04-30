# Round 5 Robust Mean Reversion Analysis

Data inspected: `prosperity_rust_backtester/datasets/round5/prices_round_5_day_{2,3,4}.csv`.

Backtester inspected: `prosperity_rust_backtester`, using the local release binary at `$HOME/Library/Caches/rust_backtester/target/release/rust_backtester`.

Note on day labels: this repo's public Round 5 files are days `2`, `3`, and `4`. In the validation below, "Day 1 removed" means the first available public day, `D+2`.

## Research Setup

For every product I computed:

- Mid-price deviation from rolling fair value.
- Fair variants: SMA, EMA, rolling median, and visible-book VWAP-like fair.
- Windows: 20, 50, 100, 200, 500, plus final perturbations around 288.
- Vol-normalized z-score, AR(1) half-life, autocorrelation at 20 and 100 ticks.
- Spread-adjusted 20-tick expected edge.
- Cross-product residuals: product minus same-category index, product minus cross-category index, and synthetic beta fair.

Main warning from the research: most apparent mean reversion disappears after half-spread. The broad all-product version made money in offline tables but lost in official product PnL. I accepted only `PEBBLES_XL`.

## Product Classification

| Product | Class | Decision |
|---|---:|---|
| PEBBLES_XL | strong mean reverting | Trade. Best robust self-SMA product. |
| PEBBLES_XS | weak mean reverting | Excluded; residual looked okay but official PnL was unstable. |
| PEBBLES_S | noisy / avoid | Excluded; weak edge after spread. |
| PEBBLES_M | weak mean reverting | Excluded; residual signal was not stable enough. |
| PEBBLES_L | noisy / avoid | Excluded; no robust edge after spread. |
| MICROCHIP_RECTANGLE | weak mean reverting | Excluded; cross residual passed offline but lost in official backtest. |
| MICROCHIP_CIRCLE | weak mean reverting | Excluded; cross residual was too day-sensitive. |
| MICROCHIP_OVAL | trending | Excluded; high residual persistence, poor realized edge. |
| MICROCHIP_SQUARE | trending | Excluded; high residual persistence, poor realized edge. |
| MICROCHIP_TRIANGLE | noisy / avoid | Excluded; no robust spread-adjusted edge. |
| TRANSLATOR_VOID_BLUE | weak mean reverting | Excluded; official PnL was negative. |
| TRANSLATOR_ASTRO_BLACK | noisy / avoid | Excluded; rolling fair signal failed after spread. |
| TRANSLATOR_ECLIPSE_CHARCOAL | trending | Excluded; persistent residuals. |
| TRANSLATOR_GRAPHITE_MIST | noisy / avoid | Excluded; marginal/unstable. |
| TRANSLATOR_SPACE_GRAY | noisy / avoid | Excluded; no robust edge. |
| ROBOT_IRONING | weak mean reverting | Excluded; official PnL was negative. |
| ROBOT_DISHES | trending | Excluded; high persistence and weak edge. |
| ROBOT_LAUNDRY | trending | Excluded; high persistence and weak edge. |
| ROBOT_MOPPING | noisy / avoid | Excluded; short half-life but negative edge after spread. |
| ROBOT_VACUUMING | trending | Excluded; high persistence and weak edge. |
| SLEEP_POD_NYLON | trending | Excluded; high persistence and weak edge. |
| SLEEP_POD_SUEDE | noisy / avoid | Excluded; unstable edge. |
| SLEEP_POD_LAMB_WOOL | trending | Excluded; high persistence. |
| SLEEP_POD_POLYESTER | trending | Excluded; high persistence. |
| SLEEP_POD_COTTON | noisy / avoid | Excluded; negative edge after spread. |
| PANEL_1X2 | noisy / avoid | Excluded; negative edge after spread. |
| PANEL_1X4 | noisy / avoid | Excluded; negative edge after spread. |
| PANEL_2X2 | trending | Excluded; high persistence and weak edge. |
| PANEL_2X4 | trending | Excluded; high persistence and weak edge. |
| PANEL_4X4 | noisy / avoid | Excluded; unstable edge. |
| OXYGEN_SHAKE_CHOCOLATE | trending | Excluded; poor hit rate after spread. |
| OXYGEN_SHAKE_EVENING_BREATH | noisy / avoid | Excluded; short-window signal lost to spread. |
| OXYGEN_SHAKE_GARLIC | trending | Excluded; high persistence and high spread. |
| OXYGEN_SHAKE_MINT | noisy / avoid | Excluded; negative edge after spread. |
| OXYGEN_SHAKE_MORNING_BREATH | noisy / avoid | Excluded; negative edge after spread. |
| SNACKPACK_CHOCOLATE | trending | Excluded; high spread and poor hit rate. |
| SNACKPACK_PISTACHIO | noisy / avoid | Excluded; high spread and poor hit rate. |
| SNACKPACK_RASPBERRY | noisy / avoid | Excluded; high spread and poor hit rate. |
| SNACKPACK_STRAWBERRY | trending | Excluded; high spread and poor hit rate. |
| SNACKPACK_VANILLA | trending | Excluded; high spread and poor hit rate. |
| GALAXY_SOUNDS_BLACK_HOLES | noisy / avoid | Excluded; short-window signal failed after spread. |
| GALAXY_SOUNDS_DARK_MATTER | trending | Excluded; high persistence. |
| GALAXY_SOUNDS_PLANETARY_RINGS | trending | Excluded; high persistence. |
| GALAXY_SOUNDS_SOLAR_FLAMES | noisy / avoid | Excluded; negative edge after spread. |
| GALAXY_SOUNDS_SOLAR_WINDS | noisy / avoid | Excluded; negative edge after spread. |
| UV_VISOR_AMBER | trending | Excluded; high persistence and high spread. |
| UV_VISOR_MAGENTA | noisy / avoid | Excluded; negative edge after spread. |
| UV_VISOR_ORANGE | noisy / avoid | Excluded; negative edge after spread. |
| UV_VISOR_RED | noisy / avoid | Excluded; negative edge after spread. |
| UV_VISOR_YELLOW | noisy / avoid | Excluded; negative edge after spread. |

## Key Diagnostics

Best pure rolling-fair product: `PEBBLES_XL`.

Best robust rolling-fair offline config before execution testing:

| Product | Fair | Window | Edge min | Hit median | Half-life | AC20 | Avg spread |
|---|---:|---:|---:|---:|---:|---:|---:|
| PEBBLES_XL | median | 200 | 1.04 | 0.524 | 80.7 | 0.801 | 16.9 |

Best residual screens:

| Product | Residual | Window | Days | Edge min | Hit median | Notes |
|---|---:|---:|---:|---:|---:|---|
| PEBBLES_XL | cross-category | 500 | 3 | 1.99 | 0.521 | Profitable, but self-SMA was simpler and better after tuning. |
| PEBBLES_XS | category | 500 | 3 | -0.01 | 0.538 | Excluded after product PnL instability. |
| MICROCHIP_RECTANGLE | cross-category | 100 | 2 robust days | 3.12 | 0.535 | Excluded after official backtest loss. |
| TRANSLATOR_VOID_BLUE | cross-category | 50/200 | 2 robust days | 1.62 | 0.514 | Excluded after official backtest loss. |
| ROBOT_IRONING | category | 200 | 2 robust days | 0.93 | 0.510 | Excluded after official backtest loss. |

## Final Strategy

File: `traders/r5_mean_reversion_trader.py`.

Accepted product: `PEBBLES_XL` only.

Parameters:

| Parameter | Value |
|---|---:|
| Fair | rolling SMA of self residual |
| Window | 288 ticks |
| Entry | `abs(z) >= 1.75` |
| Exit | `abs(z) < 0.35` |
| Edge gate | `abs(mid - fair) - spread / 2 > 0.45` |
| Volatility gate | rolling residual stdev in `[1, 1000]` |
| Inventory skew | `fair -= position * min(6, 0.08 * vol)` |
| Position limit | 10 |
| Order size | 8, clipped to limit |

The code supports category/cross residual fair values, but the final active config is self-only because the residual basket products failed official PnL validation.

