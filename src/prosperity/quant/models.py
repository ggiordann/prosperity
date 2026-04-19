from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QuantState(BaseModel):
    last_git_sha: str | None = None
    completed_cycles: int = 0
    accepted_ideas: list[dict[str, Any]] = Field(default_factory=list)
    rejected_ideas: list[dict[str, Any]] = Field(default_factory=list)


class ChangedFile(BaseModel):
    path: str
    status: str
    category: str
    exists: bool


class GitCommitInsight(BaseModel):
    sha: str
    subject: str
    author: str
    changed_files: list[ChangedFile]


class GitScoutResult(BaseModel):
    base_sha: str | None
    target_sha: str | None
    commits: list[GitCommitInsight]
    candidate_strategy_files: list[str]
    fetched: bool
    error: str | None = None


class AlphaSignal(BaseModel):
    product: str
    feature: str
    horizon: int
    correlation: float
    directional_accuracy: float
    observations: int
    score: float
    interpretation: str


class AlphaMiningResult(BaseModel):
    dataset: str
    products: list[str]
    top_signals: list[AlphaSignal]
    rows_analyzed: int
    notes: list[str] = Field(default_factory=list)


class StrategyIdea(BaseModel):
    source: str
    path: str | None = None
    name: str
    summary: str
    products: list[str]
    tags: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class StrategyEvaluation(BaseModel):
    strategy_id: str
    path: str
    source: str
    status: str
    total_pnl: float | None = None
    worst_day_pnl: float | None = None
    own_trade_count: int | None = None
    per_day_pnl: dict[str, float] = Field(default_factory=dict)
    per_product_pnl: dict[str, dict[str, float]] = Field(default_factory=dict)
    error: str | None = None


class BudgetPolicy(BaseModel):
    git_fraction: float
    raw_alpha_fraction: float
    champion_fraction: float
    structural_fraction: float
    direct_git_tests: int
    git_variant_tests: int
    alpha_strategy_tests: int
    reason: str


class QuantCycleSummary(BaseModel):
    cycle_id: str
    session_name: str
    iteration: int
    dataset: str
    git: GitScoutResult
    budget: BudgetPolicy
    alpha: AlphaMiningResult
    team_ideas: list[StrategyIdea]
    team_evaluations: list[StrategyEvaluation]
    generated_evaluations: list[StrategyEvaluation]
    champion: StrategyEvaluation | None = None
    best_candidate: StrategyEvaluation | None = None
    decision: str
    reason: str
    report_path: str
    discord: dict[str, Any] | None = None
    created_at: str
