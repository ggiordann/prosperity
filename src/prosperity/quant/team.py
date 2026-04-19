from __future__ import annotations

import re
from pathlib import Path

from prosperity.backtester.datasets import resolve_dataset_argument
from prosperity.backtester.runner import BacktesterRunner, BacktestRequest
from prosperity.evaluation.metrics import compute_metrics
from prosperity.quant.models import StrategyEvaluation, StrategyIdea
from prosperity.settings import AppSettings

PRODUCT_RE = re.compile(r'"([A-Z][A-Z0-9_]+)"')


def is_strategy_file(path: Path) -> bool:
    if not path.exists() or path.suffix != ".py":
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return "class Trader" in text and "def run" in text


def extract_strategy_idea(path: Path) -> StrategyIdea:
    text = path.read_text(encoding="utf-8", errors="ignore")
    products = sorted({match.group(1) for match in PRODUCT_RE.finditer(text) if "_" in match.group(1)})
    tags: list[str] = []
    for pattern, tag in (
        ("imbalance", "imbalance"),
        ("micro", "microprice"),
        ("ema", "ema"),
        ("spread", "spread"),
        ("inventory", "inventory"),
        ("black_scholes", "black_scholes"),
        ("mean", "mean_reversion"),
        ("momentum", "momentum"),
    ):
        if pattern in text.lower():
            tags.append(tag)
    if not tags:
        tags.append("unclassified_strategy")
    summary = f"Strategy file with tags: {', '.join(tags)}."
    if products:
        summary += f" Products mentioned: {', '.join(products[:6])}."
    return StrategyIdea(
        source="git",
        path=str(path),
        name=path.stem,
        summary=summary,
        products=products,
        tags=tags,
        risk_notes=["Needs direct backtest plus ablation before promotion."],
    )


def evaluate_strategy_file(
    runner: BacktesterRunner,
    settings: AppSettings,
    path: Path,
    *,
    source: str,
) -> StrategyEvaluation:
    strategy_id = f"{source}:{path.stem}"
    if not is_strategy_file(path):
        return StrategyEvaluation(
            strategy_id=strategy_id,
            path=str(path),
            source=source,
            status="skipped",
            error="not a valid Prosperity Trader file",
        )
    try:
        result = runner.run(
            BacktestRequest(
                trader_path=str(path.resolve()),
                dataset=resolve_dataset_argument(settings.backtester.default_dataset),
                products_mode=settings.backtester.default_products_mode,
            )
        )
        metrics = compute_metrics(result.summary)
        return StrategyEvaluation(
            strategy_id=strategy_id,
            path=str(path),
            source=source,
            status="ok",
            total_pnl=float(metrics["total_pnl"]),
            worst_day_pnl=float(metrics["worst_day_pnl"]),
            own_trade_count=int(metrics["own_trade_count"]),
            per_day_pnl={str(key): float(value) for key, value in metrics["per_day_pnl"].items()},
            per_product_pnl=metrics["per_product_pnl"],
        )
    except Exception as exc:
        return StrategyEvaluation(
            strategy_id=strategy_id,
            path=str(path),
            source=source,
            status="error",
            error=str(exc),
        )

