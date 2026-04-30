# Round 5 Oxygen Shakes Analysis

Category:

- `OXYGEN_SHAKE_MORNING_BREATH`
- `OXYGEN_SHAKE_EVENING_BREATH`
- `OXYGEN_SHAKE_MINT`
- `OXYGEN_SHAKE_CHOCOLATE`
- `OXYGEN_SHAKE_GARLIC`

Data source: `prosperity_rust_backtester/datasets/round5`.

Rust backtester: `prosperity_rust_backtester/`, run with:

```bash
cd /Users/giordanmasen/Desktop/projects/prosperity/prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/oxygen_shakes/oxygen_shakes_strategy.py --dataset round5 --products full --artifact-mode none
```

Current broad submission candidate: `prosperity_rust_backtester/traders/latest_trader.py`.

Final category implementation: `research/round5/oxygen_shakes/oxygen_shakes_strategy.py`.

## Repository Findings

- Round 5 CSV files are in `prosperity_rust_backtester/datasets/round5`.
- Available days are public days `2`, `3`, and `4`.
- Each price file has 500,000 rows: 10,000 timestamps times 50 products.
- Price CSV columns are semicolon-separated top-three book levels plus `mid_price` and `profit_and_loss`.
- Trade CSV columns are semicolon-separated `timestamp;buyer;seller;symbol;currency;price;quantity`.
- Round 5 product limits are implemented in `prosperity_rust_backtester/src/runner.rs`: every prefix matching `OXYGEN_SHAKE_` has limit `10`.
- The backtester embeds the Prosperity `datamodel`; final trader imports should be Prosperity-compatible. The category implementation uses only `datamodel`, `typing`, and `json`.
- The implementation is 5,979 bytes, comfortably below the final 100KB combined-file constraint.

## Product Diagnostics

All five products have synchronized trade counts and total public quantity. Across days 2-4, each Oxygen product has 733 public trade rows and 5,415 total traded quantity. Mean visible top-three total depth is about 99 units, so passive quoting is feasible, but the 10-lot position cap makes inventory selection matter more than raw size.

| Product | Mean Mid | Price Std | Return Std | Ret AC1 | ADF-lite t | Mean Spread | Trade Qty | Jump >20 | Max Jump | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Morning Breath | 10000.45 | 652.79 | 10.10 | -0.005 | -1.25 | 12.78 | 5415 | 4.65% | 40.0 | Trade and signal |
| Evening Breath | 9271.90 | 399.81 | 10.98 | -0.123 | -2.71 | 11.86 | 5415 | 1.56% | 100.0 | Trade and signal |
| Mint | 9838.39 | 508.12 | 9.88 | -0.003 | -1.64 | 12.59 | 5415 | 4.01% | 42.0 | Trade and signal |
| Chocolate | 9556.88 | 560.59 | 10.89 | -0.089 | -1.14 | 12.19 | 5415 | 3.14% | 103.5 | Trade, mainly market make |
| Garlic | 11925.64 | 953.33 | 12.01 | -0.004 | -1.06 | 15.05 | 5415 | 9.27% | 48.0 | Trade cautiously and signal |

Stationarity conclusion: price levels are not strongly stationary. The ADF-lite regression t-stat is not strong enough to trust raw level mean reversion alone, except Evening Breath is closer than the others. Returns are close to white noise at same timestamp, so the real edge is not contemporaneous correlation.

Market-making conclusion: feasible but not enough alone. Pure mid-price market making made about 68K with nearly 3,000 fills. The selected hybrid made 242.7K with only 450 fills.

Aggressive crossing conclusion: feasible when large deviations from robust static fair values appear. The final strategy crosses only under wide deviation thresholds and otherwise quotes passively.

## Relationships

### Correlation

Price correlations are unstable by day and often flip sign. Examples:

- Chocolate/Garlic price correlation: `-0.628` on day 2, `0.578` on day 3, `0.894` on day 4.
- Morning/Evening price correlation: `-0.290` on day 2, `-0.481` on day 3, `0.345` on day 4.
- Mint/Garlic price correlation: `-0.041` on day 2, `-0.546` on day 3, `0.402` on day 4.

Same-timestamp return correlations are tiny, mostly around `0.00` to `0.02`. This rejects simple same-tick pair-following.

### Lead-Lag

Lagged source moves are much more useful than same-tick returns. Stable examples from source past move versus target future move:

- Morning 500-tick move predicts Garlic 100-tick future move negatively: mean corr `-0.106`.
- Morning 500-tick move predicts Mint 100-tick future move negatively: mean corr `-0.095`.
- Evening 100-tick move predicts Morning 100-tick future move negatively: mean corr `-0.096`.
- Evening 500-tick move predicts Mint 100-tick future move positively: mean corr `0.087`.
- Chocolate 100-tick move predicts Evening 100-tick future move positively: mean corr `0.080`.

However, adding all statistically interesting lead-lag signals degraded live backtest PnL. The final strategy keeps the smaller signal set that survived direct ablation:

- Morning fair uses Mint 500-tick and 10-tick differential moves.
- Evening fair uses Morning 200-tick and Chocolate 5-tick moves.
- Mint fair uses Garlic 200-tick move.
- Chocolate fair uses Evening 50-tick and Garlic 2-tick moves.
- Garlic fair uses Mint 500-tick and 200-tick differential moves.

### Pair Trading

Raw pair spreads are not stable enough for standalone pair trading:

- Morning minus Evening spread mean moved from `1399.7` to `706.8` to `79.1` across days.
- Morning minus Garlic spread mean moved from `-474.0` to `-1896.7` to `-3404.9`.
- Mint minus Chocolate spread mean moved from `537.7` to `1021.9` to `-715.0`.

Estimated spread AR(1) half-lives are often hundreds to thousands of ticks. This is too slow and unstable relative to the 10-lot cap and turnover costs.

### Basket Fair Value

Leave-one-day-out OLS basket regressions against the other four products produced large residual mean shifts and very slow residual mean reversion:

- Residual AR(1) phi usually landed around `0.998` to `0.9999`.
- Residual half-lives ranged from hundreds to several thousand ticks.
- Residual means shifted by hundreds to nearly two thousand price units out of sample.

Basket fair values are useful as research context, but not robust enough to trade directly in this category.

### Order Book Signals

Visible imbalance has a weak negative relation to short-horizon returns, but the imbalance series is effectively identical across the five products because the public book shape/volumes are synchronized. That makes it more likely to be a common book-construction artifact than a product-specific edge. It is not used in the final strategy.

## Strategy Choice

Selected strategy: compact hybrid of static fair-value reversion, restrained passive market making, and a small set of lagged cross-product fair-value adjustments.

Why this strategy:

- Best ablation result across the tested family: `242,742` PnL.
- Positive on every public day: `65,431`, `118,668`, `58,643`.
- Every traded Oxygen product is positive overall.
- Pure market making, pure static variants, added lead-lag variants, and parameter perturbations were all worse.
- No exact timestamp hard-coding.
- No lookahead inside `Trader.run`.
- Uses only compact historical mid arrays capped at 501 observations.

Products traded: all five.

Products ignored: none.

Products used as signals: all five, with Mint and Garlic especially important as cross-product leaders.

Strongest alpha source: static fair-value reversion plus validated lagged cross-product fair shifts. The lag signals add about 39.9K versus the no-signal ablation.

Recommendation: include this Oxygen Shakes strategy in the final combined Round 5 submission unless a portfolio-level interaction later requires reducing category risk.
