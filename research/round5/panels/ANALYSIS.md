# Round 5 Construction Panels Analysis

Scope: `PANEL_1X2`, `PANEL_2X2`, `PANEL_1X4`, `PANEL_2X4`, `PANEL_4X4`.

## Repository And Data Map

- Rust backtester: `prosperity_rust_backtester/`
- Backtester runner: `prosperity_rust_backtester/src/main.rs` / `src/cli.rs`
- Normal command form: `cd prosperity_rust_backtester && ./scripts/cargo_local.sh run --release -- --trader traders/latest_trader.py --dataset round5 --products summary`
- Round 5 CSVs: `prosperity_rust_backtester/datasets/round5/`
- Price files: `prices_round_5_day_2.csv`, `prices_round_5_day_3.csv`, `prices_round_5_day_4.csv`
- Trade files: `trades_round_5_day_2.csv`, `trades_round_5_day_3.csv`, `trades_round_5_day_4.csv`
- Current all-product trader context: `prosperity_rust_backtester/traders/latest_trader.py`
- Panel-only implementation: `research/round5/panels/panel_trader.py`

Round 5 price format is semicolon-delimited with `day`, `timestamp`, `product`, three bid levels, three ask levels, `mid_price`, and `profit_and_loss`. Trade format is semicolon-delimited with `timestamp`, `buyer`, `seller`, `symbol`, `currency`, `price`, `quantity`.

Round 5 has 50 products. All products in this category use position limit 10. Final submission constraints are compatible with this implementation: correct `datamodel` import style, standard-library-only extras, no unsupported packages, no timestamp hard-coding, and the category file is 3,482 bytes, well below 100KB.

## Product Diagnostics

All panels have complete quote data for 30,000 public timestamps and identical public market trade volume, 1,805 units per product.

| Product | Mean Mid | Avg Spread | Avg Top Depth | Avg 3-Level Depth | Ret Vol | Ret AC1 | ADF-Like t | Trade Qty | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `PANEL_1X2` | 8922.7 | 11.51 | 36.51 | 99.14 | 9.05 | -0.003 | -1.63 | 1805 | Trade; strong anchor and lag response |
| `PANEL_2X2` | 9576.6 | 8.52 | 23.66 | 59.09 | 9.60 | -0.010 | -1.30 | 1805 | Trade smaller; useful follower |
| `PANEL_1X4` | 9397.6 | 8.38 | 24.38 | 59.09 | 9.48 | -0.002 | -1.11 | 1805 | Trade; day 2 risk, positive total |
| `PANEL_2X4` | 11265.4 | 9.84 | 21.74 | 59.09 | 11.29 | -0.001 | -1.73 | 1805 | Trade; best product PnL |
| `PANEL_4X4` | 9878.7 | 8.75 | 22.64 | 59.09 | 9.96 | -0.006 | -1.54 | 1805 | Trade; strong lag/anchor edge |

Return autocorrelation is close to zero; simple one-product mean reversion is weak. ADF-like diagnostics do not support tight stationarity. Market making is feasible only conservatively at the current best bid/ask; improving inside the spread overtrades. Aggressive crossing is feasible only when the product is hundreds of ticks away from slow fair value.

## Relationship Findings

Area-normalized prices are not stable. Same-area products `PANEL_2X2` and `PANEL_1X4` are not interchangeable: daily price correlations were 0.330, 0.084, and 0.696, while return correlations were near zero.

Simple basket relationships failed. Regressing each product against the other four products had good in-sample fits on some train windows, but holdout-day R² was negative almost everywhere. Pair residuals had AR(1) coefficients near 1.0 and practical half-lives at random-walk scale, so classic pair or basket residual z-score trading was rejected.

Lead-lag was weak but useful when treated as a fair-value tilt rather than a standalone predictor. Return lead-lag correlations from 1 to 100 timestamps were small, with the best stable values around 0.02. Slower windowed deltas were more useful; the robust additions retained were:

- `PANEL_2X2` 200-tick move negatively tilts `PANEL_1X2`
- `PANEL_1X2` 50-tick move positively tilts `PANEL_2X2`
- `PANEL_1X2` and `PANEL_4X4` moves tilt `PANEL_1X4`
- `PANEL_1X4` moves plus a small `PANEL_1X2` 200-tick term tilt `PANEL_2X4`
- `PANEL_2X2` and `PANEL_2X4` moves tilt `PANEL_4X4`

Order book imbalance showed small same-sign predictive correlations, especially `PANEL_1X2` and `PANEL_2X4` imbalance into 1-tick future moves. It did not survive execution well enough to keep; a tested imbalance tilt added only about 10 PnL and was excluded as noise.

## Strategy Selected

The selected category strategy is a slow-anchor relative-value trader:

- Product-specific slow fair anchors, not area-normalized fair values.
- Sparse lagged cross-panel fair-value tilts.
- Rare aggressive crossing only when visible prices are far beyond fair.
- Conservative passive quoting at the current best bid/ask when fair edge allows.
- Position limit 10 per product.
- Tracks only the last 501 mids per panel in `traderData`.

Products traded: all five panel products. Products ignored: none.

Strongest alpha source: slow product-specific fair anchors combined with sparse cross-panel lag tilts, especially `PANEL_2X2 -> PANEL_4X4`, `PANEL_2X2 -> PANEL_1X2`, and the added `PANEL_1X2 -> PANEL_2X4` term.

Rejected alpha sources: area normalization, same-area pair trading, basket regression residuals, continuous market making, inside-spread improvement, and standalone order book imbalance.
