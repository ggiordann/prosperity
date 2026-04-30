# Oxygen Shakes Backtest Log

Final implementation:

`research/round5/oxygen_shakes/oxygen_shakes_strategy.py`

Exact final command:

```bash
cd /Users/giordanmasen/Desktop/projects/prosperity/prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/oxygen_shakes/oxygen_shakes_strategy.py --dataset round5 --products full --artifact-mode none
```

## Final Result

| Day | Own Trades | PnL |
|---:|---:|---:|
| 2 | 118 | 65,431 |
| 3 | 194 | 118,668 |
| 4 | 138 | 58,643 |
| Total | 450 | 242,742 |

PnL by product:

| Product | Day 2 | Day 3 | Day 4 | Total |
|---|---:|---:|---:|---:|
| `OXYGEN_SHAKE_CHOCOLATE` | 12,416 | 15,986 | 17,908 | 46,310 |
| `OXYGEN_SHAKE_EVENING_BREATH` | 361 | 32,473 | 25,966 | 58,800 |
| `OXYGEN_SHAKE_GARLIC` | 19,232 | 30,159 | -4,761 | 44,630 |
| `OXYGEN_SHAKE_MINT` | 31,847 | 4,000 | 15,805 | 51,652 |
| `OXYGEN_SHAKE_MORNING_BREATH` | 1,575 | 36,050 | 3,725 | 41,350 |

## Strategy Ablations

| Variant | Total | Day 2 | Day 3 | Day 4 | Own Trades | Notes |
|---|---:|---:|---:|---:|---:|---|
| `hybrid_base` | 242,742 | 65,431 | 118,668 | 58,643 | 450 | Selected |
| `no_garlic_walk` | 242,629 | 65,431 | 118,615 | 58,583 | 450 | Same idea, slightly lower |
| `garlic_take2x` | 232,108 | 66,751 | 112,645 | 52,712 | 470 | Lower total |
| `plus_small_stable` | 210,495 | 49,734 | 112,309 | 48,452 | 419 | Extra lead-lag signals overfit/noisy |
| `plus_medium_stable` | 208,148.5 | 48,327.5 | 113,374 | 46,447 | 441 | Extra lead-lag signals overfit/noisy |
| `no_signals` | 202,797 | 62,048 | 100,585 | 40,164 | 525 | Cross-product signals add 39,945 |
| `garlic_mid` | 198,751 | 44,266 | 91,396 | 63,089 | 594 | Helps day 4 but hurts days 2-3 |
| `no_garlic_product` | 195,208 | 45,385 | 86,497 | 63,326 | 393 | Garlic worth keeping despite day 4 |
| `no_morning_product` | 193,966 | 64,945 | 75,717 | 53,304 | 424 | Morning worth keeping |
| `static_all_no_mid` | 184,109 | 61,930 | 98,612 | 23,567 | 188 | Static-only weaker |
| `replace_research_signals` | 171,586 | 40,238 | 91,046 | 40,302 | 383 | Statistical signal list did not trade well |
| `quotes_only_base` | 122,592 | 35,984 | 61,594 | 25,014 | 486 | Crossing thresholds matter |
| `mid_mm_edge2` | 68,871 | 9,635 | 23,845.5 | 35,390.5 | 3,210 | Pure market making small |
| `mid_mm_edge5` | 68,079.5 | 10,173 | 24,436.5 | 33,470 | 2,987 | Pure market making small |

## Parameter Perturbation

| Perturbation | Total | Day 2 | Day 3 | Day 4 |
|---|---:|---:|---:|---:|
| Signal scale `0.5x` | 211,364 | 64,404 | 104,830 | 42,130 |
| Signal scale `0.75x` | 227,257 | 64,624 | 108,784 | 53,849 |
| Signal scale `1.25x` | 226,781 | 64,240 | 109,866 | 52,675 |
| Signal scale `1.5x` | 203,111 | 58,824 | 98,057 | 46,230 |
| Edge scale `0.75x` | 235,310 | 62,406 | 113,461 | 59,443 |
| Edge scale `1.25x` | 236,679 | 64,049 | 114,986 | 57,644 |
| Edge scale `1.5x` | 227,312 | 63,193 | 112,776 | 51,343 |
| Take scale `0.75x` | 196,828 | 53,427 | 97,964 | 45,437 |
| Take scale `1.25x` | 163,162 | 46,420 | 69,932 | 46,810 |
| Take scale `1.5x` | 166,371 | 50,461 | 67,528 | 48,382 |
| All fair shift `-50` | 157,270 | 55,424 | 95,270 | 6,576 |
| All fair shift `-25` | 169,815 | 56,175 | 103,508 | 10,132 |
| All fair shift `+25` | 178,144 | 37,442 | 90,998 | 49,704 |
| All fair shift `+50` | 162,076.5 | 25,746 | 84,768.5 | 51,562 |

Interpretation: nearby perturbations remained positive but underperformed the selected base. The strategy is not relying on a one-tick threshold accident, but the current constants are locally best among tested variants.

## Walk-Forward Checks

Train-derived variants used only training-day mean/std levels with the same signal topology, then tested out of sample.

| Training Days | Test Day | PnL |
|---|---:|---:|
| Day 2 | Day 3 | 33,305 |
| Day 2 | Day 4 | 15,869 |
| Days 2-3 | Day 4 | 23,817 |
| Days 3-4 | Day 2 | 40,083 |
| Days 2 and 4 | Day 3 | 82,106.5 |
| Days 2-3 | Day 4 | 23,817 |

Interpretation: train-only calibrations are positive but materially weaker. This supports using all public days for final calibration, while avoiding fragile pair/basket coefficients that failed out of sample.

## Include Decision

Include in final combined Round 5 submission.

Reason: best tested category strategy, positive on all public days, all five products positive overall, compact implementation, and no unsupported imports or lookahead mechanics.
