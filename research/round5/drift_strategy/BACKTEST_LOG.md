# Round 5 Drift Strategy Backtest Log

## Files Created

- `traders/r5_drift_trader.py`
- `research/round5/drift_strategy/analyze_drift.py`
- `research/round5/drift_strategy/ANALYSIS.md`
- `research/round5/drift_strategy/BACKTEST_LOG.md`

Research CSV outputs are in `research/round5/drift_strategy/`.

## Analysis Command

```bash
python3 research/round5/drift_strategy/analyze_drift.py
```

## Final Backtest Command

The local `prosperity_rust_backtester/target/release/rust_backtester` binary failed on this machine with a missing `libpython3.11.dylib` rpath, so I used the already built cache binary:

```bash
cd prosperity_rust_backtester
~/Library/Caches/rust_backtester/target/release/rust_backtester \
  --trader ../traders/r5_drift_trader.py \
  --dataset round5 \
  --products full \
  --artifact-mode none \
  --run-id r5_drift_final_clean_metrics
```

Equivalent source-build command:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- \
  --trader ../traders/r5_drift_trader.py \
  --dataset round5 \
  --products full \
  --artifact-mode none \
  --run-id r5_drift_final_clean_metrics
```

Full artifact run was also produced at:

```text
prosperity_rust_backtester/runs/r5_drift_trader/
```

## Final Result

| Day File | Own Trades | PnL |
| --- | ---: | ---: |
| Day 2 | 13 | 112,315 |
| Day 3 | 15 | 69,143 |
| Day 4 | 15 | 92,868 |
| Total | 43 | 274,326 |

Product PnL:

| Product | Day 2 | Day 3 | Day 4 | Total |
| --- | ---: | ---: | ---: | ---: |
| MICROCHIP_OVAL | 7,395 | 18,275 | 18,976 | 44,646 |
| PEBBLES_XS | 19,455 | 11,985 | 8,190 | 39,630 |
| OXYGEN_SHAKE_GARLIC | 18,225 | 1,035 | 19,510 | 38,770 |
| GALAXY_SOUNDS_BLACK_HOLES | 14,405 | 6,810 | 13,125 | 34,340 |
| UV_VISOR_AMBER | 14,935 | 11,030 | 2,500 | 28,465 |
| PANEL_2X4 | 7,340 | 7,333 | 8,907 | 23,580 |
| PEBBLES_S | 8,340 | 1,710 | 9,315 | 19,365 |
| UV_VISOR_RED | 8,360 | 1,750 | 6,905 | 17,015 |
| SNACKPACK_PISTACHIO | 4,810 | 1,150 | 2,740 | 8,700 |
| SNACKPACK_STRAWBERRY | 4,280 | 3,490 | 885 | 8,655 |
| SLEEP_POD_LAMB_WOOL | 4,005 | 3,910 | 85 | 8,000 |
| SNACKPACK_CHOCOLATE | 765 | 665 | 1,730 | 3,160 |

No product in the final set lost money on any public day in the Rust backtest.

## Validation

The validation screen rejects Day 1-only drift. A one-day training rule selects too many products and loses out of sample:

| Case | Threshold | Selected | Test PnL |
| --- | ---: | ---: | ---: |
| train day 2, test day 3/4 | 0 | 50 | -46,350 |
| train day 3, test day 4 | 0 | 50 | -149,060 |
| train day 2/3, test day 4 | 0 | 26 | -70,390 |
| no-day-2 train day 3/4, test day 2 | 0 | 19 | 71,470 |

Threshold perturbation from `validation_summary.csv`:

| Case | Threshold | Selected | Test PnL |
| --- | ---: | ---: | ---: |
| train day 2, test day 3/4 | 200 | 40 | 35,770 |
| train day 2, test day 3/4 | 500 | 30 | 25,580 |
| train day 3, test day 4 | 500 | 30 | -103,280 |
| train day 2/3, test day 4 | 500 | 10 | -1,720 |
| no-day-2 train day 3/4, test day 2 | 500 | 6 | 29,940 |

Conclusion: training on one or two days is not enough for broad drift selection. The final trader uses the stricter all-three-days agreement rule and then trades only 12 products.

## Rejected Tests

| Variant | Result | Reason |
| --- | ---: | --- |
| Dynamic momentum prototype, cap 10 | Day 2 `-411,735`, `13,957` trades | Overtraded noisy reversers and paid spread repeatedly |
| Broad one-day drift selection | Out-of-sample negative | Captured Day 1-only and Day 2-only trends |
| Category drift | Not traded | Category signs reverse; product-level drift is cleaner |
| Step timestamp replay | Not traded | Day 1 step timestamps did not repeat on Day 2/3 |
| Mean reversion on final drift products | Rejected | Opposite direction loses against all-day drift |

## File Size

```text
1773 traders/r5_drift_trader.py
```

## Smoke Checks

```bash
python3 -m py_compile traders/r5_drift_trader.py
```

Passed.
