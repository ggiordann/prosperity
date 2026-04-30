# Round 5 Pebbles Research

Scope: Purification Pebbles only: `PEBBLES_XS`, `PEBBLES_S`, `PEBBLES_M`, `PEBBLES_L`, `PEBBLES_XL`.

## Repository And Data Inspection

- Rust backtester: `prosperity_rust_backtester/`
- Backtester command shape:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/pebbles/pebbles_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_pebbles_final
```

- Round 5 CSVs: `prosperity_rust_backtester/datasets/round5/`
  - `prices_round_5_day_2.csv`, `prices_round_5_day_3.csv`, `prices_round_5_day_4.csv`
  - `trades_round_5_day_2.csv`, `trades_round_5_day_3.csv`, `trades_round_5_day_4.csv`
- Current all-product trader: `prosperity_rust_backtester/traders/latest_trader.py`
- Pebbles category strategy: `research/round5/pebbles/pebbles_trader.py`
- Data format:
  - price rows are semicolon-delimited with `day`, `timestamp`, `product`, three bid/ask levels, `mid_price`, and `profit_and_loss`;
  - trade rows are semicolon-delimited with `timestamp`, `buyer`, `seller`, `symbol`, `currency`, `price`, `quantity`;
  - Round 5 buyer/seller fields are blank, so counterparty alpha is unavailable.
- Product list: 50 Round 5 products in 10 categories of 5. Pebbles are one category.
- Position limit: the Rust backtester enforces limit `10` for all Round 5 products, including all Pebbles.
- Final file constraints: Prosperity imports only; compact single-file implementation; final combined submission under `100KB`. The Pebbles strategy file is `4,954` bytes.

## Core Finding

The Pebbles category has a near-exact fixed-sum identity:

| day | sum mean | sum std | min | max | sum half-life |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 49,999.91 | 2.82 | 49,981.5 | 50,016.0 | 0.71 |
| 3 | 49,999.97 | 2.76 | 49,981.5 | 50,016.5 | 0.70 |
| 4 | 49,999.94 | 2.82 | 49,981.5 | 50,016.0 | 0.70 |

`PEBBLES_XL` is effectively the balancing leg: its one-tick returns have about `-0.50` correlation with each smaller Pebble. Directly trading the fixed-sum residual is too small after spread, but the identity creates useful lagged reactions.

## Product Diagnostics

| product | ret vol | avg spread | avg top depth | jump 95 | return ac1 | trade volume | decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `PEBBLES_XS` | 15.05 | 9.74 | 26.80 | 29.33 | -0.016 | 2,283 | trade + signal |
| `PEBBLES_S` | 15.02 | 11.55 | 24.81 | 29.35 | 0.008 | 2,283 | trade + signal |
| `PEBBLES_M` | 15.13 | 13.12 | 24.81 | 29.68 | -0.005 | 2,283 | trade + follower |
| `PEBBLES_L` | 15.02 | 13.02 | 24.81 | 29.33 | 0.007 | 2,283 | trade + signal |
| `PEBBLES_XL` | 30.31 | 16.63 | 24.81 | 59.35 | 0.008 | 2,283 | trade + strongest leader |

Market making is feasible in all five products: spreads are wide, top-book depth is enough for limit `10`, and passive fills are meaningful. Aggressive crossing is feasible only with strong fair-value displacement; blind crossing loses too much spread.

## Size Curve

The intuitive `XS < S < M < L < XL` ordering is only partly true:

| day | strict ordered pct | `XS<S` | `S<M` | `M<L` | `L<XL` |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 21.2% | 84.9% | 61.3% | 62.5% | 76.4% |
| 3 | 21.6% | 100.0% | 81.5% | 40.1% | 100.0% |
| 4 | 36.0% | 100.0% | 100.0% | 36.0% | 100.0% |

The curve is ordered at the ends but not reliable around `M/L`. Linear curve mean reversion and `M` butterfly trading against `(S+L)/2` both underperformed lead-lag execution.

## Correlation

Average same-day return correlations:

| pair | return corr mean | price corr mean | note |
| --- | ---: | ---: | --- |
| `XS` / `XL` | -0.497 | -0.563 | fixed-sum balancing |
| `S` / `XL` | -0.496 | -0.602 | fixed-sum balancing |
| `M` / `XL` | -0.512 | -0.305 | strongest XL offset |
| `L` / `XL` | -0.500 | -0.739 | stable negative |
| small-small pairs | about `0.00` to `0.015` | unstable | weak same-bar coupling |

The return structure says this is not a simple all-products-move-together basket. The smaller four are mostly independent on same-bar returns, while `XL` absorbs the category sum.

## Lead-Lag

Best stable lead-lag diagnostics, tested for lags `1..100`, plus `150/200/300/500`:

| horizon | leader | target | lag | mean corr | sign stability |
| ---: | --- | --- | ---: | ---: | --- |
| 100 | `PEBBLES_XL` | `PEBBLES_M` | 150 | 0.174 | 3/3 positive |
| 100 | `PEBBLES_XL` | `PEBBLES_M` | 100 | 0.163 | 3/3 positive |
| 20 | `PEBBLES_XL` | `PEBBLES_M` | 150 | 0.103 | 3/3 positive |
| 20 | `PEBBLES_XL` | `PEBBLES_XS` | 200 | 0.067 | 3/3 positive |
| 20 | `PEBBLES_L` | `PEBBLES_M` | 150 | -0.064 | 3/3 negative |

The executable edge set uses a compact validated subset:

- `XS <- XL` at lags `200`, `500`
- `S <- XS` at lag `500`, and `S <- L` at lag `10`
- `M <- XS` at lag `200`, and `M <- XL` at lag `200`
- `L <- S` at lag `500`, and `L <- XL` at lag `5`
- `XL <- M` at lags `20`, `500`

Refinement found that scaling only the `PEBBLES_M` lead-lag coefficients by `1.25x` improves standalone category PnL while preserving three positive days.

## Pair And Basket Tests

Raw pair spreads are not stationary enough to trade directly. Average ADF t-stats are mostly around `-1.2` to `-2.4`, and half-lives are hundreds to thousands of ticks. The best z-reversion pair was `XS-S`, but it was not competitive in the Rust backtest.

Basket regressions against the other four products produce tiny residuals because of the fixed-sum identity: average out-of-sample residual standard deviation is about `2.8`, with residual half-life around `0.70`. That is structurally real, but the edge is usually smaller than the visible spread. Fixed-sum and linear-curve residual variants lost to the lead-lag trader.

## Order Book Signals

Top-book imbalance has weak same-tick/next-tick predictive value and is largely shared across the category. The strongest stable top-imbalance correlations were only around `0.036`. Spread widening has some longer-horizon regime information, but adding it to the executable trader did not beat the lead-lag strategy.

## Strategy Conclusion

Trade all five Pebbles. Do not ignore any product. `PEBBLES_XL` is the strongest signal product; `PEBBLES_M` is the most valuable follower after the final refinement. The best robust implementation is a hybrid of:

- static anchors for `XS/M/L/XL`,
- current-mid market making for `S`,
- selective crossing only when fair displacement clears the tuned take threshold,
- passive quote placement around fair value,
- same-category lead-lag fair-value overlays.

Include the strategy in the final combined submission.
