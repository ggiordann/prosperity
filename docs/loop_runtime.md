# Loop Runtime

The loop has two modes:
- `loop once`: a single deterministic research cycle
- `loop daemon`: repeated cycles with locking and crash-safe status tracking

High-level cycle:
1. ingest sources
2. rebuild corpora
3. summarize quarantined public motifs
4. generate or mutate specs
5. compile and smoke test
6. backtest
7. evaluate and score
8. check novelty / similarity / plagiarism
9. promote and package
10. persist postmortems
