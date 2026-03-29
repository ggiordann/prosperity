# Architecture

The platform is structured as a deterministic local research loop:

1. Ingest trusted and untrusted sources into separate corpora
2. Summarize public code into motif notes under source-policy controls
3. Generate structured `StrategySpec` candidates
4. Compile candidates into runnable strategy modules and single-file submission artifacts
5. Backtest through the Rust simulator
6. Evaluate PnL, robustness, novelty, similarity, and plagiarism risk
7. Promote approved candidates and package manual submission bundles
8. Persist runs, prompts, lineage, and postmortems for future cycles

The compiler is deterministic. Models may influence strategy ideas, but the submission artifact itself is generated from internal specs and templates.
