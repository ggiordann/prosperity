# Operator Runbook

## Setup
1. Create a Python environment
2. `make setup`
3. Verify Rust backtester path in `config/settings.yaml`

## First Run
1. `prosperity audit`
2. `prosperity baselines list`
3. `prosperity baselines run --name legacy_newalgo --dataset submission`
4. `prosperity ingest all`
5. `prosperity loop once`

## Dashboard
- `prosperity dashboard serve`

## Submission Packaging
- `prosperity submission package --strategy-id <id>`

## Safety
- Portal upload is manual by default
- Browser automation requires explicit config enablement
- Review plagiarism and similarity reports before promotion
