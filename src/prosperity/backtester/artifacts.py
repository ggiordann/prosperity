from __future__ import annotations

from pathlib import Path

from prosperity.backtester.parser import BacktestSummary


def collect_run_dirs(summary: BacktestSummary, backtester_root: Path) -> list[Path]:
    run_dirs: list[Path] = []
    for row in summary.day_results:
        candidate = backtester_root / row.run_dir
        if candidate.exists():
            run_dirs.append(candidate)
    return run_dirs
