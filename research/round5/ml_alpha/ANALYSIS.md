# Round 5 ML Alpha Analysis

Generated from `prosperity_rust_backtester/datasets/round5` days 2, 3, and 4. These are treated as public day 1/2/3 in the requested validation splits. The research script is `research/round5/ml_alpha/ml_alpha_research.py`.

## Feature Set

All features are current/past only:

- Product returns over lags 1, 2, 3, 5, 10, 20, 50, 100, 200, 500.
- Top-book and three-level order book imbalance, spread, and depth.
- Rolling z-scores over 50/200/500 ticks and realized-volatility regimes over 20/100 ticks.
- Same-category index returns excluding the target product.
- Cross-category index returns.
- Basket residuals from leave-one-day-out ridge fits inside each 5-product category.
- Market-trade flow quantity/count/signed flow. Buyer/seller IDs are blank in the public Round 5 CSVs, so participant-specific alpha is unavailable.

Targets:

- `target_1`, `target_3`, `target_5`: future mid-price change.
- `target_cross_buy_5`, `target_cross_sell_5`: whether crossing the spread has enough next-5-tick edge.
- `target_revert_5`: whether an extreme z-score mean-reverts.

## Models Tried

- Ridge linear regression per product.
- Logistic-like ridge score for spread-cross direction.
- Manual shallow decision stump using simple threshold features.
- Random forest skipped: `sklearn` is not installed in this workspace and was not vendored.
- Neural net not promoted: the three public days are too few for a high-variance model, and final submission runtime should not depend on `torch`.

## Top Robust Features

| Target | Best robust features | Read |
| --- | --- | --- |
| Next 1 tick | `obi_3`, `obi_1`, `xcat_snack_ret_1` | OBI has consistent sign but small IC. |
| Next 3/5 ticks | `obi_3`, `obi_1`, recent returns | Predictive, but not enough to cross spread alone. |
| Cross spread | `spread`, `depth_3`, `depth_1`, OBI | Wider/deeper books are less favorable for immediate crossing. |
| Z-score reversion | volatility regime, weak z/residual support | Useful for filtering but not a standalone model. |

Best aggregate ICs were small: `obi_3` was about `-0.019` vs next-5 returns, and spread was about `-0.064` vs crossing-spread profit. Direct ML scores failed spread-adjusted validation, so they were rejected as trading rules.

## Lead-Lag Findings

Top same-category robust edges by day-split IC:

| Leader | Follower | Lag | Mean IC |
| --- | --- | ---: | ---: |
| `ROBOT_MOPPING` | `ROBOT_IRONING` | 10 | 0.0430 |
| `PEBBLES_XL` | `PEBBLES_M` | 200 | 0.0430 |
| `SLEEP_POD_POLYESTER` | `SLEEP_POD_SUEDE` | 500 | -0.0377 |
| `UV_VISOR_AMBER` | `UV_VISOR_MAGENTA` | 200 | -0.0373 |
| `GALAXY_SOUNDS_DARK_MATTER` | `GALAXY_SOUNDS_PLANETARY_RINGS` | 100 | -0.0370 |

Top cross-category predictors existed, but were not promoted because they were weaker in rule/backtest form:

| Leader | Follower | Lag | Mean IC |
| --- | --- | ---: | ---: |
| `TRANSLATOR_ECLIPSE_CHARCOAL` | `SNACKPACK_VANILLA` | 100 | -0.0479 |
| `UV_VISOR_AMBER` | `PANEL_1X4` | 200 | 0.0463 |
| `PEBBLES_XS` | `OXYGEN_SHAKE_GARLIC` | 100 | -0.0446 |
| `UV_VISOR_RED` | `MICROCHIP_RECTANGLE` | 5 | 0.0445 |

## Basket Residuals

Robust mean-reversion residuals:

| Basket target | Edge mean | Worst split | Note |
| --- | ---: | ---: | --- |
| `PEBBLES_XL` | 7.63 | 4.60 | Strongest residual, sparse extremes. |
| `PEBBLES_S` | 1.86 | 0.88 | High sample count, modest edge. |
| `PANEL_2X2` | 0.81 | 0.78 | Stable but small. |
| `TRANSLATOR_VOID_BLUE` | 1.88 | 0.33 | Stable but not enough beyond final static/lag rules. |

These informed the static fair-value layer, but the full basket regression coefficients were rejected for the final trader because they add code size and did not improve public-day backtests on top of the lag overlay.

## Validation Results

Direct ML crossing models were rejected:

| Split | Ridge IC | Sign accuracy | Spread-adjusted proxy |
| --- | ---: | ---: | ---: |
| Train D+2, test D+3/D+4 | 0.0111 | 48.9% | -225,831 |
| Train D+2/D+3, test D+4 | 0.0118 | 48.4% | -48,539 |
| Leave out D+2 | 0.0134 | 48.9% | -36,735 |
| Leave out D+3 | 0.0150 | 49.4% | -58,547 |
| Leave out D+4 | 0.0118 | 48.4% | -48,539 |

Feature ablation confirmed that no raw ML score was usable for crossing. Local-only features lost the least money because they traded least; order-book and category features increased activity but still did not clear spread.

Threshold perturbation on the direct ML score stayed negative from `0.5x` to `1.5x` spread threshold, so the final submission uses rule-based fair values and passive inventory-aware quoting instead.

## Distilled Rules

Final trader: `traders/r5_ml_distilled_trader.py`.

- Trade all 50 products with position cap 10.
- Use a static fair-value anchor for stable mean-reverting products.
- Use current mid plus a small shift for products where day-split static anchoring was unstable.
- Add a compact same-category lead-lag fair-value overlay from robust causal edges.
- Cross only when visible ask/bid beats fair by product-specific take threshold.
- Otherwise quote passively around fair with product-specific edge/improvement.
- Clip aggregate orders by current inventory every tick.

Rejected features:

- Direct ridge/logistic/decision-stump next-return models.
- Cross-category raw IC edges.
- Public trade-flow overlays.
- Full basket regression tables.
- Any large coefficient matrix or unsupported runtime library.
