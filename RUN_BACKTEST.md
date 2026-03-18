# Run Everything

Run from the repo root:

```bash
cd /Users/giordanmasen/Desktop/prosperity
```

Run all IMC replay files in `imcdata`:

```bash
python3 run_backtest.py --data-dir imcdata
```

Run all IMC replay files to a custom output folder:

```bash
python3 run_backtest.py --data-dir imcdata --output-dir outputs/imc_run
```

Run one replay day only:

```bash
python3 run_backtest.py --order-depth-csv imcdata/prices_round_0_day_-2.csv --trade-csv imcdata/trades_round_0_day_-2.csv
```

Run the synthetic tutorial scenario:

```bash
python3 run_backtest.py --steps 1000 --seed 7
```

Start the frontend dashboard:

```bash
python3 dashboard_server.py
open http://127.0.0.1:8765
```

In the dashboard:

```text
1. Keep Data Dir as imcdata
2. Keep Output Dir as outputs/imcdata
3. Click Run Backtest
4. Click a replay day to view equity and fills
```

Inspect generated files:

```bash
ls outputs/imcdata
cat outputs/imcdata/aggregate_summary.json
```

Stop the dashboard:

```bash
Ctrl+C
```
