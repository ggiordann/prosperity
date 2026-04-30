# Round 5 Final Merge Log

Generated on 2026-04-30 from the local Rust backtester and bundled Round 5 public days 2, 3, and 4.

## Repository Inspection

- Candidate files found: `r5_basket_trader.py`, `r5_drift_trader.py`, `r5_latency_trader.py`, `r5_mean_reversion_trader.py`, `r5_orderbook_trader.py`, `r5_participant_trader.py`, `r5_regime_filter_trader.py`, `r5_ml_distilled_trader.py`, `r5_strategy_tournament_trader.py`.
- Data: `prosperity_rust_backtester/datasets/round5/prices_round_5_day_{2,3,4}.csv` and matching trades.
- Backtester: `prosperity_rust_backtester`, command shape `./scripts/cargo_local.sh run --release -- --trader <file> --dataset round5 --products off --artifact-mode none --flat --run-id <id>`.
- Datamodel: injected by the Rust backtester from `src/pytrader.rs`; final file uses normal `from datamodel import Order, OrderDepth, TradingState`.
- Existing prior best: `prosperity_rust_backtester/traders/final_round5_trader.py`, 17.45 KiB, prior log PnL `2,557,286.50`.

## Robustness Score

Approximate score used for ranking:

`mean_day_pnl - 0.50 * day_pnl_stdev - 0.02 * own_trades - 100 * file_size_kib - concentration_penalty`

Concentration penalty applies only when the largest day is more than 45 percent of total PnL. Metrics-only runs do not expose intraday drawdown, so day instability and turnover were used as drawdown/fragility proxies.

## Standalone Candidate Validation

| Candidate | Total PnL | D+2 | D+3 | D+4 | Trades | KiB | Robust score | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `r5_latency_trader.py` | 2,557,286.50 | 789,912.50 | 1,062,299.50 | 705,074.50 | 3,893 | 17.5 | 774,411 | Keep as core |
| `r5_ml_distilled_trader.py` | 2,557,286.50 | 789,912.50 | 1,062,299.50 | 705,074.50 | 3,893 | 17.5 | 774,411 | Reject duplicate; byte-identical to latency |
| `r5_orderbook_trader.py` | 2,557,286.50 | 789,912.50 | 1,062,299.50 | 705,074.50 | 3,893 | 20.2 | 774,139 | Reject duplicate behavior; heavier file |
| `r5_participant_trader.py` | 2,557,286.50 | 789,912.50 | 1,062,299.50 | 705,074.50 | 3,893 | 17.5 | 774,411 | Reject duplicate; byte-identical to latency |
| `r5_strategy_tournament_trader.py` | 2,543,655.50 | 787,022.50 | 1,058,008.50 | 698,624.50 | 3,891 | 17.3 | 769,625 | Reject; lower than latency |
| `r5_regime_filter_trader.py` | 1,357,756.00 | 405,867.00 | 514,722.00 | 437,167.00 | 1,805 | 21.9 | 427,483 | Use only selected product filter slice |
| `r5_basket_trader.py` | 1,057,361.50 | 381,659.00 | 335,472.50 | 340,230.00 | 2,547 | 7.4 | 341,289 | Use only selected product basket slice |
| `r5_drift_trader.py` | 274,326.00 | 112,315.00 | 69,143.00 | 92,868.00 | 43 | 1.7 | 82,441 | Reject; low incremental expectation and conflicts with core |
| `r5_mean_reversion_trader.py` | 73,628.00 | 1,094.00 | 33,905.00 | 38,629.00 | 692 | 7.7 | 14,583 | Reject; weak, concentrated away from D+2 |

All candidates used legal imports only: `datamodel`, `typing`, and sometimes `json`. No debug prints or file reads were detected in candidate files.

## Incremental Merge Tests

Probe trader: `research/round5/merge_probe.py`. It ran candidate modules with isolated `traderData` and routed selected products so interaction tests used actual backtester fills. The cargo wrapper strips arbitrary environment variables, so routed probes were run via the compiled release binary directly.

Baseline: `r5_latency_trader.py`, PnL `2,557,286.50`.

| Step | Routed products | PnL | D+2 | D+3 | D+4 | Increment | Action |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Basket top 3 | `PANEL_2X2`, `PEBBLES_M`, `ROBOT_MOPPING` | 2,638,429.50 | 868,208.50 | 1,057,513.50 | 712,707.50 | +81,143.00 | Keep |
| Basket top 4 | top 3 + `ROBOT_IRONING` | 2,649,992.50 | 878,715.50 | 1,047,851.50 | 723,425.50 | +11,563.00 vs top 3 | Keep |
| Basket top 7 | top 4 + `MICROCHIP_RECTANGLE`, `SNACKPACK_STRAWBERRY`, `GALAXY_SOUNDS_SOLAR_WINDS` | 2,664,492.50 | 906,207.50 | 1,019,894.50 | 738,390.50 | +14,500.00 vs top 4 | Reject as less robust |
| Regime stable | `SLEEP_POD_SUEDE`, `ROBOT_LAUNDRY`, `PANEL_2X4` | 2,562,198.50 | 789,677.50 | 1,064,575.50 | 707,945.50 | +4,912.00 | Keep as slice |
| Basket top 4 + regime stable | combined kept slices | 2,654,904.50 | 878,480.50 | 1,050,127.50 | 726,296.50 | +97,618.00 vs baseline | Final |

Rejected basket-top-7 additions were positive in local total but less robust:

- `MICROCHIP_RECTANGLE`: incremental deltas `+19,109`, `-8,224`, `-3,063`.
- `SNACKPACK_STRAWBERRY`: incremental deltas `+9,606`, `-7,590`, `+2,558`.
- `GALAXY_SOUNDS_SOLAR_WINDS`: incremental deltas `-1,223`, `-12,143`, `+15,470`.

The final route has no negative product totals and no product losing on two or more days.

## Final Selection

Included:

- Lead-lag/static fair-value core from the latency/orderbook/ML/participant duplicate family.
- Basket residual slice for `PANEL_2X2`, `PEBBLES_M`, `ROBOT_MOPPING`, `ROBOT_IRONING`.
- Regime-filtered slice for `SLEEP_POD_SUEDE`, `ROBOT_LAUNDRY`, `PANEL_2X4`.
- Shared final aggregate position-limit safety layer.

Excluded:

- Duplicate candidate modules as separate inclusions.
- Full basket strategy: lower standalone PnL and several unstable product swaps.
- Full regime filter: lower PnL; only three products added incrementally.
- Drift and mean reversion: low standalone/incremental quality.
- Tournament compressed trader: lower than latency core.

## Final Backtest

Command run:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../traders/final_round5_trader.py --dataset round5 --products off --artifact-mode none --flat --run-id r5_final_integrated
```

Result:

| Day | Trades | PnL |
| --- | ---: | ---: |
| D+2 | 1,266 | 878,480.50 |
| D+3 | 1,564 | 1,050,127.50 |
| D+4 | 1,365 | 726,296.50 |
| Total | 4,195 | 2,654,904.50 |

File checks:

- `traders/final_round5_trader.py`: 32,642 bytes, under 100 KiB.
- Imports: `from datamodel import Order, OrderDepth, TradingState`, `from typing import Dict, List`, `import json`.
- `python3 -m py_compile traders/final_round5_trader.py` passed.
- Exactly one `Trader` class and one `run(self, state: TradingState)`.
