# Round 5 ML-Distilled Backtest Log

## Research Command

```bash
python3 research/round5/ml_alpha/ml_alpha_research.py
```

Artifacts written in `research/round5/ml_alpha/`:

- `feature_power.csv`
- `leadlag_edges.csv`
- `leadlag_distilled_candidates.csv`
- `basket_residuals.csv`
- `model_validation.csv`
- `feature_ablation.csv`
- `threshold_perturbation.csv`
- `distilled_params.json`
- `summary.json`

## Final Trader

File:

```bash
traders/r5_ml_distilled_trader.py
```

Size:

```text
17,872 bytes
```

Compile check:

```bash
python3 -m py_compile traders/r5_ml_distilled_trader.py
```

Allowed runtime imports only:

```text
datamodel, typing, json
```

## Final Backtest

The full three-day command can exceed the local shell timeout because this strategy carries lag histories through `traderData`, so verification was run day-by-day:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../traders/r5_ml_distilled_trader.py --dataset round5 --day 2 --artifact-mode none --products off
./scripts/cargo_local.sh run --release -- --trader ../traders/r5_ml_distilled_trader.py --dataset round5 --day 3 --artifact-mode none --products off
./scripts/cargo_local.sh run --release -- --trader ../traders/r5_ml_distilled_trader.py --dataset round5 --day 4 --artifact-mode none --products off
```

Results:

| Day | Ticks | Own trades | PnL |
| --- | ---: | ---: | ---: |
| D+2 | 10,000 | 1,116 | 789,912.50 |
| D+3 | 10,000 | 1,502 | 1,062,299.50 |
| D+4 | 10,000 | 1,275 | 705,074.50 |
| Total | 30,000 | 3,893 | 2,557,286.50 |

Top product PnL:

| Product | Total PnL |
| --- | ---: |
| `PEBBLES_XL` | 132,822.00 |
| `PEBBLES_L` | 94,924.00 |
| `MICROCHIP_SQUARE` | 88,572.00 |
| `PEBBLES_XS` | 83,327.00 |
| `MICROCHIP_OVAL` | 82,123.50 |
| `GALAXY_SOUNDS_SOLAR_FLAMES` | 77,184.00 |
| `UV_VISOR_MAGENTA` | 75,443.00 |
| `SLEEP_POD_LAMB_WOOL` | 70,886.00 |
| `SLEEP_POD_SUEDE` | 67,060.00 |
| `PEBBLES_S` | 65,861.00 |

## Baseline Comparison

Simple mean-reversion baseline command:

```bash
cd prosperity_rust_backtester
./scripts/cargo_local.sh run --release -- --trader ../research/round5/generated_traders/static_ztake_all.py --dataset round5 --artifact-mode none --products off
```

Baseline result:

| Day | Own trades | PnL |
| --- | ---: | ---: |
| D+2 | 893 | 507,979.50 |
| D+3 | 1,348 | 433,914.50 |
| D+4 | 844 | 114,424.50 |
| Total | 3,085 | 1,056,318.50 |

Distilled trader improvement over baseline:

```text
+1,500,968.00 PnL
2.42x baseline total
```

## Day-Split ML Validation

Direct ML score validation, using public D+2/D+3/D+4 as requested day 1/2/3:

| Split | Ridge IC | Sign accuracy | Spread-adjusted proxy |
| --- | ---: | ---: | ---: |
| Train D+2, test D+3/D+4 | 0.0111 | 48.9% | -225,831 |
| Train D+2/D+3, test D+4 | 0.0118 | 48.4% | -48,539 |
| Leave out D+2 | 0.0134 | 48.9% | -36,735 |
| Leave out D+3 | 0.0150 | 49.4% | -58,547 |
| Leave out D+4 | 0.0118 | 48.4% | -48,539 |

Conclusion: ML was useful for ranking features and finding lead-lag relationships, but direct next-return models did not survive spread-adjusted validation.

## Feature Ablation

Proxy validation over all day splits:

| Feature set | Mean IC | Sign accuracy | Proxy edge |
| --- | ---: | ---: | ---: |
| Local only | 0.0045 | 48.8% | -81,697.5 |
| No category | 0.0134 | 48.9% | -123,078.5 |
| No z-score | 0.0135 | 48.8% | -384,025.5 |
| No order book | 0.0090 | 48.8% | -388,604.0 |

## Threshold Perturbation

Direct ML crossing threshold sensitivity:

| Spread threshold multiplier | Trades | Proxy edge |
| --- | ---: | ---: |
| 0.50 | 244,404 | -1,175,518.5 |
| 0.75 | 156,609 | -686,786.0 |
| 1.00 | 103,846 | -418,189.5 |
| 1.25 | 70,983 | -258,644.5 |
| 1.50 | 50,410 | -165,332.5 |

Direct ML crossing was rejected at all tested thresholds. The submitted trader uses spread-adjusted fair-value rules instead.
