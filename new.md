# Prosperity Research Platform

This repository is a local research platform for IMC Prosperity 4. It is built to support long-running, reproducible strategy research while still producing safe single-file Python submission artifacts for the competition.

The platform is opinionated around a few rules:
- official mechanics are the source of truth for environment rules
- public repos and writeups are hypothesis fuel, not copy-paste sources
- generated strategies come from a typed `StrategySpec` DSL plus internal primitives
- promotion favors robustness, novelty, and compliance, not just raw backtest PnL
- portal automation is optional and disabled by default

## What is in the repo

- `baselines/`: preserved team baselines and wrappers for running them through the platform
- `src/prosperity/`: ingestion, corpus, DSL, compilation, backtesting, evaluation, dashboard, and orchestration code
- `docs/`: architecture, runbook, source policy, DSL, dashboard, and loop docs
- `data/`: SQLite DB, corpora, processed summaries, caches, and local research state
- `artifacts/`: compiled strategies, run logs, reports, and packaged submissions
- `.research_repos/`: quarantined public research repos used for idea extraction only
- `prosperity_rust_backtester/`: local Rust backtester integration

## Quickstart

1. Create local config files:

```bash
cp config/settings.example.yaml config/settings.yaml
cp config/sources.example.yaml config/sources.yaml
cp config/loop.example.yaml config/loop.yaml
cp config/scoring.example.yaml config/scoring.yaml
cp .env.example .env
```

2. Install the platform:

```bash
make setup
```

3. Verify local wiring:

```bash
make smoke
python3 -m prosperity.cli backtest datasets
```

4. Run the preserved baseline through the Rust backtester:

```bash
make baseline
```

5. Ingest local sources and build the corpora:

```bash
make ingest
```

6. Run one research cycle:

```bash
make loop-once
```

7. Start the dashboard:

```bash
make dashboard
```

## Required local setup

You need:
- Python 3.11+
- Rust toolchain usable by the local backtester
- the local backtester available at `prosperity_rust_backtester/` or configured via `config/settings.yaml`

Optional:
- OpenAI API key for live idea-generation and summarization
- Playwright only if you intentionally enable browser automation

## Configuration

Primary configuration lives in:
- `config/settings.yaml`
- `config/sources.yaml`
- `config/loop.yaml`
- `config/scoring.yaml`

Environment overrides are supported through `PROSPERITY_*` variables. Important examples are:
- `PROSPERITY_SETTINGS_FILE`
- `OPENAI_API_KEY`
- `PROSPERITY_LOG_LEVEL`

Default behavior is conservative:
- live LLM requests are off unless enabled
- portal mode defaults to `manual`
- browser automation and live upload are disabled

## Core workflows

### Audit the repo

```bash
python3 -m prosperity.cli audit
```

### Run baselines

```bash
python3 -m prosperity.cli baselines list
python3 -m prosperity.cli baselines run legacy_newalgo --dataset submission
python3 -m prosperity.cli baselines run legacy_jinxingtest --dataset submission
```

### Generate, compile, and evaluate a candidate

```bash
python3 -m prosperity.cli ideas generate --count 2
python3 -m prosperity.cli loop once
```

`loop once` performs the platform pipeline end to end:
- ingest configured local sources
- update corpora and repo summaries
- generate `StrategySpec` candidates
- compile them into runnable Python modules
- run the Rust backtester
- score robustness, novelty, similarity, and plagiarism risk
- persist DB records and reports
- package promoted candidates into manual submission bundles

### Package a submission manually

```bash
python3 -m prosperity.cli submission package <strategy-id>
```

Submission bundles are written to `artifacts/submissions/<strategy-id>/` and include:
- `submission.py`
- `metadata.json`
- `explanation.md`
- `manifest.json`

### Run a portal dry-run

```bash
python3 -m prosperity.cli portal dry-run <strategy-id>
```

This keeps the workflow fail-safe:
- packages the submission bundle
- emits a Playwright dry-run payload
- emits an EquiRAG dry-run payload
- does not attempt a live upload

## Dashboard

The local Streamlit dashboard surfaces:
- recent runs
- candidate metrics
- lineage and family history
- corpus/source stats
- packaged submissions

Start it with:

```bash
make dashboard
```

## Testing and quality checks

```bash
make lint
make typecheck
make test
```

## Source policy

This repository has a strict source separation model:
- official competition mechanics: trusted for rules and environment behavior
- internal code and results: trusted for generation and promotion
- public repos and writeups: allowed for hypothesis generation only
- public source code: quarantined from direct code generation

Before promotion, candidates are checked against:
- `.research_repos/`
- prior generated strategies
- preserved baselines

See:
- `docs/compliance_and_source_policy.md`
- `docs/current_state_audit.md`
- `AGENTS.md`

## Optional portal automation

Manual packaging is the default and recommended path. Browser automation exists only as an optional adapter behind explicit config flags. Do not enable it casually.

See `docs/portal_adapters.md` before touching any live portal workflow.

## Useful docs

- `docs/architecture.md`
- `docs/operator_runbook.md`
- `docs/strategy_dsl.md`
- `docs/backtester_integration.md`
- `docs/dashboard.md`
- `docs/loop_runtime.md`

## Current state

The repo preserves the legacy strategy files at the root and also mirrors them into `baselines/` so the old workflow is still available while the new platform remains structured and reproducible.
