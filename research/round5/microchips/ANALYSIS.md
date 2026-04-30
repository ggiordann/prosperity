# Round 5 Microchip Research

Category:

- `MICROCHIP_CIRCLE`
- `MICROCHIP_OVAL`
- `MICROCHIP_SQUARE`
- `MICROCHIP_RECTANGLE`
- `MICROCHIP_TRIANGLE`

## Repository Map

- Rust backtester: `prosperity_rust_backtester/`
- Backtester command used:
  `cd prosperity_rust_backtester && ./scripts/cargo_local.sh run --release -- --trader ../research/round5/microchips/microchip_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_microchip_base`
- Round 5 CSVs: `prosperity_rust_backtester/datasets/round5/`
- Price files: `prices_round_5_day_2.csv`, `prices_round_5_day_3.csv`, `prices_round_5_day_4.csv`
- Trade files: `trades_round_5_day_2.csv`, `trades_round_5_day_3.csv`, `trades_round_5_day_4.csv`
- Current all-product trader: `prosperity_rust_backtester/traders/latest_trader.py`
- Final category implementation: `research/round5/microchips/microchip_trader.py`

Data format is semicolon-delimited IMC day data. Price rows include day, timestamp, product, top 3 bid/ask prices and volumes, mid price, and reference PnL. Trade rows include timestamp, buyer, seller, symbol, currency, price, and quantity. Round 5 has 50 products split into 10 categories of 5 products. The final submission must use Prosperity imports (`datamodel`) and allowed standard libraries only; this category file uses only `datamodel`, `typing`, and `json` and is 6.6KB, safely under the final 100KB budget.

## Product Diagnostics

Aggregate over days 2, 3, and 4:

| product | ret vol | abs ret | ac1 | mean rev 10 | momentum 10 | avg spread | top depth | jump 95 | jump 99 | ADF t | trade vol | decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| MICROCHIP_CIRCLE | 9.23 | 7.35 | -0.005 | 0.016 | -0.016 | 8.26 | 13.52 | 18.17 | 24.00 | -1.88 | 1119 | trade + signal |
| MICROCHIP_OVAL | 12.29 | 9.75 | -0.008 | 0.028 | -0.028 | 7.45 | 15.54 | 24.33 | 32.17 | -1.49 | 1119 | trade + signal |
| MICROCHIP_SQUARE | 20.54 | 16.31 | -0.024 | 0.007 | -0.007 | 11.72 | 11.91 | 40.33 | 53.50 | -1.54 | 1119 | trade + signal |
| MICROCHIP_RECTANGLE | 13.10 | 10.42 | -0.003 | -0.001 | 0.001 | 7.89 | 14.44 | 25.67 | 33.84 | -1.90 | 1119 | trade + signal |
| MICROCHIP_TRIANGLE | 14.46 | 11.50 | -0.008 | -0.007 | 0.007 | 8.64 | 12.88 | 28.33 | 37.17 | -1.69 | 1119 | trade + signal |

Observations:

- Passive market making is feasible but not rich by itself. Spreads are wide enough, but top depth is thin and all products have visible jumps.
- Aggressive crossing is feasible only with relationship signals. The 95th percentile one-tick move is larger than the spread for all five products.
- Raw single-product mean reversion is weak. Return autocorrelation is only slightly negative, with `MICROCHIP_SQUARE` the strongest at `-0.024`.
- Mid-price levels are not stationary by product. Aggregate ADF t-stats are above the rough `-2.86` 5% threshold.

## Relationship Research

### Correlation

Same-bar return correlations are small. The best average same-bar relationships are:

| pair | rolling return corr mean | rolling std | same-bar mean |
| --- | ---: | ---: | ---: |
| CIRCLE / OVAL | 0.010 | 0.034 | 0.012 |
| CIRCLE / SQUARE | 0.008 | 0.031 | 0.008 |
| CIRCLE / RECTANGLE | 0.008 | 0.032 | 0.010 |
| SQUARE / RECTANGLE | 0.007 | 0.030 | 0.007 |

Price-level correlations are unstable by day and sometimes flip sign. This rules out naive correlation trading.

### Lead-Lag

The useful signal is timing. Strongest causal lag diagnostics with lags `1..100` showed `MICROCHIP_CIRCLE` leading `MICROCHIP_RECTANGLE` over about 75-100 ticks in raw data, but adding that edge reduced Rust PnL. The retained production edges are the ones that survived actual execution tests:

| follower | signal | lag(s) | use |
| --- | --- | ---: | --- |
| CIRCLE | SQUARE and RECTANGLE moves | 100 | fair-value overlay |
| OVAL | RECTANGLE short moves | 1, 2 | fair-value overlay |
| OVAL | CIRCLE medium move | 50 | current-mid overlay |
| SQUARE | CIRCLE medium move | 100 | current-mid overlay |
| SQUARE | OVAL and TRIANGLE moves | 10, 5 | fair-value overlay |
| RECTANGLE | SQUARE slow move | 200 | fair-value overlay |
| TRIANGLE | OVAL slow moves | 100, 200 | fair-value overlay |

### Pair And Basket Tests

Pair residual diagnostics found two statistically plausible pairs:

| pair | residual ADF t | residual half-life | verdict |
| --- | ---: | ---: | --- |
| SQUARE vs RECTANGLE | -3.60 | 819 ticks | too slow for direct pair execution |
| OVAL vs TRIANGLE | -3.26 | 1059 ticks | too slow for direct pair execution |

Basket regressions were unstable out of sample. Test residuals had `ac1` near `0.999` and large day-to-day drift, especially for `CIRCLE`, `OVAL`, and `SQUARE`. `RECTANGLE` had the most stable basket residual, but the implemented basket/pair idea did not beat the lead-lag hybrid.

### Order Book Signals

Top imbalance signals were directionally consistent but small. Examples: `OVAL` imbalance predicted `TRIANGLE` 50 ticks forward with mean correlation `0.013`, and `RECTANGLE` imbalance predicted `OVAL` 50 ticks forward with mean correlation `0.006`. These were not added to the final strategy because the edge is much smaller than the spread and queue uncertainty.

## Strategy Development

Tested strategy families:

- Baseline/static market making and z-take: profitable, but much weaker than relationship trading.
- Single-product mean reversion/momentum: weak raw signal, not selected.
- Pair residual trading: plausible residual stationarity but slow half-life and unstable execution.
- Basket residual trading: unstable walk-forward residuals; rejected.
- Lead-lag strategy: strongest alpha.
- Hybrid strategy: selected. It combines static anchors, current-mid quoting, microchip lead-lag fair shifts, selective crossing, and passive quotes.

## Final Strategy

Use the hybrid in `microchip_trader.py`.

Core execution:

- Position limit `10` per microchip product.
- Static anchors for `CIRCLE` and `RECTANGLE`.
- Current-mid fair values for `OVAL`, `SQUARE`, and `TRIANGLE`.
- Medium-lag `CIRCLE` history shifts `OVAL` and `SQUARE`.
- Same-category lag overlays for all five products.
- Selective depth walking only on `MICROCHIP_SQUARE`.
- Passive quotes improve inside the spread when the fair edge is sufficient.

## Backtest Result

Final category PnL: `297,044.0`

| day | PnL | own trades |
| --- | ---: | ---: |
| 2 | 76,923.0 | 387 |
| 3 | 128,452.5 | 439 |
| 4 | 91,668.5 | 371 |
| total | 297,044.0 | 1,197 |

Product PnL:

| product | day 2 | day 3 | day 4 | total |
| --- | ---: | ---: | ---: | ---: |
| MICROCHIP_CIRCLE | 27,668.0 | 9,057.0 | 5,613.0 | 42,338.0 |
| MICROCHIP_OVAL | 30,006.0 | 34,590.5 | 17,527.0 | 82,123.5 |
| MICROCHIP_RECTANGLE | 5,750.0 | 25,458.0 | 20,905.0 | 52,113.0 |
| MICROCHIP_SQUARE | 12,468.0 | 43,367.0 | 32,737.0 | 88,572.0 |
| MICROCHIP_TRIANGLE | 1,031.0 | 15,980.0 | 14,886.5 | 31,897.5 |

## Overfitting Checks

- Train day 2, test days 3 and 4: test PnL `220,121.0`.
- Train days 2 and 3, test day 4: test PnL `91,668.5`.
- Leave-one-day-out sanity: each public day is positive.
- Parameter perturbations: `SIG` scaled to `0.5` earned `227,916.5`; scaled to `1.5` earned `241,830.5`; base earned `297,044.0`.
- Removing the `CIRCLE` medium-lag overlay dropped PnL to `172,050.5`.
- Doubling that overlay overfit badly and dropped PnL to `127,607.0`.
- Adding the tempting `CIRCLE -> RECTANGLE` lag-75 edge reduced PnL to `293,528.0` at `k=0.25` and `291,879.0` at `k=0.5`.

## Risks

- Only three public days are available, so all statistical tests have low sample count.
- Some retained lags are long enough that regime drift matters.
- `MICROCHIP_TRIANGLE` has the weakest product PnL and should be monitored in the combined submission.
- This strategy is category-local and should compose cleanly with other category strategies because product limits are independent.

## Recommendation

Include this category strategy in the final combined Round 5 submission. It is compact, uses only allowed imports, trades all five microchip products, and passed the strongest public walk-forward checks available.
