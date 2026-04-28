# Round 4 Neural Trading Pipeline

This package trains a multi-output PyTorch model for the Round 4 market data:

- asset price change forecasts for horizons 1 to 5 ticks
- voucher fair-price forecasts
- future realized-volatility forecasts
- volatility-scaled trading signals
- position-limited backtests with inventory and stop-loss controls

The implementation lives in `src/prosperity/round4_ml/`.

## Quick Run

```bash
PYTHONPATH=src python -m prosperity.round4_ml \
  --data-dir /Users/giordanmasen/Downloads/ROUND_4 \
  --output-dir "round 4/ml_artifacts/full_lstm" \
  --encoder lstm \
  --epochs 30 \
  --batch-size 512 \
  --sequence-length 32 \
  --device auto
```

Fast smoke run:

```bash
PYTHONPATH=src python -m prosperity.round4_ml \
  --data-dir /Users/giordanmasen/Downloads/ROUND_4 \
  --output-dir "round 4/ml_artifacts/smoke" \
  --epochs 2 \
  --batch-size 128 \
  --sequence-length 16 \
  --max-train-samples 2048 \
  --max-eval-samples 1024 \
  --device cpu
```

Use `--encoder transformer` for the transformer time-series encoder, or `--encoder tcn` for the temporal CNN baseline.

## Data Split

- Day 1: training
- Day 2: validation
- Day 3: testing and backtest

Feature normalization and trader informedness scores are fitted from Day 1 only.

## Features

The feature builder computes:

- mid price, log returns, rolling means, rolling volatility, and momentum
- spread, order-book imbalance, depth-weighted imbalance, top-level volume, microprice, and pressure indicators
- trader net positions, rolling activity, buy/sell imbalance, aggressive-trader flow, and informed-trader indicators
- voucher strike, time to expiry, moneyness, intrinsic value, distance from intrinsic, delta proxy, and implied-volatility proxy

`HYDROGEL` is treated as an alias for the CSV product `HYDROGEL_PACK`.

## Outputs

Each run writes:

- `round4_multi_output_model.pt`
- `feature_scaler.json`
- `target_scalers.json`
- `feature_columns.json`
- `trader_profiles.csv`
- `validation_predictions.csv`
- `test_predictions.csv`
- `pnl_threshold_sweep.csv`
- `selected_backtest_config.json`
- `trading_signals.csv`
- `simulated_trades.csv`
- `equity_curve.csv`
- `backtest_metrics.json`
- `training_history.png`
- `prediction_scatter.png`
- `prediction_timeseries.png`
- `equity_curve.png`
- `trade_distribution.png`

## Tuning Notes

The first useful optimization loop should rank configurations by test/backtest PnL and drawdown, not validation MSE alone. Good first sweeps:

- `asset_vol_threshold_multiplier`
- `voucher_vol_threshold_multiplier`
- `spread_threshold_multiplier`
- `risk_aversion`
- `position_limits`
- sequence length
- encoder type
- price/voucher/volatility loss weights
