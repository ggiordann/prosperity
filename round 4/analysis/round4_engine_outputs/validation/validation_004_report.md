# Round 4 Multi-Strategy Trading Report

## Metrics

- Total PnL: 16880.50
- Sharpe ratio: 0.4395
- Max drawdown: 20203.50
- Trade win rate: 0.4983
- Trade count: 187
- Turnover: 2094001.00
- Mean gross exposure: 1325419.89
- Max gross exposure: 1687650.50

## Strategies

- Mean reversion: rolling-20 fair value with volatility-scaled thresholds.
- Order-book imbalance: top-three-level depth imbalance with momentum confirmation.
- Market making: dynamic fair-value quoting widened by volatility and inventory.
- Voucher arbitrage: intrinsic-value, monotonicity, and call-spread-bound checks.
- Trader behavior: walk-forward trader alpha scores from post-trade price movement.

## Product PnL

| product | realized_cash_flow | final_position | final_mid_price | mark_to_market | total_pnl | turnover | trade_count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VEV_4500 | -225633.0000 | 299 | 795.5000 | 237854.5000 | 12221.5000 | 225633.0000 | 83 |
| VEV_4000 | -375133.0000 | 299 | 1295.0000 | 387205.0000 | 12072.0000 | 375133.0000 | 83 |
| HYDROGEL_PACK | 0.0000 | 0 | 10010.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5000 | 0.0000 | 0 | 296.5000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5100 | 0.0000 | 0 | 201.5000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5200 | 0.0000 | 0 | 119.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5300 | 0.0000 | 0 | 58.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5400 | 0.0000 | 0 | 20.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_5500 | 0.0000 | 0 | 7.0000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_6000 | 0.0000 | 0 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VEV_6500 | 0.0000 | 0 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0 |
| VELVETFRUIT_EXTRACT | 1051687.0000 | -200 | 5295.5000 | -1059100.0000 | -7413.0000 | 1493235.0000 | 21 |

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
