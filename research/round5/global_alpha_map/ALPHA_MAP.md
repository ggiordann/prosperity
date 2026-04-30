# Round 5 Global Alpha Map

Generated from the bundled Round 5 public files. In this report, validation day 1/2/3 means public data day 2/3/4 respectively.

## Repository Map

- Rust backtester: `prosperity_rust_backtester/`.
- Backtest command: `cd prosperity_rust_backtester && ./scripts/cargo_local.sh run --release -- --trader traders/latest_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id <run_id>`.
- Round 5 data: `prosperity_rust_backtester/datasets/round5/prices_round_5_day_{2,3,4}.csv` and `trades_round_5_day_{2,3,4}.csv`.
- Current trader files: `prosperity_rust_backtester/traders/latest_trader.py`, `all_products_trader.py`, `limit_breach_trader.py`, plus untracked `final_round5_trader.py` and `final_round5_trader_expanded.py` in this workspace.
- `datamodel.py`: the Rust backtester embeds it in `prosperity_rust_backtester/src/pytrader.rs`; the official reference copy is in `wiki/writing-an-algorithm-in-python.md` Appendix B. There is no standalone checked-in backtester `datamodel.py` file.
- Supported final imports from the official wiki: standard Python 3.12 libraries plus `pandas`; current local traders use `from datamodel import Order, OrderDepth, TradingState`, `typing`, and `json`.
- Final submission constraints to preserve: single Python file, under 100KB, correct Prosperity `datamodel` imports, 900ms `run` budget, `traderData` practical cap around 50,000 chars, and Round 5 position limit 10 for every product.

## Scope Checks

- Products analyzed: `50` across `10` categories.
- Cross-category share among top pairs: `70%`.
- Cross-category share among top lead-lag edges: `87%`.
- Global/cross-category share among top basket models: `65%`.
- Trade CSV buyer/seller fields are blank, so counterparty-ID flow alpha is unavailable from public Round 5 files.

## Top 30 Pair Relationships

| pair | cats | target | hedge | return_corr_mean | rolling_return_corr_mean | price_level_corr_mean | spread_corr_mean | loo_edge_mean | loo_positive_days | relationship_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SNACKPACK_CHOCOLATE / SNACKPACK_VANILLA | snackpacks / snackpacks | SNACKPACK_CHOCOLATE | SNACKPACK_VANILLA | -0.9159 | -0.9149 | -0.9718 | 0.8915 | 1.1674 | 3 | 2.0884 |
| SNACKPACK_STRAWBERRY / SNACKPACK_RASPBERRY | snackpacks / snackpacks | SNACKPACK_RASPBERRY | SNACKPACK_STRAWBERRY | -0.9238 | -0.9233 | -0.8101 | 0.8872 | 3.0590 | 3 | 2.0200 |
| SNACKPACK_PISTACHIO / SNACKPACK_RASPBERRY | snackpacks / snackpacks | SNACKPACK_RASPBERRY | SNACKPACK_PISTACHIO | -0.8309 | -0.8303 | -0.7164 | 0.8957 | 3.8653 | 3 | 1.9544 |
| SNACKPACK_PISTACHIO / SNACKPACK_STRAWBERRY | snackpacks / snackpacks | SNACKPACK_PISTACHIO | SNACKPACK_STRAWBERRY | 0.9133 | 0.9131 | 0.3903 | 0.9185 | 1.9825 | 3 | 1.8828 |
| PEBBLES_S / PEBBLES_XL | pebbles / pebbles | PEBBLES_XL | PEBBLES_S | -0.4957 | -0.4942 | -0.6016 | 0.3851 | 7.6359 | 3 | 1.0997 |
| PEBBLES_L / PEBBLES_XL | pebbles / pebbles | PEBBLES_L | PEBBLES_XL | -0.5000 | -0.4991 | -0.7388 | 0.3297 | 3.1772 | 3 | 1.0885 |
| PEBBLES_XS / PEBBLES_XL | pebbles / pebbles | PEBBLES_XL | PEBBLES_XS | -0.4973 | -0.4964 | -0.5632 | 0.2440 | 8.7129 | 2 | 1.0456 |
| PEBBLES_M / PEBBLES_XL | pebbles / pebbles | PEBBLES_XL | PEBBLES_M | -0.5115 | -0.5111 | -0.3046 | 0.5009 | 12.9072 | 2 | 1.0257 |
| TRANSLATOR_ECLIPSE_CHARCOAL / OXYGEN_SHAKE_MINT | translators / oxygen_shakes | OXYGEN_SHAKE_MINT | TRANSLATOR_ECLIPSE_CHARCOAL | 0.0075 | 0.0071 | 0.0724 | 0.7712 | 30.1940 | 3 | 0.9937 |
| MICROCHIP_SQUARE / ROBOT_LAUNDRY | microchips / robotics | MICROCHIP_SQUARE | ROBOT_LAUNDRY | -0.0004 | -0.0009 | -0.1773 | -0.0125 | 75.4765 | 2 | 0.7976 |
| PEBBLES_XL / OXYGEN_SHAKE_MINT | pebbles / oxygen_shakes | OXYGEN_SHAKE_MINT | PEBBLES_XL | -0.0025 | -0.0023 | 0.3199 | 0.0768 | 20.4673 | 3 | 0.7847 |
| GALAXY_SOUNDS_SOLAR_FLAMES / ROBOT_DISHES | galaxy_sounds / robotics | ROBOT_DISHES | GALAXY_SOUNDS_SOLAR_FLAMES | 0.0005 | 0.0005 | 0.1051 | 0.7769 | 31.8046 | 2 | 0.7772 |
| OXYGEN_SHAKE_MORNING_BREATH / OXYGEN_SHAKE_MINT | oxygen_shakes / oxygen_shakes | OXYGEN_SHAKE_MINT | OXYGEN_SHAKE_MORNING_BREATH | 0.0070 | 0.0064 | 0.0147 | 0.7717 | 19.8138 | 3 | 0.6272 |
| GALAXY_SOUNDS_DARK_MATTER / UV_VISOR_YELLOW | galaxy_sounds / uv_visors | GALAXY_SOUNDS_DARK_MATTER | UV_VISOR_YELLOW | 0.0174 | 0.0170 | 0.7220 | 0.8623 | 8.5518 | 3 | 0.6204 |
| TRANSLATOR_VOID_BLUE / SNACKPACK_CHOCOLATE | translators / snackpacks | TRANSLATOR_VOID_BLUE | SNACKPACK_CHOCOLATE | 0.0046 | 0.0044 | -0.4582 | 0.8253 | 16.3791 | 3 | 0.6177 |
| MICROCHIP_SQUARE / PANEL_1X4 | microchips / panels | MICROCHIP_SQUARE | PANEL_1X4 | -0.0033 | -0.0029 | -0.3473 | -0.0884 | 39.0604 | 3 | 0.6171 |
| SLEEP_POD_SUEDE / ROBOT_IRONING | sleep_pods / robotics | SLEEP_POD_SUEDE | ROBOT_IRONING | 0.0098 | 0.0089 | -0.0623 | 0.6242 | 23.8244 | 3 | 0.5941 |
| PANEL_1X2 / SNACKPACK_STRAWBERRY | panels / snackpacks | SNACKPACK_STRAWBERRY | PANEL_1X2 | 0.0138 | 0.0140 | -0.1949 | 0.8028 | 17.6300 | 2 | 0.5933 |
| MICROCHIP_OVAL / PEBBLES_L | microchips / pebbles | MICROCHIP_OVAL | PEBBLES_L | -0.0009 | 0.0005 | -0.0674 | 0.0225 | 51.0447 | 2 | 0.5843 |
| SLEEP_POD_LAMB_WOOL / SNACKPACK_RASPBERRY | sleep_pods / snackpacks | SNACKPACK_RASPBERRY | SLEEP_POD_LAMB_WOOL | 0.0082 | 0.0084 | 0.4063 | 0.8406 | 6.9693 | 3 | 0.5778 |
| MICROCHIP_CIRCLE / PANEL_2X2 | microchips / panels | PANEL_2X2 | MICROCHIP_CIRCLE | 0.0056 | 0.0054 | 0.1070 | 0.0264 | 15.9304 | 3 | 0.5705 |
| PEBBLES_XL / PANEL_2X4 | pebbles / panels | PANEL_2X4 | PEBBLES_XL | -0.0061 | -0.0077 | 0.6530 | 0.1483 | 10.4102 | 3 | 0.5419 |
| PEBBLES_S / TRANSLATOR_GRAPHITE_MIST | pebbles / translators | PEBBLES_S | TRANSLATOR_GRAPHITE_MIST | 0.0070 | 0.0069 | 0.2636 | 0.0570 | 29.0033 | 2 | 0.5364 |
| TRANSLATOR_SPACE_GRAY / OXYGEN_SHAKE_MINT | translators / oxygen_shakes | OXYGEN_SHAKE_MINT | TRANSLATOR_SPACE_GRAY | 0.0094 | 0.0103 | -0.0973 | 0.7270 | 15.1967 | 3 | 0.5349 |
| SLEEP_POD_SUEDE / MICROCHIP_SQUARE | sleep_pods / microchips | MICROCHIP_SQUARE | SLEEP_POD_SUEDE | -0.0017 | -0.0022 | 0.5642 | 0.0837 | 27.8078 | 3 | 0.5314 |
| MICROCHIP_CIRCLE / OXYGEN_SHAKE_MINT | microchips / oxygen_shakes | OXYGEN_SHAKE_MINT | MICROCHIP_CIRCLE | 0.0030 | 0.0047 | 0.3049 | 0.0648 | 15.4182 | 3 | 0.5217 |
| UV_VISOR_AMBER / SNACKPACK_STRAWBERRY | uv_visors / snackpacks | SNACKPACK_STRAWBERRY | UV_VISOR_AMBER | 0.0134 | 0.0154 | -0.4616 | 0.7949 | 6.3398 | 3 | 0.5180 |
| TRANSLATOR_ECLIPSE_CHARCOAL / SNACKPACK_STRAWBERRY | translators / snackpacks | SNACKPACK_STRAWBERRY | TRANSLATOR_ECLIPSE_CHARCOAL | 0.0171 | 0.0185 | 0.2556 | 0.8348 | 8.2752 | 3 | 0.5146 |
| SLEEP_POD_NYLON / SNACKPACK_RASPBERRY | sleep_pods / snackpacks | SNACKPACK_RASPBERRY | SLEEP_POD_NYLON | 0.0203 | 0.0201 | 0.2846 | 0.8229 | 6.3749 | 3 | 0.5127 |
| SLEEP_POD_SUEDE / PANEL_1X4 | sleep_pods / panels | SLEEP_POD_SUEDE | PANEL_1X4 | -0.0028 | -0.0032 | -0.1105 | 0.6938 | 20.5747 | 3 | 0.5084 |

## Top 30 Lead-Lag Relationships

| edge | cats | lag | day1_corr | day2_corr | day3_corr | loo_edge_mean | loo_positive_days | train_day1_test_day2_3_edge | train_day1_2_test_day3_edge | beta_all_days |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MICROCHIP_CIRCLE -> MICROCHIP_SQUARE | microchips -> microchips | 100 | 0.04495 | 0.07226 | 0.06517 | 1.02510 | 3 | 1.35001 | 1.36549 | 0.13785 |
| MICROCHIP_CIRCLE -> MICROCHIP_OVAL | microchips -> microchips | 50 | 0.04944 | 0.05326 | 0.04961 | 0.48409 | 3 | 0.50317 | 0.38532 | 0.06725 |
| OXYGEN_SHAKE_EVENING_BREATH -> PEBBLES_XL | oxygen_shakes -> pebbles | 1 | -0.02001 | -0.02815 | -0.00452 | 0.56945 | 3 | 0.50020 | 0.13783 | -0.04858 |
| GALAXY_SOUNDS_PLANETARY_RINGS -> PEBBLES_XL | galaxy_sounds -> pebbles | 3 | 0.00941 | 0.02435 | 0.00727 | 0.45913 | 3 | 0.48144 | 0.27691 | 0.03900 |
| ROBOT_LAUNDRY -> PEBBLES_XL | robotics -> pebbles | 100 | -0.01896 | -0.01788 | -0.00140 | 0.45926 | 3 | 0.41865 | 0.08976 | -0.04059 |
| PEBBLES_M -> PEBBLES_XL | pebbles -> pebbles | 5 | -0.00997 | -0.02763 | -0.01521 | 0.42651 | 3 | 0.56862 | 0.35531 | -0.03538 |
| PANEL_1X2 -> PEBBLES_XL | panels -> pebbles | 2 | 0.01678 | 0.01067 | 0.01835 | 0.42976 | 3 | 0.39437 | 0.52966 | 0.05150 |
| PEBBLES_XS -> PEBBLES_XL | pebbles -> pebbles | 2 | -0.00848 | -0.01560 | -0.00264 | 0.41956 | 3 | 0.42798 | 0.34200 | -0.01796 |
| MICROCHIP_OVAL -> PEBBLES_XL | microchips -> pebbles | 5 | -0.00539 | -0.01142 | -0.01556 | 0.40262 | 3 | 0.49627 | 0.68411 | -0.02409 |
| SNACKPACK_STRAWBERRY -> PEBBLES_XL | snackpacks -> pebbles | 5 | -0.01387 | -0.01902 | -0.00419 | 0.36951 | 3 | 0.38476 | 0.26246 | -0.04616 |
| TRANSLATOR_ASTRO_BLACK -> PEBBLES_XL | translators -> pebbles | 2 | 0.01220 | -0.00212 | 0.01080 | 0.38668 | 3 | 0.29269 | 0.38311 | 0.02310 |
| SNACKPACK_CHOCOLATE -> PEBBLES_XL | snackpacks -> pebbles | 10 | -0.00369 | -0.00485 | -0.01971 | 0.37505 | 3 | 0.40560 | 0.53058 | -0.04332 |
| SNACKPACK_VANILLA -> MICROCHIP_SQUARE | snackpacks -> microchips | 100 | -0.01220 | 0.00114 | -0.01812 | 0.36918 | 3 | 0.35031 | 0.50349 | -0.03039 |
| GALAXY_SOUNDS_SOLAR_WINDS -> MICROCHIP_SQUARE | galaxy_sounds -> microchips | 20 | -0.02044 | -0.01191 | -0.01473 | 0.34902 | 3 | 0.29925 | 0.27959 | -0.02968 |
| GALAXY_SOUNDS_SOLAR_FLAMES -> PEBBLES_XL | galaxy_sounds -> pebbles | 2 | 0.00071 | 0.00293 | 0.02464 | 0.36794 | 3 | 0.54341 | 1.08673 | 0.02562 |
| SLEEP_POD_SUEDE -> PEBBLES_XL | sleep_pods -> pebbles | 20 | -0.00424 | -0.01647 | -0.01499 | 0.35834 | 3 | 0.50944 | 0.56749 | -0.03253 |
| MICROCHIP_CIRCLE -> PEBBLES_XL | microchips -> pebbles | 1 | 0.02000 | 0.01760 | -0.00055 | 0.35594 | 3 | 0.29206 | 0.01570 | 0.03976 |
| GALAXY_SOUNDS_DARK_MATTER -> PEBBLES_XL | galaxy_sounds -> pebbles | 50 | -0.00980 | -0.01608 | -0.00904 | 0.35318 | 3 | 0.32423 | 0.16228 | -0.03465 |
| TRANSLATOR_VOID_BLUE -> MICROCHIP_SQUARE | translators -> microchips | 10 | 0.01478 | 0.00304 | 0.02744 | 0.34218 | 3 | 0.50586 | 0.77480 | 0.02906 |
| PANEL_1X4 -> PEBBLES_S | panels -> pebbles | 1 | -0.01089 | -0.02428 | -0.02003 | 0.32070 | 3 | 0.34134 | 0.32922 | -0.02887 |
| PEBBLES_S -> ROBOT_DISHES | pebbles -> robotics | 3 | 0.01869 | 0.00446 | 0.01635 | 0.32848 | 3 | 0.39388 | 0.73679 | 0.01489 |
| SLEEP_POD_POLYESTER -> MICROCHIP_SQUARE | sleep_pods -> microchips | 100 | -0.00326 | 0.00089 | -0.03494 | 0.32769 | 3 | 0.42966 | 0.75402 | -0.02453 |
| TRANSLATOR_SPACE_GRAY -> PEBBLES_XL | translators -> pebbles | 2 | 0.00944 | 0.01203 | 0.02178 | 0.32010 | 3 | 0.28919 | 0.02041 | 0.04560 |
| PEBBLES_M -> MICROCHIP_SQUARE | pebbles -> microchips | 20 | 0.00912 | 0.03161 | 0.00692 | 0.31571 | 3 | 0.37196 | 0.14651 | 0.02228 |
| SNACKPACK_STRAWBERRY -> PEBBLES_S | snackpacks -> pebbles | 5 | 0.01806 | 0.02960 | 0.01567 | 0.30115 | 3 | 0.35324 | 0.23549 | 0.03911 |
| UV_VISOR_YELLOW -> MICROCHIP_SQUARE | uv_visors -> microchips | 5 | 0.01485 | 0.00806 | 0.02210 | 0.31697 | 3 | 0.21996 | 0.47819 | 0.02808 |
| ROBOT_VACUUMING -> MICROCHIP_SQUARE | robotics -> microchips | 100 | -0.01522 | -0.00778 | -0.00866 | 0.32699 | 3 | 0.34380 | 0.56551 | -0.02276 |
| PANEL_2X4 -> MICROCHIP_SQUARE | panels -> microchips | 100 | -0.00606 | -0.01874 | -0.01349 | 0.31961 | 3 | 0.39693 | 0.40307 | -0.02457 |
| GALAXY_SOUNDS_SOLAR_WINDS -> PEBBLES_XL | galaxy_sounds -> pebbles | 2 | 0.00773 | 0.00772 | 0.00652 | 0.33240 | 3 | 0.29239 | 0.23557 | 0.02083 |
| PANEL_4X4 -> PEBBLES_XL | panels -> pebbles | 2 | 0.00645 | 0.01696 | 0.00182 | 0.32353 | 3 | 0.15390 | 0.06872 | 0.02506 |

## Top 20 Basket Residual Opportunities

| target | category | model_type | feature_preview | loo_edge_mean | loo_positive_days | loo_mr_ic_mean | train_day1_2_test_day3_edge | residual_std | basket_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PEBBLES_XL | pebbles | same_category | PEBBLES_XS, PEBBLES_S, PEBBLES_M, PEBBLES_L | 16.5775 | 3 | 0.7081 | 16.5079 | 2.8048 | 2.1282 |
| PEBBLES_XS | pebbles | same_category | PEBBLES_S, PEBBLES_M, PEBBLES_L, PEBBLES_XL | 6.1043 | 3 | 0.6485 | 16.2429 | 2.8342 | 1.2908 |
| PEBBLES_L | pebbles | same_category | PEBBLES_XS, PEBBLES_S, PEBBLES_M, PEBBLES_XL | 7.6673 | 3 | 0.6318 | 4.6982 | 2.9020 | 1.2011 |
| PEBBLES_M | pebbles | same_category | PEBBLES_XS, PEBBLES_S, PEBBLES_L, PEBBLES_XL | 6.9615 | 3 | 0.5775 | 5.1272 | 2.9170 | 1.0462 |
| PEBBLES_S | pebbles | same_category | PEBBLES_XS, PEBBLES_M, PEBBLES_L, PEBBLES_XL | 3.9893 | 3 | 0.5337 | 0.5573 | 2.9598 | 0.6621 |
| PEBBLES_S | pebbles | cross_category_top8 | MICROCHIP_OVAL, GALAXY_SOUNDS_BLACK_HOLES, OXYGEN_SHAKE_GARLIC, ROBOT_DISHES, PANEL_2X4, +3 | 8.7454 | 3 | 0.0992 | 9.2665 | 274.9546 | 0.1591 |
| SNACKPACK_RASPBERRY | snackpacks | cross_category_top8 | OXYGEN_SHAKE_MINT, SLEEP_POD_LAMB_WOOL, PEBBLES_L, UV_VISOR_YELLOW, SLEEP_POD_COTTON, +3 | 3.3354 | 3 | 0.0995 | 1.7561 | 138.5117 | 0.1169 |
| PEBBLES_S | pebbles | global_top8 | PEBBLES_XL, MICROCHIP_OVAL, GALAXY_SOUNDS_BLACK_HOLES, OXYGEN_SHAKE_GARLIC, ROBOT_DISHES, +3 | 5.2902 | 3 | 0.0965 | 4.9414 | 243.7492 | 0.1148 |
| MICROCHIP_RECTANGLE | microchips | same_category | MICROCHIP_CIRCLE, MICROCHIP_OVAL, MICROCHIP_SQUARE, MICROCHIP_TRIANGLE | 5.3089 | 3 | 0.1038 | 3.2962 | 329.6257 | 0.1077 |
| PANEL_2X2 | panels | global_all_ridge | GALAXY_SOUNDS_DARK_MATTER, GALAXY_SOUNDS_BLACK_HOLES, GALAXY_SOUNDS_PLANETARY_RINGS, GALAXY_SOUNDS_SOLAR_WINDS, GALAXY_SOUNDS_SOLAR_FLAMES, +44 | 4.4248 | 3 | 0.1056 | 4.2975 | 108.4158 | 0.1023 |
| GALAXY_SOUNDS_DARK_MATTER | galaxy_sounds | cross_category_top8 | UV_VISOR_YELLOW, MICROCHIP_CIRCLE, PANEL_1X2, MICROCHIP_RECTANGLE, OXYGEN_SHAKE_CHOCOLATE, +3 | 3.5406 | 3 | 0.1276 | 0.4502 | 180.9297 | 0.0998 |
| GALAXY_SOUNDS_DARK_MATTER | galaxy_sounds | global_top8 | UV_VISOR_YELLOW, MICROCHIP_CIRCLE, PANEL_1X2, GALAXY_SOUNDS_PLANETARY_RINGS, MICROCHIP_RECTANGLE, +3 | 3.5406 | 3 | 0.1276 | 0.4502 | 182.9248 | 0.0998 |
| SLEEP_POD_POLYESTER | sleep_pods | global_top8 | UV_VISOR_AMBER, UV_VISOR_MAGENTA, MICROCHIP_SQUARE, PEBBLES_XS, SLEEP_POD_COTTON, +3 | 5.9721 | 3 | 0.0736 | 11.1440 | 259.5782 | 0.0928 |
| PEBBLES_XL | pebbles | global_all_ridge | GALAXY_SOUNDS_DARK_MATTER, GALAXY_SOUNDS_BLACK_HOLES, GALAXY_SOUNDS_PLANETARY_RINGS, GALAXY_SOUNDS_SOLAR_WINDS, GALAXY_SOUNDS_SOLAR_FLAMES, +44 | 1.9312 | 3 | 0.0846 | 1.6222 | 31.6996 | 0.0885 |
| PEBBLES_XL | pebbles | cross_category_top8 | PANEL_2X4, OXYGEN_SHAKE_GARLIC, TRANSLATOR_VOID_BLUE, ROBOT_DISHES, UV_VISOR_AMBER, +3 | 13.8553 | 3 | 0.0917 | 8.4063 | 574.5802 | 0.0863 |
| SLEEP_POD_POLYESTER | sleep_pods | same_category | SLEEP_POD_SUEDE, SLEEP_POD_LAMB_WOOL, SLEEP_POD_NYLON, SLEEP_POD_COTTON | 4.5684 | 3 | 0.0762 | 3.6286 | 327.3067 | 0.0781 |
| TRANSLATOR_ECLIPSE_CHARCOAL | translators | global_all_ridge | GALAXY_SOUNDS_DARK_MATTER, GALAXY_SOUNDS_BLACK_HOLES, GALAXY_SOUNDS_PLANETARY_RINGS, GALAXY_SOUNDS_SOLAR_WINDS, GALAXY_SOUNDS_SOLAR_FLAMES, +44 | 3.7385 | 3 | 0.0860 | 2.4011 | 110.5713 | 0.0745 |
| ROBOT_VACUUMING | robotics | global_all_ridge | GALAXY_SOUNDS_DARK_MATTER, GALAXY_SOUNDS_BLACK_HOLES, GALAXY_SOUNDS_PLANETARY_RINGS, GALAXY_SOUNDS_SOLAR_WINDS, GALAXY_SOUNDS_SOLAR_FLAMES, +44 | 3.4910 | 3 | 0.0821 | 5.5021 | 111.9411 | 0.0742 |
| PEBBLES_XL | pebbles | global_top8 | PEBBLES_XS, PEBBLES_S, PEBBLES_M, PEBBLES_L, PANEL_2X4, +3 | 0.7410 | 3 | 0.3249 | 1.0444 | 3.4965 | 0.0738 |
| SNACKPACK_CHOCOLATE | snackpacks | cross_category_top8 | GALAXY_SOUNDS_BLACK_HOLES, PANEL_1X4, ROBOT_IRONING, PANEL_2X4, ROBOT_MOPPING, +3 | 2.0111 | 3 | 0.0931 | 0.1597 | 124.5256 | 0.0732 |

## Top 20 Mean-Reverting Products

| product | category | mean_reversion_score | mean_reversion_ic_h20 | ret_ac1 | ret_vol | avg_spread | trade_volume |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OXYGEN_SHAKE_EVENING_BREATH | oxygen_shakes | 0.1584 | 0.0344 | -0.1150 | 10.9345 | 11.8605 | 1805 |
| ROBOT_IRONING | robotics | 0.1325 | 0.0080 | -0.1176 | 10.3309 | 6.3929 | 1805 |
| ROBOT_DISHES | robotics | 0.1268 | 0.0203 | -0.0985 | 15.7128 | 7.3503 | 1805 |
| OXYGEN_SHAKE_CHOCOLATE | oxygen_shakes | 0.1251 | 0.0453 | -0.0798 | 10.8110 | 12.1855 | 1805 |
| PEBBLES_XL | pebbles | 0.0852 | 0.0852 | 0.0076 | 30.3126 | 16.6308 | 2283 |
| SNACKPACK_PISTACHIO | snackpacks | 0.0802 | 0.0416 | -0.0251 | 5.2374 | 15.9256 | 1805 |
| SNACKPACK_RASPBERRY | snackpacks | 0.0642 | 0.0380 | -0.0169 | 8.0916 | 16.8425 | 1805 |
| ROBOT_LAUNDRY | robotics | 0.0618 | 0.0503 | 0.0061 | 9.8055 | 7.1651 | 1805 |
| UV_VISOR_MAGENTA | uv_visors | 0.0585 | 0.0513 | -0.0034 | 11.1914 | 14.0916 | 1805 |
| PEBBLES_XS | pebbles | 0.0570 | 0.0413 | -0.0157 | 15.0518 | 9.7449 | 2283 |
| SNACKPACK_STRAWBERRY | snackpacks | 0.0563 | 0.0315 | -0.0142 | 8.1328 | 17.8265 | 1805 |
| PEBBLES_M | pebbles | 0.0508 | 0.0449 | -0.0048 | 15.1327 | 13.1209 | 2283 |
| TRANSLATOR_VOID_BLUE | translators | 0.0489 | 0.0398 | -0.0091 | 10.8228 | 9.5247 | 1805 |
| GALAXY_SOUNDS_DARK_MATTER | galaxy_sounds | 0.0474 | 0.0174 | -0.0117 | 10.2439 | 13.0508 | 1805 |
| TRANSLATOR_GRAPHITE_MIST | translators | 0.0450 | 0.0384 | -0.0033 | 10.1234 | 8.9121 | 1805 |
| SNACKPACK_CHOCOLATE | snackpacks | 0.0446 | -0.0021 | -0.0310 | 6.5755 | 16.4712 | 1805 |
| UV_VISOR_YELLOW | uv_visors | 0.0431 | 0.0348 | 0.0032 | 10.9986 | 13.9100 | 1805 |
| GALAXY_SOUNDS_SOLAR_FLAMES | galaxy_sounds | 0.0430 | -0.0032 | -0.0122 | 11.0934 | 14.0715 | 1805 |
| OXYGEN_SHAKE_MORNING_BREATH | oxygen_shakes | 0.0397 | 0.0289 | -0.0057 | 10.0897 | 12.7829 | 1805 |
| SNACKPACK_VANILLA | snackpacks | 0.0392 | -0.0075 | -0.0269 | 6.5129 | 16.8687 | 1805 |

## Top 20 Drift/Trend Products

| product | category | trend_score | drift_abs_mean_ticks | drift_z_abs_mean | trend_ic_50_20 | ret_vol | avg_spread |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PANEL_1X4 | panels | 1.4140 | 1,311.5 | 1.3597 | 0.0542 | 9.4572 | 8.3766 |
| MICROCHIP_SQUARE | microchips | 1.3480 | 2,724.0 | 1.3390 | 0.0041 | 20.5412 | 11.7188 |
| MICROCHIP_OVAL | microchips | 1.3300 | 1,488.5 | 1.3169 | -0.0020 | 12.2854 | 7.4498 |
| UV_VISOR_YELLOW | uv_visors | 1.2387 | 1,339.7 | 1.2387 | -0.0545 | 10.9986 | 13.9100 |
| TRANSLATOR_GRAPHITE_MIST | translators | 1.1952 | 1,212.0 | 1.1943 | -0.0231 | 10.1234 | 8.9121 |
| MICROCHIP_CIRCLE | microchips | 1.1927 | 1,108.3 | 1.1798 | 0.0129 | 9.2278 | 8.2622 |
| UV_VISOR_AMBER | uv_visors | 1.1796 | 954.5000 | 1.1469 | 0.0327 | 7.9549 | 10.3205 |
| OXYGEN_SHAKE_GARLIC | oxygen_shakes | 1.0986 | 1,299.3 | 1.0842 | 0.0032 | 11.9920 | 15.0546 |
| SLEEP_POD_POLYESTER | sleep_pods | 1.0975 | 1,267.0 | 1.0941 | -0.0206 | 11.8628 | 10.2957 |
| SLEEP_POD_NYLON | sleep_pods | 1.0447 | 990.6667 | 1.0294 | -0.0094 | 9.6137 | 8.5647 |
| PANEL_1X2 | panels | 1.0438 | 946.6667 | 1.0271 | -0.0119 | 9.0416 | 11.5098 |
| TRANSLATOR_SPACE_GRAY | translators | 1.0398 | 944.6667 | 1.0216 | 0.0058 | 9.4188 | 8.4022 |
| GALAXY_SOUNDS_BLACK_HOLES | galaxy_sounds | 1.0326 | 1,151.8 | 1.0101 | -0.0010 | 11.4475 | 14.5128 |
| GALAXY_SOUNDS_PLANETARY_RINGS | galaxy_sounds | 1.0235 | 1,058.0 | 1.0010 | -0.0090 | 10.8614 | 13.6900 |
| PEBBLES_XL | pebbles | 1.0164 | 3,080.3 | 1.0163 | -0.0485 | 30.3126 | 16.6308 |
| ROBOT_MOPPING | robotics | 0.9415 | 1,038.2 | 0.9275 | -0.0094 | 11.1341 | 7.9707 |
| ROBOT_IRONING | robotics | 0.9350 | 940.0000 | 0.9350 | -0.0303 | 10.3309 | 6.3929 |
| SLEEP_POD_COTTON | sleep_pods | 0.8998 | 994.1667 | 0.8654 | 0.0226 | 11.6497 | 10.0502 |
| PEBBLES_XS | pebbles | 0.8829 | 1,326.2 | 0.8792 | -0.0249 | 15.0518 | 9.7449 |
| MICROCHIP_TRIANGLE | microchips | 0.8428 | 1,162.7 | 0.8065 | 0.0247 | 14.4586 | 8.6354 |

## Relationships That Failed Validation

| type | relationship | reason | in_sample_metric | oos_metric | positive_days |
| --- | --- | --- | --- | --- | --- |
| basket | ROBOT_LAUNDRY global_top8 | residual looked mean-reverting but failed edge or final-day validation | 0.12623 | 2.59614 | 2 |
| basket | ROBOT_LAUNDRY same_category | residual looked mean-reverting but failed edge or final-day validation | 0.12448 | 2.09583 | 2 |
| basket | SNACKPACK_PISTACHIO global_all_ridge | residual looked mean-reverting but failed edge or final-day validation | 0.12301 | 0.65311 | 2 |
| basket | ROBOT_LAUNDRY cross_category_top8 | residual looked mean-reverting but failed edge or final-day validation | 0.11509 | 2.00638 | 2 |
| basket | UV_VISOR_RED same_category | residual looked mean-reverting but failed edge or final-day validation | 0.11117 | -0.18742 | 2 |
| basket | UV_VISOR_MAGENTA same_category | residual looked mean-reverting but failed edge or final-day validation | 0.10890 | 3.62682 | 2 |
| basket | TRANSLATOR_SPACE_GRAY global_all_ridge | residual looked mean-reverting but failed edge or final-day validation | 0.10236 | 1.47674 | 2 |
| basket | UV_VISOR_RED cross_category_top8 | residual looked mean-reverting but failed edge or final-day validation | 0.10099 | 2.91738 | 2 |
| basket | TRANSLATOR_VOID_BLUE global_all_ridge | residual looked mean-reverting but failed edge or final-day validation | 0.10068 | 2.33794 | 2 |
| basket | TRANSLATOR_GRAPHITE_MIST global_all_ridge | residual looked mean-reverting but failed edge or final-day validation | 0.09898 | 0.79668 | 2 |
| basket | MICROCHIP_SQUARE cross_category_top8 | residual looked mean-reverting but failed edge or final-day validation | 0.09757 | 1.40312 | 2 |
| basket | UV_VISOR_RED global_top8 | residual looked mean-reverting but failed edge or final-day validation | 0.09620 | 2.48833 | 2 |
| basket | MICROCHIP_SQUARE global_top8 | residual looked mean-reverting but failed edge or final-day validation | 0.09364 | -0.17227 | 2 |
| basket | SLEEP_POD_NYLON same_category | residual looked mean-reverting but failed edge or final-day validation | 0.09359 | 4.91634 | 2 |
| correlation | SLEEP_POD_POLYESTER / SLEEP_POD_COTTON | high blended score but daily return-correlation sign was unstable | 0.11257 | -0.00717 | 1 |
| correlation | PEBBLES_XS / PANEL_2X4 | high blended score but daily return-correlation sign was unstable | 0.11006 | 0.00141 | 1 |
| lead_lag | TRANSLATOR_ASTRO_BLACK -> UV_VISOR_RED lag 1 | large in-sample lag correlation did not survive leave-one-day-out edge | 0.01434 | 0.05011 | 1 |

## Leaders

| leader | leader_category | edge_count | unique_followers | score_sum | avg_oos_edge |
| --- | --- | --- | --- | --- | --- |
| MICROCHIP_CIRCLE | microchips | 117 | 46 | 15.84070 | 0.09976 |
| OXYGEN_SHAKE_EVENING_BREATH | oxygen_shakes | 138 | 46 | 14.28724 | 0.08265 |
| PEBBLES_M | pebbles | 120 | 46 | 14.15881 | 0.09296 |
| SNACKPACK_RASPBERRY | snackpacks | 128 | 48 | 13.69939 | 0.08478 |
| TRANSLATOR_GRAPHITE_MIST | translators | 126 | 46 | 13.56875 | 0.08437 |
| ROBOT_LAUNDRY | robotics | 112 | 46 | 13.49804 | 0.09317 |
| GALAXY_SOUNDS_SOLAR_WINDS | galaxy_sounds | 125 | 48 | 13.27747 | 0.08348 |
| PEBBLES_XL | pebbles | 126 | 47 | 13.19402 | 0.08425 |
| TRANSLATOR_VOID_BLUE | translators | 124 | 46 | 13.06584 | 0.08353 |
| SNACKPACK_STRAWBERRY | snackpacks | 122 | 47 | 12.96902 | 0.08250 |
| OXYGEN_SHAKE_GARLIC | oxygen_shakes | 124 | 47 | 12.82490 | 0.08072 |
| SNACKPACK_PISTACHIO | snackpacks | 114 | 44 | 12.70618 | 0.08661 |
| PANEL_4X4 | panels | 111 | 46 | 12.66545 | 0.08980 |
| PANEL_1X4 | panels | 112 | 47 | 12.59548 | 0.08781 |
| GALAXY_SOUNDS_SOLAR_FLAMES | galaxy_sounds | 114 | 43 | 12.51974 | 0.08619 |

## Laggards

| follower | follower_category | edge_count | unique_leaders | score_sum | avg_oos_edge |
| --- | --- | --- | --- | --- | --- |
| PEBBLES_XL | pebbles | 105 | 45 | 29.03398 | 0.21928 |
| MICROCHIP_SQUARE | microchips | 101 | 48 | 23.46681 | 0.17596 |
| ROBOT_DISHES | robotics | 118 | 47 | 18.19600 | 0.12441 |
| PEBBLES_S | pebbles | 122 | 43 | 16.61331 | 0.10719 |
| PEBBLES_L | pebbles | 120 | 46 | 15.86929 | 0.10375 |
| MICROCHIP_OVAL | microchips | 119 | 45 | 14.82520 | 0.09467 |
| PEBBLES_M | pebbles | 105 | 43 | 14.65417 | 0.11059 |
| MICROCHIP_RECTANGLE | microchips | 117 | 47 | 14.29116 | 0.09721 |
| PEBBLES_XS | pebbles | 102 | 44 | 14.13304 | 0.11055 |
| OXYGEN_SHAKE_GARLIC | oxygen_shakes | 126 | 47 | 13.91802 | 0.08662 |
| MICROCHIP_TRIANGLE | microchips | 93 | 40 | 13.50299 | 0.11299 |
| SLEEP_POD_COTTON | sleep_pods | 115 | 48 | 13.33726 | 0.09004 |
| SLEEP_POD_POLYESTER | sleep_pods | 115 | 46 | 13.20148 | 0.09058 |
| UV_VISOR_MAGENTA | uv_visors | 127 | 46 | 12.92631 | 0.08036 |
| PANEL_2X4 | panels | 113 | 46 | 12.46309 | 0.08857 |

## Products And Categories To Avoid

Categories with little validated alpha mass or worse liquidity:

| category | validated_alpha_score | avoid_score | liquidity_score | avg_spread |
| --- | --- | --- | --- | --- |
| uv_visors | 117.9023 | 0.2455 | 2.8325 | 13.1291 |
| robotics | 121.7805 | 0.2522 | 2.2526 | 7.1264 |
| panels | 122.4591 | 0.2525 | 2.7435 | 9.3986 |
| translators | 123.2766 | 0.2350 | 2.6267 | 8.7812 |
| galaxy_sounds | 126.5753 | 0.2359 | 2.6687 | 13.7253 |
| sleep_pods | 131.2829 | 0.2566 | 2.3090 | 9.6520 |
| oxygen_shakes | 132.3789 | 0.2208 | 2.8556 | 12.8954 |
| microchips | 140.3547 | 0.2982 | 1.6470 | 8.7904 |
| snackpacks | 161.7338 | 0.2247 | 3.5197 | 16.7869 |
| pebbles | 243.8983 | 0.2053 | 2.0625 | 12.8137 |

Product-level avoid list:

| product | category | avoid_score | validated_alpha_score | liquidity_score | avg_spread | reason |
| --- | --- | --- | --- | --- | --- | --- |
| UV_VISOR_AMBER | uv_visors | 0.2526 | 20.0517 | 3.5820 | 10.3205 | few validated global edges and/or unattractive spread/liquidity |
| TRANSLATOR_SPACE_GRAY | translators | 0.2468 | 21.2226 | 2.8500 | 8.4022 | few validated global edges and/or unattractive spread/liquidity |
| UV_VISOR_ORANGE | uv_visors | 0.2632 | 21.5281 | 2.7521 | 13.2841 | few validated global edges and/or unattractive spread/liquidity |
| ROBOT_MOPPING | robotics | 0.3080 | 21.5558 | 1.7791 | 7.9707 | few validated global edges and/or unattractive spread/liquidity |
| ROBOT_IRONING | robotics | 0.2385 | 21.7344 | 2.5880 | 6.3929 | few validated global edges and/or unattractive spread/liquidity |
| GALAXY_SOUNDS_PLANETARY_RINGS | galaxy_sounds | 0.2515 | 21.7693 | 2.6754 | 13.6900 | few validated global edges and/or unattractive spread/liquidity |
| UV_VISOR_RED | uv_visors | 0.2753 | 22.4234 | 2.6057 | 14.0394 | few validated global edges and/or unattractive spread/liquidity |
| PANEL_4X4 | panels | 0.2624 | 22.9341 | 2.5900 | 8.7505 | few validated global edges and/or unattractive spread/liquidity |
| ROBOT_VACUUMING | robotics | 0.2528 | 23.1927 | 2.5479 | 6.7533 | few validated global edges and/or unattractive spread/liquidity |
| OXYGEN_SHAKE_MORNING_BREATH | oxygen_shakes | 0.2317 | 23.2290 | 2.8612 | 12.7829 | few validated global edges and/or unattractive spread/liquidity |
| PANEL_1X2 | panels | 0.2398 | 23.4521 | 3.1798 | 11.5098 | few validated global edges and/or unattractive spread/liquidity |
| PANEL_1X4 | panels | 0.2624 | 23.5485 | 2.9356 | 8.3766 | few validated global edges and/or unattractive spread/liquidity |
| UV_VISOR_YELLOW | uv_visors | 0.2344 | 23.5606 | 2.6267 | 13.9100 | few validated global edges and/or unattractive spread/liquidity |
| TRANSLATOR_VOID_BLUE | translators | 0.2410 | 23.8417 | 2.2954 | 9.5247 | few validated global edges and/or unattractive spread/liquidity |
| MICROCHIP_CIRCLE | microchips | 0.3159 | 23.8580 | 1.6391 | 8.2622 | few validated global edges and/or unattractive spread/liquidity |
| GALAXY_SOUNDS_BLACK_HOLES | galaxy_sounds | 0.2482 | 24.0239 | 2.5270 | 14.5128 | few validated global edges and/or unattractive spread/liquidity |
| PANEL_2X2 | panels | 0.2392 | 24.1111 | 2.8004 | 8.5155 | few validated global edges and/or unattractive spread/liquidity |
| OXYGEN_SHAKE_CHOCOLATE | oxygen_shakes | 0.2123 | 24.2547 | 3.0011 | 12.1855 | few validated global edges and/or unattractive spread/liquidity |
| SLEEP_POD_SUEDE | sleep_pods | 0.2614 | 24.2738 | 2.2030 | 9.9495 | few validated global edges and/or unattractive spread/liquidity |
| SLEEP_POD_NYLON | sleep_pods | 0.2472 | 24.3534 | 2.7361 | 8.5647 | few validated global edges and/or unattractive spread/liquidity |

## Best Alpha Hypotheses

- Use validated lead-lag as small fair-value nudges, not standalone max-size trades; require at least the reported lag history and suppress if the follower spread is too wide.
- Prioritize residual models with positive leave-one-day-out edge on at least two days and positive train-day1/day2-to-day3 validation; this is the strongest guard against day 1 red herrings.
- For pair and basket spreads, trade residual z-scores with entry around 1.25 and exit near 0.25; do not use raw level correlation as a trading rule.
- Cross-category candidates exist, but the report keeps same-category candidates when they validate better; strategy agents should compare both because all products share the same tight position limit.

## Supporting Tables

- `product_diagnostics.csv` and `product_diagnostics_by_day.csv`
- `cross_product_correlations.csv`
- `lead_lag_relationships.csv`
- `pair_spread_models.csv`
- `basket_models.csv`
- `failed_validation.csv`, `leaders.csv`, `laggards.csv`
- `alpha_candidates.json` for machine-readable strategy-agent handoff
