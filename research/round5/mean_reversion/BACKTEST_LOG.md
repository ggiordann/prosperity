# Round 5 Mean Reversion Backtest Log

Final trader: `traders/r5_mean_reversion_trader.py`.

Exact final command:

```bash
cd prosperity_rust_backtester
$HOME/Library/Caches/rust_backtester/target/release/rust_backtester --trader ../traders/r5_mean_reversion_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id r5_mean_reversion_final
```

Final saved run: `prosperity_rust_backtester/runs/r5_mean_reversion_final`.

File size: `7,935` bytes.

## Final PnL

| Day | Own trades | Final PnL |
|---:|---:|---:|
| D+2 | 230 | 1,094 |
| D+3 | 207 | 33,905 |
| D+4 | 255 | 38,629 |
| Total | 692 | 73,628 |

PnL by product:

| Product | D+2 | D+3 | D+4 | Total |
|---|---:|---:|---:|---:|
| PEBBLES_XL | 1,094 | 33,905 | 38,629 | 73,628 |
| All other 49 products | 0 | 0 | 0 | 0 |

Maximum drawdown from saved PnL series:

| Scope | Max drawdown |
|---|---:|
| D+2 | 17,200 |
| D+3 | 9,525 |
| D+4 | 9,617 |
| Combined no-carry series | 17,200 |

## Train/Test And Leave-One-Day-Out

No state is carried across days. Product selection was driven by robust diagnostics, then checked on each day.

| Validation | PnL |
|---|---:|
| All days | 73,628 |
| Day 1 removed (`D+2` removed) | 72,534 |
| Day 2 removed (`D+3` removed) | 39,723 |
| Day 3 removed (`D+4` removed) | 34,999 |

The strategy is not Day-1-only: removing the first available public day retains nearly all PnL.

## Parameter Perturbation

Final parameters: `PEBBLES_XL`, self SMA, window `288`, entry z `1.75`.

| Variant | D+2 | D+3 | D+4 | Total |
|---|---:|---:|---:|---:|
| Window 230 (-20%) | -3,774 | 33,706 | 27,226 | 57,158 |
| Window 288 final | 1,094 | 33,905 | 38,629 | 73,628 |
| Window 346 (+20%) | -6,704 | 33,596 | 30,120 | 57,012 |

This passes the non-collapse check: both 20% perturbations stay strongly positive.

## EMA Vs SMA Vs Median

Same rough signal family at window 200 and z 1.35:

| Fair method | D+2 | D+3 | D+4 | Total | Decision |
|---|---:|---:|---:|---:|---|
| EMA | -13,392 | 9,405 | 1,990 | -1,997 | Reject |
| Median | -4,803 | 22,440 | 17,786 | 35,423 | Acceptable but worse |
| SMA | 1,287 | 28,786 | 17,640 | 47,713 | Best method |

## Other Tested / Excluded

| Variant | Total | Reason excluded |
|---|---:|---|
| PEBBLES_XL cross residual, median 500 | 67,325 | Good, but self-SMA z 1.75 was simpler and higher PnL. |
| First multi-product residual candidate set | 8,981 | Weak products leaked losses. |
| MICROCHIP_RECTANGLE residual | -34,554 inside candidate set | Offline edge did not survive execution. |
| PEBBLES_XS residual | -3,779 inside candidate set | Too unstable. |
| TRANSLATOR_VOID_BLUE residual | -10,453 inside candidate set | Too unstable. |
| ROBOT_IRONING residual | -9,558 inside candidate set | Too unstable. |

## Final Acceptance

Accepted because:

- Trades one product with the only robust official PnL.
- Positive on every available day.
- Strongly positive with first public day removed.
- Window perturbation by 20% does not collapse.
- EMA comparison explicitly rejects the fragile method.
- Product limit is capped at 10 and orders are clipped.
