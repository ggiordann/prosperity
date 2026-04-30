# Round 5 Domestic Robotics Analysis

Scope: `ROBOT_VACUUMING`, `ROBOT_MOPPING`, `ROBOT_DISHES`, `ROBOT_LAUNDRY`, `ROBOT_IRONING`.

## Repository Findings

- Rust backtester: `prosperity_rust_backtester/`
- Backtester entry point: `prosperity_rust_backtester/src/main.rs`; CLI/backtest flow in `src/cli.rs` and matching in `src/runner.rs`.
- Normal run command from the backtester directory:

```bash
./scripts/cargo_local.sh run --release -- --trader <trader.py> --dataset round5 --products full
```

- Round 5 data: `prosperity_rust_backtester/datasets/round5/`
- Price CSVs: `prices_round_5_day_2.csv`, `prices_round_5_day_3.csv`, `prices_round_5_day_4.csv`
- Trade CSVs: `trades_round_5_day_2.csv`, `trades_round_5_day_3.csv`, `trades_round_5_day_4.csv`
- Price format: semicolon CSV with `day`, `timestamp`, `product`, 3 bid/ask levels, `mid_price`, `profit_and_loss`.
- Trade format: semicolon CSV with `timestamp`, blank `buyer`/`seller`, `symbol`, `currency`, `price`, `quantity`.
- Current full submission file: `prosperity_rust_backtester/traders/latest_trader.py`.
- Backtester position limits: every Round 5 product prefix, including `ROBOT_`, is capped at 10.
- Final file constraints: use `datamodel` imports, allowed standard-library helpers only, and remain under 100KB. The robotics implementation is 4,531 bytes.

## Product Diagnostics

Aggregate across days 2, 3, and 4:

| product | avg spread | avg top depth | ret vol | ret ac1 | jump95 | trade vol | read |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| ROBOT_DISHES | 7.35 | 15.23 | 15.71 | -0.098 | 46.17 | 1805 | Tradable, but day 4 jump tail is the main risk. |
| ROBOT_IRONING | 6.39 | 16.70 | 10.33 | -0.118 | 20.00 | 1805 | Best mean-reversion profile. Trade. |
| ROBOT_LAUNDRY | 7.17 | 16.10 | 9.81 | 0.006 | 19.00 | 1805 | Tradable anchor product; weak self mean reversion. |
| ROBOT_MOPPING | 7.97 | 14.13 | 11.13 | -0.012 | 21.67 | 1805 | Tradable, but more directional. |
| ROBOT_VACUUMING | 6.75 | 17.15 | 9.22 | -0.008 | 18.00 | 1805 | Lower standalone PnL; still useful and profitable. |

Passive market making is feasible by spread, but inventory drift is material. Aggressive crossing is feasible only when anchored fair value is far from the visible book; raw current-mid momentum is bad.

## Relationships

Return correlations are almost zero; price-level correlations exist mostly because products share slow regime movement:

| pair | price corr | return corr | note |
| --- | ---: | ---: | --- |
| VACUUMING / LAUNDRY | 0.787 | -0.002 | Best stationary pair candidate. |
| MOPPING / IRONING | -0.815 | -0.000 | Strong level relation, no return timing. |
| VACUUMING / IRONING | 0.784 | 0.012 | Weak but consistent level relation. |

Stable lead-lag tests from lags 1 to 100 found only tiny return correlations. Best examples:

| leader -> follower | lag | mean corr |
| --- | ---: | ---: |
| MOPPING -> LAUNDRY | 38 | 0.0199 |
| VACUUMING -> MOPPING | 17 | -0.0194 |
| DISHES -> IRONING | 88 | -0.0184 |
| VACUUMING -> IRONING | 44 | -0.0172 |

The final strategy uses the more robust PnL-validated longer-lag overlays from the existing Round 5 search:

| follower | leader | lag | coeff |
| --- | --- | ---: | ---: |
| ROBOT_DISHES | ROBOT_IRONING | 200 | -0.50 |
| ROBOT_DISHES | ROBOT_IRONING | 200 | -0.05 |
| ROBOT_IRONING | ROBOT_MOPPING | 20 | -0.25 |
| ROBOT_IRONING | ROBOT_VACUUMING | 2 | -0.25 |
| ROBOT_LAUNDRY | ROBOT_MOPPING | 500 | 1.00 |
| ROBOT_LAUNDRY | ROBOT_VACUUMING | 500 | 1.00 |
| ROBOT_MOPPING | ROBOT_DISHES | 500 | -0.05 |
| ROBOT_MOPPING | ROBOT_VACUUMING | 20 | -0.10 |
| ROBOT_VACUUMING | ROBOT_MOPPING | 100 | 0.05 |
| ROBOT_VACUUMING | ROBOT_LAUNDRY | 200 | -0.25 |

Pair and basket diagnostics:

- `ROBOT_VACUUMING - 0.686 * ROBOT_LAUNDRY` residual is stationary-ish, but half-life is about 1,000 ticks, so it is slow.
- Basket synthetic fair values fit levels well, but residual autocorrelation is above 0.997, so deviations are persistent and dangerous as a pure mean-reversion trade.
- Order book imbalance has weak predictive correlations, max around 0.03 for 1-tick horizons. It did not improve Rust PnL.

## Product Decisions

- Trade: all five robotics products.
- Use as signals: all five, through capped mid histories.
- Ignore within category: none.
- Strongest alpha source: product-specific static anchors plus selected long-lag same-category overlays.
- Weakest leg: `ROBOT_DISHES`, because day 4 has large upward jumps and a negative final PnL, but dropping it lowers total category PnL too much.

## Final Strategy

File: `research/round5/robotics/robotics_trader.py`

Mechanics:

- Static fair values per product.
- Product-specific crossing thresholds and passive quote edges.
- Depth walking only for `ROBOT_DISHES` and `ROBOT_LAUNDRY`.
- Rolling mid histories capped at 501 ticks.
- Same-category lead-lag fair-value shifts.
- No timestamp hardcoding, no future data reads, no external files at runtime.
