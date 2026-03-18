# Run Backtest

From the repo root:

```bash
python3 run_backtest.py --data-dir imcdata
```

Write outputs to a custom folder:

```bash
python3 run_backtest.py --data-dir imcdata --output-dir outputs/imc_run
```

Run one replay file only:

```bash
python3 run_backtest.py --order-depth-csv imcdata/prices_round_0_day_-2.csv --trade-csv imcdata/trades_round_0_day_-2.csv
```

Artifacts written after each run:

```bash
ls outputs
cat outputs/aggregate_summary.json
```
