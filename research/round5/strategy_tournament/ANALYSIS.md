# Round 5 Strategy Tournament Analysis

This directory contains a fresh Round 5 tournament pass over the bundled days 2, 3, and 4. The broad screen is intentionally harsh: it evaluates simple families across all 50 products with a vectorized limit-10 simulator, then only Rust-validates compact survivors.

Robust screen objective:

`mean_pnl - 0.65 * day_stdev - 0.20 * max_drawdown - 0.018 * turnover - 0.50 * parameter_fragility`

Selection gates:

- profitable on at least 2 of 3 days
- no one-day-only dependence
- average signal edge above spread
- bounded turnover
- non-fragile parameter neighborhood
- compact enough for the final trader

## Candidate Coverage

| family | candidates | verdict |
| --- | ---: | --- |
| mean_reversion | 600 | Rejected: high raw totals came with unstable day splits and turnover. |
| momentum | 1050 | Rejected except MICROCHIP_CIRCLE lag filters for OVAL/SQUARE. |
| drift_hold | 200 | Rejected: weak holdout behavior. |
| basket_residual | 150 | Rejected from live file: offline winners were not Rust-robust/compact enough. |
| lead_lag | 561 | Selected only as same-category causal overlays already validated in Rust. |
| order_book_imbalance | 150 | Rejected: unstable sign and weak edge after spread. |
| passive_market_making | 200 | Selected as guarded fair-value quoting layer, not as standalone zero-edge quoting. |
| crossing_high_edge | 250 | Selected as static/mid fair-value crossing layer. |
| participant_flow | 450 | Rejected: anonymous flow overlay reduced Rust PnL. |

## Final Selected Live Families

| live family | implementation |
| --- | --- |
| static/crossing fair value | Per-product static or current-mid fair anchors with tuned take thresholds. |
| passive market making | Quote only when fair edge clears product edge/improvement filters. |
| lead-lag | Same-category lagged leader moves added to fair values. |
| micro momentum | MICROCHIP_CIRCLE lag filters for MICROCHIP_OVAL and MICROCHIP_SQUARE. |

Participant names are unavailable in Round 5 trade CSVs, so participant-flow alpha was tested only as anonymous signed flow.

## Rejected Families

- Basket residual: attractive offline for several microchip/robot names, but direct basket overlays were too bulky and weaker in Rust validation than the selected lead-lag/static blend.
- Broad momentum/drift: turnover and sign instability dominated after spread.
- Order book imbalance: no stable product-level edge after costs.
- Anonymous participant flow: selected core plus flow overlay scored `2,541,058.50`, below selected-only `2,543,655.50`.
- Max public lead-lag additions: higher public total in prior local sweeps, but failed robust predictive/2-day filters and were not included.

## Product Risk

All 50 products have positive total PnL in the selected Rust run. Every product is profitable on at least 2 of 3 public days; the weakest total is ROBOT_VACUUMING at `15,278.00`.

Day-level total drawdown from Rust `pnl_by_product.csv`:

| day | final_pnl | max_drawdown | min_pnl |
| ---: | ---: | ---: | ---: |
| 2 | 787,022.50 | 18,418.00 | -8,451.50 |
| 3 | 1,058,008.50 | 18,827.00 | -1,007.00 |
| 4 | 698,624.50 | 24,197.50 | -10,458.50 |

## Notes

- Broad offline leave-one-day-out candidate selection was deliberately conservative and rejected most standalone modules; held-out sums were negative for the basket-heavy offline winners. This is why the live file uses the Rust-validated union rather than blindly adopting offline top rows.
- The final trader has no debug prints and uses only `datamodel`, `typing`, and `json`.
- File size is `17,744` bytes.
