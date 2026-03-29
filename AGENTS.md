# Repository Instructions

## Purpose
This repository is a local research platform for IMC Prosperity 4. It supports:
- preserving hand-written baseline strategies
- ingesting official notes, local datasets, and quarantined public research repos
- generating structured `StrategySpec` ideas
- compiling deterministic strategy modules and single-file submission artifacts
- backtesting through the local Rust backtester
- scoring robustness, novelty, and similarity
- packaging manual submission bundles

## Layout
- `baselines/`: preserved team strategies and baseline registry
- `src/prosperity/`: package code for ingestion, generation, compilation, evaluation, dashboard, and orchestration
- `config/`: example configuration files
- `docs/`: architecture, runbooks, policy, and operator notes
- `data/`: local corpora, caches, SQLite DB, and processed summaries
- `artifacts/`: compiled strategies, reports, runs, and submission bundles
- `.research_repos/`: read-only quarantine zone for public reference repos
- `prosperity_rust_backtester/`: local Rust backtester dependency

## Source Policy
- Treat `.research_repos/` as read-only.
- Public repos and writeups are hypothesis fuel only.
- Never copy public code into generated submission artifacts.
- Generated strategies must come from internal specs, templates, and primitives.
- Run the plagiarism guard before promotion or packaging.

## Secrets
- Never commit API keys or cookies.
- Load secrets only from `.env` or untracked config files.
- Portal automation is disabled by default and must remain opt-in.

## Working Conventions
- Prefer `rg` for search.
- Preserve baseline files in the repo root; do not delete or rewrite them casually.
- Keep generated submission files single-file and dependency-light.
- Persist experiment metadata and artifacts for reproducibility.

## Commands
- Setup: `make setup`
- Lint: `make lint`
- Typecheck: `make typecheck`
- Tests: `make test`
- Smoke baseline: `make baseline`
- One loop cycle: `make loop-once`
- Conversation loop until `Ctrl-C`: `make loop-run` or `python3 -m prosperity.cli loop run`
- Conversation loop for `n` cycles: `python3 -m prosperity.cli loop run --cycles 10`
- Single conversation cycle: `python3 -m prosperity.cli loop cycle`
- Dashboard: `make dashboard`

## Done Means
- Baselines run through the new wrapper.
- A `StrategySpec` can be generated, compiled, backtested, evaluated, and stored.
- Similarity / novelty / plagiarism checks run.
- A manual submission bundle can be packaged.
- `prosperity loop once` completes locally on repo data.
- `prosperity loop run` can run continuously until interrupted, or for a bounded number of cycles.
- The dashboard opens and shows persisted data.
