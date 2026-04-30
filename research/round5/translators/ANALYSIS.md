# Round 5 Translators Analysis

Scope: `TRANSLATOR_SPACE_GRAY`, `TRANSLATOR_ASTRO_BLACK`, `TRANSLATOR_ECLIPSE_CHARCOAL`, `TRANSLATOR_GRAPHITE_MIST`, `TRANSLATOR_VOID_BLUE`.

## Repository Inspection

- Rust backtester: `prosperity_rust_backtester/`
- Backtester source: `prosperity_rust_backtester/src/`
- Round 5 CSV data: `prosperity_rust_backtester/datasets/round5/`
- Current full submission file: `prosperity_rust_backtester/traders/latest_trader.py`
- Translator category strategy: `research/round5/translators/translator_strategy.py`
- Data format: price CSVs are semicolon-delimited IMC activities with 3 bid/ask levels, `mid_price`, and `profit_and_loss`; trade CSVs are semicolon-delimited prints with `timestamp`, `buyer`, `seller`, `symbol`, `currency`, `price`, `quantity`.
- Available public Round 5 days: 2, 3, 4.
- Product count: 50 Round 5 products, 10 categories of 5.
- Position limits: the Rust runner enforces limit 10 for every Round 5 product.
- Final-file constraints: keep merged final submission under 100KB and use Prosperity-compatible imports only. The standalone Translator file is 4,066 bytes.

Backtester command pattern:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/translators/translator_strategy.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_translators_take_lag_v1
```

## Product Diagnostics

Aggregated over days 2, 3, and 4.

| product | ret_vol | abs_ret | ac1 | spread | top_depth | jump99 | adf_t | volume | decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| TRANSLATOR_ASTRO_BLACK | 9.44 | 7.52 | -0.0067 | 8.37 | 24.10 | 24.33 | -2.42 | 1805 | trade and signal |
| TRANSLATOR_ECLIPSE_CHARCOAL | 9.86 | 7.84 | -0.0076 | 8.70 | 22.65 | 25.67 | -1.47 | 1805 | trade and signal |
| TRANSLATOR_GRAPHITE_MIST | 10.12 | 8.08 | -0.0033 | 8.91 | 22.20 | 25.67 | -0.92 | 1805 | trade and signal |
| TRANSLATOR_SPACE_GRAY | 9.42 | 7.52 | 0.0077 | 8.40 | 23.88 | 24.17 | -1.58 | 1805 | trade and signal |
| TRANSLATOR_VOID_BLUE | 10.82 | 8.63 | -0.0091 | 9.52 | 21.82 | 27.83 | -1.31 | 1805 | trade and signal |

Interpretation:

- Spreads are wide enough for selective execution, but pure passive market making is weak in this replay model.
- Return autocorrelation is near zero, so single-product momentum and naive rolling mean reversion are not attractive.
- ADF statistics generally do not reject non-stationarity at the 5 percent level. Raw levels and basket residuals should not be trusted without PnL validation.
- Trade counts and volumes are equal across the five products in public data. Liquidity is sufficient for limit 10, but not enough to justify high-turnover momentum.

## Relationships

Same-bar return correlations are small. The strongest same-category mean return correlation is only about 0.018 for `TRANSLATOR_GRAPHITE_MIST` and `TRANSLATOR_VOID_BLUE`. Price-level correlations are much larger but unstable by day, so same-time pair trading is fragile.

The useful structure is delayed movement. The final model uses these fair-value shifts:

| target | leader | lag | weight |
| --- | --- | ---: | ---: |
| TRANSLATOR_ASTRO_BLACK | TRANSLATOR_VOID_BLUE | 200 | 0.10 |
| TRANSLATOR_ASTRO_BLACK | TRANSLATOR_GRAPHITE_MIST | 200 | 0.10 |
| TRANSLATOR_ECLIPSE_CHARCOAL | TRANSLATOR_GRAPHITE_MIST | 100 | 0.50 |
| TRANSLATOR_ECLIPSE_CHARCOAL | TRANSLATOR_SPACE_GRAY | 100 | -0.25 |
| TRANSLATOR_ECLIPSE_CHARCOAL | TRANSLATOR_SPACE_GRAY | 5 | 0.20 |
| TRANSLATOR_GRAPHITE_MIST | TRANSLATOR_VOID_BLUE | 500 | 0.50 |
| TRANSLATOR_GRAPHITE_MIST | TRANSLATOR_ECLIPSE_CHARCOAL | 20 | 0.10 |
| TRANSLATOR_SPACE_GRAY | TRANSLATOR_ECLIPSE_CHARCOAL | 500 | 0.50 |
| TRANSLATOR_SPACE_GRAY | TRANSLATOR_GRAPHITE_MIST | 200 | -0.25 |
| TRANSLATOR_VOID_BLUE | TRANSLATOR_ECLIPSE_CHARCOAL | 200 | -0.10 |
| TRANSLATOR_VOID_BLUE | TRANSLATOR_ASTRO_BLACK | 20 | -0.10 |

Signal form:

```text
fair[target] += weight * (mid[leader][now] - mid[leader][now - lag])
```

The additional short edge `ECLIPSE_CHARCOAL <- SPACE_GRAY`, lag 5, weight 0.20 was added after category-only testing. It improved all three public days in the final take-only execution variant. A public-score maximum at 0.22 was rejected as too small to justify the less clean coefficient.

## Rejected Alphas

- Baseline current-mid passive market making: no fills in the raw replay when not improving/crossing.
- Quote-only around the lead-lag fair value: profitable but weak, 67,675 total.
- Single-product momentum: strongly negative due to high turnover, best tested momentum variant was -358,070.
- Rolling mean reversion: also negative, best tested rolling mean variant was -127,326.
- Pair residual trading: best tested pair was `ECLIPSE_CHARCOAL` versus `VOID_BLUE`, only 26,698 total.
- Basket residual trading: even with all-public fitted ridge coefficients, only 122,745 total and residual autocorrelation near 1.0.
- Order-book imbalance: top-depth imbalance had short-horizon negative correlation with future returns, but the signal was effectively category-synchronous rather than product-specific; it was not included.

## Final Strategy

Use static anchored fair values plus validated same-category delayed fair-value shifts. Execute only by crossing visible best bid/ask when the quote is beyond the take threshold. Do not leave passive market-making quotes.

Why take-only:

- Mixed passive+take lead-lag strategy: 249,025.
- Take-only lead-lag strategy: 252,599.
- Take-only plus short Eclipse-from-Space edge: 254,547.
- Take-only improved all three public days versus the mixed passive version while reducing trades from 348 to 311.

## Final Result

| product | day 2 | day 3 | day 4 | total |
| --- | ---: | ---: | ---: | ---: |
| TRANSLATOR_ASTRO_BLACK | -1,590 | 16,787 | 24,388 | 39,585 |
| TRANSLATOR_ECLIPSE_CHARCOAL | 10,036 | 17,447 | 28,622 | 56,105 |
| TRANSLATOR_GRAPHITE_MIST | 22,948 | 21,218 | 19,195 | 63,361 |
| TRANSLATOR_SPACE_GRAY | 21,347 | 8,445 | 5,168 | 34,960 |
| TRANSLATOR_VOID_BLUE | 14,490 | 26,576 | 19,470 | 60,536 |
| Total | 67,231 | 90,473 | 96,843 | 254,547 |

Products traded: all five Translator products.

Products ignored inside category: none.

Products used as signal: all five.

Recommendation: include this category strategy in the final combined submission. It is compact, independent of other categories, positive on all public days, and beats the previous full-strategy Translator slice by 5,522.
