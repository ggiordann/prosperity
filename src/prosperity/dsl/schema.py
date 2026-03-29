from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrategyMetadata(BaseModel):
    id: str
    name: str
    family: str
    source_refs: list[str] = Field(default_factory=list)
    parent_ids: list[str] = Field(default_factory=list)
    created_by_role: str
    confidence_notes: str = ""


class StrategyScope(BaseModel):
    products: list[str]
    round_assumptions: str = ""
    required_signals: list[str] = Field(default_factory=list)
    required_datasets: list[str] = Field(default_factory=list)


class PersistentStateField(BaseModel):
    name: str
    kind: str
    initial_value: Any


class FairValueComponent(BaseModel):
    kind: str
    weight: float = 1.0
    params: dict[str, Any] = Field(default_factory=dict)


class SignalComponent(BaseModel):
    name: str
    kind: str
    weight: float = 1.0
    params: dict[str, Any] = Field(default_factory=dict)


class TakingRule(BaseModel):
    enabled: bool = True
    min_edge: float = 1.0
    max_size: int = 10
    params: dict[str, Any] = Field(default_factory=dict)


class QuoteLayer(BaseModel):
    name: str
    side: str
    offset: float
    size: int
    join_best: bool = True
    product: str | None = None


class MarketMakingRule(BaseModel):
    enabled: bool = True
    base_half_spread: float = 2.0
    inventory_skew: float = 0.0
    layers: list[QuoteLayer] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class ExecutionPolicy(BaseModel):
    taking: TakingRule = Field(default_factory=TakingRule)
    market_making: MarketMakingRule = Field(default_factory=MarketMakingRule)
    clear_inventory_width: float = 0.0
    conversion_policy: dict[str, Any] = Field(default_factory=dict)


class RiskPolicy(BaseModel):
    per_product_position_caps: dict[str, int]
    dynamic_inventory_aversion: float = 0.0
    kill_switches: list[str] = Field(default_factory=list)
    unwind_rules: list[str] = Field(default_factory=list)
    turnover_throttles: dict[str, Any] = Field(default_factory=dict)
    max_aggressive_size: int = 10


class ParameterDef(BaseModel):
    name: str
    lower: float
    upper: float
    default: float
    mutation_scale: float = 0.1


class ExpectedEdge(BaseModel):
    narrative_hypothesis: str
    target_inefficiency: str
    expected_conditions: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)


class Explainability(BaseModel):
    crowded_motif_references: list[str] = Field(default_factory=list)
    anti_consensus_rationale: str = ""
    novelty_rationale: str = ""


class StrategySpec(BaseModel):
    metadata: StrategyMetadata
    scope: StrategyScope
    state: list[PersistentStateField] = Field(default_factory=list)
    fair_value_models: list[FairValueComponent] = Field(default_factory=list)
    signal_models: list[SignalComponent] = Field(default_factory=list)
    execution_policy: ExecutionPolicy
    risk_policy: RiskPolicy
    parameter_space: list[ParameterDef] = Field(default_factory=list)
    expected_edge: ExpectedEdge
    explainability: Explainability
