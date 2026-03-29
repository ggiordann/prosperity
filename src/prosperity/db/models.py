from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentRecord(BaseModel):
    document_id: str
    corpus_name: str
    title: str
    content: str
    metadata: dict[str, Any]
    embedding: list[float] = Field(default_factory=list)
    created_at: str


class StrategyRecord(BaseModel):
    strategy_id: str
    name: str
    family: str
    stage: str
    spec_json: str
    code_path: str | None = None
    submission_path: str | None = None
    created_at: str
    score: float | None = None
    notes: str | None = None


class RunRecord(BaseModel):
    run_id: str
    strategy_id: str | None = None
    dataset_id: str
    trader_path: str
    status: str
    final_pnl_total: float | None = None
    own_trade_count: int | None = None
    tick_count: int | None = None
    summary_json: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    created_at: str


class EvaluationRecord(BaseModel):
    evaluation_id: str
    strategy_id: str
    run_id: str
    score: float
    robustness_score: float | None = None
    novelty_score: float | None = None
    similarity_score: float | None = None
    plagiarism_score: float | None = None
    metrics_json: str
    created_at: str


class SimilarityRecord(BaseModel):
    similarity_id: str
    strategy_id: str
    neighbor_id: str
    neighbor_source: str
    modality: str
    score: float
    details_json: str
    created_at: str


class PromotionRecord(BaseModel):
    promotion_id: str
    strategy_id: str
    decision: str
    reason: str
    package_dir: str | None = None
    created_at: str


class ConversationCycleRecord(BaseModel):
    cycle_id: str
    session_name: str
    iteration: int
    champion_strategy_id: str | None = None
    promoted_strategy_id: str | None = None
    status: str
    summary_json: str
    created_at: str
    finished_at: str | None = None


class ConversationMessageRecord(BaseModel):
    message_id: str
    cycle_id: str
    session_name: str
    role: str
    content_json: str
    created_at: str


class MemoryNoteRecord(BaseModel):
    note_id: str
    session_name: str
    cycle_id: str | None = None
    strategy_id: str | None = None
    note_kind: str
    content: str
    created_at: str
