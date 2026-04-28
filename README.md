# Prosperity Research Workspace

Round 5 is now the active workspace.

## Layout

- `prosperity_rust_backtester/` contains the upstream Rust backtester, updated to v0.5.0 with Round 5 data.
- `round 4/` archives the Round 4 research code, generated analysis, temporary searches, and final champion files.
- `round 5/` is the clean working area for the new round.
- `src/prosperity/` contains the reusable research platform code that is not tied to a single round.

## Quick Backtest

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run -- --trader traders/latest_trader.py --dataset round5 --products summary
```
