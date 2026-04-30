# Snack Packs Round 5 Analysis

Scope: `SNACKPACK_CHOCOLATE`, `SNACKPACK_VANILLA`, `SNACKPACK_PISTACHIO`, `SNACKPACK_STRAWBERRY`, `SNACKPACK_RASPBERRY` only.

## Repository And Data

- Rust backtester: `prosperity_rust_backtester/`
- Run command pattern: `cd prosperity_rust_backtester && /Users/giordanmasen/Library/Caches/rust_backtester/target/release/rust_backtester --trader <file.py> --dataset round5`
- Round 5 CSVs: `prosperity_rust_backtester/datasets/round5/`
- Current combined trader: `prosperity_rust_backtester/traders/latest_trader.py`
- Category implementation produced here: `research/round5/snackpacks/snackpack_strategy.py`
- Data format: semicolon-delimited prices with `day,timestamp,product,bid_price_1,bid_volume_1,...,ask_price_3,ask_volume_3,mid_price,profit_and_loss`; trades with `timestamp,buyer,seller,symbol,currency,price,quantity`.
- Available public Round 5 days are 2, 3, and 4. I treated these as chronological validation days D1/D2/D3.
- All Round 5 products, including all Snack Packs, have position limit 10 in `prosperity_rust_backtester/src/runner.rs`.
- Final submission constraint: Python under 100KB, Prosperity `datamodel` imports only, no unsupported runtime dependencies. This category file is 4,848 bytes and imports only `datamodel`, `typing`, and `json`.

Loaded Snack Pack data: 150,000 price rows and 3,665 public trade rows.

## Product Diagnostics

| product | avg spread | top depth | ret vol | ret ac1 | trade qty | trade count | view |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CHOCOLATE | 16.47 | 58.99 | 6.58 | -0.031 | 1,805 | 733 | trade |
| VANILLA | 16.87 | 58.99 | 6.51 | -0.027 | 1,805 | 733 | trade |
| PISTACHIO | 15.93 | 58.99 | 5.24 | -0.025 | 1,805 | 733 | trade |
| STRAWBERRY | 17.83 | 58.99 | 8.13 | -0.014 | 1,805 | 733 | trade |
| RASPBERRY | 16.84 | 58.99 | 8.09 | -0.017 | 1,805 | 733 | trade |

All five products are liquid enough for passive market making. Average spreads are wide relative to one-tick queue improvement, and top depth is large. Return autocorrelation is negative but small, so pure single-product mean reversion is not the main edge. Aggressive crossing is feasible only for large fair-value deviations; crossing on ordinary book imbalance is not net-positive.

Level half-life estimates are very slow: roughly 624 ticks for RASPBERRY and 1,000-2,250 ticks for the others. This supports anchored fair values plus cautious relationship overlays rather than fast standalone reversion.

## Relationship Map

Return correlations are much stronger than the product names suggest:

| pair | return corr | rolling 500 corr by day | interpretation |
| --- | ---: | --- | --- |
| CHOCOLATE / VANILLA | -0.916 | -0.919, -0.916, -0.912 | strongest base-flavour anti-pair |
| PISTACHIO / STRAWBERRY | +0.913 | +0.913, +0.913, +0.914 | strongest same-direction pair |
| STRAWBERRY / RASPBERRY | -0.924 | -0.932, -0.921, -0.918 | fruit names are anti-correlated |
| PISTACHIO / RASPBERRY | -0.831 | -0.834, -0.830, -0.829 | stable anti-pair |

Price-level correlations show the same structure: CHOCOLATE/VANILLA is -0.926; PISTACHIO/STRAWBERRY is -0.441 in levels but +0.913 in returns; STRAWBERRY/RASPBERRY is -0.414 in levels and -0.924 in returns.

## Lead-Lag Findings

Tested leader mid-price changes over lags 1-100 plus 150, 200, 300, and 500 against follower future returns at horizons 1, 2, 5, 10, 20, 50, and 100. The broad scan found several statistically consistent slow effects:

| follower | leader | lag | horizon | mean corr | day corrs |
| --- | --- | ---: | ---: | ---: | --- |
| CHOCOLATE | VANILLA | 300 | 100 | +0.103 | +0.082, +0.198, +0.029 |
| RASPBERRY | CHOCOLATE | 500 | 100 | -0.080 | -0.075, -0.125, -0.041 |
| PISTACHIO | CHOCOLATE | 200 | 100 | +0.068 | +0.090, +0.056, +0.058 |
| RASPBERRY | VANILLA | 300 | 100 | +0.058 | +0.061, +0.057, +0.055 |

However, adding these extra predictive-looking overlays reduced Rust PnL to 170,278. The final strategy therefore keeps the already validated same-category lead-lag set from the Round 5 union trader and rejects additional statistical-only overlays.

Final retained Snack Pack lead-lag overlays:

| follower | signal(s) |
| --- | --- |
| CHOCOLATE | STRAWBERRY lag 50 x 0.25; PISTACHIO lag 100 x -0.05 |
| VANILLA | CHOCOLATE lag 100 x -0.05; CHOCOLATE lag 2 x -0.25 |
| PISTACHIO | RASPBERRY lag 20 x -0.10; RASPBERRY lag 500 x 0.05 |
| STRAWBERRY | CHOCOLATE lag 100 x 1.00; PISTACHIO lag 10 x -0.50 |
| RASPBERRY | PISTACHIO lag 50 x -0.25; PISTACHIO lag 200 x -0.10 |

## Pair And Basket Tests

Pair regressions found stable-looking pairs, but they were too slow and too non-stationary for direct pair trading:

| spread model | R2 | spread std | AR1 phi | half-life | verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| VANILLA ~ CHOCOLATE | 0.857 | 67.45 | 0.99923 | 905 | useful signal, not direct pair trade |
| CHOCOLATE ~ VANILLA | 0.857 | 75.84 | 0.99934 | 1058 | useful signal, not direct pair trade |
| PISTACHIO ~ RASPBERRY | 0.247 | 162.66 | 0.99975 | 2750 | too slow |
| RASPBERRY ~ PISTACHIO | 0.247 | 147.32 | 0.99908 | 752 | weak |

Basket regressions were in-sample attractive for CHOCOLATE and VANILLA, but leave-one-day-out validation broke:

| target | all-day R2 | residual std | LOO result |
| --- | ---: | ---: | --- |
| CHOCOLATE | 0.948 | 45.6 | day 2 R2 only 0.149 |
| VANILLA | 0.929 | 47.4 | day 2 R2 only 0.051 |
| STRAWBERRY | 0.799 | 163.1 | all LOO R2 negative |
| PISTACHIO | 0.770 | 89.9 | negative on days 2 and 3 |
| RASPBERRY | 0.746 | 85.7 | negative on day 2 |

Direct pair blend and basket blend were rejected in exact Rust backtests.

## Order Book Signals

Top and total book imbalance were nearly identical across Snack Pack products because the visible volumes are structurally synchronized. The one-tick predictive correlation was consistent and negative, around -0.11 to -0.13 for CHOCOLATE, VANILLA, and PISTACHIO, but the fitted fair shift is less than one tick for normal imbalance values. A Rust overlay using imbalance cut PnL from 187,420 to 75,057, so imbalance is rejected for trading.

## Strategy Decision

Use all five products. Ignore none. Each product is both traded and stored as a same-category signal.

The final category strategy is:

- anchored static fair values with product-specific shifts;
- selective aggressive crossing only when best quotes are far beyond fair;
- passive quoting with conservative product-specific quote edges;
- same-category lead-lag fair-value shifts using only current and past mid prices;
- no pair residual, basket residual, book imbalance, timestamp, or future-price logic.

This should be included in the final combined Round 5 submission.
