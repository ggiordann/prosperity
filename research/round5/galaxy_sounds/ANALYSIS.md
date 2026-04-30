# Galaxy Sounds Recorders Analysis

## Repository Inspection

- Rust backtester: `prosperity_rust_backtester/`.
- Round 5 data: `prosperity_rust_backtester/datasets/round5/`.
- Public Round 5 files loaded: `prices_round_5_day_2.csv`, `prices_round_5_day_3.csv`, `prices_round_5_day_4.csv`, and matching `trades_*.csv` files.
- Current full submission file inspected: `prosperity_rust_backtester/traders/latest_trader.py`.
- Category implementation produced here: `research/round5/galaxy_sounds/galaxy_sounds_strategy.py`.
- Data format: semicolon-delimited prices with 3 bid/ask levels, `mid_price`, and `profit_and_loss`; semicolon-delimited trades with blank Round 5 `buyer`/`seller` fields.
- Product universe: 50 Round 5 products split into 10 categories of 5; this research trades only the 5 Galaxy Sounds products.
- Position limit: the Rust runner maps every Round 5 product prefix, including `GALAXY_SOUNDS_`, to limit `10`.
- Final-file constraints observed: strategy file is 5,846 bytes; imports are only `datamodel`, `typing`, and `json`; no debug prints or external files.

Backtester command pattern:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/galaxy_sounds/galaxy_sounds_strategy.py --dataset round5 --products full --artifact-mode full --flat --run-id galaxy_final_winds78
```

## Product Diagnostics

All five products are tradeable. Average spreads are 13-15 ticks, visible top depth is about 36.5 lots, and 99% one-tick mid jumps are materially larger than half-spread, so passive market making plus selective crossing is feasible. Mid levels are not stationary, but returns are strongly stationary; this argues against naive fixed pair spreads and for either static anchor reversion or causal lagged fair-value shifts.

| product | ret vol | AC1 | mean_reversion_score | momentum_score | spread | top depth | jump99 | volume | mid ADF | decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GALAXY_SOUNDS_BLACK_HOLES | 11.4475 | -0.0159 | 0.0017 | 0.0011 | 14.5128 | 36.5128 | 29.6667 | 1805 | -0.7443 | trade |
| GALAXY_SOUNDS_DARK_MATTER | 10.2439 | -0.0117 | 0.0068 | 0.0019 | 13.0508 | 36.5128 | 26.5000 | 1805 | -1.7959 | trade |
| GALAXY_SOUNDS_PLANETARY_RINGS | 10.8614 | -0.0042 | -0.0004 | -0.0026 | 13.6900 | 36.5128 | 28.1667 | 1805 | -0.8905 | trade |
| GALAXY_SOUNDS_SOLAR_FLAMES | 11.0934 | -0.0122 | 0.0012 | 0.0027 | 14.0715 | 36.5128 | 29.0000 | 1805 | -1.5760 | trade |
| GALAXY_SOUNDS_SOLAR_WINDS | 10.5335 | -0.0078 | -0.0012 | -0.0017 | 13.3013 | 36.5128 | 27.3333 | 1805 | -1.1700 | trade |

Product decisions:

- `GALAXY_SOUNDS_BLACK_HOLES`: trade and use as the main slow leader; current-mid market making is safer than static anchoring.
- `GALAXY_SOUNDS_DARK_MATTER`: trade static anchor mean reversion; also reacts mildly to `BLACK_HOLES`.
- `GALAXY_SOUNDS_PLANETARY_RINGS`: trade static anchor with wide passive edge; product has one weak day but positive total.
- `GALAXY_SOUNDS_SOLAR_WINDS`: trade static anchor and use as a short/medium lag signal for `SOLAR_FLAMES`.
- `GALAXY_SOUNDS_SOLAR_FLAMES`: strongest traded target; receives the clearest relationship alpha.

## Correlation

Same-bar return correlations are tiny, despite some high or unstable level correlations. This category is not a same-timestamp basket arb.

| a | b | price_corr_mean | price_corr_min | price_corr_max | return_corr_mean | return_corr_min | return_corr_max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GALAXY_SOUNDS_PLANETARY_RINGS | GALAXY_SOUNDS_SOLAR_FLAMES | -0.2969 | -0.6346 | 0.2582 | 0.0132 | 0.0004 | 0.0268 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_WINDS | -0.3231 | -0.5941 | -0.1315 | 0.0092 | 0.0005 | 0.0244 |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_PLANETARY_RINGS | 0.2365 | -0.0136 | 0.5105 | 0.0068 | -0.0023 | 0.0154 |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_SOLAR_FLAMES | -0.1553 | -0.5933 | 0.6375 | 0.0042 | 0.0001 | 0.0074 |
| GALAXY_SOUNDS_SOLAR_WINDS | GALAXY_SOUNDS_SOLAR_FLAMES | -0.1781 | -0.6150 | 0.2175 | 0.0041 | -0.0035 | 0.0130 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 0.1106 | -0.1421 | 0.4278 | 0.0021 | -0.0026 | 0.0051 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_PLANETARY_RINGS | -0.0687 | -0.4468 | 0.3204 | 0.0012 | -0.0043 | 0.0049 |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_BLACK_HOLES | 0.2250 | -0.4789 | 0.7537 | 0.0007 | -0.0150 | 0.0139 |
| GALAXY_SOUNDS_PLANETARY_RINGS | GALAXY_SOUNDS_SOLAR_WINDS | -0.0006 | -0.3795 | 0.6968 | -0.0002 | -0.0041 | 0.0073 |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_SOLAR_WINDS | -0.0819 | -0.6254 | 0.6075 | -0.0012 | -0.0113 | 0.0079 |

## Lead-Lag

The strongest causal structure is slow movement into `SOLAR_FLAMES`. Two effects matter in the final strategy:

- `BLACK_HOLES -> SOLAR_FLAMES`, lag 500, negative sign: validated in all three days and inherited from the full-round robust union.
- `SOLAR_WINDS -> SOLAR_FLAMES`, lag 78, positive sign: discovered in the Galaxy-only sweep; nearby lags 70-80 and k values 0.10-0.15 were also profitable, so it is not an exact timestamp fit.

Top lead-lag diagnostics:

| leader | follower | lag | horizon | corr_mean | corr_min | corr_max | slope_mean | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GALAXY_SOUNDS_PLANETARY_RINGS | GALAXY_SOUNDS_SOLAR_FLAMES | 500 | 500 | 0.2271 | 0.1769 | 0.2900 | 0.2069 | 0.2881 |
| GALAXY_SOUNDS_PLANETARY_RINGS | GALAXY_SOUNDS_SOLAR_FLAMES | 400 | 500 | 0.1888 | 0.1203 | 0.2499 | 0.1878 | 0.2286 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 500 | 500 | -0.2404 | -0.4070 | -0.1309 | -0.2420 | 0.1950 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 400 | 500 | -0.2378 | -0.4163 | -0.1305 | -0.2609 | 0.1860 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 300 | 500 | -0.2331 | -0.4196 | -0.1293 | -0.2961 | 0.1780 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 400 | 200 | -0.2052 | -0.3579 | -0.1147 | -0.1398 | 0.1761 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 300 | 200 | -0.1828 | -0.3108 | -0.1068 | -0.1446 | 0.1729 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 500 | 200 | -0.2066 | -0.3699 | -0.1243 | -0.1303 | 0.1712 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 200 | 500 | -0.2107 | -0.3789 | -0.1092 | -0.3292 | 0.1708 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 200 | 200 | -0.1368 | -0.2064 | -0.0905 | -0.1325 | 0.1694 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 150 | 500 | -0.1922 | -0.3439 | -0.0752 | -0.3447 | 0.1617 |
| GALAXY_SOUNDS_SOLAR_WINDS | GALAXY_SOUNDS_SOLAR_FLAMES | 74 | 50 | 0.1080 | 0.0662 | 0.1320 | 0.0905 | 0.1585 |

Final signal day split:

| day | leader | follower | lag | horizon | corr | slope |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 500 | 500 | -0.4070 | -0.4733 |
| 2 | GALAXY_SOUNDS_SOLAR_WINDS | GALAXY_SOUNDS_SOLAR_FLAMES | 78 | 50 | 0.1339 | 0.1162 |
| 3 | GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 500 | 500 | -0.1834 | -0.1577 |
| 3 | GALAXY_SOUNDS_SOLAR_WINDS | GALAXY_SOUNDS_SOLAR_FLAMES | 78 | 50 | 0.0639 | 0.0566 |
| 4 | GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | 500 | 500 | -0.1309 | -0.0951 |
| 4 | GALAXY_SOUNDS_SOLAR_WINDS | GALAXY_SOUNDS_SOLAR_FLAMES | 78 | 50 | 0.1281 | 0.0927 |

## Pairs And Baskets

Pair and basket models looked plausible only for `DARK_MATTER` versus `PLANETARY_RINGS`; the hedged residual passes a rough 5% ADF threshold, but its half-life is above 1,000 ticks. Rust tests confirmed this was too slow and too unstable versus the simple static anchor plus lead-lag strategy.

| a | b | price_corr | return_corr | spread_adf_t | hedge_beta | hedged_adf_t | hedged_half_life | hedged_stationary_5pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_PLANETARY_RINGS | 0.4342 | 0.0065 | -1.6013 | 0.1875 | -2.9835 | 1,149.3 | True |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_SOLAR_FLAMES | -0.0225 | 0.0043 | -2.5268 | -0.0166 | -2.7361 | 1,416.5 | False |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_SOLAR_WINDS | -0.0157 | -0.0011 | -1.9966 | -0.0096 | -2.7292 | 1,420.4 | False |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_BLACK_HOLES | -0.0081 | 0.0001 | -0.9030 | -0.0028 | -2.7292 | 1,421.1 | False |
| GALAXY_SOUNDS_SOLAR_WINDS | GALAXY_SOUNDS_SOLAR_FLAMES | -0.3352 | 0.0042 | -1.7412 | -0.4030 | -2.2069 | 2,337.1 | False |
| GALAXY_SOUNDS_PLANETARY_RINGS | GALAXY_SOUNDS_SOLAR_WINDS | 0.0876 | -0.0000 | -1.3177 | 0.1240 | -1.0516 | 8,314.6 | False |
| GALAXY_SOUNDS_PLANETARY_RINGS | GALAXY_SOUNDS_SOLAR_FLAMES | -0.0091 | 0.0137 | -1.4194 | -0.0155 | -1.0507 | 8,389.2 | False |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_FLAMES | -0.1171 | 0.0021 | -0.4321 | -0.2493 | -0.9308 | 10,727.0 | False |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_WINDS | 0.4653 | 0.0103 | -0.8508 | 0.8242 | -0.7430 | 10,811.0 | False |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_PLANETARY_RINGS | 0.0743 | 0.0016 | 0.2179 | 0.0930 | -0.4354 | 24,621.7 | False |

Basket residuals are highly autocorrelated and mostly non-stationary out of sample:

| target | resid_std | resid_mae | resid_ac1 | resid_adf_t | resid_half_life |
| --- | --- | --- | --- | --- | --- |
| GALAXY_SOUNDS_SOLAR_FLAMES | 476.2732 | 598.3047 | 0.9996 | -1.3197 | 2,001.2 |
| GALAXY_SOUNDS_DARK_MATTER | 450.1320 | 603.2632 | 0.9997 | -1.5329 | 1,847.2 |
| GALAXY_SOUNDS_SOLAR_WINDS | 521.8555 | 956.3001 | 0.9997 | -1.6930 | 1,642.7 |
| GALAXY_SOUNDS_PLANETARY_RINGS | 515.2150 | 1,720.5 | 0.9994 | -0.8187 | inf |
| GALAXY_SOUNDS_BLACK_HOLES | 815.7431 | 2,031.1 | 0.9998 | -0.9943 | inf |

## Order Book Signals

The apparent top order-book imbalance signal is short-horizon and almost identical across all Galaxy products because the public books share symmetric depth patterns. Small negative fair-value overlays improved some variants by a few hundred PnL, but the effect was not better than the lagged `SOLAR_WINDS -> SOLAR_FLAMES` improvement and is not included in the final category strategy.

| signal_product | target | horizon | corr_mean | corr_min | corr_max | same_sign_days |
| --- | --- | --- | --- | --- | --- | --- |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_SOLAR_WINDS | 1 | -0.0586 | -0.0771 | -0.0481 | 1 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_SOLAR_WINDS | 1 | -0.0586 | -0.0771 | -0.0481 | 1 |
| GALAXY_SOUNDS_PLANETARY_RINGS | GALAXY_SOUNDS_SOLAR_WINDS | 1 | -0.0586 | -0.0771 | -0.0481 | 1 |
| GALAXY_SOUNDS_SOLAR_WINDS | GALAXY_SOUNDS_SOLAR_WINDS | 1 | -0.0586 | -0.0771 | -0.0481 | 1 |
| GALAXY_SOUNDS_SOLAR_FLAMES | GALAXY_SOUNDS_SOLAR_WINDS | 1 | -0.0586 | -0.0771 | -0.0481 | 1 |
| GALAXY_SOUNDS_SOLAR_WINDS | GALAXY_SOUNDS_PLANETARY_RINGS | 1 | -0.0580 | -0.0621 | -0.0503 | 1 |
| GALAXY_SOUNDS_BLACK_HOLES | GALAXY_SOUNDS_PLANETARY_RINGS | 1 | -0.0580 | -0.0621 | -0.0503 | 1 |
| GALAXY_SOUNDS_PLANETARY_RINGS | GALAXY_SOUNDS_PLANETARY_RINGS | 1 | -0.0580 | -0.0621 | -0.0503 | 1 |
| GALAXY_SOUNDS_SOLAR_FLAMES | GALAXY_SOUNDS_PLANETARY_RINGS | 1 | -0.0580 | -0.0621 | -0.0503 | 1 |
| GALAXY_SOUNDS_DARK_MATTER | GALAXY_SOUNDS_PLANETARY_RINGS | 1 | -0.0580 | -0.0621 | -0.0503 | 1 |

## Strategy Tests

Main sweep result highlights:

| name | total_pnl | day_2 | day_3 | day_4 | own_trades |
| --- | --- | --- | --- | --- | --- |
| hybrid_add_winds75_to_flames | 282,157.5 | 86,599.5 | 89,170.0 | 106,388.0 | 506 |
| hybrid_add_rings_to_flames | 281,544.5 | 90,212.5 | 88,338.0 | 102,994.0 | 504 |
| hybrid_orderbook_neg50 | 281,111.5 | 87,570.5 | 87,926.0 | 105,615.0 | 509 |
| hybrid_orderbook_neg20 | 280,664.5 | 87,181.5 | 88,269.0 | 105,214.0 | 505 |
| hybrid_current | 280,131.5 | 87,181.5 | 88,102.0 | 104,848.0 | 507 |
| hybrid_flames_k_m0p75 | 275,813.5 | 91,111.5 | 81,758.0 | 102,944.0 | 490 |
| hybrid_flames_k_m1p5 | 273,150.5 | 84,656.5 | 87,856.0 | 100,638.0 | 518 |
| hybrid_flames_k_m1p75 | 272,322.5 | 79,952.5 | 91,016.0 | 101,354.0 | 517 |
| hybrid_no_flames_signal | 272,233.5 | 89,054.5 | 82,203.0 | 100,976.0 | 493 |
| hybrid_flames_k_m1p0 | 271,523.5 | 88,519.5 | 85,035.0 | 97,969.0 | 504 |
| hybrid_flames_only | 270,990.5 | 89,434.0 | 86,306.0 | 95,250.5 | 466 |
| static_shift_nosig | 263,092.5 | 91,307.0 | 80,407.0 | 91,378.5 | 452 |

Refinement around the new `SOLAR_WINDS -> SOLAR_FLAMES` signal:

| name | total_pnl | day_2 | day_3 | day_4 | own_trades |
| --- | --- | --- | --- | --- | --- |
| refine_winds_lag78_k0p15 | 283,385.5 | 87,214.5 | 89,170.0 | 107,001.0 | 509 |
| refine_winds_lag80_k0p15 | 283,179.5 | 87,381.5 | 88,726.0 | 107,072.0 | 507 |
| refine_winds_lag72_k0p15 | 283,088.5 | 87,518.5 | 89,170.0 | 106,400.0 | 508 |
| refine_winds_lag75_k0p15 | 282,784.5 | 87,214.5 | 89,170.0 | 106,400.0 | 507 |
| refine_winds_lag74_k0p15 | 282,784.5 | 87,214.5 | 89,170.0 | 106,400.0 | 507 |
| refine_winds75_obneg20 | 282,690.5 | 86,599.5 | 89,337.0 | 106,754.0 | 504 |
| refine_winds75_rings500 | 282,651.5 | 89,136.5 | 88,373.0 | 105,142.0 | 506 |
| refine_winds_lag70_k0p15 | 282,533.5 | 87,518.5 | 88,886.0 | 106,129.0 | 508 |
| refine_winds_lag76_k0p15 | 282,513.5 | 87,214.5 | 89,170.0 | 106,129.0 | 508 |
| refine_winds_lag74_k0p1 | 282,473.5 | 86,903.5 | 89,170.0 | 106,400.0 | 507 |
| refine_winds_lag72_k0p1 | 282,290.5 | 86,732.5 | 89,170.0 | 106,388.0 | 507 |
| refine_winds_lag75_k0p1 | 282,157.5 | 86,599.5 | 89,170.0 | 106,388.0 | 506 |

## Final Strategy

The final strategy is a compact hybrid:

- `BLACK_HOLES`: current-mid passive market making with small positive shift.
- `DARK_MATTER`, `PLANETARY_RINGS`, `SOLAR_WINDS`, `SOLAR_FLAMES`: static anchor mean reversion with product-specific z-take thresholds and passive quote edges.
- Causal lag overlays using only stored historical mids:
  - `PLANETARY_RINGS -> BLACK_HOLES`, lags 1 and 10.
  - `BLACK_HOLES -> DARK_MATTER`, lags 1 and 50.
  - `SOLAR_FLAMES` and `SOLAR_WINDS -> PLANETARY_RINGS`, lags 500 and 100.
  - `BLACK_HOLES -> SOLAR_FLAMES`, lag 500.
  - `SOLAR_WINDS -> SOLAR_FLAMES`, lag 78.
  - `BLACK_HOLES -> SOLAR_WINDS`, lag 50.

Final backtest:

| day | pnl | own_trades |
| --- | --- | --- |
| D+2 | 87,214.5 | 132 |
| D+3 | 89,170.0 | 187 |
| D+4 | 107,001.0 | 190 |
| TOTAL | 283,385.5 | 509 |

Final PnL by product:

| product | day_2 | day_3 | day_4 | total |
| --- | --- | --- | --- | --- |
| GALAXY_SOUNDS_BLACK_HOLES | 14,658.5 | 14,142.0 | 21,124.0 | 49,924.5 |
| GALAXY_SOUNDS_DARK_MATTER | 14,473.0 | 31,791.0 | 18,118.0 | 64,382.0 |
| GALAXY_SOUNDS_PLANETARY_RINGS | 13,200.0 | -1,655.0 | 37,537.0 | 49,082.0 |
| GALAXY_SOUNDS_SOLAR_FLAMES | 25,975.0 | 28,622.0 | 22,587.0 | 77,184.0 |
| GALAXY_SOUNDS_SOLAR_WINDS | 18,908.0 | 16,270.0 | 7,635.0 | 42,813.0 |

## Validation

- Public day split is stable: final PnL is positive on days 2, 3, and 4.
- Inherited hybrid benchmark: `280,131.5`; final: `283,385.5`, improving all three days by `+33.0`, `+1,068.0`, and `+2,153.0`.
- Walk-forward framing: day 2 as first public train/diagnostic day, days 3-4 as tests; days 2+3 as train/diagnostic, day 4 as test; leave-one-day-out basket fits rejected.
- Parameter perturbation passed for the added signal: lags 70, 72, 74, 75, 76, 78, and 80 with k 0.10-0.15 all stayed near or above the inherited hybrid, with best at lag 78/k 0.15.
- Overfitting controls rejected exact basket coefficients, pair-only trading, pure momentum, pure order-book overlay, and passive-only quoting.

## Risks

- Most PnL still comes from public-data anchor levels; if final hidden data shifts regime hard, static anchors can accumulate inventory.
- `PLANETARY_RINGS` had a negative day 3 despite positive total.
- The incremental `SOLAR_WINDS -> SOLAR_FLAMES` alpha is modest, so it should be included only as a small fair-value overlay, as implemented.
- Category strategy assumes no cross-category risk netting; later combined submission should keep per-product limit accounting unchanged.

## Recommendation

Include this Galaxy Sounds strategy in the final combined Round 5 submission. It is compact, causal, under 100KB by a wide margin, improves the inherited Galaxy subset, and passed day split plus perturbation checks.
