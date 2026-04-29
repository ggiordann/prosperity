# Round 5 Relationship Map

Generated from bundled Round 5 days 2, 3, and 4. The final strategy treats the market as 10 category clusters of 5 related products and trades only same-category relationships.

## Final Edge Policy

The final file uses `leadlag_union_robust2_pred2.py` copied into `prosperity_rust_backtester/traders/latest_trader.py`.

An edge is included only if it passed at least one of these filters:

- predictive filter: leader mid change has the expected sign against follower future return on at least two public days;
- robust-PnL filter: adding the edge improved product PnL on at least two public days in the second-layer search.

Counts:

- Total final lead-lag edges: 95
- Passed both filters: 57
- Passed robust-PnL only: 15
- Passed predictive only: 23
- Removed from max-public-score trader: 5

Removed failed-both edges:

| follower | leader | lag | k |
| --- | --- | ---: | ---: |
| OXYGEN_SHAKE_MINT | OXYGEN_SHAKE_MORNING_BREATH | 500 | 0.1 |
| PANEL_1X2 | PANEL_4X4 | 500 | -0.1 |
| PANEL_2X2 | PANEL_1X2 | 100 | 0.1 |
| SLEEP_POD_COTTON | SLEEP_POD_SUEDE | 20 | -0.1 |
| UV_VISOR_ORANGE | UV_VISOR_MAGENTA | 500 | 0.25 |

## Strong Relationship Clusters

- Pebbles: strongest category contribution. `PEBBLES_XL`, `PEBBLES_L`, `PEBBLES_XS`, and `PEBBLES_S` all retain high-value slow-response edges.
- Microchips: robust short and medium lags among circle, oval, rectangle, square, and triangle. `MICROCHIP_SQUARE` and `MICROCHIP_OVAL` are top PnL contributors.
- UV-visors: long-lag visor relationships, especially `UV_VISOR_MAGENTA`, `UV_VISOR_AMBER`, and `UV_VISOR_RED`.
- Translators: stable slow edges around `TRANSLATOR_GRAPHITE_MIST`, `TRANSLATOR_VOID_BLUE`, and `TRANSLATOR_ECLIPSE_CHARCOAL`.
- Sleep pods: `SLEEP_POD_LAMB_WOOL`, `SLEEP_POD_SUEDE`, and `SLEEP_POD_POLYESTER` are profitable with slow category relationships.
- Panels and oxygen shakes: weaker raw correlations but useful selected lagged reactions.

## Strongest Final Edges

| follower | leader | lag | k | note |
| --- | --- | ---: | ---: | --- |
| PEBBLES_XS | PEBBLES_XL | 200 | 0.1 | high first-layer gain |
| PEBBLES_L | PEBBLES_S | 500 | 0.5 | high first-layer gain |
| PEBBLES_L | PEBBLES_XL | 5 | 0.5 | high second-layer gain |
| UV_VISOR_MAGENTA | UV_VISOR_AMBER | 500 | 1.0 | strong visor lag |
| UV_VISOR_MAGENTA | UV_VISOR_YELLOW | 20 | -0.25 | robust second signal |
| PANEL_1X2 | PANEL_2X2 | 200 | -1.0 | strong panel reaction |
| MICROCHIP_OVAL | MICROCHIP_RECTANGLE | 2 | -0.05 | short-lag microchip |
| MICROCHIP_SQUARE | MICROCHIP_TRIANGLE | 5 | 0.05 | high second-layer gain |
| SLEEP_POD_LAMB_WOOL | SLEEP_POD_COTTON | 500 | -1.0 | slow sleep-pod effect |
| OXYGEN_SHAKE_CHOCOLATE | OXYGEN_SHAKE_EVENING_BREATH | 50 | -0.1 | oxygen category lag |
| TRANSLATOR_GRAPHITE_MIST | TRANSLATOR_VOID_BLUE | 500 | 0.5 | slow translator effect |
| GALAXY_SOUNDS_SOLAR_FLAMES | GALAXY_SOUNDS_BLACK_HOLES | 500 | -1.0 | validated galaxy lag |

## Other Research Findings

- Direct fixed-sum pebbles basket trading was structurally real but weaker than the selected lag overlays.
- Same-category basket ridge models produced stationary-looking residuals, but live quoting around those residuals underperformed the simpler lead-lag fair-value shift.
- Public trade-flow direction showed statistical predictive structure at 200-500 tick horizons. Product-flow and category-flow overlays were tested and rejected because they reduced final Rust PnL.
- Cross-category exploration did not beat same-category structure after overfitting controls, so the final trader avoids cross-category edges.
- Counterparty analysis was unavailable because buyer/seller fields are blank.
