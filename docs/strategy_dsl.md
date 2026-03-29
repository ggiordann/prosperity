# Strategy DSL

`StrategySpec` is the canonical structured representation of a candidate strategy.

It contains:
- metadata and lineage
- product scope and assumptions
- persistent state requirements
- fair value components
- signal components
- execution policy
- risk policy
- tunable parameter space
- expected edge narrative
- explainability and anti-crowding notes

The compiler turns `StrategySpec` into a runnable `Trader` module using only internal templates and supported primitives.
