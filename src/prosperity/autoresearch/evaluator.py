from __future__ import annotations

from math import fsum
from pathlib import Path
from statistics import mean, pstdev

from prosperity.autoresearch.models import DayScore, ResearchScore
from prosperity.backtester.datasets import resolve_dataset_argument
from prosperity.backtester.runner import BacktesterRunner, BacktestRequest
from prosperity.settings import AppSettings


def evaluate_locked_strategy(
    runner: BacktesterRunner,
    settings: AppSettings,
    path: Path,
) -> ResearchScore:
    """Run the sealed train/validation/stress evaluator.

    This is intentionally separate from candidate generation: experiments can mutate strategy
    files, but they cannot change how they are scored.
    """
    try:
        train_scores = [
            _run_day(runner, settings, path, day, label=f"train:{day}", stressed=False)
            for day in settings.autoresearch.train_days
        ]
        validation_scores = [
            _run_day(runner, settings, path, day, label=f"validation:{day}", stressed=False)
            for day in settings.autoresearch.validation_days
        ]
        stress_scores = [
            _run_day(runner, settings, path, day, label=f"stress:{day}", stressed=True)
            for day in settings.autoresearch.validation_days
        ]
    except Exception as exc:
        return ResearchScore(status="error", error=str(exc))

    all_scores = [*train_scores, *validation_scores]
    train_mean = _mean([score.pnl for score in train_scores])
    validation_mean = _mean([score.pnl for score in validation_scores])
    stress_mean = _mean([score.pnl for score in stress_scores])
    worst_day = min((score.pnl for score in [*all_scores, *stress_scores]), default=0.0)
    stability = _stability([score.pnl for score in all_scores])
    concentration = _product_concentration(all_scores)
    train_validation_gap = max(0.0, train_mean - validation_mean)
    stress_gap = max(0.0, validation_mean - stress_mean)
    own_trade_count = sum(score.own_trades for score in [*all_scores, *stress_scores])

    raw_score = (
        0.35 * validation_mean
        + 0.30 * stress_mean
        + 0.20 * worst_day
        + 0.15 * train_mean
    )
    raw_score -= 0.20 * train_validation_gap
    raw_score -= 0.15 * stress_gap
    raw_score -= _concentration_penalty(raw_score, concentration, settings.autoresearch.max_product_concentration)

    return ResearchScore(
        status="ok",
        score=raw_score,
        train_mean=train_mean,
        validation_mean=validation_mean,
        stress_mean=stress_mean,
        worst_day_pnl=worst_day,
        stability=stability,
        product_concentration=concentration,
        train_validation_gap=train_validation_gap,
        stress_gap=stress_gap,
        own_trade_count=own_trade_count,
        day_scores=all_scores,
        stress_day_scores=stress_scores,
    )


def candidate_clears_gate(
    candidate: ResearchScore,
    champion: ResearchScore,
    settings: AppSettings,
) -> tuple[bool, str]:
    if candidate.status != "ok":
        return False, candidate.error or "candidate evaluation failed"
    if champion.status != "ok":
        return True, "champion evaluation failed, candidate is valid"

    score_delta = candidate.score - champion.score
    validation_delta = candidate.validation_mean - champion.validation_mean
    if score_delta < settings.autoresearch.promote_min_score_delta:
        return (
            False,
            f"score delta {score_delta:.2f} below gate {settings.autoresearch.promote_min_score_delta:.2f}",
        )
    if validation_delta < settings.autoresearch.promote_min_validation_delta:
        return (
            False,
            f"validation delta {validation_delta:.2f} below gate {settings.autoresearch.promote_min_validation_delta:.2f}",
        )
    if candidate.train_validation_gap > settings.autoresearch.max_train_validation_gap:
        return (
            False,
            f"train-validation gap {candidate.train_validation_gap:.2f} exceeds cap",
        )
    if candidate.product_concentration > settings.autoresearch.max_product_concentration:
        return (
            False,
            f"product concentration {candidate.product_concentration:.3f} exceeds cap",
        )
    return True, f"score delta {score_delta:.2f}, validation delta {validation_delta:.2f}"


def _run_day(
    runner: BacktesterRunner,
    settings: AppSettings,
    path: Path,
    day: int,
    *,
    label: str,
    stressed: bool,
) -> DayScore:
    request = BacktestRequest(
        trader_path=str(path.resolve()),
        dataset=resolve_dataset_argument(settings.backtester.default_dataset),
        day=day,
        products_mode=settings.backtester.default_products_mode,
    )
    if stressed:
        request.trade_match_mode = settings.autoresearch.stress_trade_match_mode
        request.queue_penetration = settings.autoresearch.stress_queue_penetration
        request.price_slippage_bps = settings.autoresearch.stress_price_slippage_bps
    result = runner.run(request)
    row = result.summary.day_results[0]
    product_pnl = {
        contribution.product: float(next(iter(contribution.values.values()), 0.0))
        for contribution in result.summary.product_contributions
    }
    return DayScore(
        label=label,
        day=day,
        pnl=float(row.final_pnl),
        own_trades=int(row.own_trades),
        product_pnl=product_pnl,
    )


def _mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def _stability(values: list[float]) -> float:
    if len(values) < 2:
        return 1.0
    baseline = max(abs(_mean(values)), 1.0)
    return max(0.0, min(1.0, 1.0 - (pstdev(values) / baseline)))


def _product_concentration(day_scores: list[DayScore]) -> float:
    totals: dict[str, float] = {}
    for day in day_scores:
        for product, pnl in day.product_pnl.items():
            totals[product] = totals.get(product, 0.0) + pnl
    gross = fsum(abs(value) for value in totals.values())
    if gross <= 0.0:
        return 0.0
    return max(abs(value) for value in totals.values()) / gross


def _concentration_penalty(score: float, concentration: float, max_concentration: float) -> float:
    excess = max(0.0, concentration - max_concentration)
    if excess <= 0.0:
        return 0.0
    return abs(score) * min(0.50, excess * 1.5)

