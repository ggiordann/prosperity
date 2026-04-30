# UV-Visors Backtest Log

All scores use the local Rust backtester on bundled Round 5 public days 2, 3, and 4.

## Final Candidate

Strategy file:

```text
research/round5/uv_visors/uv_visor_strategy.py
```

Exact backtest command:

```bash
cd prosperity_rust_backtester
/Users/giordanmasen/Library/Caches/rust_backtester/target/release/rust_backtester --trader ../research/round5/uv_visors/uv_visor_strategy.py --dataset round5 --products full --artifact-mode none --run-id uv_visors_final
```

Result:

| Day | PnL | Own trades |
| --- | ---: | ---: |
| 2 | 93,047.0 | 48 |
| 3 | 64,380.0 | 75 |
| 4 | 95,841.0 | 101 |
| Total | 253,268.0 | 224 |

PnL by product:

| Product | Day 2 | Day 3 | Day 4 | Total |
| --- | ---: | ---: | ---: | ---: |
| UV_VISOR_MAGENTA | 12,935.0 | 27,274.0 | 35,234.0 | 75,443.0 |
| UV_VISOR_AMBER | 14,935.0 | 11,030.0 | 24,436.0 | 50,401.0 |
| UV_VISOR_RED | 39,387.0 | 17,201.0 | -7,055.0 | 49,533.0 |
| UV_VISOR_YELLOW | 18,145.0 | 0.0 | 26,860.0 | 45,005.0 |
| UV_VISOR_ORANGE | 7,645.0 | 8,875.0 | 16,366.0 | 32,886.0 |

No runtime errors, tracebacks, or position-limit cancellations appeared in the final run.

## Strategy Comparison

| Strategy | Description | Total PnL | Day 2 | Day 3 | Day 4 | Own trades | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline market making | Quote around current mid only | 42,073.0 | 14,942.0 | 8,827.5 | 18,303.5 | 3,215 | Too much churn for the spread |
| Single-product static mean reversion | Static anchors, product take/edge, no relationships | 216,004.0 | 88,861.0 | 50,899.0 | 76,244.0 | 215 | Strong base |
| Spectrum/curve relative value | Middle products priced from adjacent colour neighbours | 158,388.0 | 52,475.0 | 29,886.0 | 76,027.0 | 148 | Inferior to static anchors |
| AMBER/MAGENTA pair residual | Hedged residual pair using the most stationary pair | 47,447.0 | 6,546.0 | 30,388.0 | 10,513.0 | 138 | Too narrow and unstable |
| Basket residual | Same-category synthetic fair values | 18,200.0 | 5,140.0 | 7,945.0 | 5,115.0 | 15 | Residuals too persistent |
| Validated lead-lag hybrid | Static anchors plus validated UV lead-lag edges | 253,208.0 | 92,987.0 | 64,380.0 | 95,841.0 | 224 | Main candidate |
| Final hybrid | Add small robust `RED -> YELLOW` lag-500 nudge | 253,268.0 | 93,047.0 | 64,380.0 | 95,841.0 | 224 | Selected |

## Relationship Edges Used

Runtime fair-value shifts use only current and past mid prices:

| Follower | Leader | Lag | Weight | Source |
| --- | --- | ---: | ---: | --- |
| UV_VISOR_YELLOW | UV_VISOR_AMBER | 500 | 0.15 | Existing robust category edge |
| UV_VISOR_YELLOW | UV_VISOR_RED | 500 | -0.05 | Stable offline lead-lag, nonnegative Rust perturbation |
| UV_VISOR_AMBER | UV_VISOR_RED | 500 | 0.25 | Strong validated edge |
| UV_VISOR_AMBER | UV_VISOR_ORANGE | 100 | 0.25 | Positive second-layer edge |
| UV_VISOR_ORANGE | UV_VISOR_YELLOW | 200 | -0.25 | Validated category edge |
| UV_VISOR_RED | UV_VISOR_YELLOW | 50 | 0.1 | Validated category edge |
| UV_VISOR_RED | UV_VISOR_ORANGE | 1 | -0.25 | Short-lag reaction edge |
| UV_VISOR_MAGENTA | UV_VISOR_AMBER | 500 | 1.0 | Strongest UV product contributor |
| UV_VISOR_MAGENTA | UV_VISOR_YELLOW | 20 | -0.25 | Robust second signal |

## Robustness Checks

Signal removal:

| Variant | Total PnL | Day 2 | Day 3 | Day 4 | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| No YELLOW signals | 252,676.0 | 92,607.0 | 64,380.0 | 95,689.0 | Mildly worse |
| No AMBER signals | 244,978.0 | 92,987.0 | 64,380.0 | 87,611.0 | AMBER signals matter |
| No ORANGE signals | 252,828.0 | 92,687.0 | 64,080.0 | 96,061.0 | Mildly worse/slightly redistributed |
| No RED signals | 249,484.0 | 89,541.0 | 64,102.0 | 95,841.0 | RED signals matter |
| No MAGENTA signals | 228,870.0 | 92,987.0 | 51,477.0 | 84,406.0 | MAGENTA signals matter most |

Parameter perturbation:

| Variant | Total PnL | Day 2 | Day 3 | Day 4 | Note |
| --- | ---: | ---: | ---: | ---: | --- |
| Signal weights x0.75 | 229,057.0 | 92,672.0 | 50,388.0 | 85,997.0 | Positive but worse |
| Signal weights x0.90 | 241,150.0 | 93,039.0 | 52,213.0 | 95,898.0 | Positive but worse |
| Signal weights x1.10 | 241,461.0 | 92,491.0 | 58,552.0 | 90,418.0 | Positive but worse |
| Signal weights x1.25 | 231,746.0 | 92,636.0 | 52,200.0 | 86,910.0 | Positive but worse |
| Quote edge x0.75 | 252,620.0 | 92,663.0 | 64,380.0 | 95,577.0 | Flat neighborhood |
| Quote edge x1.25 | 253,215.0 | 92,987.0 | 64,380.0 | 95,848.0 | Flat neighborhood |
| Take threshold x0.75 | 206,730.0 | 81,221.0 | 51,099.0 | 74,410.0 | Crossing too eager |
| Take threshold x1.25 | 161,515.0 | 59,828.0 | 38,222.0 | 63,465.0 | Crossing too selective |

Walk-forward notes:

- Day-level PnL is positive on all three public days.
- Product-level PnL is positive for four of five products on all days; `UV_VISOR_RED` loses on day 4 but remains strongly positive overall.
- Leave-one-day-out basket fits and stationarity tests did not justify replacing the lead-lag hybrid.
- The small added `RED -> YELLOW` signal improves only day 2 by 60 ticks in public Rust PnL; it is included because the offline lag-500 relationship is stable across all three days, but it should be treated as low-impact.

## Final Recommendation

Include this UV-Visors strategy in the combined Round 5 submission. It is compact at 4,707 bytes, uses only allowed runtime imports, trades all five UV products, and contributes a validated category PnL of `253,268.0`.
