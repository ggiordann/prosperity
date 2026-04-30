# UV-Visors Round 5 Analysis

Scope: `UV_VISOR_YELLOW`, `UV_VISOR_AMBER`, `UV_VISOR_ORANGE`, `UV_VISOR_RED`, `UV_VISOR_MAGENTA` only.

## Repository And Data

- Rust backtester: `prosperity_rust_backtester/`.
- Backtester command: `cd prosperity_rust_backtester && ./scripts/cargo_local.sh run --release -- --trader <file> --dataset round5 --products full`.
- Round 5 data: `prosperity_rust_backtester/datasets/round5/prices_round_5_day_{2,3,4}.csv` and matching `trades_round_5_day_{2,3,4}.csv`.
- Current submission path: `prosperity_rust_backtester/traders/latest_trader.py`.
- Data format: semicolon-delimited price rows with three visible bid/ask levels plus `mid_price`; trade rows with `timestamp`, blank `buyer`/`seller`, `symbol`, `price`, and `quantity`.
- Products: 50 total Round 5 products, grouped as 10 categories of 5; all Round 5 products have limit 10 in `prosperity_rust_backtester/src/runner.rs`.
- Final constraints: one Python submission under 100KB with Prosperity `datamodel` imports and standard-library-only runtime code.

## Product Diagnostics

| product | mid_mean | mid_std | ret_vol | ret_ac1 | mean_reversion_score | momentum_20 | avg_spread | avg_top_depth | trade_volume | jump_95 | role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UV_VISOR_AMBER | 7911.6963 | 282.6513 | 7.9549 | -0.0038 | 0.0038 | 0.0016 | 10.3205 | 36.5396 | 1805 | 15.6667 | trade_and_signal |
| UV_VISOR_MAGENTA | 11111.7929 | 330.2968 | 11.1914 | -0.0034 | 0.0034 | -0.0074 | 14.0916 | 36.5128 | 1805 | 22.0000 | trade_and_signal |
| UV_VISOR_ORANGE | 10426.5062 | 352.6002 | 10.4544 | 0.0015 | -0.0015 | 0.0050 | 13.2841 | 36.5128 | 1805 | 20.6667 | trade_and_signal |
| UV_VISOR_RED | 11063.2936 | 280.6754 | 11.0168 | -0.0039 | 0.0039 | -0.0087 | 14.0394 | 36.5128 | 1805 | 21.5000 | trade_and_signal |
| UV_VISOR_YELLOW | 10957.4607 | 559.8579 | 10.9986 | 0.0032 | -0.0032 | -0.0021 | 13.9100 | 36.5128 | 1805 | 21.3500 | trade_and_signal |

All five UV-visors are tradeable. Spreads average around 13 ticks and visible top depth around 36 lots, so passive making is feasible. Aggressive crossing is useful only when a relationship signal moves fair value well beyond half-spread; blind crossing is too expensive.

## Spectrum And Curve

Adjacent return correlations are weak; the ordered colour spectrum is not a simple same-bar gradient. The exploitable structure is slower, with long-lag movements and product-specific offsets rather than tight adjacent spreads.

| a | b | mean | min | max | std |
| --- | --- | --- | --- | --- | --- |
| UV_VISOR_AMBER | UV_VISOR_ORANGE | 0.0044 | 0.0016 | 0.0085 | 0.0036 |
| UV_VISOR_ORANGE | UV_VISOR_RED | 0.0196 | 0.0049 | 0.0291 | 0.0129 |
| UV_VISOR_RED | UV_VISOR_MAGENTA | 0.0053 | -0.0128 | 0.0167 | 0.0159 |
| UV_VISOR_YELLOW | UV_VISOR_AMBER | -0.0021 | -0.0071 | 0.0067 | 0.0077 |

Butterfly residuals are persistent and not cleanly stationary, so curve trades are useful as diagnostics but not as the main live signal.

| butterfly | resid_mean | resid_std | adf_t | half_life |
| --- | --- | --- | --- | --- |
| UV_VISOR_AMBER - 0.5*(UV_VISOR_YELLOW+UV_VISOR_ORANGE) | -2780.2872 | 1285.8792 | -2.3121 | 6061.7488 |
| UV_VISOR_RED - 0.5*(UV_VISOR_ORANGE+UV_VISOR_MAGENTA) | 294.1440 | 605.4597 | -1.5608 | 3434.3020 |
| UV_VISOR_ORANGE - 0.5*(UV_VISOR_AMBER+UV_VISOR_RED) | 939.0113 | 849.1097 | -1.2115 | 6774.8487 |

## Correlation

Price levels can look highly related or anti-related, but return correlations are small and unstable. This argues against plain pair z-score trading without a separate timing signal.

| a | b | mean | min | max | std |
| --- | --- | --- | --- | --- | --- |
| UV_VISOR_YELLOW | UV_VISOR_MAGENTA | 0.3089 | 0.0128 | 0.7861 | 0.4172 |
| UV_VISOR_ORANGE | UV_VISOR_RED | 0.0755 | -0.0719 | 0.3120 | 0.2069 |
| UV_VISOR_AMBER | UV_VISOR_ORANGE | -0.0939 | -0.5881 | 0.3710 | 0.4802 |
| UV_VISOR_ORANGE | UV_VISOR_MAGENTA | -0.1021 | -0.1933 | 0.0495 | 0.1322 |
| UV_VISOR_AMBER | UV_VISOR_RED | -0.2096 | -0.5089 | 0.0114 | 0.2688 |
| UV_VISOR_YELLOW | UV_VISOR_AMBER | -0.2283 | -0.9089 | 0.3917 | 0.6524 |
| UV_VISOR_YELLOW | UV_VISOR_RED | -0.2589 | -0.6986 | 0.1229 | 0.4138 |
| UV_VISOR_YELLOW | UV_VISOR_ORANGE | -0.2719 | -0.4712 | 0.1006 | 0.3228 |
| UV_VISOR_RED | UV_VISOR_MAGENTA | -0.3265 | -0.4654 | -0.1134 | 0.1874 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | -0.3304 | -0.7501 | 0.1644 | 0.4619 |

| a | b | mean | min | max | std |
| --- | --- | --- | --- | --- | --- |
| UV_VISOR_ORANGE | UV_VISOR_RED | 0.0196 | 0.0049 | 0.0291 | 0.0129 |
| UV_VISOR_YELLOW | UV_VISOR_MAGENTA | 0.0091 | -0.0043 | 0.0221 | 0.0132 |
| UV_VISOR_YELLOW | UV_VISOR_RED | 0.0077 | -0.0085 | 0.0197 | 0.0145 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 0.0066 | 0.0002 | 0.0130 | 0.0064 |
| UV_VISOR_ORANGE | UV_VISOR_MAGENTA | 0.0066 | 0.0006 | 0.0120 | 0.0058 |
| UV_VISOR_RED | UV_VISOR_MAGENTA | 0.0053 | -0.0128 | 0.0167 | 0.0159 |
| UV_VISOR_YELLOW | UV_VISOR_ORANGE | 0.0045 | -0.0050 | 0.0099 | 0.0082 |
| UV_VISOR_AMBER | UV_VISOR_ORANGE | 0.0044 | 0.0016 | 0.0085 | 0.0036 |
| UV_VISOR_AMBER | UV_VISOR_RED | -0.0014 | -0.0109 | 0.0101 | 0.0107 |
| UV_VISOR_YELLOW | UV_VISOR_AMBER | -0.0021 | -0.0071 | 0.0067 | 0.0077 |

## Lead-Lag

The strongest robust UV alpha is slow leader/follower fair-value shifting. `AMBER -> MAGENTA` at lag 500 and `RED -> AMBER` at lag 500 are the cleanest category relationships; `YELLOW -> MAGENTA` has a smaller but stable negative-sign effect.

| leader | follower | lag | horizon | corr_mean | corr_min | corr_max | edge_mean | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UV_VISOR_RED | UV_VISOR_YELLOW | 500 | 100 | -0.1959 | -0.2465 | -0.1511 | -17.5795 | 0.3739 |
| UV_VISOR_RED | UV_VISOR_YELLOW | 400 | 100 | -0.1698 | -0.1905 | -0.1499 | -15.1634 | 0.3329 |
| UV_VISOR_RED | UV_VISOR_YELLOW | 300 | 100 | -0.1611 | -0.2160 | -0.1004 | -13.0172 | 0.3044 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 150 | 100 | -0.1475 | -0.1928 | -0.0719 | -10.2196 | 0.2768 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 200 | 100 | -0.1416 | -0.2073 | -0.0330 | -9.7432 | 0.2587 |
| UV_VISOR_RED | UV_VISOR_YELLOW | 500 | 50 | -0.1275 | -0.1623 | -0.0903 | -8.8324 | 0.2461 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 100 | 100 | -0.1143 | -0.1610 | -0.0889 | -9.6827 | 0.2197 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 200 | 50 | -0.1156 | -0.1501 | -0.0553 | -4.8209 | 0.2196 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 99 | 100 | -0.1137 | -0.1598 | -0.0898 | -9.7657 | 0.2186 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 150 | 50 | -0.1121 | -0.1401 | -0.0782 | -6.3431 | 0.2173 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 98 | 100 | -0.1129 | -0.1585 | -0.0899 | -9.6051 | 0.2173 |
| UV_VISOR_RED | UV_VISOR_YELLOW | 400 | 50 | -0.1117 | -0.1404 | -0.0806 | -7.1039 | 0.2169 |
| UV_VISOR_RED | UV_VISOR_YELLOW | 200 | 100 | -0.1148 | -0.1620 | -0.0487 | -11.5769 | 0.2167 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 97 | 100 | -0.1121 | -0.1572 | -0.0884 | -9.4496 | 0.2157 |

## Pair And Basket Tests

Only `AMBER`/`MAGENTA` has a hedged residual passing the rough ADF 5% threshold. Even there, the half-life is long enough that passive execution around fair value beats explicit spread inventory bets.

| a | b | adjacent | spread_std | spread_adf_t | spread_half_life | hedge_beta | resid_std | resid_adf_t | resid_half_life |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | False | 1559.2221 | -1.9542 | 6996.1328 | -1.4092 | 496.2845 | -3.1210 | 1058.0384 |
| UV_VISOR_YELLOW | UV_VISOR_RED | False | 1079.3127 | -0.7969 | 9984.6901 | -0.5134 | 611.3904 | -2.5332 | 2361.2886 |
| UV_VISOR_RED | UV_VISOR_MAGENTA | True | 704.4307 | -1.8755 | 2816.7792 | 0.2997 | 558.2057 | -1.8723 | 3066.0762 |
| UV_VISOR_AMBER | UV_VISOR_RED | False | 1424.3836 | -2.0333 | 6281.5518 | -0.9984 | 805.9461 | -1.7238 | 4095.9979 |
| UV_VISOR_YELLOW | UV_VISOR_ORANGE | False | 883.8339 | -1.5572 | 4560.0200 | -0.0217 | 681.6919 | -1.4459 | 5163.7299 |
| UV_VISOR_ORANGE | UV_VISOR_MAGENTA | False | 533.6315 | -1.8146 | 2274.7246 | 0.5244 | 446.7937 | -1.3909 | 3176.5096 |
| UV_VISOR_AMBER | UV_VISOR_ORANGE | True | 1441.2104 | -1.7304 | 7568.2441 | -1.2867 | 701.3769 | -1.3270 | 4084.3862 |
| UV_VISOR_YELLOW | UV_VISOR_AMBER | True | 1272.9747 | -2.5117 | 4542.2608 | -0.0814 | 676.9495 | -1.3007 | 5667.1332 |
| UV_VISOR_YELLOW | UV_VISOR_MAGENTA | False | 776.6656 | -1.3106 | 4443.1313 | 0.3162 | 653.6092 | -1.2678 | 5357.1488 |
| UV_VISOR_ORANGE | UV_VISOR_RED | True | 615.8909 | -1.2854 | 3797.0074 | 0.3897 | 500.6887 | -1.0079 | 5265.3151 |

Leave-one-day-out basket fair values reduce level error for some products, but residuals have near-unit autocorrelation and unstable intercepts. They are weaker than using the same relationships as lagged fair-value nudges.

| target | resid_std | resid_mae | resid_ac1 | resid_adf_t | half_life |
| --- | --- | --- | --- | --- | --- |
| UV_VISOR_MAGENTA | 286.9216 | 383.4056 | 0.9988 | -2.4420 | 768.7979 |
| UV_VISOR_ORANGE | 450.7827 | 395.7512 | 0.9995 | -1.0343 | inf |
| UV_VISOR_AMBER | 386.9361 | 781.9420 | 0.9992 | -1.9893 | 1362.9571 |
| UV_VISOR_YELLOW | 702.0014 | 850.8558 | 0.9996 | -1.4213 | 3161.3478 |
| UV_VISOR_RED | 313.7170 | 1001.7906 | 0.9990 | -2.4917 | 632.4584 |

## Order Book Signals

Top-book imbalance has statistical signal, especially self-imbalance at short horizons, but the average edge is small versus the spread. I kept it out of the final compact strategy to reduce turnover and overfit risk.

| source | target | horizon | corr_mean | corr_min | corr_max | edge_mean | score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UV_VISOR_MAGENTA | UV_VISOR_YELLOW | 1 | -0.0605 | -0.0655 | -0.0575 | -0.1256 | 0.1210 |
| UV_VISOR_ORANGE | UV_VISOR_YELLOW | 1 | -0.0605 | -0.0655 | -0.0575 | -0.1256 | 0.1210 |
| UV_VISOR_RED | UV_VISOR_YELLOW | 1 | -0.0605 | -0.0655 | -0.0575 | -0.1256 | 0.1210 |
| UV_VISOR_AMBER | UV_VISOR_YELLOW | 1 | -0.0605 | -0.0655 | -0.0575 | -0.1256 | 0.1210 |
| UV_VISOR_YELLOW | UV_VISOR_YELLOW | 1 | -0.0605 | -0.0655 | -0.0575 | -0.1256 | 0.1210 |
| UV_VISOR_AMBER | UV_VISOR_MAGENTA | 1 | -0.0590 | -0.0622 | -0.0560 | -0.1259 | 0.1180 |
| UV_VISOR_RED | UV_VISOR_MAGENTA | 1 | -0.0590 | -0.0622 | -0.0560 | -0.1259 | 0.1180 |
| UV_VISOR_ORANGE | UV_VISOR_MAGENTA | 1 | -0.0590 | -0.0622 | -0.0560 | -0.1259 | 0.1180 |
| UV_VISOR_MAGENTA | UV_VISOR_MAGENTA | 1 | -0.0590 | -0.0622 | -0.0560 | -0.1259 | 0.1180 |
| UV_VISOR_YELLOW | UV_VISOR_MAGENTA | 1 | -0.0590 | -0.0622 | -0.0560 | -0.1259 | 0.1180 |
| UV_VISOR_AMBER | UV_VISOR_AMBER | 1 | -0.0583 | -0.0657 | -0.0509 | -0.0891 | 0.1167 |
| UV_VISOR_MAGENTA | UV_VISOR_AMBER | 1 | -0.0583 | -0.0657 | -0.0509 | -0.0891 | 0.1167 |

## Strategy Decision

- Trade all five products.
- Use static fair values plus small product-specific anchor shifts.
- Add only validated same-category lead-lag fair-value shifts.
- Use passive quotes and selective crossing when fair value is far enough through the touch.
- Ignore direct basket residual and butterfly trades in the final category implementation.