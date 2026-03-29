# Current State Audit

## Repository State At Start
- Flat root layout with two strategy files: `jinxingtest.py` and `newalgo.py`
- Tutorial CSVs in `imcdata/`
- Local Rust backtester in `prosperity_rust_backtester/`
- Large archive of public reference repos in `.research_repos/`
- Minimal original `README.md`

## Preserved Assets
- Root-level `jinxingtest.py` preserved untouched
- Root-level `newalgo.py` preserved as a current baseline artifact
- Raw CSVs in `imcdata/` preserved untouched
- `.research_repos/` treated as read-only quarantine input
- Rust backtester left in place and wrapped rather than replaced

## Migrations
- `baselines/legacy_jinxingtest.py` copied from root baseline
- `baselines/legacy_newalgo.py` copied from root baseline
- New package structure under `src/prosperity/`
- New `config/`, `docs/`, `data/`, `artifacts/`, `scripts/`, and `tests/`

## Assumptions
- The local repo is the primary operator workspace
- The bundled Rust backtester is the authoritative local simulator
- Public research repos are not safe direct codegen sources
- Live portal automation should remain disabled by default
- Local development uses Python 3.11+ and a manually installed Rust toolchain

## Known Unknowns
- Prosperity 4 round-specific product rules beyond currently available data will need future ingest
- Official site automation stability is unknown, so portal integration remains optional
- Some official docs are web-only today and may need manual export for richer local corpora
