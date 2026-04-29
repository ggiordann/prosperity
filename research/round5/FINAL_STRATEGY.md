# Round 5 Final Strategy

Final file to upload:

```text
prosperity_rust_backtester/traders/latest_trader.py
```

## Strategy

The submitted trader is the validated same-category relationship strategy, not the prior max-public-score tail variant.

Core components:

- Static/current-mid fair values with product-specific anchor shifts.
- Product-level z-take, passive quote edge, quote improvement, and selective depth walking.
- Same-category lead-lag fair-value overlays using only current and past mid prices.
- 95 retained lead-lag edges. An edge is retained only if it passed at least one validation screen:
  - causal predictive support on at least two public days, or
  - PnL improvement on at least two public days in the robust second-layer search.
- Five edges from the public max-score trader were removed because they failed both validation screens.

Runtime state stores rolling mid histories for selected same-category leaders, capped at 501 points. There are no external files, no timestamp hardcoding, no future path constants, and no unsupported imports.

## Final Backtest

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader traders/latest_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_final_validated_union
```

Total PnL: `2,543,655.5`

Day PnL:

- Day 2: `787,022.5`
- Day 3: `1,058,008.5`
- Day 4: `698,624.5`

Own trades: `3,891`

File size: `17,486 bytes`, safely below 100KB.

Allowed imports only:

```python
from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json
```

## Strongest Alpha Sources

- Same-category "same but slower" price lead-lag in pebbles, microchips, UV-visors, translators, sleep pods, panels, and oxygen shakes.
- Pebbles fixed-sum/category structure, exploited indirectly through lead-lag rather than direct basket trading.
- Product anchor shifts and execution retuning, which lifted the baseline before relationship signals were added.
- Microchip short-lag relationships, especially `MICROCHIP_CIRCLE`, `MICROCHIP_OVAL`, `MICROCHIP_RECTANGLE`, `MICROCHIP_SQUARE`, and `MICROCHIP_TRIANGLE`.

## Rejected From Final

- Max-public-score two-layer lead-lag trader: `2,546,711.5`, but kept five edges that failed both validation screens.
- Product and category public-trade-flow overlays: statistically interesting but reduced backtest PnL versus the validated union.
- Direct basket fair-value blends: structurally plausible, but worse in Rust than lead-lag plus execution tuning.
- Counterparty alpha: unavailable because Round 5 trade counterparty fields are blank.

## Key Artifacts

- `research/round5/BACKTEST_LOG.md`
- `research/round5/RELATIONSHIP_MAP.md`
- `research/round5/final_product_pnl.csv`
- `research/round5/leadlag_edge_predictive_stats.csv`
- `research/round5/generated_traders/leadlag_union_robust2_pred2.py`
