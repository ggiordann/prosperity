# Round 4 Multi-Strategy Trading Report

## Metrics

- Total PnL: 3812.00
- Sharpe ratio: 0.0754
- Max drawdown: 22350.00
- Trade win rate: 0.5001
- Trade count: 201
- Turnover: 1966290.00
- Mean gross exposure: 1368569.66
- Max gross exposure: 1674400.00

## Strategies

- Mean reversion: rolling-20 fair value with volatility-scaled thresholds.
- Order-book imbalance: top-three-level depth imbalance with momentum confirmation.
- Market making: dynamic fair-value quoting widened by volatility and inventory.
- Voucher arbitrage: intrinsic-value, monotonicity, and call-spread-bound checks.
- Trader behavior: walk-forward trader alpha scores from post-trade price movement.

## Product PnL

| product | realized_cash_flow | final_position | final_mid_price | mark_to_market | total_pnl | turnover | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VELVETFRUIT_EXTRACT | 1051412.0000 | -200 | 5232.0000 | -1046400.0000 | 5012.0000 | 1375890.0000 | 19 |
| HYDROGEL_PACK | 0.0000 | 0 | 10001.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5000 | 0.0000 | 0 | 234.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5100 | 0.0000 | 0 | 141.5000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5200 | 0.0000 | 0 | 70.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5300 | 0.0000 | 0 | 26.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5400 | 0.0000 | 0 | 5.5000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5500 | 0.0000 | 0 | 1.5000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_6000 | 0.0000 | 0 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_6500 | 0.0000 | 0 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_4000 | -370200.0000 | 300 | 1232.0000 | 369600.0000 | -600.0000 | 370200.0000 | 91 |
| VEV_4500 | -220200.0000 | 300 | 732.0000 | 219600.0000 | -600.0000 | 220200.0000 | 91 |

## Validation Sweep Top 10

| run | score | total_pnl | sharpe_ratio | max_drawdown | trade_count | mean_reversion_weight | imbalance_weight | trader_weight | mean_reversion_vol_multiplier | imbalance_threshold | combined_signal_threshold | voucher_cross_edge | execution_cost_multiplier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4.0000 | 15870.3250 | 16880.5000 | 0.4395 | 20203.5000 | 187.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.7000 | 0.2500 | 5.0000 |
| 8.0000 | 15870.3250 | 16880.5000 | 0.4395 | 20203.5000 | 187.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.7000 | 0.4500 | 5.0000 |
| 16.0000 | 15870.3250 | 16880.5000 | 0.4395 | 20203.5000 | 187.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.9000 | 0.4500 | 5.0000 |
| 12.0000 | 15870.3250 | 16880.5000 | 0.4395 | 20203.5000 | 187.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.9000 | 0.2500 | 5.0000 |
| 15.0000 | 15782.8250 | 16818.5000 | 0.4375 | 20713.5000 | 218.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.9000 | 0.4500 | 3.0000 |
| 3.0000 | 15782.8250 | 16818.5000 | 0.4375 | 20713.5000 | 218.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.7000 | 0.2500 | 3.0000 |
| 7.0000 | 15782.8250 | 16818.5000 | 0.4375 | 20713.5000 | 218.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.7000 | 0.4500 | 3.0000 |
| 11.0000 | 15782.8250 | 16818.5000 | 0.4375 | 20713.5000 | 218.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.9000 | 0.2500 | 3.0000 |
| 9.0000 | 14877.6750 | 15939.0000 | 0.4138 | 21226.5000 | 352.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.9000 | 0.2500 | 1.5000 |
| 13.0000 | 14877.6750 | 15939.0000 | 0.4138 | 21226.5000 | 352.0000 | 0.8500 | 0.9500 | 0.5500 | 0.8500 | 0.1200 | 0.9000 | 0.4500 | 1.5000 |

## Risk Settings

- Max gross exposure: 2200000.00
- Stop loss: 45000.00
- Max daily loss: 30000.00
- Position limits: {'HYDROGEL_PACK': 200, 'VELVETFRUIT_EXTRACT': 200, 'VEV_4000': 300, 'VEV_4500': 300, 'VEV_5000': 300, 'VEV_5100': 300, 'VEV_5200': 300, 'VEV_5300': 300, 'VEV_5400': 300, 'VEV_5500': 300, 'VEV_6000': 300, 'VEV_6500': 300}
