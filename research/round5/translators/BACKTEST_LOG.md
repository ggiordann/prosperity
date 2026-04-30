# Translator Backtest Log

All scores use the Rust backtester on bundled Round 5 days 2, 3, and 4.

## Final Command

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/translators/translator_strategy.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_translators_take_lag_v1
```

Final artifacts:

```text
prosperity_rust_backtester/runs/r5_translators_take_lag_v1/
```

## Strategy Sweep

| strategy | total | day 2 | day 3 | day 4 | trades | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Current-mid passive maker | 0 | 0 | 0 | 0 | 0 | No executable edge |
| Static fair, no shift | 139,683 | 14,524 | 55,833 | 69,326 | 196 | Weak single-product baseline |
| Static shifted fair | 214,738 | 53,136 | 82,238 | 79,364 | 291 | Stronger anchor baseline |
| Lead-lag first edge only | 237,562 | 64,587 | 86,419 | 86,556 | 327 | Relationships add value |
| Lead-lag two-edge mixed passive+take | 249,025 | 65,246 | 88,940 | 94,839 | 348 | Previous full-strategy slice |
| Lead-lag take-only | 252,599 | 67,098 | 90,269 | 95,232 | 310 | Better execution |
| Lead-lag take-only plus short Eclipse edge | 254,547 | 67,231 | 90,473 | 96,843 | 311 | Final |
| Quote-only around lead-lag fair | 67,675 | 10,046 | 22,521 | 35,108 | 196 | Rejected |
| Pair residual, Eclipse vs Void | 26,698 | 6,697 | 17,129 | 2,872 | 25 | Rejected |
| Basket ridge all-public fit | 122,745 | 37,143 | 52,593 | 33,009 | 137 | Rejected |
| Best tested rolling mean reversion | -127,326 | -24,927 | -47,637 | -54,762 | 4,160 | Rejected |
| Best tested single-product momentum | -358,070 | -163,308 | -95,841 | -98,921 | 7,127 | Rejected |

## Parameter Checks

Lead-lag coefficient scale, mixed passive+take:

| scale | total | day 2 | day 3 | day 4 |
| ---: | ---: | ---: | ---: | ---: |
| 0.50 | 211,665 | 45,533 | 84,291 | 81,841 |
| 0.75 | 222,875 | 52,482 | 85,690 | 84,703 |
| 1.00 | 249,025 | 65,246 | 88,940 | 94,839 |
| 1.25 | 221,702 | 55,355 | 76,937 | 89,410 |
| 1.50 | 209,079 | 55,238 | 74,216 | 79,625 |
| 2.00 | 188,919 | 51,244 | 69,434 | 68,241 |

Take-threshold scale, take-only:

| scale | total | day 2 | day 3 | day 4 |
| ---: | ---: | ---: | ---: | ---: |
| 0.70 | 185,919 | 50,323 | 63,749 | 71,847 |
| 0.80 | 202,541 | 52,141 | 75,092 | 75,308 |
| 0.90 | 224,803 | 57,922 | 82,431 | 84,450 |
| 1.00 | 252,599 | 67,098 | 90,269 | 95,232 |
| 1.05 | 238,081 | 57,130 | 88,547 | 92,404 |
| 1.10 | 212,300 | 56,144 | 84,343 | 71,813 |
| 1.20 | 191,672 | 58,058 | 76,069 | 57,545 |
| 1.30 | 177,918 | 53,134 | 66,631 | 58,153 |

Short Eclipse-from-Space lag-5 add-on, take-only:

| added weight | total | day 2 | day 3 | day 4 |
| ---: | ---: | ---: | ---: | ---: |
| 0.12 | 253,818 | 66,945 | 90,251 | 96,622 |
| 0.15 | 254,111 | 67,255 | 90,150 | 96,706 |
| 0.18 | 254,283 | 67,231 | 90,146 | 96,906 |
| 0.20 | 254,547 | 67,231 | 90,473 | 96,843 |
| 0.22 | 254,584 | 67,273 | 90,473 | 96,838 |
| 0.25 | 254,205 | 67,273 | 90,144 | 96,788 |
| 0.30 | 251,628 | 66,293 | 90,144 | 95,191 |
| 0.35 | 251,696 | 66,255 | 90,144 | 95,297 |
| 0.40 | 251,544 | 66,255 | 90,175 | 95,114 |

The public maximum was 0.22, but 0.20 was selected because it is simpler, inside the plateau, and only 37 lower on public data.

## Final Per-Product PnL

| product | day 2 | day 3 | day 4 | total |
| --- | ---: | ---: | ---: | ---: |
| TRANSLATOR_ASTRO_BLACK | -1,590 | 16,787 | 24,388 | 39,585 |
| TRANSLATOR_ECLIPSE_CHARCOAL | 10,036 | 17,447 | 28,622 | 56,105 |
| TRANSLATOR_GRAPHITE_MIST | 22,948 | 21,218 | 19,195 | 63,361 |
| TRANSLATOR_SPACE_GRAY | 21,347 | 8,445 | 5,168 | 34,960 |
| TRANSLATOR_VOID_BLUE | 14,490 | 26,576 | 19,470 | 60,536 |
| Total | 67,231 | 90,473 | 96,843 | 254,547 |

## Validation Notes

- Positive category PnL on every public day.
- All five products have positive total PnL.
- The final execution change, take-only, improved every public day versus mixed passive+take.
- The added lag-5 Eclipse edge improved the take-only strategy on every public day at weight 0.20.
- Coefficient and threshold perturbations generally underperformed, so the selected parameters are not simply part of a broad overtrading region.
- No `Traceback`, runtime error, or position-limit breach was found in the final artifact logs.

Include in final combined submission: yes.
