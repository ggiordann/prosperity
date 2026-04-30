# Round 5 Regime Filter Backtest Log

## Trader

- File: `traders/r5_regime_filter_trader.py`
- File size: `22,396` bytes
- Imports: `datamodel`, `typing`, `json`
- Runtime files: none
- Debug prints: none
- Products considered: all 50 Round 5 products
- Products traded after filter: 37

## Exact Command

Run from `prosperity_rust_backtester/`:

```bash
./scripts/cargo_local.sh run --release -- --trader ../traders/r5_regime_filter_trader.py --dataset round5 --products full --artifact-mode none --flat --run-id r5_regime_filter_metrics
```

I used `--artifact-mode none` because `--artifact-mode full` produced a multi-gigabyte Day 1 replay bundle and was killed before finishing all days. Metrics-only mode completed cleanly and wrote:

- `prosperity_rust_backtester/runs/r5_regime_filter_metrics/round5-day+2-metrics.json`
- `prosperity_rust_backtester/runs/r5_regime_filter_metrics/round5-day+3-metrics.json`
- `prosperity_rust_backtester/runs/r5_regime_filter_metrics/round5-day+4-metrics.json`

## Rust Output

```text
trader: r5_regime_filter_trader.py
dataset: round5
mode: fast
artifacts: metrics-only
bundle: runs/r5_regime_filter_metrics [flat multi-run output]
SET             DAY    TICKS  OWN_TRADES    FINAL_PNL
D+2               2    10000         499    405867.00
D+3               3    10000         699    514722.00
D+4               4    10000         607    437167.00
TOTAL             -    30000        1805   1357756.00
```

## Comparison

| Strategy | Day 1 | Day 2 | Day 3 | Total | Trades | Stability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unfiltered final merged | 789,912.50 | 1,062,299.50 | 705,074.50 | 2,557,286.50 | 3,893 | 0.664 |
| Regime-filtered | 405,867.00 | 514,722.00 | 437,167.00 | 1,357,756.00 | 1,805 | 0.789 |

Stability is `min(day PnL) / max(day PnL)`.

## Validation Summary

- Day 1 removed: `951,889.00`
- Day 2 removed: `843,034.00`
- Day 3 removed: `920,589.00`
- Stable-filtered versus unfiltered: lower PnL, lower turnover, better day balance
- Parameter perturbation: concentration thresholds from `0.55` to `0.75` all remained positive on all days in the product-filter arithmetic
- Standalone simple-signal grid: filtered out as primary alpha; retained only as classifier/risk context

## Notes

The implemented trader is intentionally conservative. It should be treated as a robustness/risk layer for merged strategies, not as a replacement for the highest local-PnL submission.
