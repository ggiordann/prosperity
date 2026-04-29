# Round 5 Backtest Log

All scores use the Rust backtester unless marked otherwise.

## Repository Inspection

- Rust backtester: `prosperity_rust_backtester/`
- Round 5 data: `prosperity_rust_backtester/datasets/round5/`
- Final submission file: `prosperity_rust_backtester/traders/latest_trader.py`
- Backtest command pattern:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader traders/latest_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id <run_id>
```

- Public days: 2, 3, 4; 50 products; position limit 10 for every product.
- Trade CSV buyer/seller fields are blank in Round 5, so counterparty-ID alpha is unavailable.

## Iterations

| Strategy | Main change | Total PnL | D+2 | D+3 | D+4 | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Baseline all-product maker | Quote around current mid | 401,540.0 | 118,766.0 | 105,255.5 | 177,518.5 | Spread capture only |
| Static fair all-products | Historical mean/std z-take plus passive quotes | 1,056,318.5 | 507,979.5 | 433,914.5 | 114,424.5 | First real baseline |
| Static/mid hybrid | Per-product best static fair or current mid | 1,249,831.0 | 592,554.5 | 412,230.0 | 245,046.5 | Product specialization helps |
| Refined grid | Product z/quote tuning, Rust verified | 1,826,713.0 | 646,094.5 | 748,193.0 | 432,425.5 | Strong execution baseline |
| Selective depth walk | Walk visible depth only where useful | 1,830,192.0 | 646,296.5 | 749,329.0 | 434,566.5 | Small execution win |
| Anchor shift search | Product fair-value bias | 2,077,288.5 | 695,372.0 | 844,009.0 | 537,907.5 | Static anchors were too neutral |
| Anchor + z/edge retune | Retune take z, quote edge, improvement | 2,182,319.0 | 696,143.0 | 913,537.0 | 572,639.0 | Better fair/execution blend |
| Same-category lead-lag layer 1 | One causal same-category leader per product | 2,408,478.0 | 737,193.0 | 1,036,937.5 | 634,347.5 | Main Rook-E1 alpha |
| Lead-lag layer 2 filtered | Add second edge with >1000 PnL and >=2 positive days | 2,509,985.0 | 767,745.0 | 1,071,336.5 | 670,903.5 | Robust >2.5M variant |
| Predictive 2-day filter | Keep edges with two-day causal predictive support | 2,478,499.5 | 758,336.5 | 1,031,679.0 | 688,484.0 | Clean but over-pruned |
| Predictive 3-day filter | Keep edges with three-day predictive support | 2,320,322.5 | 731,787.5 | 967,628.0 | 620,907.0 | Too conservative |
| Validated union | Keep edges passing predictive 2-day OR robust PnL 2-day screen | 2,543,655.5 | 787,022.5 | 1,058,008.5 | 698,624.5 | Final |
| Max public score | Two same-category edges per product with no final validation prune | 2,546,711.5 | 786,649.5 | 1,058,219.5 | 701,842.5 | Rejected as higher overfit risk |
| Product trade-flow overlay | Decayed product aggressor-flow fair shift | 2,539,157.5 to 2,542,492.5 | mixed | mixed | mixed | Rejected |
| Category trade-flow overlay | Decayed category aggressor-flow fair shift | 2,541,092.5 to 2,543,122.5 | mixed | mixed | mixed | Rejected |

## Final Backtest

Command:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader traders/latest_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_final_validated_union
```

Result:

| Day | PnL | Own trades |
| --- | ---: | ---: |
| 2 | 787,022.5 | 1,112 |
| 3 | 1,058,008.5 | 1,498 |
| 4 | 698,624.5 | 1,281 |
| Total | 2,543,655.5 | 3,891 |

No runtime errors, tracebacks, or position-limit breaches appeared in the final run.

## Product PnL Leaders

| product | day_2 | day_3 | day_4 | total |
| --- | ---: | ---: | ---: | ---: |
| PEBBLES_XL | 71,115.0 | 64,081.0 | -2,374.0 | 132,822.0 |
| PEBBLES_L | 43,877.0 | 39,042.0 | 12,005.0 | 94,924.0 |
| MICROCHIP_SQUARE | 12,468.0 | 43,367.0 | 32,737.0 | 88,572.0 |
| PEBBLES_XS | 19,455.0 | 39,811.0 | 24,061.0 | 83,327.0 |
| MICROCHIP_OVAL | 30,006.0 | 34,590.5 | 17,527.0 | 82,123.5 |
| UV_VISOR_MAGENTA | 12,935.0 | 27,274.0 | 35,234.0 | 75,443.0 |
| GALAXY_SOUNDS_SOLAR_FLAMES | 25,942.0 | 27,554.0 | 20,434.0 | 73,930.0 |
| SLEEP_POD_LAMB_WOOL | 18,390.0 | 31,387.0 | 21,109.0 | 70,886.0 |
| SLEEP_POD_SUEDE | 10,950.0 | 37,249.0 | 18,861.0 | 67,060.0 |
| PEBBLES_S | 13,525.0 | 18,363.0 | 33,973.0 | 65,861.0 |

Full table: `research/round5/final_product_pnl.csv`.

## Validation Notes

- Final edge set has 95 same-category edges.
- 57 retained edges passed both the robust-PnL and predictive filters.
- 15 retained edges passed robust two-day PnL validation only.
- 23 retained edges passed two-day causal predictive validation only.
- Five max-score edges were removed because they failed both filters:
  - `OXYGEN_SHAKE_MINT <- OXYGEN_SHAKE_MORNING_BREATH`, lag 500, k 0.1
  - `PANEL_1X2 <- PANEL_4X4`, lag 500, k -0.1
  - `PANEL_2X2 <- PANEL_1X2`, lag 100, k 0.1
  - `SLEEP_POD_COTTON <- SLEEP_POD_SUEDE`, lag 20, k -0.1
  - `UV_VISOR_ORANGE <- UV_VISOR_MAGENTA`, lag 500, k 0.25

## Rejected Tests

- Direct pebbles basket fair-value blend reduced PnL despite the fixed-sum identity.
- Snack and same-category synthetic fair-value blends were weaker than lead-lag overlays.
- Public trade-flow product/category overlays had visible statistical signal, but reduced Rust PnL on top of the validated lead-lag trader.
- External reference repos provided useful workflow ideas but no hidden Round 5 algorithmic alpha beyond same-category relationship exploration.
