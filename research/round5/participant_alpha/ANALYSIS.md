# Round 5 Participant And Order-Flow Alpha

## Executive Finding

Round 5 public trade CSVs contain `buyer` and `seller` columns, but every value is blank across all public days. There is no direct counterparty-ID alpha to mine.

The useful market-participant-style signal is therefore not a named participant. It is predictable public order-flow and quote-response structure:

- same-category mid-price lead-lag effects are real and executable;
- direct product/category trade-flow overlays are statistically visible but do not improve Rust PnL after spread and existing lead-lag signals;
- future-trade prediction is mostly a synchronized public-tape artifact, not a reusable participant identity;
- passive quote placement is fill-sensitive by one tick, but the public book does not endogenously react to our quotes in the backtester.

Final implementation: `traders/r5_participant_trader.py`.

## Counterparty Fields

| day | trade rows | nonblank buyers | nonblank sellers | products |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 11,090 | 0 | 0 | 50 |
| 3 | 12,320 | 0 | 0 | 50 |
| 4 | 11,975 | 0 | 0 | 50 |

Conclusion: recurring named participants, per-participant directional edge, participant future-return prediction, and participant future-trade prediction are unavailable in Round 5 public data.

## Aggregate Tape Flow

I inferred aggressor side from trade price versus the contemporaneous best bid/ask and mid:

- buy-aggressor prints: `17,425`
- sell-aggressor prints: `17,960`
- unclassified prints: `0`

The tape is highly synchronized by product groups rather than participant names. Trade timestamps often fire for complete categories:

| timestamp product set | count |
| --- | ---: |
| eight non-Microchip/non-Pebble categories | 707 |
| Pebbles only | 617 |
| Microchips only | 546 |
| nine categories excluding Microchips | 15 |
| Microchips + Pebbles | 12 |
| nine categories excluding Pebbles | 11 |

This explains why many raw cross-product flow correlations are duplicated across unrelated products: the print scheduler itself is shared.

## Strongest Self-Flow Signals

Stable on all three public days, using inferred signed volume and future mid return:

| flow product | horizon | corr | signed edge | class |
| --- | ---: | ---: | ---: | --- |
| `SLEEP_POD_LAMB_WOOL` | 500 | 0.0957 | +25.33 | informed/momentum |
| `PEBBLES_S` | 200 | -0.0945 | -22.22 | mean-reversion triggering |
| `PEBBLES_M` | 500 | 0.0608 | +21.18 | informed/momentum |
| `PANEL_1X2` | 500 | 0.0751 | +16.61 | informed/momentum |
| `OXYGEN_SHAKE_CHOCOLATE` | 500 | -0.0887 | -16.50 | mean-reversion triggering |
| `OXYGEN_SHAKE_EVENING_BREATH` | 500 | -0.0825 | -15.55 | mean-reversion triggering |
| `GALAXY_SOUNDS_SOLAR_FLAMES` | 500 | 0.0678 | +11.12 | informed/momentum |
| `UV_VISOR_AMBER` | 500 | -0.0510 | -9.58 | mean-reversion triggering |

These are too slow and too spread-sensitive to add directly on top of the final strategy. Existing product/category flow overlays peaked below the validated baseline and were rejected.

## Cross-Product Flow

The strongest apparent cross-product flow signals are mostly not genuine cross-product alpha. Example: many unrelated products appear to predict `SLEEP_POD_LAMB_WOOL` at horizon 500 with identical statistics because those products share trade timestamps and signed print patterns.

Accepted cross-product structure is instead same-category mid lead-lag, already encoded in the trader. Strongest retained examples:

- `PEBBLES_XS <- PEBBLES_XL`, lags 200 and 500
- `PEBBLES_L <- PEBBLES_S`, lag 500
- `UV_VISOR_MAGENTA <- UV_VISOR_AMBER`, lag 500
- `PANEL_1X2 <- PANEL_2X2`, lag 200
- `MICROCHIP_OVAL <- MICROCHIP_RECTANGLE`, lags 1 and 2
- `SLEEP_POD_LAMB_WOOL <- SLEEP_POD_COTTON`, lag 500
- `TRANSLATOR_GRAPHITE_MIST <- TRANSLATOR_VOID_BLUE`, lag 500
- `GALAXY_SOUNDS_SOLAR_FLAMES <- GALAXY_SOUNDS_BLACK_HOLES`, lag 500

Cross-category flow was rejected. It did not survive overfit controls once synchronized tape artifacts were accounted for.

## Future Trade Prediction

Signed flow does weakly predict future signed flow, but the effect size is tiny. The top stable future-flow edges had about `0.57` lots of signed edge over 500 ticks, far below a robust execution threshold. Classification: noisy/scheduler-driven, not informed flow.

## Basket Residual Flow

Category-sum residual extremes mean-revert mechanically at longer horizons, especially at 500 ticks, but direct basket trading was weaker than lead-lag fair-value shifts.

The Pebbles fixed-sum identity is structurally real, but the residual standard deviation is only about `2.8` ticks in the dedicated Pebbles research. That is usually smaller than visible spread, so the trader exploits Pebbles indirectly through lagged category reactions rather than direct residual crossing.

## Order Book Behaviour

Repeated quote signatures exist but are moderate, not hard-coded single books. Top signature shares:

| product | top signature share | avg spread | avg top depth |
| --- | ---: | ---: | ---: |
| `ROBOT_IRONING` | 14.68% | 6.39 | 16.70 |
| `MICROCHIP_CIRCLE` | 11.13% | 8.26 | 13.52 |
| `MICROCHIP_TRIANGLE` | 9.25% | 8.64 | 12.88 |
| `ROBOT_MOPPING` | 7.71% | 7.97 | 14.13 |
| `ROBOT_DISHES` | 7.63% | 7.35 | 15.23 |

Quote shifts after price changes are mostly weak. The clearest one-tick mean-reversion books:

| product | return ac1 |
| --- | ---: |
| `ROBOT_DISHES` | -0.232 |
| `ROBOT_IRONING` | -0.125 |
| `OXYGEN_SHAKE_EVENING_BREATH` | -0.123 |
| `OXYGEN_SHAKE_CHOCOLATE` | -0.089 |

The Rust backtester does not feed our passive quotes into future public books, so "bot response to our quote" is only observed through fill/queue mechanics. A one-tick quote perturbation can matter for fills: the Panel research found "improve one tick inside spread" dropped Panel PnL to `89,845` versus selected `201,600`, so one-tick aggressiveness can flip economics even without named bots.

## Classification

| entity | classification | action |
| --- | --- | --- |
| named participants | absent | no direct participant alpha |
| slow positive self-flow products | informed/momentum, but decays slowly | use only if spread-adjusted; direct overlay rejected |
| negative self-flow products | mean-reversion triggering | fade statistically, but direct overlay rejected |
| future-flow tape | noisy/scheduler-driven | reject |
| same-category mid lead-lag | informed order-flow/quote response proxy | trade |
| passive quote fills | liquidity providing with fill sensitivity | quote only with edge and limit 10 |

## Strategy Decision

The final trader follows the validated same-category lead-lag/order-flow proxy and rejects direct public tape flow. It uses:

- static/current-mid fair values;
- causal rolling mid histories;
- lagged same-category fair-value shifts;
- spread-adjusted take thresholds and passive quote edges;
- selective depth walking only where tested;
- position limit `10` on every product;
- no participant IDs, no future data, no timestamp hard-coding, no external files.

