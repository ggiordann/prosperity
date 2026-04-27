# Round 3 Alpha Source Sweep

Signals are evaluated per product against next-tick mid-price return. Negative raw correlations are automatically marked as `inverted` so contrarian versions are not thrown away.

## Source Family Summary

| source_family | signals_tested | median_corr | max_corr | viable_rows | top_examples |
|---|---:|---:|---:|---:|---|
| microprice | 2 | 0.2897 | 0.5147 | 20 | VEV_4000:micro_edge_l3=0.515; VEV_4000:micro_edge_l1=0.480; VEV_4500:micro_edge_l3=0.439; VEV_4500:micro_edge_l1=0.397; VELVETFRUIT_EXTRACT:micro_edge_l3=0.370 |
| composite_book | 2 | 0.2386 | 0.5014 | 20 | VEV_4000:micro_l1_plus_inv_imb_l3=0.501; VEV_4000:micro_l3_plus_ofi_10=0.487; VEV_4500:micro_l1_plus_inv_imb_l3=0.428; VEV_4500:micro_l3_plus_ofi_10=0.403; VELVETFRUIT_EXTRACT:micro_l1_plus_inv_imb_l3=0.351 |
| book_shape | 1 | 0.3043 | 0.4942 | 10 | VEV_4000:book_slope_skew=0.494; VEV_4500:book_slope_skew=0.430; VEV_5300:book_slope_skew=0.355; VELVETFRUIT_EXTRACT:book_slope_skew=0.353; HYDROGEL_PACK:book_slope_skew=0.318 |
| book_imbalance | 4 | 0.2284 | 0.4828 | 35 | VEV_4000:imbalance_l1=0.483; VEV_4000:imbalance_l3=0.475; VEV_4000:book_pressure_3=0.474; VEV_4500:imbalance_l3=0.409; VEV_4500:book_pressure_3=0.406 |
| book_walls | 1 | 0.2862 | 0.4802 | 10 | VEV_4000:wall_skew_1=0.480; VEV_4500:wall_skew_1=0.406; VEV_5300:wall_skew_1=0.354; HYDROGEL_PACK:wall_skew_1=0.321; VEV_5500:wall_skew_1=0.288 |
| book_depth | 1 | 0.1802 | 0.4756 | 9 | VEV_4000:depth_ratio_l3=0.476; VEV_4500:depth_ratio_l3=0.409; HYDROGEL_PACK:depth_ratio_l3=0.327; VELVETFRUIT_EXTRACT:depth_ratio_l3=0.321; VEV_5000:depth_ratio_l3=0.199 |
| options_value | 3 | 0.0342 | 0.4470 | 12 | VEV_4000:option_time_value_pct_spot=0.447; VEV_4000:option_time_value=0.447; VEV_4500:option_time_value_pct_spot=0.376; VEV_4500:option_time_value=0.376; VEV_5500:option_time_value_pct_spot=0.052 |
| cross_product_book | 4 | 0.0029 | 0.3268 | 6 | HYDROGEL_PACK:xprod_HYDROGEL_PACK_imbalance_l3=0.327; VELVETFRUIT_EXTRACT:xprod_VELVETFRUIT_EXTRACT_imbalance_l3=0.321; HYDROGEL_PACK:xprod_HYDROGEL_PACK_micro_edge_l1=0.297; VELVETFRUIT_EXTRACT:xprod_VELVETFRUIT_EXTRACT_micro_edge_l1=0.227; VEV_4500:xprod_VELVETFRUIT_EXTRACT_micro_edge_l1=0.098 |
| cross_underlying | 2 | 0.0032 | 0.3209 | 4 | VELVETFRUIT_EXTRACT:underlying_imbalance_l3=0.321; VELVETFRUIT_EXTRACT:underlying_micro_edge_l1=0.227; VEV_4500:underlying_micro_edge_l1=0.098; VEV_4000:underlying_micro_edge_l1=0.095; VEV_5300:underlying_imbalance_l3=0.010 |
| price_reversion | 12 | 0.0899 | 0.3152 | 109 | VEV_5500:mid_zscore_5=0.315; VEV_5400:mid_zscore_5=0.286; VEV_4000:mid_reversion_1=0.284; VEV_5500:mid_zscore_10=0.263; VEV_5400:mid_reversion_1=0.254 |
| trade_flow | 22 | 0.0054 | 0.3104 | 13 | VEV_5300:trade_qty_imbalance=0.310; VELVETFRUIT_EXTRACT:trade_qty_imbalance=0.207; VELVETFRUIT_EXTRACT:signed_trade_notional=0.072; VELVETFRUIT_EXTRACT:signed_trade_qty=0.072; VELVETFRUIT_EXTRACT:trade_qty=0.055 |
| price_momentum | 7 | 0.0912 | 0.2841 | 62 | VEV_4000:mid_momentum_1=0.284; VEV_5400:mid_momentum_1=0.254; VEV_5500:mid_momentum_1=0.245; VEV_4000:mid_momentum_2=0.236; VEV_5500:mid_momentum_2=0.234 |
| cross_product_lead_lag | 33 | 0.0061 | 0.2841 | 33 | VEV_4000:xprod_VEV_4000_ret_lag_1=0.284; VEV_5400:xprod_VEV_5400_ret_lag_1=0.254; VEV_5500:xprod_VEV_5500_ret_lag_1=0.245; VEV_4500:xprod_VEV_4500_ret_lag_1=0.225; VEV_4000:xprod_VEV_4500_ret_lag_1=0.214 |
| composite_options | 1 | 0.0043 | 0.2270 | 3 | VELVETFRUIT_EXTRACT:under_micro_plus_option_price_resid=0.227; VEV_4500:under_micro_plus_option_price_resid=0.095; VEV_4000:under_micro_plus_option_price_resid=0.093; VEV_5400:under_micro_plus_option_price_resid=0.007; VEV_5500:under_micro_plus_option_price_resid=0.005 |
| book_order_flow | 5 | 0.0197 | 0.1654 | 18 | VEV_5400:ofi_l1=0.165; VEV_5500:ofi_l1=0.156; VEV_5500:ofi_l1_roll_3=0.146; VEV_5500:ofi_l1_roll_5=0.144; VEV_5400:ofi_l1_roll_3=0.131 |
| spread_regime | 3 | 0.0404 | 0.1072 | 19 | VELVETFRUIT_EXTRACT:spread=0.107; VELVETFRUIT_EXTRACT:rel_spread=0.107; VELVETFRUIT_EXTRACT:spread_change_1=0.072; VEV_4500:spread=0.065; VEV_4000:spread=0.059 |
| options_relative_value | 3 | 0.0295 | 0.0534 | 12 | VEV_5200:option_price_resid=0.053; VEV_5200:option_price_resid_pct=0.053; VEV_4500:option_price_resid_pct=0.049; VEV_4500:option_price_resid=0.046; VEV_4000:option_price_fit=0.042 |
| options_moneyness | 2 | 0.0205 | 0.0256 | 0 | VEV_5100:log_moneyness=0.026; VEV_5100:moneyness=0.026; VEV_5000:log_moneyness=0.025; VEV_5000:moneyness=0.025; VEV_5200:moneyness=0.024 |
| volatility_regime | 5 | 0.0056 | 0.0184 | 0 | VELVETFRUIT_EXTRACT:realized_abs_ret_5=0.018; VELVETFRUIT_EXTRACT:realized_abs_ret_10=0.015; HYDROGEL_PACK:realized_abs_ret_5=0.014; VEV_4000:realized_abs_ret_5=0.014; VEV_5200:realized_abs_ret_100=0.013 |
| liquidity_depth | 3 | 0.0061 | 0.0150 | 0 | VELVETFRUIT_EXTRACT:depth_change_l3=0.015; VEV_5100:total_depth_1=0.014; VEV_5400:depth_change_l3=0.014; VEV_4500:total_depth_1=0.013; VELVETFRUIT_EXTRACT:total_depth_3=0.013 |
| time_seasonality | 2 | 0.0028 | 0.0061 | 0 | HYDROGEL_PACK:tod_lodo_mean_ret_50=0.006; VEV_5000:tod_lodo_mean_ret_50=0.005; VEV_4500:tod_lodo_mean_ret_50=0.005; VEV_5100:tod_lodo_mean_ret_50=0.004; VELVETFRUIT_EXTRACT:tod_lodo_mean_ret_50=0.004 |

## Top Directional Signals

| product | signal | family | direction | corr_fwd1 | corr_fwd5 | hit_rate | day_frac |
|---|---|---|---|---:|---:|---:|---:|
| VEV_4000 | micro_edge_l3 | microprice | positive | 0.5147 | 0.3060 | 0.6626 | 1.00 |
| VEV_4000 | micro_l1_plus_inv_imb_l3 | composite_book | positive | 0.5014 | 0.2954 | 0.5088 | 1.00 |
| VEV_4000 | book_slope_skew | book_shape | inverted | 0.4942 | 0.2955 | 0.6626 | 1.00 |
| VEV_4000 | micro_l3_plus_ofi_10 | composite_book | positive | 0.4866 | 0.2892 | 0.5709 | 1.00 |
| VEV_4000 | imbalance_l1 | book_imbalance | positive | 0.4828 | 0.2838 | 0.9964 | 1.00 |
| VEV_4000 | micro_edge_l1 | microprice | positive | 0.4802 | 0.2827 | 0.9964 | 1.00 |
| VEV_4000 | wall_skew_1 | book_walls | positive | 0.4802 | 0.2825 | 0.9964 | 1.00 |
| VEV_4000 | depth_ratio_l3 | book_depth | inverted | 0.4756 | 0.2806 | 0.9964 | 1.00 |
| VEV_4000 | imbalance_l3 | book_imbalance | inverted | 0.4754 | 0.2805 | 0.9964 | 1.00 |
| VEV_4000 | book_pressure_3 | book_imbalance | inverted | 0.4737 | 0.2798 | 0.9964 | 1.00 |
| VEV_4000 | option_time_value_pct_spot | options_value | inverted | 0.4470 | 0.2647 | 0.6359 | 1.00 |
| VEV_4000 | option_time_value | options_value | inverted | 0.4469 | 0.2647 | 0.6359 | 1.00 |
| VEV_4500 | micro_edge_l3 | microprice | positive | 0.4392 | 0.2397 | 0.6793 | 1.00 |
| VEV_4500 | book_slope_skew | book_shape | inverted | 0.4297 | 0.2345 | 0.6793 | 1.00 |
| VEV_4500 | micro_l1_plus_inv_imb_l3 | composite_book | positive | 0.4282 | 0.2337 | 0.5101 | 1.00 |
| VEV_4500 | depth_ratio_l3 | book_depth | inverted | 0.4091 | 0.2231 | 0.9964 | 1.00 |
| VEV_4500 | imbalance_l3 | book_imbalance | inverted | 0.4089 | 0.2230 | 0.9964 | 1.00 |
| VEV_4500 | wall_skew_1 | book_walls | positive | 0.4059 | 0.2202 | 0.9964 | 1.00 |
| VEV_4500 | book_pressure_3 | book_imbalance | inverted | 0.4056 | 0.2217 | 0.9964 | 1.00 |
| VEV_4500 | micro_l3_plus_ofi_10 | composite_book | positive | 0.4034 | 0.2188 | 0.5372 | 1.00 |
| VEV_4500 | imbalance_l1 | book_imbalance | positive | 0.4012 | 0.2185 | 0.9964 | 1.00 |
| VEV_4500 | micro_edge_l1 | microprice | positive | 0.3974 | 0.2171 | 0.9964 | 1.00 |
| VEV_4500 | option_time_value_pct_spot | options_value | inverted | 0.3762 | 0.2056 | 0.6290 | 1.00 |
| VEV_4500 | option_time_value | options_value | inverted | 0.3762 | 0.2056 | 0.6290 | 1.00 |
| VELVETFRUIT_EXTRACT | micro_edge_l3 | microprice | positive | 0.3700 | 0.1892 | 0.6829 | 1.00 |
| VEV_5300 | book_slope_skew | book_shape | inverted | 0.3552 | 0.2060 | 0.9069 | 1.00 |
| VEV_5300 | micro_edge_l3 | microprice | positive | 0.3551 | 0.2068 | 0.8974 | 1.00 |
| VEV_5300 | wall_skew_1 | book_walls | positive | 0.3545 | 0.2063 | 0.9055 | 1.00 |
| VEV_5300 | imbalance_l1 | book_imbalance | positive | 0.3533 | 0.2061 | 0.8994 | 1.00 |
| VELVETFRUIT_EXTRACT | book_slope_skew | book_shape | inverted | 0.3526 | 0.1820 | 0.6827 | 1.00 |

## Top Volatility/Regime Signals

| product | signal | family | direction | corr_abs_fwd5 |
|---|---|---|---|---:|
| VEV_5500 | spread | spread_regime | positive | 0.3192 |
| VEV_4000 | rel_spread | spread_regime | inverted | 0.3011 |
| VEV_5500 | realized_abs_ret_5 | volatility_regime | positive | 0.2952 |
| VEV_4000 | spread | spread_regime | inverted | 0.2923 |
| VEV_5500 | realized_abs_ret_10 | volatility_regime | positive | 0.2744 |
| VEV_5500 | realized_abs_ret_20 | volatility_regime | positive | 0.2199 |
| VEV_4000 | spread_change_1 | spread_regime | inverted | 0.2139 |
| VEV_4500 | rel_spread | spread_regime | inverted | 0.2032 |
| VEV_4500 | spread | spread_regime | inverted | 0.1897 |
| VEV_5500 | realized_abs_ret_50 | volatility_regime | positive | 0.1594 |
| VEV_5500 | rel_spread | spread_regime | positive | 0.1548 |
| VEV_4500 | spread_change_1 | spread_regime | inverted | 0.1480 |
