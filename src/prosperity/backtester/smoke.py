from __future__ import annotations

from baselines.baseline_wrappers import get_baseline_path
from prosperity.backtester.datasets import resolve_dataset_argument
from prosperity.backtester.runner import BacktesterRunner, BacktestRequest


def smoke_baseline(runner: BacktesterRunner, baseline_name: str, dataset: str = "submission"):
    baseline_path = get_baseline_path(baseline_name)
    request = BacktestRequest(
        trader_path=str(baseline_path),
        dataset=resolve_dataset_argument(dataset),
    )
    return runner.run(request)
