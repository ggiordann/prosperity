# Round 5 Sleeping Pods Analysis

## Repository Inspection

- Rust backtester: `prosperity_rust_backtester/`.
- Main runner: `prosperity_rust_backtester/src/cli.rs` and `prosperity_rust_backtester/src/runner.rs`.
- Round 5 CSVs: `prosperity_rust_backtester/datasets/round5/`.
- Current all-product submission: `prosperity_rust_backtester/traders/latest_trader.py`.
- Backtester command shape:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader <trader.py> --dataset round5 --products full --artifact-mode none
```

- Price CSV schema: semicolon separated `day`, `timestamp`, `product`, three bid levels, three ask levels, `mid_price`, `profit_and_loss`.
- Trade CSV schema: semicolon separated `timestamp`, `buyer`, `seller`, `symbol`, `currency`, `price`, `quantity`.
- Round 5 public days: 2, 3, 4.
- Round 5 product count: 50, arranged as 10 categories of 5 products.
- Position limit: `runner.rs` maps every `SLEEP_POD_` product to limit 10.
- Final file constraints: one Python `Trader` class using Prosperity `datamodel` imports and allowed standard-library style imports. The category file here is under 100KB and uses only `datamodel`, `typing`, and `json`.

## Product Diagnostics

All numbers use the three public days, one row per product averaged across days.

| Product | Ret vol | Abs ret | AC1 | Mom10 | Avg spread | Top depth | Book depth | Jump 95 | Jump 99 | Trades | ADF t | Half-life | Day net moves |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| SLEEP_POD_SUEDE | 11.395 | 9.084 | -0.006 | -0.012 | 9.949 | 21.819 | 59.093 | 22.167 | 29.500 | 733 | -1.565 | 3189 | 2:+1099, 3:+1048, 4:-338 |
| SLEEP_POD_LAMB_WOOL | 10.710 | 8.510 | 0.003 | 0.017 | 9.400 | 21.745 | 59.093 | 21.000 | 27.503 | 733 | -1.599 | 1509 | 2:+404.5, 3:+395.5, 4:+16 |
| SLEEP_POD_POLYESTER | 11.863 | 9.469 | -0.001 | -0.008 | 10.296 | 21.752 | 59.093 | 23.167 | 30.167 | 733 | -0.762 | 4451 | 2:+1765.5, 3:+1118.5, 4:-917 |
| SLEEP_POD_NYLON | 9.614 | 7.643 | 0.001 | 0.000 | 8.565 | 23.365 | 59.093 | 18.833 | 24.837 | 733 | -1.327 | 1726 | 2:-1123, 3:+828.5, 4:+1020.5 |
| SLEEP_POD_COTTON | 11.650 | 9.287 | -0.003 | 0.018 | 10.050 | 21.739 | 59.093 | 22.833 | 30.167 | 733 | -0.870 | 5256 | 2:+1123, 3:+1075.5, 4:-784 |

Interpretation:

- Passive market making is feasible because spreads are around 8.6 to 10.3 with stable visible depth around 22 at top of book.
- Pure single-product momentum is not feasible. Return autocorrelation is essentially zero and a Rust momentum quote test lost money.
- Aggressive crossing is only attractive when anchored to a slow fair value or a validated lead-lag fair shift. Raw jumps are not large enough to cross indiscriminately.
- Stationarity is weak in raw mid series. ADF t-stats are not strong enough to rely on single-product mean reversion alone, but static anchors plus wide z-take thresholds work because the public fair levels are biased away from 10000.

## Relationships

Same-timestamp return correlations are very small. Average absolute return correlation by day was about 0.8 to 1.0 percent. Raw return correlation is therefore not the alpha.

Price-level relationships are stronger:

| Pair | Avg price corr | Min | Max | Avg return corr |
| --- | ---: | ---: | ---: | ---: |
| POLYESTER / COTTON | 0.740 | 0.624 | 0.844 | -0.007 |
| SUEDE / COTTON | 0.446 | 0.305 | 0.665 | -0.000 |
| LAMB_WOOL / NYLON | 0.428 | 0.235 | 0.567 | 0.003 |
| SUEDE / POLYESTER | 0.425 | 0.251 | 0.597 | 0.005 |

The most useful lead-lag effects from offline tests were:

- `SLEEP_POD_SUEDE -> SLEEP_POD_COTTON`, lag 35 to 50, positive future Cotton drift. This looked good offline but did not beat the existing Rust-validated Cotton fair shift in a robust way.
- `SLEEP_POD_NYLON -> SLEEP_POD_LAMB_WOOL`, lag around 44 to 50 and 200, negative future Lamb-Wool drift. This looked coherent offline but is not in the final strategy because the Rust search found stronger Lamb-Wool signals from Cotton and Polyester.
- Existing Rust-validated edges that survived:
  - `LAMB_WOOL <- COTTON`, lag 500, scale -1.0.
  - `LAMB_WOOL <- POLYESTER`, lag 50, scale +1.0.
  - `NYLON <- COTTON`, lag 100, scale +1.0.
  - `NYLON <- SUEDE`, lag 100, scale -0.5.
  - `SUEDE <- LAMB_WOOL`, lag 200, scale +0.1.
  - `SUEDE <- COTTON`, lag 200, scale -0.5.
  - `COTTON <- LAMB_WOOL`, lag 500, scale +0.25.
  - `POLYESTER <- SUEDE`, lag 200, scale -0.05.
  - `POLYESTER <- NYLON`, lag 1, scale +1.0.

## Pair And Basket Tests

Pair residual diagnostics found the best stationary-looking spread in `POLYESTER / COTTON`, with residual ADF t around -3.0 depending on direction. The problem is speed: half-life is hundreds of timestamps, and standalone pair-residual quoting produced only `14,095`, matching a weak Nylon-like mid-maker outcome rather than adding category edge.

Basket regressions against the other four products had large residuals:

| Target | LOO residual reversion h=20 | Train residual sd | Signal frequency |
| --- | ---: | ---: | ---: |
| POLYESTER | 3.601 | 294.7 | 70.1% |
| LAMB_WOOL | 2.001 | 338.2 | 43.5% |
| SUEDE | 1.812 | 377.7 | 81.5% |
| NYLON | 1.768 | 336.0 | 75.1% |
| COTTON | 1.483 | 351.7 | 82.9% |

These residuals revert statistically, but not tightly enough for a position limit of 10 and visible spreads near 10. The final strategy does not use a basket model.

## Order Book Signals

Top-of-book imbalance had small positive future-return correlations, especially Nylon imbalance into Lamb-Wool over 20 to 100 ticks. The edge size was too small versus spread and turnover. It is not included.

## Failed Hypotheses

- Baseline mid market making: positive but too small.
- Single-product momentum: negative total PnL.
- Pair residual trading: too slow and weak.
- Basket synthetic fair values: residuals too persistent and too wide.
- Extra public-score Cotton edge `COTTON <- SUEDE`, lag 20, scale -0.1: +241 public PnL, but rejected as too small and not robust enough.

## Final Strategy

Use a static fair-value market-making and z-take baseline for Suede, Lamb-Wool, Polyester, and Cotton; use current-mid fair for Nylon; then apply same-category lead-lag fair-value shifts. Suede and Cotton also walk visible depth when the fair value is far enough through the book.

All five products are traded. All five products are also used as signals.

Risk controls:

- Per-product position limit is hard capped at 10.
- Orders are sized no larger than remaining legal capacity.
- No timestamp hard-coding.
- No future prices in runtime.
- History window is capped at 501 mids per product.
- Strategy is small enough to merge into the final combined submission.

