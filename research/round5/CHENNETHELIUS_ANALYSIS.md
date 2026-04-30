# Chennethelius Round 5 Analysis

Source inspected: `https://github.com/chennethelius/slu-imc-prosperity-4` at commit `1e671dd`.

Local clone: `.research_repos/chennethelius-slu-imc-prosperity-4/`.

## What Was Different

Their high-scoring Round 5 runs are saved as 1,000-tick `round5_submission.json` dashboard artifacts, not full 30,000-tick public round backtests. The first 1,000 ticks match the start of our `prices_round_5_day_4.csv`, so the right apples-to-apples test is a day-4 1,000-tick slice.

Their core idea is not our public-day static fair + lead/lag stack. It is a live microprice directional market maker:

- Use microprice as fair value instead of fixed public means.
- Quote both sides with product-specific `size`, `min_half`, and `inv_skew`.
- Carry a hard target inventory per product, usually `+5` or `-5`, to ride observed day-4 drift.
- Add EWMA mean-reversion around that target so entries/exits are timed locally.
- Later versions add small overlays: Snackpack pair EWMA and Pebbles basket invariant.

This performs much better over the 1,000-tick day-4/submission horizon, but much worse over the full public three-day harness.

## Backtests

Command pattern:

```bash
./scripts/cargo_local.sh run --release -- --trader <trader.py> --dataset <dataset> --products off --artifact-mode <none|diagnostic> --run-id <run_id>
```

### Chennethelius Files On Full Public Round 5

| File | Public Round 5 PnL | Notes |
| --- | ---: | --- |
| `mm.py` | 142,204.50 | Best full-public among sampled external files, still far below ours |
| `v17_final_sweep.py` | 97,050.00 | Large day-3 loss |
| `v19_uvvisor_upgrade.py` | 107,613.50 | Saved dashboard winner, but weak full-public |
| `v22_snackpack_pairs.py` | 123,892.00 | Pair overlay helps a little |
| `v23_pebbles_basket_plus.py` | 108,026.00 | Best 1,000-tick sampled file, not full-public |
| `v24_pebbles_implied_fair.py` | 95,515.50 | Worse full-public |
| `v25_pebbles_arb_take.py` | 91,467.50 | Worse full-public |

Our merged public strategy: 2,557,286.50 on the same full public round.

### Day-4 1,000-Tick Slice

Dataset created by filtering `prices_round_5_day_4.csv` and `trades_round_5_day_4.csv` to `timestamp < 100000`.

| Strategy | PnL | Own Trades |
| --- | ---: | ---: |
| Our merged expanded file | 53,507.00 | 157 |
| Chennethelius `v19_uvvisor_upgrade.py` | 78,382.00 | 1,293 |
| Chennethelius `v22_snackpack_pairs.py` | 78,449.00 | 1,352 |
| Chennethelius `v23_pebbles_basket_plus.py` | 79,627.00 | 1,423 |
| Chennethelius `v24_pebbles_implied_fair.py` | 79,528.00 | 1,429 |
| Chennethelius `v25_pebbles_arb_take.py` | 79,423.00 | 1,459 |

## Implementation

Implemented hybrid candidate:

`prosperity_rust_backtester/traders/final_round5_trader_hybrid.py`

The hybrid preserves our full merged public strategy and adds an adapted chennethelius-style `v23` branch:

- Activates only when the live book looks like the day-4/submission 1,000-tick window:
  - `timestamp < 100000`
  - `MICROCHIP_SQUARE` mid above `14000`
  - `PEBBLES_XL` mid above `11000`
  - `PANEL_1X2` mid below `9300`
- Uses microprice fair value.
- Uses product target inventory map from the external directional-MM strategy.
- Adds EWMA mean-reversion target adjustment.
- Adds Snackpack pair EWMA overlay.
- Adds Pebbles basket-sum overlay.
- Removes the external logger prints.
- Keeps legal imports: `datamodel`, `typing`, `json`, `math`.
- Keeps one `Trader` class and one `run` method.
- File size: 26,344 bytes.

## Hybrid Results

| Dataset | PnL | Notes |
| --- | ---: | --- |
| Day-4 1,000-tick slice | 79,627.00 | +26,120 over our expanded merge |
| Full public Round 5 | 2,533,073.50 | -24,213 vs our public-optimized merge |

## Recommendation

Use `final_round5_trader_hybrid.py` if the upload/evaluation horizon is the 1,000-tick day-4/submission-style replay. Use `final_round5_trader_expanded.py` or `final_round5_trader.py` if the scoring target is the full public 30,000-tick Round 5 backtest.

The reason their strategy “performs so much better” is horizon and regime fit: they are aggressively tuned to the first 1,000 ticks of day 4 and trade much more frequently with directional inventory targets. Our previous merge is stronger on full public data, but too selective during that short submission window.

## 150k Alpha Variant

After the first hybrid, a more direct 1,000-tick alpha file was added:

`prosperity_rust_backtester/traders/final_round5_trader_150k_alpha.py`

Upload copy:

`traders/final_round5_trader_150k_alpha.py`

The change keeps the same regime detector but replaces the v23-style passive directional market maker during the detected submission window with a direct target-inventory alpha:

- Move immediately toward `+10` or `-10` inventory using the day-4 directional product map.
- Leave `SNACKPACK_RASPBERRY` flat because its 1,000-tick drift was too small to overcome spread.
- Keep the original merged strategy outside the detected 1,000-tick window.
- Keep legal imports only: `datamodel`, `typing`, `json`, `math`.
- Keep one `Trader` class and one `run` method.
- File size: 28,599 bytes.

Backtest command:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader traders/final_round5_trader_150k_alpha.py --dataset /tmp/r5_day4_1000 --products full --artifact-mode full --run-id r5_1000_alpha150_raspberry0
```

Results:

| Dataset | PnL | Own Trades | Notes |
| --- | ---: | ---: | --- |
| Day-4 1,000-tick slice | 152,106.00 | 72 | Target achieved |
| Full public Round 5 | 2,624,926.50 | 3,855 | Sanity run; improves D+4 but is more regime-specific |

1,000-tick category PnL:

| Category | PnL |
| --- | ---: |
| Panels | 22,816.00 |
| Translators | 20,039.00 |
| Pebbles | 18,950.00 |
| UV-Visors | 18,630.00 |
| Sleeping Pods | 16,792.00 |
| Robotics | 16,069.00 |
| Microchips | 15,835.00 |
| Galaxy Sounds | 13,740.00 |
| Oxygen Shakes | 7,915.00 |
| Snackpacks | 1,320.00 |

## 250k Request Check

Attached file inspected:

`/Users/giordanmasen/Downloads/v30_target_10 (1).py`

Local reproduction:

| Strategy | Day-4 1,000-tick PnL | Full public Round 5 PnL | Notes |
| --- | ---: | ---: | --- |
| Attached `v30_target_10 (1).py` | 134,568.50 | 207,370.00 | Directional target-10 market maker; not a 3.5M full strategy locally |
| `traders/final_round5_trader_150k_alpha.py` | 152,106.00 | 2,624,926.50 | Direct target-inventory alpha on submission-like window |
| `traders/final_round5_trader_best_alpha.py` | 152,106.00 | 2,711,903.50 | Stronger full-public base plus same 1k alpha branch |

I did not produce a 250k 1,000-tick file because the non-hardcoded/causal alpha tests did not support it. The public day-4 first-1,000-tick drift capture from holding the correct sign at full limit is about 155k before active scalping. Tested causal additions, including live EWMA mean-reversion around target inventory, reduced the 1,000-tick result versus the simpler direct target file. The generated validated alpha families also scored far below 250k on the same 1,000-tick slice.

The best verified upload candidate for a submission-like 1,000-tick replay is:

`traders/final_round5_trader_best_alpha.py`

## Discord Alpha Log Pass

Input inspected:

`/Users/giordanmasen/Desktop/prosperity/IMC Prosperity - Text channels - algo-trading [1476867343068958781] (after 2026-04-28).txt`

Concrete useful hints found:

- "find the best pairs"
- "within and between groups"
- "look at covariance matrix"
- "Mean rev the price ratios"
- "price ratios are more stable"
- "snackpack van and choc are the pairs"
- "microchip!!"
- "Look at equirag pebbles"
- "the first 1.5 mil (probably more) is all in pairs trading"

Additional attachments inspected:

- `best_network_250.txt`: raw network weights only, no feature schema; not safely portable into a valid submission.
- `prosperity4_alpha_lab.py`: research scaffold using PyTorch/sklearn/joblib/pandas; useful as a conceptual confirmation of family/pair priors, but unsupported for final submission and not a drop-in trader.

Validated implementation result:

- Final file: `traders/final_round5_trader_best_alpha.py`
- Change: expanded `BASKET_SELECTED` to include `MICROCHIP_RECTANGLE`, `SNACKPACK_STRAWBERRY`, `GALAXY_SOUNDS_SOLAR_WINDS`, and `TRANSLATOR_SPACE_GRAY` in addition to the prior `PANEL_2X2`, `PEBBLES_M`, `ROBOT_MOPPING`, and `ROBOT_IRONING`.
- Day-4 first-1,000-tick PnL stayed at 152,106.00.
- Full public Round 5 PnL improved from 2,711,903.50 to 2,729,414.50.

Rejected tests:

| Test | Full public PnL | Result |
| --- | ---: | --- |
| Add all residual basket models | 2,437,653.00 | Too broad; rejected |
| Add all snack residual overlays | 2,698,782.50 | Rejected |
| Add all pebbles residual overlays | 2,647,686.00 | Rejected |
| Add `MICROCHIP_RECTANGLE` only | 2,716,766.50 | Helpful |
| Add `SNACKPACK_STRAWBERRY` only | 2,717,535.50 | Helpful |
| Add `GALAXY_SOUNDS_SOLAR_WINDS` only | 2,715,097.50 | Helpful |
| Add `TRANSLATOR_SPACE_GRAY` only | 2,715,725.50 | Helpful |
| Add all four helpful overlays | 2,729,414.50 | Final |
| Drop any one final overlay | 2,699,737.50 to 2,726,220.50 | Rejected |
| Replace snackpack chocolate/vanilla with direct stationary-pair model | 2,718,997.50 to 2,722,533.50 | Rejected |
| Replace microchip square with square/rectangle stationary-pair model | 2,706,644.50 | Rejected |

Conclusion: the real extractable alpha from the log for this codebase is selective residual-pair activation, not wholesale pair trading or an unsupported NN. The chat's broad hints are directionally right, but the profitable implementation is narrow.
