# Pebbles Backtest Log

All runs use the Rust backtester and bundled Round 5 days `2`, `3`, and `4`.

## Final Command

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/pebbles/pebbles_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_pebbles_final
```

## Final Result

| day | own trades | PnL |
| --- | ---: | ---: |
| 2 | 185 | 148,194.0 |
| 3 | 211 | 185,892.0 |
| 4 | 148 | 94,638.0 |
| total | 544 | 428,724.0 |

## PnL By Product

| product | day 2 | day 3 | day 4 | total |
| --- | ---: | ---: | ---: | ---: |
| `PEBBLES_XL` | 71,115.0 | 64,081.0 | -2,374.0 | 132,822.0 |
| `PEBBLES_L` | 43,877.0 | 39,042.0 | 12,005.0 | 94,924.0 |
| `PEBBLES_XS` | 19,455.0 | 39,811.0 | 24,061.0 | 83,327.0 |
| `PEBBLES_S` | 13,525.0 | 18,363.0 | 33,973.0 | 65,861.0 |
| `PEBBLES_M` | 222.0 | 24,595.0 | 26,973.0 | 51,790.0 |

No runtime errors or position-limit breaches appeared in the final run. The trader returns orders only for the five Pebbles products.

## Strategy Iterations

| strategy | total | day 2 | day 3 | day 4 | note |
| --- | ---: | ---: | ---: | ---: | --- |
| pure current-mid market making | 50,654.0 | 16,899.0 | 19,403.0 | 14,352.0 | spread capture only |
| static anchors, no lead-lag | 352,928.0 | 142,328.0 | 155,555.0 | 55,045.0 | strong baseline |
| fixed-sum residual | 344,974.0 | 141,886.0 | 155,468.0 | 47,620.0 | residual is real but too small |
| linear size-curve residual | 303,496.0 | 137,823.0 | 120,678.0 | 44,995.0 | curve shape unstable |
| `M` butterfly vs `(S+L)/2` | 334,013.0 | 153,517.0 | 136,648.0 | 43,848.0 | day-2 lift, weak validation |
| base lead-lag hybrid | 424,587.0 | 148,718.0 | 183,483.0 | 92,386.0 | prior all-product Pebbles slice |
| final, `PEBBLES_M` lead scale `1.25x` | 428,724.0 | 148,194.0 | 185,892.0 | 94,638.0 | selected |

Variant sweep output: `research/round5/pebbles/variant_results.csv`.

## Perturbation Checks

Top refinement variants:

| variant | total | day 2 | day 3 | day 4 |
| --- | ---: | ---: | ---: | ---: |
| `pscale_pebbles_m_1p25` | 428,724.0 | 148,194.0 | 185,892.0 | 94,638.0 |
| `shift_pebbles_m_m25` | 427,650.0 | 154,788.0 | 179,876.0 | 92,986.0 |
| `shift_pebbles_xl_p25` | 427,488.0 | 150,150.0 | 184,952.0 | 92,386.0 |
| `shift_pebbles_m_p25` | 425,976.0 | 147,058.0 | 186,627.0 | 92,291.0 |
| `pscale_pebbles_m_0p75` | 425,276.0 | 150,838.0 | 180,655.0 | 93,783.0 |
| `lead_s1p0` | 424,587.0 | 148,718.0 | 183,483.0 | 92,386.0 |

The final refinement is not a one-day-only artifact: it slightly hurts day 2 versus the base but improves days 3 and 4. Nearby `PEBBLES_M` shift and scale perturbations remain close, which suggests the signal is not a knife-edge parameter.

## Products Traded

Traded: all five Pebbles.

Ignored: none.

Used as signals:

- `PEBBLES_XL`: strongest leader, especially for `PEBBLES_M` and `PEBBLES_XS`.
- `PEBBLES_M`: useful leader for `PEBBLES_XL`.
- `PEBBLES_S`, `PEBBLES_XS`, `PEBBLES_L`: slower relationship signals and passive quoting targets.

## Include Recommendation

Include this category strategy in the final combined Round 5 submission. It is compact, uses only allowed imports, has no timestamp hard-coding, stores only rolling mid histories, respects per-product limit `10`, and contributes positive PnL on every public Round 5 day.
