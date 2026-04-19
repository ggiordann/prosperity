from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AutoResearchState(BaseModel):
    completed_cycles: int = 0
    champion_path: str | None = None
    best_score: float | None = None
    archive: list[dict[str, Any]] = Field(default_factory=list)


class ExperimentRecipe(BaseModel):
    name: str
    kind: str
    description: str
    changes: dict[str, Any] = Field(default_factory=dict)


class DayScore(BaseModel):
    label: str
    day: int
    pnl: float
    own_trades: int
    product_pnl: dict[str, float] = Field(default_factory=dict)


class ResearchScore(BaseModel):
    status: str
    score: float = 0.0
    train_mean: float = 0.0
    validation_mean: float = 0.0
    stress_mean: float = 0.0
    worst_day_pnl: float = 0.0
    stability: float = 0.0
    product_concentration: float = 0.0
    train_validation_gap: float = 0.0
    stress_gap: float = 0.0
    own_trade_count: int = 0
    day_scores: list[DayScore] = Field(default_factory=list)
    stress_day_scores: list[DayScore] = Field(default_factory=list)
    error: str | None = None


class ResearchExperiment(BaseModel):
    experiment_id: str
    recipe: ExperimentRecipe
    path: str
    source_path: str
    status: str
    score: ResearchScore | None = None
    decision: str = "pending"
    reason: str = ""


class AutoResearchCycleSummary(BaseModel):
    cycle_id: str
    session_name: str
    iteration: int
    dataset: str
    champion_path: str | None
    champion_score: ResearchScore | None
    experiments: list[ResearchExperiment]
    best_experiment: ResearchExperiment | None
    decision: str
    reason: str
    promoted_path: str | None = None
    report_path: str
    discord: dict[str, Any] | None = None
    created_at: str

