# Round 5 Regime Filter Analysis

## Scope

Round 5 CSV days map to contest validation days as:

- Day 1: `prices_round_5_day_2.csv`
- Day 2: `prices_round_5_day_3.csv`
- Day 3: `prices_round_5_day_4.csv`

The deliverable trader is `traders/r5_regime_filter_trader.py`. It is a conservative risk layer over the validated static fair-value and lead-lag mechanics, not a max in-sample PnL submission.

## Signal Diagnostics

I tested all 50 products against five simple standalone signal families:

- mean reversion
- momentum
- basket residual
- lead-lag
- top-book imbalance

Artifacts:

- `research/round5/regime_filter/signal_diagnostics.csv`
- `research/round5/regime_filter/signal_param_grid.csv`
- `research/round5/regime_filter/product_filter_decisions.csv`

The standalone spread-paying signal grid was intentionally harsh. No product-signal family passed the strict filter of positive PnL on all three days, non-concentrated segment PnL, and acceptable parameter robustness. That does not mean the relationships are useless; it means they are unsafe as standalone live alphas. In the implemented trader:

- mean reversion is represented only through vetted static fair values
- lead-lag is retained only where the existing validated coefficients apply
- basket residual is used as a regime/conflict gate
- imbalance is not used as a standalone alpha
- momentum is used only as a trend-vs-reversion risk gate

## Product Filter

The anti-overfit product filter used actual Rust product PnL from the existing unfiltered final merged strategy and kept products with nonnegative day PnL and no excessive one-day dependence. This dropped 13 products:

`GALAXY_SOUNDS_PLANETARY_RINGS`, `MICROCHIP_CIRCLE`, `OXYGEN_SHAKE_GARLIC`, `OXYGEN_SHAKE_MORNING_BREATH`, `PANEL_1X2`, `PANEL_1X4`, `PEBBLES_XL`, `ROBOT_DISHES`, `ROBOT_IRONING`, `ROBOT_MOPPING`, `ROBOT_VACUUMING`, `TRANSLATOR_ASTRO_BLACK`, `UV_VISOR_RED`.

The remaining 37 products are still regime-gated online for spread, liquidity, trend/reversion conflict, basket residual conflict, and confidence.

## Final Metrics

Rust metrics-only backtest:

| Day | CSV day | Trades | PnL |
| --- | ---: | ---: | ---: |
| Day 1 | 2 | 499 | 405,867.00 |
| Day 2 | 3 | 699 | 514,722.00 |
| Day 3 | 4 | 607 | 437,167.00 |
| Total | - | 1,805 | 1,357,756.00 |

Stability score used here is `min(day PnL) / max(day PnL)`.

- Filtered stability score: `0.789`
- Filtered daily CV: `0.101`
- Unfiltered final stability score: `0.664`
- Unfiltered final daily CV: `0.179`
- Turnover reduction versus unfiltered final: `3,893 -> 1,805` trades

## Validation

Leave-one-day-out on the implemented filtered trader:

| Removed | Remaining PnL |
| --- | ---: |
| Day 1 removed | 951,889.00 |
| Day 2 removed | 843,034.00 |
| Day 3 removed | 920,589.00 |

Two-day product-filter train, held-out day evaluation using unfiltered per-product Rust PnL:

| Held out | Products kept | Train PnL | Held-out PnL |
| --- | ---: | ---: | ---: |
| Day 1 | 27 | 1,068,661.50 | 372,619.50 |
| Day 2 | 16 | 555,728.50 | 358,018.50 |
| Day 3 | 20 | 875,145.00 | 293,675.00 |

Parameter perturbation on the product concentration threshold:

| Max day-share threshold | Products kept | Inferred stable-filter PnL | Stability |
| ---: | ---: | ---: | ---: |
| 0.55 | 25 | 1,477,835.50 | 0.675 |
| 0.60 | 29 | 1,693,362.50 | 0.673 |
| 0.65 | 37 | 1,962,006.50 | 0.761 |
| 0.70 | 38 | 2,004,344.50 | 0.788 |
| 0.75 | 40 | 2,077,226.50 | 0.810 |

The implemented runtime gates reduce that inferred 37-product PnL to 1.358M, but improve turnover and avoid leaning entirely on the static product filter.

## Recommendation

Use this as a final risk layer if robustness is preferred over peak local CSV PnL. It deliberately gives up roughly 47% of the unfiltered local PnL to reduce turnover, avoid Day-1-only and one-segment effects, and keep every validation day positive. It should be tested on the website before final use because website PnL can diverge materially from local CSV matching.
