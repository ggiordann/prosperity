# AI Quant Loop

The `quant` loop is the research-first loop for finding alpha, not just tuning parameters.

## Command

Run one cycle:

```bash
python3 -m prosperity.cli quant cycle
```

Run continuously until `Ctrl-C`:

```bash
python3 -m prosperity.cli quant run
```

Run without backtests, useful for a fast scan:

```bash
python3 -m prosperity.cli quant cycle --no-backtests
```

## Cycle Logic

Each cycle starts from four inputs:

- active dataset and backtester from `config/settings.yaml`
- raw market CSVs
- current champion or seed strategy
- new git commits since the last quant cycle

The loop then runs these lanes:

- `git scout`: fetches/reads new commits, classifies changed files, and extracts teammate strategy files.
- `alpha miner`: scans order-book data for predictive signals such as imbalance, microprice delta, spread, lagged returns, and EMA reversion.
- `budget policy`: gives git ideas a real lane while capping them so they cannot dominate the whole search.
- `strategy builder`: turns top alpha signals into new structural strategy files under `artifacts/strategies/quant/`.
- `experiment judge`: backtests teammate strategies, generated alpha strategies, and the current champion.
- `memory/reporting`: writes state to `data/quant/` and reports to `artifacts/reports/quant/`.
- `discord log`: sends a compact cycle embed when `discord.enabled` is true, including champion, best candidate, top alpha signal, git scan, and system health.

## Git Commit Policy

Git ideas are treated as one source of signal, not the whole search.

- If teammate strategy code appears, the git budget is boosted.
- Git budget is capped by `quant.max_git_budget_fraction`.
- At least one direct git strategy test can run when new strategy commits exist.
- Git-tagged ideas can influence generated variants, but promotions still require evidence.

## Promotion Policy

By default, the quant loop does not overwrite `current_best_algo`.

To allow promotion from a cycle:

```bash
python3 -m prosperity.cli quant cycle --promote
```

A candidate must beat the champion by `quant.promote_min_improvement`. The default still favors safety: report first, promote only when explicitly enabled or configured.

## Outputs

- `data/quant/state.json`: last scanned git SHA and compact loop memory.
- `artifacts/reports/quant/*.md`: human-readable cycle reports.
- `artifacts/reports/quant/*.json`: full machine-readable cycle summaries.
- `artifacts/strategies/quant/*/*.py`: generated alpha strategy candidates.

Discord logs use `discord.channel_id` from `config/settings.yaml`. If a real promotion happens, the loop pings `discord.promote_ping_user_id`.

## Autoresearch Lane

For a stricter autonomous experiment harness, use `python3 -m prosperity.cli autoresearch cycle`. That lane keeps the evaluator locked, writes isolated strategy experiments, and promotes only after train/validation/stress gates clear. See `docs/autoresearch.md`.
