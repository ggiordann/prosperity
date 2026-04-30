# Round 5 Order Book Strategy Analysis

## Scope

- Data: `prosperity_rust_backtester/datasets/round5`, days 2, 3, and 4.
- Products: all 50 Round 5 products.
- Ticks: 30,000 total, 10,000 per day.
- Position limit: 10 per product.
- Matching model: raw CSV public tape. Crosses fill visible book immediately. Passive orders rest and are filled only when same-timestamp public trades sweep through the quote. Joining the best quote sits behind the visible queue; improving inside the spread avoids that queue.

The key output tables from the scan are:

- `research/round5/orderbook_strategy/microstructure_metrics.csv`
- `research/round5/orderbook_strategy/signal_rankings.csv`

## Microstructure Findings

Spread and depth:

- Average best bid/ask spread ranges from `6.39` to `17.83`.
- Best-level depth is shallow for some products, especially microchips and robotics, but larger for snackpacks and several galaxy/oxygen products.
- Quote stability is low for most products. This makes stale passive quotes dangerous unless the fair-value edge is strong.

Passive fill mechanics:

- Joining best bid/ask had measured size-1 fill probability of `0.0` across public data because visible queue ahead was not cleared.
- Improving one tick inside the spread had fill probability around `0.95%` to `1.22%` per product-tick.
- Inside-spread passive fills had positive average 10-tick markout for every product, but the size of that edge varied sharply.

Top passive quote candidates by unconditional 10-tick edge:

| Product | Inside Fill Prob | Markout 10 | Uncond Edge 10 |
| --- | ---: | ---: | ---: |
| PEBBLES_XL | 0.0107 | 14.388 | 0.1545 |
| SNACKPACK_VANILLA | 0.0122 | 8.495 | 0.1034 |
| SNACKPACK_RASPBERRY | 0.0122 | 8.432 | 0.1029 |
| SLEEP_POD_SUEDE | 0.0122 | 7.499 | 0.0915 |
| GALAXY_SOUNDS_PLANETARY_RINGS | 0.0122 | 7.322 | 0.0893 |
| GALAXY_SOUNDS_BLACK_HOLES | 0.0122 | 7.324 | 0.0889 |
| SNACKPACK_STRAWBERRY | 0.0122 | 6.960 | 0.0847 |
| GALAXY_SOUNDS_SOLAR_WINDS | 0.0122 | 6.919 | 0.0847 |
| MICROCHIP_SQUARE | 0.0095 | 8.832 | 0.0844 |
| OXYGEN_SHAKE_GARLIC | 0.0122 | 6.582 | 0.0805 |

Weak passive quote candidates:

- `PEBBLES_M`
- `ROBOT_MOPPING`
- `ROBOT_DISHES`
- `MICROCHIP_RECTANGLE`
- `MICROCHIP_OVAL`
- `ROBOT_IRONING`
- `PEBBLES_XS`
- `TRANSLATOR_GRAPHITE_MIST`
- `MICROCHIP_CIRCLE`
- `MICROCHIP_TRIANGLE`

## Signal Tests

Order book imbalance was measurable but weak. The best 10-tick decile spreads were:

| Signal | Product | Top-Bottom Future Move | Corr |
| --- | --- | ---: | ---: |
| `imb1` | ROBOT_LAUNDRY | 1.812 | 0.0089 |
| `imb1` | ROBOT_VACUUMING | 1.515 | 0.0130 |
| `micro_edge` | ROBOT_LAUNDRY | 1.678 | 0.0095 |
| `abs_book_chg` | PEBBLES_L | -2.550 | -0.0102 |
| `depth_chg` | MICROCHIP_SQUARE | -1.993 | -0.0020 |

Interpretation:

- Imbalance predicts small next-mid movement in a few products.
- The effect is much smaller than the half-spread for crossing.
- Imbalance-only trading over-trades and earns only `211,614.0` across all days.
- Top/bottom imbalance decile crossing markout stayed negative after spread. The best product in that crossing screen, `ROBOT_VACUUMING`, still averaged about `-2.71` after spread.

Spread/depth/book-change signals:

- Spread compression/expansion and depth changes were unstable by product.
- Large book changes sometimes predicted reversal, sometimes continuation.
- None beat the existing fair-value and lead-lag layer after spread.

## Strategy Decision

The selected trader is a fair-value market maker with selective crossing:

- Fair value from static mean-reversion anchors or local mid, depending on product.
- Same-category lead-lag fair-value overlays.
- Passive quotes placed inside the spread only where the quote still has fair-value edge.
- Crosses only when the fair-value edge clears product take thresholds.
- Translators are treated as take-only because passive quote edge was weaker.
- Position-limit clipping is applied per product.

Rejected overlays:

- Raw imbalance-only: too small after spread.
- Microprice/book-shift overlay: `2,553,092.5`, slightly below clean fair-value market making.
- Inventory skew at tested strength: reduced PnL materially.
- Extra spread guard and volatility size cap: reduced PnL.
- Direct basket fair value: `2,016,481.0`, much weaker than lead-lag.

## Product Suitability

Suitable for passive market making:

`PEBBLES_XL`, `SNACKPACK_VANILLA`, `SNACKPACK_RASPBERRY`, `SLEEP_POD_SUEDE`, `GALAXY_SOUNDS_PLANETARY_RINGS`, `GALAXY_SOUNDS_BLACK_HOLES`, `SNACKPACK_STRAWBERRY`, `GALAXY_SOUNDS_SOLAR_WINDS`, `MICROCHIP_SQUARE`, `OXYGEN_SHAKE_GARLIC`, `GALAXY_SOUNDS_SOLAR_FLAMES`, `UV_VISOR_ORANGE`, `SNACKPACK_PISTACHIO`, `OXYGEN_SHAKE_EVENING_BREATH`, `SNACKPACK_CHOCOLATE`, `GALAXY_SOUNDS_DARK_MATTER`, `SLEEP_POD_COTTON`, `SLEEP_POD_POLYESTER`, `OXYGEN_SHAKE_CHOCOLATE`, `OXYGEN_SHAKE_MINT`.

Unsuitable or weak as standalone passive market-making products:

`PEBBLES_M`, `ROBOT_MOPPING`, `ROBOT_DISHES`, `MICROCHIP_RECTANGLE`, `MICROCHIP_OVAL`, `ROBOT_IRONING`, `PEBBLES_XS`, `TRANSLATOR_GRAPHITE_MIST`, `MICROCHIP_CIRCLE`, `MICROCHIP_TRIANGLE`, plus most robotics products.

These weak products can still be profitable with fair-value and lead-lag signals, but not from passive spread capture alone.
