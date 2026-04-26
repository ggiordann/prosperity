# Chennethelius Round 3 Strategy Review

Generated: 2026-04-26 08:06 UTC

## Scope

- Source repo: `https://github.com/chennethelius/slu-imc-prosperity-4`
- Strategy folder reviewed: `C:\Users\josh\Documents\GitHub\prosperity\.research_repos\p4-chennethelius\strategies\round3`
- Backtester: `C:\Users\josh\Documents\GitHub\prosperity\prosperity_rust_backtester\target\release\rust_backtester` against `datasets/round3`
- Files tested: 27

## Champions

| Rank | Strategy | Total PnL | Day 0 | Day 1 | Day 2 | Min Day | Own Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `v19_vfe_mr_3000` | 716,239.00 | 229,510.50 | 318,073.00 | 168,655.50 | 168,655.50 | 6,730 |
| 2 | `v16_hp_smaller_mr` | 714,767.00 | 229,525.50 | 316,469.00 | 168,772.50 | 168,772.50 | 6,734 |
| 3 | `v25_worst_mid_fair` | 714,323.00 | 229,384.50 | 316,640.00 | 168,298.50 | 168,298.50 | 6,732 |
| 4 | `v13_dual_informed` | 713,784.00 | 229,114.50 | 316,700.00 | 167,969.50 | 167,969.50 | 6,701 |
| 5 | `v26_worst_mid_target` | 713,544.00 | 228,258.50 | 318,691.00 | 166,594.50 | 166,594.50 | 6,701 |
| 6 | `v11_hybrid_plus_informed` | 713,432.00 | 229,106.50 | 316,700.00 | 167,625.50 | 167,625.50 | 6,700 |
| 7 | `v12_hybrid_strong_informed` | 713,432.00 | 229,106.50 | 316,700.00 | 167,625.50 | 167,625.50 | 6,700 |
| 8 | `v14_high_conviction` | 713,432.00 | 229,106.50 | 316,700.00 | 167,625.50 | 167,625.50 | 6,700 |
| 9 | `v18_both_mr_smaller` | 712,868.00 | 229,667.50 | 314,391.00 | 168,809.50 | 168,809.50 | 6,730 |
| 10 | `v17_hp_mr500` | 709,202.00 | 228,889.50 | 312,604.00 | 167,708.50 | 167,708.50 | 6,764 |

## Key Findings

- `v19_vfe_mr_3000` is the champion on total Round 3 PnL at 716,239.00, with day PnL split of 229,510.50 / 318,073.00 / 168,655.50.
- The top of the table is tight: `v19_vfe_mr_3000` beats `v16_hp_smaller_mr` by 1,472.00 total PnL.
- `hybrid` has the best worst-day result at 208,328.50, so it looks like the most stable of the batch rather than just the spikiest.
- `v21_safe_structural` is the busiest strategy at 7,207 own trades; that makes it a useful check on whether extra turnover was actually buying more PnL.
- Among the `11` strategies above 700k total PnL, `v24_partial_hedge` has the best three-day pseudo-Sharpe at 3.410 with day-PnL stdev 69,033.10.
- Feature family `ema_trend` appears in 25 files and averages 498,581.78 total PnL; its best member is `v19_vfe_mr_3000` at 716,239.00.
- Feature family `kalman_mean_reversion` appears in 25 files and averages 498,152.78 total PnL; its best member is `v19_vfe_mr_3000` at 716,239.00.
- Feature family `inventory_aware` appears in 24 files and averages 488,832.75 total PnL; its best member is `v19_vfe_mr_3000` at 716,239.00.
- The most common design ingredients across the folder are `microprice_fair` (27), `vev_divergence_mm` (27), `full_limits_focus` (27), `informed_flow` (26), `kalman_mean_reversion` (25).

## Feature Performance

| Feature | Files | Avg Total PnL | Median Total PnL | Best Strategy | Best PnL |
| --- | ---: | ---: | ---: | --- | ---: |
| `ema_trend` | 25 | 498,581.78 | 681,055.00 | `v19_vfe_mr_3000` | 716,239.00 |
| `kalman_mean_reversion` | 25 | 498,152.78 | 681,055.00 | `v19_vfe_mr_3000` | 716,239.00 |
| `inventory_aware` | 24 | 488,832.75 | 688,609.00 | `v19_vfe_mr_3000` | 716,239.00 |
| `full_limits_focus` | 27 | 465,636.20 | 679,344.00 | `v19_vfe_mr_3000` | 716,239.00 |
| `microprice_fair` | 27 | 465,636.20 | 679,344.00 | `v19_vfe_mr_3000` | 716,239.00 |
| `vev_divergence_mm` | 27 | 465,636.20 | 679,344.00 | `v19_vfe_mr_3000` | 716,239.00 |
| `drawdown_controls` | 5 | 460,820.70 | 679,344.00 | `v24_partial_hedge` | 706,155.00 |
| `informed_flow` | 26 | 457,906.56 | 680,199.50 | `v19_vfe_mr_3000` | 716,239.00 |
| `option_iv_smile` | 12 | 213,986.71 | 127,907.00 | `v24_partial_hedge` | 706,155.00 |

## Risk Rank (>700k PnL)

This uses only the three round-day PnL observations, so treat the Sharpe-like score as a rough sorter, not a statistically strong estimate.

| Sharpe Rank | Strategy | Total PnL | Mean Day PnL | Day PnL Std | Pseudo-Sharpe | Min Day |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `v24_partial_hedge` | 706,155.00 | 235,385.00 | 69,033.10 | 3.410 | 170,047.50 |
| 2 | `v17_hp_mr500` | 709,202.00 | 236,400.67 | 72,739.19 | 3.250 | 167,708.50 |
| 3 | `v18_both_mr_smaller` | 712,868.00 | 237,622.67 | 73,116.05 | 3.250 | 168,809.50 |
| 4 | `v16_hp_smaller_mr` | 714,767.00 | 238,255.67 | 74,234.26 | 3.210 | 168,772.50 |
| 5 | `v25_worst_mid_fair` | 714,323.00 | 238,107.67 | 74,554.48 | 3.194 | 168,298.50 |
| 6 | `v13_dual_informed` | 713,784.00 | 237,928.00 | 74,755.93 | 3.183 | 167,969.50 |
| 7 | `v19_vfe_mr_3000` | 716,239.00 | 238,746.33 | 75,135.70 | 3.178 | 168,655.50 |
| 8 | `v11_hybrid_plus_informed` | 713,432.00 | 237,810.67 | 74,917.44 | 3.174 | 167,625.50 |
| 9 | `v12_hybrid_strong_informed` | 713,432.00 | 237,810.67 | 74,917.44 | 3.174 | 167,625.50 |
| 10 | `v14_high_conviction` | 713,432.00 | 237,810.67 | 74,917.44 | 3.174 | 167,625.50 |
| 11 | `v26_worst_mid_target` | 713,544.00 | 237,848.00 | 76,500.36 | 3.109 | 166,594.50 |

## File-by-File Notes

- `v19_vfe_mr_3000`: Round 3 v11 — Kevin's hybrid.py + ONLY VFE informed-flow target bias. KEY FINDING: at limit=200/300 (the IMC actual limits), hybrid.py historical PnL = 716,008. v01-v10 all add layers (Stoikov skew, dual-anchor MR, IV scalp, exit-at-fair, EMA trend) on top of hybrid's Kalman-MR + Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v16_hp_smaller_mr`: Round 3 v11 — Kevin's hybrid.py + ONLY VFE informed-flow target bias. KEY FINDING: at limit=200/300 (the IMC actual limits), hybrid.py historical PnL = 716,008. v01-v10 all add layers (Stoikov skew, dual-anchor MR, IV scalp, exit-at-fair, EMA trend) on top of hybrid's Kalman-MR + Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v25_worst_mid_fair`: Round 3 v25 — v16 with worst-mid as the Kalman observation (P3 winner trick). CHRIS'S P3 INSIGHT (verbatim from his round-1 walkthrough video): "The way they actually calculate the price... it's the mid price of the worst bid and the worst ask, right? It's consistently that... we Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v13_dual_informed`: Round 3 v13 — v12 + HP informed-flow + LOWERED VFE threshold for 15x events. Empirical re-mining of trade CSV (3 days): HYDROGEL_PACK qty distribution: 2-6 (uniform). qty>=3 has 778 events with +1.5 mid move over 500t — usable informed signal we missed in v12. Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v26_worst_mid_target`: Round 3 v25 — v16 with worst-mid as the Kalman observation (P3 winner trick). CHRIS'S P3 INSIGHT (verbatim from his round-1 walkthrough video): "The way they actually calculate the price... it's the mid price of the worst bid and the worst ask, right? It's consistently that... we Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v11_hybrid_plus_informed`: Round 3 v11 — Kevin's hybrid.py + ONLY VFE informed-flow target bias. KEY FINDING: at limit=200/300 (the IMC actual limits), hybrid.py historical PnL = 716,008. v01-v10 all add layers (Stoikov skew, dual-anchor MR, IV scalp, exit-at-fair, EMA trend) on top of hybrid's Kalman-MR + Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v12_hybrid_strong_informed`: Round 3 v11 — Kevin's hybrid.py + ONLY VFE informed-flow target bias. KEY FINDING: at limit=200/300 (the IMC actual limits), hybrid.py historical PnL = 716,008. v01-v10 all add layers (Stoikov skew, dual-anchor MR, IV scalp, exit-at-fair, EMA trend) on top of hybrid's Kalman-MR + Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v14_high_conviction`: Round 3 v11 — Kevin's hybrid.py + ONLY VFE informed-flow target bias. KEY FINDING: at limit=200/300 (the IMC actual limits), hybrid.py historical PnL = 716,008. v01-v10 all add layers (Stoikov skew, dual-anchor MR, IV scalp, exit-at-fair, EMA trend) on top of hybrid's Kalman-MR + Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v18_both_mr_smaller`: Round 3 v11 — Kevin's hybrid.py + ONLY VFE informed-flow target bias. KEY FINDING: at limit=200/300 (the IMC actual limits), hybrid.py historical PnL = 716,008. v01-v10 all add layers (Stoikov skew, dual-anchor MR, IV scalp, exit-at-fair, EMA trend) on top of hybrid's Kalman-MR + Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v17_hp_mr500`: Round 3 v11 — Kevin's hybrid.py + ONLY VFE informed-flow target bias. KEY FINDING: at limit=200/300 (the IMC actual limits), hybrid.py historical PnL = 716,008. v01-v10 all add layers (Stoikov skew, dual-anchor MR, IV scalp, exit-at-fair, EMA trend) on top of hybrid's Kalman-MR + Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v24_partial_hedge`: Round 3 v23 — v16 + cross-product DELTA HEDGING (VFE neutralises VEV exposure). The VEV options are calls on VFE. Each long call has positive delta toward VFE (option price moves with the underlying). When the strategy accumulates Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, drawdown_controls, full_limits_focus.
- `v22_negskew_stable`: Round 3 v22 — v16 + reduced spread-paying + informed-flow exit-at-fair. Goal: maintain v16's ~720k historical PnL while improving Sharpe and reducing realised drawdown. NEG-SKEW design — avoid the "buying above mid / selling below mid" expense that drives MTM swings. Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, drawdown_controls, full_limits_focus.
- `v15_hp_cap_150`: Round 3 v11 — Kevin's hybrid.py + ONLY VFE informed-flow target bias. KEY FINDING: at limit=200/300 (the IMC actual limits), hybrid.py historical PnL = 716,008. v01-v10 all add layers (Stoikov skew, dual-anchor MR, IV scalp, exit-at-fair, EMA trend) on top of hybrid's Kalman-MR + Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v23_delta_hedge`: Round 3 v23 — v16 + cross-product DELTA HEDGING (VFE neutralises VEV exposure). The VEV options are calls on VFE. Each long call has positive delta toward VFE (option price moves with the underlying). When the strategy accumulates Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, drawdown_controls, full_limits_focus.
- `hybrid`: Round 3 submission — two pipelines, one Trader. HYDROGEL_PACK / VELVETFRUIT_EXTRACT → Kalman-MR (proportional reversion to fair_static) VEV_4000 … VEV_5500                 → anchor-divergence + market-make PRE-SUBMISSION CHECKLIST: Features: kalman_mean_reversion, microprice_fair, ema_trend, vev_divergence_mm, full_limits_focus.
- `v21_safe_structural`: Round 3 v11 — Kevin's hybrid.py + ONLY VFE informed-flow target bias. KEY FINDING: at limit=200/300 (the IMC actual limits), hybrid.py historical PnL = 716,008. v01-v10 all add layers (Stoikov skew, dual-anchor MR, IV scalp, exit-at-fair, EMA trend) on top of hybrid's Kalman-MR + Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v10_full_limits`: Round 3 v10 — v09 with full IMC position limits (200/300 like hybrid.py). Same logic as v09; only the position_limit values change (100 -> 200 for HP/VFE, 100 -> 300 for VEV_*) to match Kevin's hybrid.py and Test_1.py — both of which Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v20_structural`: Round 3 v20 — seven structural improvements over v16. User-prescribed changes (each is structural, not a parameter sweep): 1. HP fair_static 10030 -> 9990 (the actual 3-day mean — eliminates the structural long bias that bled through Day-0/Day-2 down-trends). Features: kalman_mean_reversion, microprice_fair, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, drawdown_controls, full_limits_focus.
- `v09_hybrid_informed_ema`: Round 3 v09 — hybrid.py's tighter VEV thresholds + v07 informed-flow + v08 EMA trend. Integrates teammate Kevin's hybrid.py with our own informed-flow + EMA-trend work: - Adopt hybrid.py's TIGHTER per-strike divergence thresholds for VEV — Kevin Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v03_iv_scalp_dual_mr`: Round 3 v03 — v02 + IV scalping + dual-anchor mean reversion. What's new vs v02 ----------------- 1. **IV scalping per option.** Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v07_v03_plus_pos_reduce`: Round 3 v07 — v03 + position-reducing-at-fair + VFE informed-flow signal. Synthesis of the experimentation in v04-v06: v04-v06 (clean P3 from-scratch) underperform v03 because the assumption "HP fair = 10,000" doesn't hold day-by-day — mid drifts to 9958 on day 0, Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v01_bs_smile_flow`: Round 3 — Test_1 verbatim, with the VEV anchor replaced by BS-with-smile. Why this is the minimal-change strategy --------------------------------------- Test_1.py earns +180,851 on round-3 day 0 via the historical backtester. Its Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, ema_trend, vev_divergence_mm, full_limits_focus.
- `v08_ema_trend_inf`: Round 3 v08 — v07 + EMA trend skew + amplified informed-flow following. Two additions on top of v07: EMA trend skew on HP/VFE position target Maintain a fast price EMA (alpha=EMA_ALPHA, ~50-tick half-life). Add Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v02_inventory_aware`: Round 3 v02 — v01 + Stoikov-style inventory skew + bot-flow-aware exit-at-fair. What's new vs v01 ----------------- 1. **Stoikov-style reservation-price skew on VEV quotes.** Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v04_p3_clean_mm`: Round 3 v04 — clean P3-finalist market maker (start-from-scratch). Design choices (all from chrispyroberts' P3 winner walkthrough) --------------------------------------------------------------- HYDROGEL_PACK   stable-fair MM at fair = 10,000 (the IMC-published true value) Features: microprice_fair, option_iv_smile, informed_flow, inventory_aware, vev_divergence_mm, full_limits_focus.
- `v05_informed_flow`: Round 3 v05 — v04 + informed-trader directional position on VFE. Bot-behaviour signal mined from data ------------------------------------ Round-3 trade CSVs (3 days) — every product, the trade-size distribution is Features: microprice_fair, option_iv_smile, informed_flow, inventory_aware, ema_trend, vev_divergence_mm, full_limits_focus.
- `v06_targeted_p3_informed`: Round 3 v06 — clean P3 MM + (fair-mid) position-targeting + VFE informed-flow. Synthesises the lessons of v01-v05: - v04 (clean P3 MM) is too passive — penny-jumping at fair captures only spread, leaving the structural mean-reversion edge on HP/VFE on the table. Features: kalman_mean_reversion, microprice_fair, option_iv_smile, informed_flow, vev_divergence_mm, drawdown_controls, full_limits_focus.

## Output Files

- Summary CSV: `C:\Users\josh\Documents\GitHub\prosperity\analysis\chennethelius_round3_review\round3_results.csv`
- Per-day CSV: `C:\Users\josh\Documents\GitHub\prosperity\analysis\chennethelius_round3_review\round3_results_per_day.csv`
- Feature CSV: `C:\Users\josh\Documents\GitHub\prosperity\analysis\chennethelius_round3_review\round3_feature_summary.csv`
- Risk-ranked CSV: `C:\Users\josh\Documents\GitHub\prosperity\analysis\chennethelius_round3_review\round3_over_700k_risk_rank.csv`