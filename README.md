# Prosperity Local Research Platform

This repository is a local research and iteration platform for IMC Prosperity strategies.

It supports:
- preserved baseline strategies
- deterministic `StrategySpec` compilation
- Rust backtester integration
- evaluation, robustness, novelty, and similarity checks
- local submission packaging
- a persistent conversation-style strategy loop that can run once, `n` times, or forever until `Ctrl-C`

## Setup

From the repo root:

```bash
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml
cp config/sources.example.yaml config/sources.yaml
cp config/loop.example.yaml config/loop.yaml
cp config/scoring.example.yaml config/scoring.yaml
make setup
```

Make sure:
- your OpenAI key is in [`.env`](/Users/giordanmasen/Desktop/prosperity/.env) if you want live LLM-guided turns
- the Rust backtester is present at [`prosperity_rust_backtester/`](/Users/giordanmasen/Desktop/prosperity/prosperity_rust_backtester)

## Core Commands

Audit the repo:

```bash
python3 -m prosperity.cli audit
```

Run the preserved baseline:

```bash
python3 -m prosperity.cli baselines run legacy_newalgo --dataset submission
```

Run one generic pipeline cycle:

```bash
python3 -m prosperity.cli loop once
```

Run one conversation-style research cycle:

```bash
python3 -m prosperity.cli loop cycle
```

Run the conversation loop forever until `Ctrl-C`:

```bash
python3 -m prosperity.cli loop run
```

Run exactly `n` conversation cycles:

```bash
python3 -m prosperity.cli loop run --cycles 10
```

Run with a pause between cycles:

```bash
python3 -m prosperity.cli loop run --cycles 10 --sleep-seconds 30
```

Start the dashboard:

```bash
python3 -m prosperity.cli dashboard serve
```

## What the Conversation Loop Does

Each cycle:
1. refreshes source ingestion
2. loads the current champion strategy
3. writes a structured strategist turn
4. writes a structured critic turn
5. mutates the champion into several nearby candidates
6. compiles and backtests those candidates
7. writes postmortems
8. promotes a challenger only if it cleanly beats the current champion

The seed champion for this loop is anchored on [submission_candidate.py](/Users/giordanmasen/Desktop/prosperity/submission_candidate.py) through an internal compiled family, so the search starts around the current best-known local behavior instead of from weak generic seeds.

## Useful Make Targets

```bash
make smoke
make test
make lint
make typecheck
make baseline
make loop-once
make loop-run
make dashboard
```
