# AutoResearch Loop

`autoresearch` is the safer autonomous experiment lane. It borrows the core shape from Andrej Karpathy's `autoresearch`: keep the evaluator locked, generate experiments in isolated files, run them, archive everything, and only promote when the evidence clears a gate.

## Why It Exists

The normal loop can drift into "tweak the same knobs forever." `autoresearch` is stricter:

- It starts from the current champion strategy.
- It creates fresh experiment files under `artifacts/strategies/autoresearch/`.
- It mutates only the strategy file, never the evaluator.
- It scores every candidate on train days, validation days, and stressed validation days.
- It writes a full report and state archive before touching `current_best_algo`.

## Commands

Run one research cycle:

```bash
python3 -m prosperity.cli autoresearch cycle
```

Run continuously until `Ctrl-C`:

```bash
python3 -m prosperity.cli autoresearch run
```

Run every 5 minutes in GitHub Actions:

```text
.github/workflows/autoresearch.yml
```

See `docs/github_actions_autoresearch.md`.

Run more experiments in one cycle:

```bash
python3 -m prosperity.cli autoresearch cycle --experiments 12
```

Promote only if the locked gate clears:

```bash
python3 -m prosperity.cli autoresearch cycle --promote
```

Disable Discord for a local smoke test:

```bash
python3 -m prosperity.cli autoresearch cycle --experiments 2 --no-discord
```

## Current Gate

The candidate is not promoted just because public backtest PnL is flashy. It must beat the champion on the locked composite score:

- validation PnL
- stressed validation PnL
- worst day PnL
- train PnL
- train-vs-validation gap
- stress gap
- product concentration

The default promotion requirements live in `config/settings.example.yaml` under `autoresearch`.

## Outputs

- `data/autoresearch/state.json`: compact memory of past cycles.
- `artifacts/strategies/autoresearch/*/*.py`: generated candidate strategies.
- `current_best_algo/current_best_V{N}.py`: written only when promotion is enabled and the gate clears.

Human-readable cycle detail is Discord-first by default. The loop does not write markdown/json report files unless `autoresearch.write_reports` is set to `true`.

## Discord

If `discord.enabled` and `autoresearch.send_discord` are true, each cycle sends a compact embed with:

- current champion score
- best experiment score
- every experiment recipe, code file, parameter/structural changes, gate reason, and train/validation/stress stats
- decision and reason

If an actual promotion happens, it pings `discord.promote_ping_user_id`.

## Important Mental Model

This is not magic proof that a strategy will win the hidden round. It is a disciplined research harness. The whole point is to make the agent explore structural ideas while punishing obvious public-data overfit before anything becomes the active best file.
