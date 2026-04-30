# Round 5 Participant Alpha Backtest Log

## Final Trader

File: `traders/r5_participant_trader.py`

File size:

```text
17,872 bytes
```

Exact command:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../traders/r5_participant_trader.py --dataset round5 --products full --artifact-mode none --run-id r5_participant_alpha_metrics
```

## Final Result

| day | ticks | own trades | PnL |
| ---: | ---: | ---: | ---: |
| 2 | 10,000 | 1,116 | 789,912.50 |
| 3 | 10,000 | 1,502 | 1,062,299.50 |
| 4 | 10,000 | 1,275 | 705,074.50 |
| Total | 30,000 | 3,893 | 2,557,286.50 |

No runtime errors or position-limit breaches appeared in the completed metrics run.

## Category PnL

| category | day 2 | day 3 | day 4 | total |
| --- | ---: | ---: | ---: | ---: |
| Pebbles | 148,194.0 | 185,892.0 | 94,638.0 | 428,724.0 |
| Microchips | 76,923.0 | 128,452.5 | 91,668.5 | 297,044.0 |
| Galaxy Sounds | 87,214.5 | 89,170.0 | 107,001.0 | 283,385.5 |
| Sleeping Pods | 60,240.0 | 128,496.0 | 76,164.0 | 264,900.0 |
| Translators | 67,231.0 | 90,473.0 | 96,843.0 | 254,547.0 |
| UV-Visors | 93,047.0 | 64,380.0 | 95,841.0 | 253,268.0 |
| Oxygen Shakes | 65,431.0 | 118,668.0 | 58,643.0 | 242,742.0 |
| Panels | 83,687.0 | 77,081.0 | 40,832.0 | 201,600.0 |
| Snackpacks | 83,799.0 | 62,185.0 | 41,436.0 | 187,420.0 |
| Robotics | 24,146.0 | 117,502.0 | 2,008.0 | 143,656.0 |

## Product PnL Leaders

| product | day 2 | day 3 | day 4 | total |
| --- | ---: | ---: | ---: | ---: |
| `PEBBLES_XL` | 71,115.0 | 64,081.0 | -2,374.0 | 132,822.0 |
| `PEBBLES_L` | 43,877.0 | 39,042.0 | 12,005.0 | 94,924.0 |
| `MICROCHIP_SQUARE` | 12,468.0 | 43,367.0 | 32,737.0 | 88,572.0 |
| `PEBBLES_XS` | 19,455.0 | 39,811.0 | 24,061.0 | 83,327.0 |
| `MICROCHIP_OVAL` | 30,006.0 | 34,590.5 | 17,527.0 | 82,123.5 |
| `GALAXY_SOUNDS_SOLAR_FLAMES` | 25,975.0 | 28,622.0 | 22,587.0 | 77,184.0 |
| `UV_VISOR_MAGENTA` | 12,935.0 | 27,274.0 | 35,234.0 | 75,443.0 |
| `SLEEP_POD_LAMB_WOOL` | 18,390.0 | 31,387.0 | 21,109.0 | 70,886.0 |
| `SLEEP_POD_SUEDE` | 10,950.0 | 37,249.0 | 18,861.0 | 67,060.0 |
| `PEBBLES_S` | 13,525.0 | 18,363.0 | 33,973.0 | 65,861.0 |

## Full Product PnL

| product | day 2 | day 3 | day 4 | total |
| --- | ---: | ---: | ---: | ---: |
| `GALAXY_SOUNDS_BLACK_HOLES` | 14,658.5 | 14,142.0 | 21,124.0 | 49,924.5 |
| `GALAXY_SOUNDS_DARK_MATTER` | 14,473.0 | 31,791.0 | 18,118.0 | 64,382.0 |
| `GALAXY_SOUNDS_PLANETARY_RINGS` | 13,200.0 | -1,655.0 | 37,537.0 | 49,082.0 |
| `GALAXY_SOUNDS_SOLAR_FLAMES` | 25,975.0 | 28,622.0 | 22,587.0 | 77,184.0 |
| `GALAXY_SOUNDS_SOLAR_WINDS` | 18,908.0 | 16,270.0 | 7,635.0 | 42,813.0 |
| `MICROCHIP_CIRCLE` | 27,668.0 | 9,057.0 | 5,613.0 | 42,338.0 |
| `MICROCHIP_OVAL` | 30,006.0 | 34,590.5 | 17,527.0 | 82,123.5 |
| `MICROCHIP_RECTANGLE` | 5,750.0 | 25,458.0 | 20,905.0 | 52,113.0 |
| `MICROCHIP_SQUARE` | 12,468.0 | 43,367.0 | 32,737.0 | 88,572.0 |
| `MICROCHIP_TRIANGLE` | 1,031.0 | 15,980.0 | 14,886.5 | 31,897.5 |
| `OXYGEN_SHAKE_CHOCOLATE` | 12,416.0 | 15,986.0 | 17,908.0 | 46,310.0 |
| `OXYGEN_SHAKE_EVENING_BREATH` | 361.0 | 32,473.0 | 25,966.0 | 58,800.0 |
| `OXYGEN_SHAKE_GARLIC` | 19,232.0 | 30,159.0 | -4,761.0 | 44,630.0 |
| `OXYGEN_SHAKE_MINT` | 31,847.0 | 4,000.0 | 15,805.0 | 51,652.0 |
| `OXYGEN_SHAKE_MORNING_BREATH` | 1,575.0 | 36,050.0 | 3,725.0 | 41,350.0 |
| `PANEL_1X2` | 31,518.0 | 4,425.0 | 8,110.0 | 44,053.0 |
| `PANEL_1X4` | -2,030.0 | 30,502.0 | 10,405.0 | 38,877.0 |
| `PANEL_2X2` | 0.0 | 16,386.0 | 10,260.0 | 26,646.0 |
| `PANEL_2X4` | 29,077.0 | 13,301.0 | 4,984.0 | 47,362.0 |
| `PANEL_4X4` | 25,122.0 | 12,467.0 | 7,073.0 | 44,662.0 |
| `PEBBLES_L` | 43,877.0 | 39,042.0 | 12,005.0 | 94,924.0 |
| `PEBBLES_M` | 222.0 | 24,595.0 | 26,973.0 | 51,790.0 |
| `PEBBLES_S` | 13,525.0 | 18,363.0 | 33,973.0 | 65,861.0 |
| `PEBBLES_XL` | 71,115.0 | 64,081.0 | -2,374.0 | 132,822.0 |
| `PEBBLES_XS` | 19,455.0 | 39,811.0 | 24,061.0 | 83,327.0 |
| `ROBOT_DISHES` | 10,068.0 | 36,978.0 | -10,374.0 | 36,672.0 |
| `ROBOT_IRONING` | 4,860.0 | 20,290.0 | 3,679.0 | 28,829.0 |
| `ROBOT_LAUNDRY` | 10,727.0 | 18,969.0 | 950.0 | 30,646.0 |
| `ROBOT_MOPPING` | -1,835.0 | 26,603.0 | 7,463.0 | 32,231.0 |
| `ROBOT_VACUUMING` | 326.0 | 14,662.0 | 290.0 | 15,278.0 |
| `SLEEP_POD_COTTON` | 11,190.0 | 15,009.0 | 20,490.0 | 46,689.0 |
| `SLEEP_POD_LAMB_WOOL` | 18,390.0 | 31,387.0 | 21,109.0 | 70,886.0 |
| `SLEEP_POD_NYLON` | 2,095.0 | 14,242.0 | 6,591.0 | 22,928.0 |
| `SLEEP_POD_POLYESTER` | 17,615.0 | 30,609.0 | 9,113.0 | 57,337.0 |
| `SLEEP_POD_SUEDE` | 10,950.0 | 37,249.0 | 18,861.0 | 67,060.0 |
| `SNACKPACK_CHOCOLATE` | 18,845.0 | 10,155.0 | 2,060.0 | 31,060.0 |
| `SNACKPACK_PISTACHIO` | 14,368.0 | 6,101.0 | 2,921.0 | 23,390.0 |
| `SNACKPACK_RASPBERRY` | 29,811.0 | 15,655.0 | 16,985.0 | 62,451.0 |
| `SNACKPACK_STRAWBERRY` | 4,280.0 | 20,688.0 | 13,230.0 | 38,198.0 |
| `SNACKPACK_VANILLA` | 16,495.0 | 9,586.0 | 6,240.0 | 32,321.0 |
| `TRANSLATOR_ASTRO_BLACK` | -1,590.0 | 16,787.0 | 24,388.0 | 39,585.0 |
| `TRANSLATOR_ECLIPSE_CHARCOAL` | 10,036.0 | 17,447.0 | 28,622.0 | 56,105.0 |
| `TRANSLATOR_GRAPHITE_MIST` | 22,948.0 | 21,218.0 | 19,195.0 | 63,361.0 |
| `TRANSLATOR_SPACE_GRAY` | 21,347.0 | 8,445.0 | 5,168.0 | 34,960.0 |
| `TRANSLATOR_VOID_BLUE` | 14,490.0 | 26,576.0 | 19,470.0 | 60,536.0 |
| `UV_VISOR_AMBER` | 14,935.0 | 11,030.0 | 24,436.0 | 50,401.0 |
| `UV_VISOR_MAGENTA` | 12,935.0 | 27,274.0 | 35,234.0 | 75,443.0 |
| `UV_VISOR_ORANGE` | 7,645.0 | 8,875.0 | 16,366.0 | 32,886.0 |
| `UV_VISOR_RED` | 39,387.0 | 17,201.0 | -7,055.0 | 49,533.0 |
| `UV_VISOR_YELLOW` | 18,145.0 | 0.0 | 26,860.0 | 45,005.0 |

## Participant-ID Validation

| test | result |
| --- | --- |
| buyer/seller existence | columns exist, all values blank |
| recurring participants | none |
| per-participant directional edge | unavailable |
| per-participant future-return prediction | unavailable |
| per-participant future-trade prediction | unavailable |
| participant removed test | degenerate: removing participant IDs changes nothing because there are no IDs |

## Aggregate Flow Tests

Direct public trade-flow overlays were tested against the validated union trader and rejected:

| variant | total PnL |
| --- | ---: |
| category flow `c=0.05` | 2,543,122.5 |
| category flow `c=0.10` | 2,542,616.5 |
| product flow `c=2.0`, decay `0.99` | 2,542,492.5 |
| product flow `c=4.0`, decay `0.99` | 2,542,224.5 |
| category flow `c=1.0` | 2,541,716.5 |
| product flow `c=0.5`, decay `0.99` | 2,539,674.5 |

Validated-union reference was `2,543,655.5`, so direct flow overlays did not pass the participant removed/added test. The final trader keeps same-category lead-lag/order-book proxy signals instead.

## Leave-One-Day-Out

Existing validation variants trained on subsets and tested held-out days remained positive:

| held-out day | test PnL range |
| ---: | ---: |
| 2 | 72,643.5 to 90,042.0 |
| 3 | 115,104.5 to 136,844.0 |
| 4 | 127,876.0 to 128,498.0 |

Category research also rejected leave-one-day-out basket regressions where held-out residuals or R2 broke, especially Snackpacks, UV-Visors, Oxygen Shakes, and Galaxy Sounds.

## Threshold Perturbation

Representative threshold perturbations:

| category | perturbation | selected/base | perturbed result | interpretation |
| --- | --- | ---: | ---: | --- |
| Translators | take threshold scale 0.90 / 1.10 | 254,547 | 224,803 / 212,300 | selected region best |
| UV-Visors | take threshold x0.75 | 253,268 | 206,730 | crossing too eager |
| UV-Visors | take threshold x1.25 | 253,268 | 161,515 | too selective |
| Panels | crossing threshold 20% lower | 201,600 | 139,237 | over-aggressive |
| Panels | crossing threshold 20% higher | 201,600 | 87,983 | too few high-edge fills |

Threshold perturbations stayed mostly positive but underperformed, which supports keeping the tuned spread-adjusted edge filters.

## Signal Delay Perturbation

Representative delay/weight perturbations:

| category | perturbation | result |
| --- | --- | ---: |
| Galaxy Sounds | `SOLAR_WINDS -> SOLAR_FLAMES` lag 78, k 0.15 | 283,385.5 |
| Galaxy Sounds | lag 80, k 0.15 | 283,179.5 |
| Galaxy Sounds | lag 72, k 0.15 | 283,088.5 |
| Galaxy Sounds | lag 75, k 0.15 | 282,784.5 |
| Microchips | lag weights x0.5 | 227,916.5 |
| Microchips | lag weights x1.5 | 241,830.5 |
| Snackpacks | lead-lag weights x0.75 | 172,967.0 |
| Snackpacks | lead-lag weights x1.25 | 154,042.0 |

The selected delays are not a single-tick accident. Nearby Galaxy delays remain close, while excessive coefficient scaling generally weakens PnL.

## One-Tick Passive Quote Test

Panel research tested improving one tick inside spread and dropped from selected `201,600` to `89,845`. This confirms one-tick passive quote placement is economically important in the matcher, but it is fill/queue sensitivity, not a named bot response visible in future books.

## Final Decision

Accept `traders/r5_participant_trader.py`.

Rationale:

- named participant alpha is unavailable;
- direct aggregate trade-flow overlays failed PnL validation;
- same-category lead-lag/order-book response signals are causal, stable enough across days, and spread-adjusted;
- all public days are positive;
- file size is safely below 100KB;
- position limit is clipped at 10 for all Round 5 products.
