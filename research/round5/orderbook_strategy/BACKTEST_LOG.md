# Round 5 Order Book Strategy Backtest Log

All scores use the local Rust backtester.

## Final Trader

File:

```text
traders/r5_orderbook_trader.py
```

File size:

```text
20,658 bytes
```

Exact command:

```bash
cd prosperity_rust_backtester
/Users/giordanmasen/Library/Caches/rust_backtester/target/release/rust_backtester --trader ../traders/r5_orderbook_trader.py --dataset round5 --products off --artifact-mode none
```

The selected file is byte-identical to the validated `/tmp/r5_ob_variants/exact_exec.py` run.

## Final Result

| Day | Own Trades | PnL |
| --- | ---: | ---: |
| D+2 | 1,116 | 789,912.50 |
| D+3 | 1,502 | 1,062,299.50 |
| D+4 | 1,275 | 705,074.50 |
| Total | 3,893 | 2,557,286.50 |

No debug prints, Python tracebacks, or position-limit warnings were produced.

## Variant Tests

| Variant | Description | D+2 | D+3 | D+4 | Total | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Pure market making | Local-mid quotes, no fair-value alpha | 56,301.00 | 37,492.50 | 68,190.50 | 161,984.00 | Too little edge after queue/spread |
| Imbalance-only | Local mid plus microprice/imbalance | 57,938.00 | 53,877.50 | 99,798.50 | 211,614.00 | Rejected |
| Crossing-only high edge | Cross only on fair-value edge | 746,696.00 | 975,118.00 | 598,558.00 | 2,320,372.00 | Profitable but leaves passive edge |
| Basket fair value | Direct same-category basket residual | 650,002.50 | 849,267.00 | 517,211.50 | 2,016,481.00 | Rejected |
| Fair-value MM plus book shift | Lead-lag fair with small microprice overlay | 789,912.50 | 1,060,990.50 | 702,189.50 | 2,553,092.50 | Close, but worse |
| Fair-value MM plus spread guard and dynamic size | No book/skew, extra cost controls | 784,905.50 | 1,046,011.50 | 688,104.50 | 2,519,021.50 | Rejected |
| Fair-value MM plus book and inventory skew | Naive hybrid | 743,502.50 | 1,012,300.50 | 669,810.50 | 2,425,613.50 | Rejected |
| Selected hybrid | Mean-reversion/static fair, lead-lag, selective crossing, passive quoting | 789,912.50 | 1,062,299.50 | 705,074.50 | 2,557,286.50 | Final |

## Product PnL

| Product | D+2 | D+3 | D+4 | Total |
| --- | ---: | ---: | ---: | ---: |
| GALAXY_SOUNDS_BLACK_HOLES | 14,658.50 | 14,142.00 | 21,124.00 | 49,924.50 |
| GALAXY_SOUNDS_DARK_MATTER | 14,473.00 | 31,791.00 | 18,118.00 | 64,382.00 |
| GALAXY_SOUNDS_PLANETARY_RINGS | 13,200.00 | -1,655.00 | 37,537.00 | 49,082.00 |
| GALAXY_SOUNDS_SOLAR_FLAMES | 25,975.00 | 28,622.00 | 22,587.00 | 77,184.00 |
| GALAXY_SOUNDS_SOLAR_WINDS | 18,908.00 | 16,270.00 | 7,635.00 | 42,813.00 |
| MICROCHIP_CIRCLE | 27,668.00 | 9,057.00 | 5,613.00 | 42,338.00 |
| MICROCHIP_OVAL | 30,006.00 | 34,590.50 | 17,527.00 | 82,123.50 |
| MICROCHIP_RECTANGLE | 5,750.00 | 25,458.00 | 20,905.00 | 52,113.00 |
| MICROCHIP_SQUARE | 12,468.00 | 43,367.00 | 32,737.00 | 88,572.00 |
| MICROCHIP_TRIANGLE | 1,031.00 | 15,980.00 | 14,886.50 | 31,897.50 |
| OXYGEN_SHAKE_CHOCOLATE | 12,416.00 | 15,986.00 | 17,908.00 | 46,310.00 |
| OXYGEN_SHAKE_EVENING_BREATH | 361.00 | 32,473.00 | 25,966.00 | 58,800.00 |
| OXYGEN_SHAKE_GARLIC | 19,232.00 | 30,159.00 | -4,761.00 | 44,630.00 |
| OXYGEN_SHAKE_MINT | 31,847.00 | 4,000.00 | 15,805.00 | 51,652.00 |
| OXYGEN_SHAKE_MORNING_BREATH | 1,575.00 | 36,050.00 | 3,725.00 | 41,350.00 |
| PANEL_1X2 | 31,518.00 | 4,425.00 | 8,110.00 | 44,053.00 |
| PANEL_1X4 | -2,030.00 | 30,502.00 | 10,405.00 | 38,877.00 |
| PANEL_2X2 | 0.00 | 16,386.00 | 10,260.00 | 26,646.00 |
| PANEL_2X4 | 29,077.00 | 13,301.00 | 4,984.00 | 47,362.00 |
| PANEL_4X4 | 25,122.00 | 12,467.00 | 7,073.00 | 44,662.00 |
| PEBBLES_L | 43,877.00 | 39,042.00 | 12,005.00 | 94,924.00 |
| PEBBLES_M | 222.00 | 24,595.00 | 26,973.00 | 51,790.00 |
| PEBBLES_S | 13,525.00 | 18,363.00 | 33,973.00 | 65,861.00 |
| PEBBLES_XL | 71,115.00 | 64,081.00 | -2,374.00 | 132,822.00 |
| PEBBLES_XS | 19,455.00 | 39,811.00 | 24,061.00 | 83,327.00 |
| ROBOT_DISHES | 10,068.00 | 36,978.00 | -10,374.00 | 36,672.00 |
| ROBOT_IRONING | 4,860.00 | 20,290.00 | 3,679.00 | 28,829.00 |
| ROBOT_LAUNDRY | 10,727.00 | 18,969.00 | 950.00 | 30,646.00 |
| ROBOT_MOPPING | -1,835.00 | 26,603.00 | 7,463.00 | 32,231.00 |
| ROBOT_VACUUMING | 326.00 | 14,662.00 | 290.00 | 15,278.00 |
| SLEEP_POD_COTTON | 11,190.00 | 15,009.00 | 20,490.00 | 46,689.00 |
| SLEEP_POD_LAMB_WOOL | 18,390.00 | 31,387.00 | 21,109.00 | 70,886.00 |
| SLEEP_POD_NYLON | 2,095.00 | 14,242.00 | 6,591.00 | 22,928.00 |
| SLEEP_POD_POLYESTER | 17,615.00 | 30,609.00 | 9,113.00 | 57,337.00 |
| SLEEP_POD_SUEDE | 10,950.00 | 37,249.00 | 18,861.00 | 67,060.00 |
| SNACKPACK_CHOCOLATE | 18,845.00 | 10,155.00 | 2,060.00 | 31,060.00 |
| SNACKPACK_PISTACHIO | 14,368.00 | 6,101.00 | 2,921.00 | 23,390.00 |
| SNACKPACK_RASPBERRY | 29,811.00 | 15,655.00 | 16,985.00 | 62,451.00 |
| SNACKPACK_STRAWBERRY | 4,280.00 | 20,688.00 | 13,230.00 | 38,198.00 |
| SNACKPACK_VANILLA | 16,495.00 | 9,586.00 | 6,240.00 | 32,321.00 |
| TRANSLATOR_ASTRO_BLACK | -1,590.00 | 16,787.00 | 24,388.00 | 39,585.00 |
| TRANSLATOR_ECLIPSE_CHARCOAL | 10,036.00 | 17,447.00 | 28,622.00 | 56,105.00 |
| TRANSLATOR_GRAPHITE_MIST | 22,948.00 | 21,218.00 | 19,195.00 | 63,361.00 |
| TRANSLATOR_SPACE_GRAY | 21,347.00 | 8,445.00 | 5,168.00 | 34,960.00 |
| TRANSLATOR_VOID_BLUE | 14,490.00 | 26,576.00 | 19,470.00 | 60,536.00 |
| UV_VISOR_AMBER | 14,935.00 | 11,030.00 | 24,436.00 | 50,401.00 |
| UV_VISOR_MAGENTA | 12,935.00 | 27,274.00 | 35,234.00 | 75,443.00 |
| UV_VISOR_ORANGE | 7,645.00 | 8,875.00 | 16,366.00 | 32,886.00 |
| UV_VISOR_RED | 39,387.00 | 17,201.00 | -7,055.00 | 49,533.00 |
| UV_VISOR_YELLOW | 18,145.00 | 0.00 | 26,860.00 | 45,005.00 |

## Notes

- The final product table matches `research/round5/final_merged_product_pnl.csv`.
- `traders/r5_orderbook_trader.py` is self-contained and uses only `datamodel`, `typing`, and `json`.
- `BOOK_WEIGHT`, `SKEW_WEIGHT`, and the volatility sizing helper remain in the file for controlled future perturbations, but the validated production calibration sets the two weak overlays to zero.
