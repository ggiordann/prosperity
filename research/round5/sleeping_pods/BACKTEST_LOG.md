# Sleeping Pods Backtest Log

All backtests use the Rust backtester on `prosperity_rust_backtester/datasets/round5/`.

## Strategy Results

| Strategy | Notes | D+2 | D+3 | D+4 | Total | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Baseline market making | Quote around current mid only | 4,025.0 | 10,423.5 | 6,801.5 | 21,250.0 | Feasible but weak |
| Single-product momentum | Current mid plus 50-tick own momentum | 881.0 | 1,117.5 | -5,334.0 | -3,335.5 | Reject |
| Static mean reversion | Static fair/z-take, no lead-lag | 66,896.0 | 98,026.5 | 71,741.5 | 236,664.0 | Strong baseline |
| Pair residual overlay | Slow pair residual quote test | 1,960.0 | 7,298.5 | 4,836.5 | 14,095.0 | Reject |
| Lead-lag hybrid | Final selected category strategy | 60,240.0 | 128,496.0 | 76,164.0 | 264,900.0 | Include |

## Final Product PnL

| Product | D+2 | D+3 | D+4 | Total |
| --- | ---: | ---: | ---: | ---: |
| SLEEP_POD_COTTON | 11,190.0 | 15,009.0 | 20,490.0 | 46,689.0 |
| SLEEP_POD_LAMB_WOOL | 18,390.0 | 31,387.0 | 21,109.0 | 70,886.0 |
| SLEEP_POD_NYLON | 2,095.0 | 14,242.0 | 6,591.0 | 22,928.0 |
| SLEEP_POD_POLYESTER | 17,615.0 | 30,609.0 | 9,113.0 | 57,337.0 |
| SLEEP_POD_SUEDE | 10,950.0 | 37,249.0 | 18,861.0 | 67,060.0 |
| Total | 60,240.0 | 128,496.0 | 76,164.0 | 264,900.0 |

Own trades in final category run: 383.

## Lead-Lag Validation Notes

Existing Round 5 search files provide useful cross-checks:

- First same-category lead-lag pass improved:
  - Lamb-Wool by +13,013 from `COTTON, lag 500, scale -1.0`.
  - Nylon by +4,577.5 from `COTTON, lag 100, scale +1.0`.
  - Suede by +900 from `LAMB_WOOL, lag 200, scale +0.1`.
  - Cotton by +719 from `LAMB_WOOL, lag 500, scale +0.25`.
  - Polyester by +632 from `SUEDE, lag 200, scale -0.05`.
- Second same-category pass improved:
  - Nylon by +4,255.5 from `SUEDE, lag 100, scale -0.5`.
  - Lamb-Wool by +3,135 from `POLYESTER, lag 50, scale +1.0`.
  - Suede by +787 from `COTTON, lag 200, scale -0.5`.
  - Polyester by +217 from `NYLON, lag 1, scale +1.0`.
- A tiny `COTTON <- SUEDE`, lag 20, scale -0.1 public-score bump was not included. It added only +241 and failed the broader validation filter.

## Overfitting Checks

- Final hybrid is positive on every public day.
- Static baseline is positive on every public day, so the strategy is not dependent on one lag edge.
- Lead-lag edge set comes from same-category relationships only.
- No exact timestamps or hard-coded event times are used.
- The weakest public-score-only edge was excluded despite a small positive backtest delta.
- Parameter perturbation from removing lead-lag shows the baseline still makes `236,664`, while the selected lead-lag overlay adds `28,236`.

## Final Verification Command

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/sleeping_pods/sleeping_pods_trader.py --dataset round5 --products full --artifact-mode none --run-id sleeping_pods_final
```

