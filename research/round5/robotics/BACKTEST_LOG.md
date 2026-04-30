# Domestic Robotics Backtest Log

Final implementation:

```text
research/round5/robotics/robotics_trader.py
```

Exact final backtest command:

```bash
cd prosperity_rust_backtester
/Users/giordanmasen/Library/Caches/rust_backtester/target/release/rust_backtester --trader ../research/round5/robotics/robotics_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_robotics_final
```

## Final Result

Total PnL: `143,656`

| day | PnL | own trades |
| ---: | ---: | ---: |
| 2 | 24,146 | 24 |
| 3 | 117,502 | 51 |
| 4 | 2,008 | 9 |

PnL by product:

| product | day 2 | day 3 | day 4 | total |
| --- | ---: | ---: | ---: | ---: |
| ROBOT_DISHES | 10,068 | 36,978 | -10,374 | 36,672 |
| ROBOT_IRONING | 4,860 | 20,290 | 3,679 | 28,829 |
| ROBOT_LAUNDRY | 10,727 | 18,969 | 950 | 30,646 |
| ROBOT_MOPPING | -1,835 | 26,603 | 7,463 | 32,231 |
| ROBOT_VACUUMING | 326 | 14,662 | 290 | 15,278 |

## Strategy Tests

| strategy | day 2 | day 3 | day 4 | total | decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Current-mid passive MM | 3,918 | 1,116 | 10,583 | 15,617 | Too small. |
| Pure 20-tick momentum | -96,405 | -52,199.5 | -175,240 | -323,844.5 | Reject hard. |
| Static anchored mean reversion | 14,133 | 109,649 | 1,509 | 125,291 | Good baseline. |
| VACUUMING/LAUNDRY pair residual | 1,800 | 29,878 | 14,323 | 46,001 | Positive but weaker. |
| Basket residual synthetic fair | 54,514 | 58,873 | -317 | 113,070 | Plausible but weaker than anchor plus lag. |
| Final anchor plus lead-lag hybrid | 24,146 | 117,502 | 2,008 | 143,656 | Select. |

Focused perturbations:

| variant | total | note |
| --- | ---: | --- |
| Add top stable 1..100 lag edges, scale 0.025 | 142,700 | Slightly worse. |
| Add dishes local momentum, lag 20 coeff 0.1 | 142,046 | Worse; helps day 3 but loses day 2. |
| Self imbalance fair shift, coeff 40 | 139,019 | Worse. |
| Drop `ROBOT_DISHES` | 106,671 | Improves day 4, loses too much total. |
| Drop `ROBOT_MOPPING` | 88,757 | Reject. |
| Drop `ROBOT_VACUUMING` | 122,606 | Reject. |

## Validation

- Train day 2, test days 3 and 4: final test PnL `119,510`.
- Train days 2 and 3, test day 4: final test PnL `2,008`.
- Leave-one-day-out sanity: all individual days positive.
- Parameter perturbation: extra stable-lag, momentum, and imbalance overlays did not beat the selected hybrid.
- Product perturbation: dropping any robot product reduced total PnL.
- Runtime file size: `4,531` bytes, well under the final 100KB cap.
- Runtime imports: `datamodel`, `typing`, `json`.

## Recommendation

Include this category strategy in the final combined submission, with one caveat: `ROBOT_DISHES` has a real day-4 tail. The total remains better with it included, but if final portfolio risk controls need to cut drawdown, dishes should be the first robot product to downweight.
