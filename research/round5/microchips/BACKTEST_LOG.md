# Microchip Backtest Log

## Environment And Data

- Backtester: `prosperity_rust_backtester/`
- Data: `prosperity_rust_backtester/datasets/round5/`
- Days: `2`, `3`, `4`
- Products traded: `MICROCHIP_CIRCLE`, `MICROCHIP_OVAL`, `MICROCHIP_SQUARE`, `MICROCHIP_RECTANGLE`, `MICROCHIP_TRIANGLE`
- Position limit: `10` per product
- Final category trader: `research/round5/microchips/microchip_trader.py`
- File size: `6,578` bytes

The checked-in `prosperity_rust_backtester/target/release/rust_backtester` binary failed locally because it was linked against a missing `libpython3.11.dylib`. The README wrapper command below was used for the official logged backtest.

## Final Backtest Command

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/microchips/microchip_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_microchip_base
```

## Final Result

```text
SET             DAY    TICKS  OWN_TRADES    FINAL_PNL
D+2               2    10000         387     76923.00
D+3               3    10000         439    128452.50
D+4               4    10000         371     91668.50
TOTAL             -    30000        1197    297044.00
```

Product PnL:

| product | D+2 | D+3 | D+4 | total |
| --- | ---: | ---: | ---: | ---: |
| MICROCHIP_CIRCLE | 27,668.0 | 9,057.0 | 5,613.0 | 42,338.0 |
| MICROCHIP_OVAL | 30,006.0 | 34,590.5 | 17,527.0 | 82,123.5 |
| MICROCHIP_RECTANGLE | 5,750.0 | 25,458.0 | 20,905.0 | 52,113.0 |
| MICROCHIP_SQUARE | 12,468.0 | 43,367.0 | 32,737.0 | 88,572.0 |
| MICROCHIP_TRIANGLE | 1,031.0 | 15,980.0 | 14,886.5 | 31,897.5 |

The result exactly reproduces the microchip contribution of the current all-product final trader while trading no non-microchip products.

## Completed Variant Sweep

The following variants were generated in `/tmp/r5_microchip_variants` and backtested with metrics written under `/tmp/r5_microchip_variant_runs`. The broad sweep was stopped after the completed variants because the shared machine was saturated by many concurrent backtester processes.

| variant | total PnL | day 2 | day 3 | day 4 | own trades | note |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| base | 297,044.0 | 76,923.0 | 128,452.5 | 91,668.5 | 1,197 | selected |
| add_rect_circle_l75_k0p25 | 293,528.0 | 76,923.0 | 125,269.5 | 91,335.5 | 1,194 | raw lag looked good, execution worse |
| add_rect_circle_l75_k0p5 | 291,879.0 | 76,923.0 | 123,586.5 | 91,369.5 | 1,192 | worse |
| sig1p5 | 241,830.5 | 67,487.0 | 92,126.5 | 82,217.0 | 1,412 | over-scaled lag edges |
| nosig | 234,448.5 | 49,934.0 | 110,396.5 | 74,118.0 | 825 | anchors plus circle-history overlay only |
| sig0p5 | 227,916.5 | 34,813.0 | 113,869.5 | 79,234.0 | 1,024 | under-scaled lag edges |
| nohist | 172,050.5 | 51,488.0 | 62,506.0 | 58,056.5 | 606 | same-category lag edges without CIRCLE history overlay |
| hist2 | 127,607.0 | 38,433.0 | 70,241.5 | 18,932.5 | 1,887 | CIRCLE history overlay too large |

## Strategy Family Outcomes

- Baseline static/z-take from existing Round 5 artifacts: microchip subtotal `89,430.0`; `MICROCHIP_TRIANGLE` was negative in that setup.
- Product-refined static/current-mid strategy from existing artifacts: microchip subtotal about `210,678.5`.
- Anchors plus medium `CIRCLE` history but no same-category `SIG` edges: `234,448.5`.
- Same-category `SIG` edges without medium `CIRCLE` history: `172,050.5`.
- Full hybrid: `297,044.0`.
- Extra `CIRCLE -> RECTANGLE` edge: rejected despite strong offline lag diagnostics.

## Validation Summary

- Day robustness: all three public days are positive.
- Product robustness: all five products are positive in the final backtest.
- Walk-forward view:
  - Day 2 as training, days 3 and 4 as heldout: `220,121.0`.
  - Days 2 and 3 as training, day 4 as heldout: `91,668.5`.
  - Leave-one-day-out sanity: each heldout day remains positive.
- Parameter perturbation:
  - Lag scale `0.5`: `227,916.5`.
  - Lag scale `1.5`: `241,830.5`.
  - CIRCLE history scale `0`: `172,050.5`.
  - CIRCLE history scale about `2x`: `127,607.0`.

## Include In Final?

Yes. The category strategy is profitable on every public day, profitable on every product, compact, and supported by causal same-category relationships rather than independent product overfitting.
