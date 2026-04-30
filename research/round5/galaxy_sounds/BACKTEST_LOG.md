# Galaxy Sounds Backtest Log

All backtests used the Rust backtester against bundled Round 5 days 2, 3, and 4. Products traded were restricted to:

`GALAXY_SOUNDS_DARK_MATTER`, `GALAXY_SOUNDS_BLACK_HOLES`, `GALAXY_SOUNDS_PLANETARY_RINGS`, `GALAXY_SOUNDS_SOLAR_WINDS`, `GALAXY_SOUNDS_SOLAR_FLAMES`.

## Commands

Final verification command:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/galaxy_sounds/galaxy_sounds_strategy.py --dataset round5 --products full --artifact-mode full --flat --run-id galaxy_final_winds78
```

Grid command pattern used for generated variants:

```bash
cd prosperity_rust_backtester
/Users/giordanmasen/Library/Caches/rust_backtester/target/release/rust_backtester --trader <trader_path> --dataset round5 --products off --artifact-mode none
```

Product PnL columns are summed across days 2-4 from each run's `metrics.json`.

## Tested Strategies

| strategy | parameters | trader | total | D+2 | D+3 | D+4 | black_holes | dark_matter | rings | flames | winds | next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| refine_winds_lag78_k0p15 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag78_k0p15.py | 283,385.5 | 87,214.5 | 89,170.0 | 107,001.0 | 49,924.5 | 64,382.0 | 49,082.0 | 77,184.0 | 42,813.0 | chosen final |
| refine_winds_lag80_k0p15 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag80_k0p15.py | 283,179.5 | 87,381.5 | 88,726.0 | 107,072.0 | 49,924.5 | 64,382.0 | 49,082.0 | 76,978.0 | 42,813.0 | supports perturbation robustness |
| refine_winds_lag72_k0p15 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag72_k0p15.py | 283,088.5 | 87,518.5 | 89,170.0 | 106,400.0 | 49,924.5 | 64,382.0 | 49,082.0 | 76,887.0 | 42,813.0 | supports perturbation robustness |
| refine_winds_lag75_k0p15 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag75_k0p15.py | 282,784.5 | 87,214.5 | 89,170.0 | 106,400.0 | 49,924.5 | 64,382.0 | 49,082.0 | 76,583.0 | 42,813.0 | supports perturbation robustness |
| refine_winds_lag74_k0p15 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag74_k0p15.py | 282,784.5 | 87,214.5 | 89,170.0 | 106,400.0 | 49,924.5 | 64,382.0 | 49,082.0 | 76,583.0 | 42,813.0 | supports perturbation robustness |
| refine_winds75_obneg20 | winds75 overlay plus small negative imbalance overlay | research/round5/galaxy_sounds/generated_traders/refine_winds75_obneg20.py | 282,690.5 | 86,599.5 | 89,337.0 | 106,754.0 | 50,457.5 | 64,382.0 | 49,082.0 | 75,956.0 | 42,813.0 | not selected |
| refine_winds75_rings500 | best winds75 overlay plus rings500 overlay | research/round5/galaxy_sounds/generated_traders/refine_winds75_rings500.py | 282,651.5 | 89,136.5 | 88,373.0 | 105,142.0 | 49,924.5 | 64,382.0 | 49,082.0 | 76,450.0 | 42,813.0 | not selected |
| refine_winds_lag70_k0p15 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag70_k0p15.py | 282,533.5 | 87,518.5 | 88,886.0 | 106,129.0 | 49,924.5 | 64,382.0 | 49,082.0 | 76,332.0 | 42,813.0 | not selected |
| refine_winds_lag76_k0p15 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag76_k0p15.py | 282,513.5 | 87,214.5 | 89,170.0 | 106,129.0 | 49,924.5 | 64,382.0 | 49,082.0 | 76,312.0 | 42,813.0 | not selected |
| refine_winds_lag74_k0p1 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag74_k0p1.py | 282,473.5 | 86,903.5 | 89,170.0 | 106,400.0 | 49,924.5 | 64,382.0 | 49,082.0 | 76,272.0 | 42,813.0 | not selected |
| refine_winds_lag72_k0p1 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag72_k0p1.py | 282,290.5 | 86,732.5 | 89,170.0 | 106,388.0 | 49,924.5 | 64,382.0 | 49,082.0 | 76,089.0 | 42,813.0 | not selected |
| refine_winds_lag75_k0p1 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag75_k0p1.py | 282,157.5 | 86,599.5 | 89,170.0 | 106,388.0 | 49,924.5 | 64,382.0 | 49,082.0 | 75,956.0 | 42,813.0 | not selected |
| hybrid_add_winds75_to_flames | hybrid plus SOLAR_WINDS lag75 k0.10 -> SOLAR_FLAMES | research/round5/galaxy_sounds/generated_traders/hybrid_add_winds75_to_flames.py | 282,157.5 | 86,599.5 | 89,170.0 | 106,388.0 | 49,924.5 | 64,382.0 | 49,082.0 | 75,956.0 | 42,813.0 | not selected |
| refine_winds_lag76_k0p1 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag76_k0p1.py | 282,097.5 | 86,599.5 | 89,310.0 | 106,188.0 | 49,924.5 | 64,382.0 | 49,082.0 | 75,896.0 | 42,813.0 | not selected |
| hybrid_add_rings_to_flames | hybrid plus PLANETARY_RINGS lag500 -> SOLAR_FLAMES | research/round5/galaxy_sounds/generated_traders/hybrid_add_rings_to_flames.py | 281,544.5 | 90,212.5 | 88,338.0 | 102,994.0 | 49,924.5 | 64,382.0 | 49,082.0 | 75,343.0 | 42,813.0 | not selected |
| refine_winds_lag78_k0p1 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag78_k0p1.py | 281,469.5 | 86,903.5 | 89,310.0 | 105,256.0 | 49,924.5 | 64,382.0 | 49,082.0 | 75,268.0 | 42,813.0 | not selected |
| hybrid_orderbook_neg50 | hybrid plus product imbalance overlay | research/round5/galaxy_sounds/generated_traders/hybrid_orderbook_neg50.py | 281,111.5 | 87,570.5 | 87,926.0 | 105,615.0 | 50,904.5 | 64,382.0 | 49,082.0 | 73,930.0 | 42,813.0 | rejected: small/less robust overlay |
| refine_winds_lag70_k0p1 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag70_k0p1.py | 280,970.5 | 86,732.5 | 89,170.0 | 105,068.0 | 49,924.5 | 64,382.0 | 49,082.0 | 74,769.0 | 42,813.0 | not selected |
| refine_winds_lag80_k0p1 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag80_k0p1.py | 280,853.5 | 86,599.5 | 88,726.0 | 105,528.0 | 49,924.5 | 64,382.0 | 49,082.0 | 74,652.0 | 42,813.0 | not selected |
| hybrid_orderbook_neg20 | hybrid plus product imbalance overlay | research/round5/galaxy_sounds/generated_traders/hybrid_orderbook_neg20.py | 280,664.5 | 87,181.5 | 88,269.0 | 105,214.0 | 50,457.5 | 64,382.0 | 49,082.0 | 73,930.0 | 42,813.0 | rejected: small/less robust overlay |
| hybrid_current | inherited validated Galaxy subset from full R5 trader | research/round5/galaxy_sounds/generated_traders/hybrid_current.py | 280,131.5 | 87,181.5 | 88,102.0 | 104,848.0 | 49,924.5 | 64,382.0 | 49,082.0 | 73,930.0 | 42,813.0 | benchmark kept as fallback |
| refine_winds_lag80_k0p05 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag80_k0p05.py | 280,052.5 | 86,903.5 | 87,893.0 | 105,256.0 | 49,924.5 | 64,382.0 | 49,082.0 | 73,851.0 | 42,813.0 | not selected |
| refine_winds_lag72_k0p05 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag72_k0p05.py | 280,052.5 | 86,903.5 | 87,893.0 | 105,256.0 | 49,924.5 | 64,382.0 | 49,082.0 | 73,851.0 | 42,813.0 | not selected |
| refine_winds_lag74_k0p05 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag74_k0p05.py | 280,052.5 | 86,903.5 | 87,893.0 | 105,256.0 | 49,924.5 | 64,382.0 | 49,082.0 | 73,851.0 | 42,813.0 | not selected |
| refine_winds_lag78_k0p05 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag78_k0p05.py | 280,052.5 | 86,903.5 | 87,893.0 | 105,256.0 | 49,924.5 | 64,382.0 | 49,082.0 | 73,851.0 | 42,813.0 | not selected |
| refine_winds_lag76_k0p05 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag76_k0p05.py | 279,852.5 | 86,903.5 | 87,893.0 | 105,056.0 | 49,924.5 | 64,382.0 | 49,082.0 | 73,651.0 | 42,813.0 | not selected |
| refine_winds_lag75_k0p05 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag75_k0p05.py | 279,852.5 | 86,903.5 | 87,893.0 | 105,056.0 | 49,924.5 | 64,382.0 | 49,082.0 | 73,651.0 | 42,813.0 | not selected |
| refine_winds_lag70_k0p05 | hybrid plus SOLAR_WINDS -> SOLAR_FLAMES lag/k perturbation | research/round5/galaxy_sounds/generated_traders/refine_winds_lag70_k0p05.py | 279,852.5 | 86,903.5 | 87,893.0 | 105,056.0 | 49,924.5 | 64,382.0 | 49,082.0 | 73,651.0 | 42,813.0 | not selected |
| hybrid_flames_k_m0p75 | hybrid with BLACK_HOLES -> SOLAR_FLAMES k perturbation | research/round5/galaxy_sounds/generated_traders/hybrid_flames_k_m0p75.py | 275,813.5 | 91,111.5 | 81,758.0 | 102,944.0 | 49,924.5 | 64,382.0 | 49,082.0 | 69,612.0 | 42,813.0 | not selected |
| hybrid_flames_k_m1p5 | hybrid with BLACK_HOLES -> SOLAR_FLAMES k perturbation | research/round5/galaxy_sounds/generated_traders/hybrid_flames_k_m1p5.py | 273,150.5 | 84,656.5 | 87,856.0 | 100,638.0 | 49,924.5 | 64,382.0 | 49,082.0 | 66,949.0 | 42,813.0 | not selected |
| hybrid_flames_k_m1p75 | hybrid with BLACK_HOLES -> SOLAR_FLAMES k perturbation | research/round5/galaxy_sounds/generated_traders/hybrid_flames_k_m1p75.py | 272,322.5 | 79,952.5 | 91,016.0 | 101,354.0 | 49,924.5 | 64,382.0 | 49,082.0 | 66,121.0 | 42,813.0 | not selected |
| hybrid_no_flames_signal | hybrid with BLACK_HOLES -> SOLAR_FLAMES removed | research/round5/galaxy_sounds/generated_traders/hybrid_no_flames_signal.py | 272,233.5 | 89,054.5 | 82,203.0 | 100,976.0 | 49,924.5 | 64,382.0 | 49,082.0 | 66,032.0 | 42,813.0 | not selected |
| hybrid_flames_k_m1p0 | hybrid with BLACK_HOLES -> SOLAR_FLAMES k perturbation | research/round5/galaxy_sounds/generated_traders/hybrid_flames_k_m1p0.py | 271,523.5 | 88,519.5 | 85,035.0 | 97,969.0 | 49,924.5 | 64,382.0 | 49,082.0 | 65,322.0 | 42,813.0 | not selected |
| hybrid_flames_only | hybrid keeping only SOLAR_FLAMES lag overlay | research/round5/galaxy_sounds/generated_traders/hybrid_flames_only.py | 270,990.5 | 89,434.0 | 86,306.0 | 95,250.5 | 45,323.5 | 63,016.0 | 46,683.0 | 73,930.0 | 42,038.0 | not selected |
| static_shift_nosig | static/mid hybrid with anchor shifts, no lead-lag | research/round5/galaxy_sounds/generated_traders/static_shift_nosig.py | 263,092.5 | 91,307.0 | 80,407.0 | 91,378.5 | 45,323.5 | 63,016.0 | 46,683.0 | 66,032.0 | 42,038.0 | not selected |
| pair_dark_rings_blend0p25 | DARK_MATTER/PLANETARY_RINGS hedged pair fair-value blend | research/round5/galaxy_sounds/generated_traders/pair_dark_rings_blend0p25.py | 238,639.5 | 102,733.0 | 71,110.0 | 64,796.5 | 45,323.5 | 52,264.0 | 32,982.0 | 66,032.0 | 42,038.0 | rejected: weaker executable PnL |
| basket_blend0p25 | leave-one-day-out averaged basket fair-value blend | research/round5/galaxy_sounds/generated_traders/basket_blend0p25.py | 235,028.0 | 96,399.0 | 78,387.0 | 60,242.0 | 27,395.0 | 57,522.0 | 42,842.0 | 64,599.0 | 42,670.0 | rejected: weaker executable PnL |
| meanrev_tighter_no_sig | static/mid mean reversion, tighter z thresholds | research/round5/galaxy_sounds/generated_traders/meanrev_tighter_no_sig.py | 214,067.5 | 81,737.0 | 59,965.0 | 72,365.5 | 45,323.5 | 48,965.0 | 33,522.0 | 52,407.0 | 33,850.0 | not selected |
| meanrev_looser_no_sig | static/mid mean reversion, looser z thresholds | research/round5/galaxy_sounds/generated_traders/meanrev_looser_no_sig.py | 205,837.5 | 62,080.0 | 65,797.0 | 77,960.5 | 45,323.5 | 61,570.0 | 27,848.0 | 46,466.0 | 24,630.0 | not selected |
| pair_dark_rings_blend1 | DARK_MATTER/PLANETARY_RINGS hedged pair fair-value blend | research/round5/galaxy_sounds/generated_traders/pair_dark_rings_blend1.py | 200,131.5 | 84,929.0 | 64,343.0 | 50,859.5 | 45,323.5 | 36,055.0 | 10,683.0 | 66,032.0 | 42,038.0 | rejected: weaker executable PnL |
| static_no_shift_nosig | single-product static mean reversion, no anchor shifts or lead-lag | research/round5/galaxy_sounds/generated_traders/static_no_shift_nosig.py | 190,761.0 | 90,718.0 | 39,194.0 | 60,849.0 | 2,002.0 | 50,714.0 | 44,778.0 | 51,229.0 | 42,038.0 | not selected |
| basket_blend1 | leave-one-day-out averaged basket fair-value blend | research/round5/galaxy_sounds/generated_traders/basket_blend1.py | 160,544.0 | 85,681.0 | 71,887.0 | 2,976.0 | 27,490.0 | 26,382.0 | 2,180.0 | 60,939.0 | 43,553.0 | rejected: weaker executable PnL |
| hybrid_passive_only | hybrid fair values, no aggressive crossing | research/round5/galaxy_sounds/generated_traders/hybrid_passive_only.py | 89,519.5 | 24,884.5 | 28,672.0 | 35,963.0 | 49,924.5 | 39,595.0 | 0.0000 | 0.0000 | 0.0000 | not selected |
| leadlag_mid_only | lead-lag overlays around current mid only | research/round5/galaxy_sounds/generated_traders/leadlag_mid_only.py | 61,768.5 | -12,618.5 | 31,077.0 | 43,310.0 | 30,218.5 | 4,567.0 | 7,349.0 | 2,083.0 | 17,551.0 | rejected: weak standalone edge |
| momentum_self50_p0p2 | single-product momentum, lag 50, k +0.2 | research/round5/galaxy_sounds/generated_traders/momentum_self50_p0p2.py | 55,756.0 | 18,760.5 | 4,694.5 | 32,301.0 | 15,507.0 | -1,206.0 | 28,108.0 | 6,530.0 | 6,817.0 | rejected: weak standalone edge |
| mm_mid_edge0 | baseline current-mid market making; edge/improve in name | research/round5/galaxy_sounds/generated_traders/mm_mid_edge0.py | 41,145.5 | 601.0000 | 19,791.5 | 20,753.0 | 14,942.5 | 7,557.5 | 18,163.0 | -8,237.0 | 8,719.5 | rejected: weak standalone edge |
| reversal_self50_m0p2 | single-product reversal, lag 50, k -0.2 | research/round5/galaxy_sounds/generated_traders/reversal_self50_m0p2.py | 40,378.5 | 1,254.0 | 24,021.5 | 15,103.0 | 14,652.0 | 14,590.5 | 22,712.5 | -19,698.5 | 8,122.0 | rejected: weak standalone edge |
| mm_mid_edge2 | baseline current-mid market making; edge/improve in name | research/round5/galaxy_sounds/generated_traders/mm_mid_edge2.py | 40,097.5 | 571.0000 | 18,773.5 | 20,753.0 | 14,942.5 | 7,557.5 | 18,163.0 | -8,237.0 | 7,671.5 | rejected: weak standalone edge |

## Final Verification

| day | pnl | own_trades |
| --- | --- | --- |
| D+2 | 87,214.5 | 132 |
| D+3 | 89,170.0 | 187 |
| D+4 | 107,001.0 | 190 |
| TOTAL | 283,385.5 | 509 |

| product | day_2 | day_3 | day_4 | total |
| --- | --- | --- | --- | --- |
| GALAXY_SOUNDS_BLACK_HOLES | 14,658.5 | 14,142.0 | 21,124.0 | 49,924.5 |
| GALAXY_SOUNDS_DARK_MATTER | 14,473.0 | 31,791.0 | 18,118.0 | 64,382.0 |
| GALAXY_SOUNDS_PLANETARY_RINGS | 13,200.0 | -1,655.0 | 37,537.0 | 49,082.0 |
| GALAXY_SOUNDS_SOLAR_FLAMES | 25,975.0 | 28,622.0 | 22,587.0 | 77,184.0 |
| GALAXY_SOUNDS_SOLAR_WINDS | 18,908.0 | 16,270.0 | 7,635.0 | 42,813.0 |

## What Improved Or Worsened

- Pure current-mid market making was liquid but too noisy: about `40k` PnL with more than 3,200 own trades.
- Static anchor mean reversion with product shifts delivered most of the edge: `263,092.5` before relationship overlays.
- Pair and basket fair values were weaker than static anchors despite some stationarity diagnostics.
- The inherited full-round Galaxy hybrid reached `280,131.5`.
- Adding `SOLAR_WINDS` lagged move into `SOLAR_FLAMES` improved the hybrid to `283,385.5`; nearby lag/k variants stayed close, so this was the only new overlay retained.
- Order-book imbalance overlays were mildly positive but not as robust as the lagged price relationship.
