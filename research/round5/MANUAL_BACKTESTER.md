# Round 5 Manual Backtester

This is a fee-aware sanity checker for the Ignith manual challenge. It does not know IMC's hidden return ranges; it tests candidate entries against the subjective ranges in `manual_scenarios.json`.

## Compare Portfolios

```bash
python3 research/round5/manual_backtester.py compare --trials 200000
```

This runs every configured Volcanic-incense scenario plus a weighted mixture and prints mean PnL, quantiles, fees, budget used, and probability of positive PnL.

To run one scenario:

```bash
python3 research/round5/manual_backtester.py compare --scenario volcanic_momentum --trials 200000
```

## Optimize Expected Value

```bash
python3 research/round5/manual_backtester.py optimize --scenario weighted
```

The optimizer uses exact dynamic programming over integer percentages. It maximizes expected PnL under:

```text
PnL = budget * allocation * signed_return - budget * allocation^2
```

Because this is an expected-value optimizer, it is only as good as the return means implied by the configured ranges. Use it as a sensitivity tool, not as truth.

## Robust Search

```bash
python3 research/round5/manual_backtester.py robust --worlds 10000 --candidate-worlds 1000
```

This is the closest analogue to the Round 4 manual approach:

1. Sample many plausible hidden-return worlds from the configured ranges.
2. Build EV-optimal integer portfolios for those worlds.
3. Evaluate all unique candidates across a fresh set of sampled worlds.
4. Rank them by a robust score:

```text
score = mean_pnl - risk_aversion * stdev - regret_aversion * average_oracle_regret
```

Useful variants:

```bash
python3 research/round5/manual_backtester.py robust --criterion mean
python3 research/round5/manual_backtester.py robust --criterion p10
python3 research/round5/manual_backtester.py robust --scenario volcanic_momentum
```

## Editing Assumptions

Change the `low`, `mode`, and `high` values in `manual_scenarios.json` to test different reads. A raw return of `0.20` means +20%; a raw return of `-0.60` means -60%.
