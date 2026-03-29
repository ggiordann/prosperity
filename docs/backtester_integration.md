# Backtester Integration

The platform wraps the local Rust backtester through subprocess calls.

Supported features:
- path discovery from config or local defaults
- baseline and candidate runs
- tutorial and explicit dataset runs
- fast mode and persisted mode
- parsed summaries and product tables
- artifact path capture from `runs/`

The backtester remains the source of truth for local simulated evaluation.
