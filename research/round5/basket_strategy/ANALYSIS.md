# Round 5 Basket / Synthetic Fair Value Analysis

Public data note: the local Round 5 files are `day_2`, `day_3`, and `day_4`. In the requested validation language, I treated these as public day 1, day 2, and day 3 respectively.

## Pipeline

Research script:

```bash
python3 research/round5/basket_strategy/research_baskets.py
```

Data:

- `prosperity_rust_backtester/datasets/round5/prices_round_5_day_2.csv`
- `prosperity_rust_backtester/datasets/round5/prices_round_5_day_3.csv`
- `prosperity_rust_backtester/datasets/round5/prices_round_5_day_4.csv`

Candidate families tested for every product `Y`:

- category OLS using the other 4 products in the same category
- top day-demeaned level-correlation baskets
- top return-correlation baskets, used as lag/lead relationship proxies
- cross-category-only top correlation baskets
- ridge-like shrinkage on top 8 correlated products
- 2 to 5 leg sparse/manual baskets selected from the above

For each basket the scan fitted a synthetic fair value, computed residual `mid - synthetic`, robust residual scale, AR(1) half-life, z-score thresholds, spread-adjusted proxy edge, and out-of-sample fold score. Dense ridge candidates were useful for discovery but rejected from the final trader when they were too large or too fragile.

## Final Strategy

Final file:

- `traders/r5_basket_trader.py`
- file size: `7603` bytes

Execution rules:

- trade only the target product of each residual
- buy when target is under fair by z-threshold and edge exceeds spread/margin
- sell when target is over fair by z-threshold and edge exceeds spread/margin
- inventory-aware exits when residual mean reverts toward zero
- position cap: 10 per product
- category throttle: max 5 simultaneous residual targets per category
- no non-basket/static-fair alphas are included

## Strongest Baskets

Top robust proxy baskets across all four validation folds:

| Target | Legs | Type | Fold proxy sum | Min fold |
|---|---|---:|---:|---:|
| `PEBBLES_XS` | `PANEL_2X4`, `UV_VISOR_AMBER` | cross | 287,699 | 50,065 |
| `SLEEP_POD_SUEDE` | `GALAXY_SOUNDS_PLANETARY_RINGS`, `MICROCHIP_SQUARE`, `UV_VISOR_AMBER` | cross | 267,616.5 | 37,707.5 |
| `PEBBLES_M` | `OXYGEN_SHAKE_MORNING_BREATH`, `ROBOT_IRONING`, `PANEL_1X4`, `GALAXY_SOUNDS_SOLAR_WINDS`, `ROBOT_MOPPING` | cross | 254,715.5 | 4,600.5 |
| `SLEEP_POD_POLYESTER` | `SLEEP_POD_COTTON`, `UV_VISOR_AMBER`, `UV_VISOR_YELLOW` | mixed | 235,319 | 21,414.5 |
| `PEBBLES_L` | `MICROCHIP_CIRCLE`, `TRANSLATOR_SPACE_GRAY` | cross | 225,282 | 19,130.5 |
| `PEBBLES_S` | `OXYGEN_SHAKE_GARLIC`, `PANEL_2X4`, `GALAXY_SOUNDS_BLACK_HOLES`, `OXYGEN_SHAKE_EVENING_BREATH`, `MICROCHIP_CIRCLE` | cross | 149,968.5 | 18,301 |

The strongest theme was not a single five-product category. The best baskets repeatedly mixed pebbles, panels, UV, galaxy, oxygen, microchips, translators, and robotics.

## Rejected Baskets

Rejected examples:

- `PEBBLES_XL ~ PANEL_2X4 + PEBBLES_L + PEBBLES_S`: high total proxy, but one fold was negative.
- `PEBBLES_XL` return basket with `UV_VISOR_RED`, galaxy, translator, and sleep legs: negative min fold.
- `PEBBLES_M ~ PEBBLES_XL + PEBBLES_XS`: category-only pair failed a fold.
- `SLEEP_POD_SUEDE` ridge8 and other ridge8 models: strong discovery signal but too many legs for compact final logic and more overfit risk.
- Very low entry thresholds around `0.20x` z-entry: more trades, lower PnL.

## Overfitting Checks

Exact held-out backtests with coefficients refit only on the train fold:

| Train | Test | Exact PnL |
|---|---|---:|
| public day 1 (`day_2`) | public days 2 and 3 (`day_3`, `day_4`) | 484,851 |
| public days 1 and 2 (`day_2`, `day_3`) | public day 3 (`day_4`) | 238,925 |
| public days 2 and 3 (`day_3`, `day_4`) | public day 1 (`day_2`) | 291,912 |
| remove public day 1, train `day_3` | test `day_4` | 246,505 |

Parameter perturbation around the final model:

| Variant | PnL |
|---|---:|
| initial conservative entry scale `1.00`, exit `0.20` | 575,594.5 |
| entry scale `0.75`, exit `0.20` | 789,631 |
| entry scale `0.55`, exit `0.20` | 872,821 |
| entry scale `0.45`, exit `0.20` | 935,006.5 |
| entry scale `0.35`, exit `0.20` | 952,350.5 |
| entry scale `0.30`, exit `0.20` | 942,818 |
| entry scale `0.25`, exit `0.20` | 923,535 |
| entry scale `0.35`, exit `0.10`, category limit 5 | 1,057,361.5 |
| entry scale `0.35`, exit `0.05` | 1,007,911.5 |
| entry scale `0.35`, exit `0.15` | 982,434.5 |

Final parameters sit near a local peak rather than at the most aggressive tested threshold.
