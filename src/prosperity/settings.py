from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from prosperity.paths import RepoPaths


class BacktesterSettings(BaseModel):
    path: str = "prosperity_rust_backtester"
    default_dataset: str = "round4"
    default_products_mode: str = "summary"


class LLMSettings(BaseModel):
    strategist_model: str = "gpt-5.4"
    critic_model: str = "gpt-5.4-mini"
    summarizer_model: str = "gpt-5.4-mini"
    embeddings_model: str = "text-embedding-3-small"
    provider: str = "openai"
    daily_budget_usd: float = 50.0
    allow_live_requests: bool = False


class DashboardSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8501


class PortalSettings(BaseModel):
    mode: str = "manual"
    enable_browser_automation: bool = False
    enable_live_upload: bool = False


class DiscordSettings(BaseModel):
    enabled: bool = False
    channel_id: str | None = None
    bot_token: str | None = None
    promote_ping_user_id: str | None = None
    application_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    api_base_url: str = "https://discord.com/api/v10"


class ConversationSettings(BaseModel):
    session_name: str = "codex-conversation"
    max_candidates_per_cycle: int = 18
    max_full_evaluations_per_cycle: int = 8
    frontier_size: int = 8
    exploit_candidates: int = 2
    explore_candidates: int = 2
    structural_candidates: int = 2
    family_jump_candidates: int = 2
    family_lab_candidates: int = 2
    expert_builder_candidates: int = 4
    survivor_tune_candidates: int = 2
    family_jump_interval: int = 3
    plateau_lookback_cycles: int = 6
    plateau_repeat_threshold: int = 2
    promote_min_improvement: float = 5.0
    shadow_promotion_max_pnl_gap: float = 20.0
    shadow_promotion_min_robustness_delta: float = 0.05
    shadow_promotion_min_validation_delta: float = 0.08
    stale_champion_cycles: int = 12
    adaptive_lookback_cycles: int = 12
    max_memory_notes: int = 12
    default_sleep_seconds: int = 0
    use_llm_roles: bool = True
    seed_strategy_path: str = "baselines/round1_256418.py"
    fallback_family: str = "round1_256418_alpha"
    tutorial_validation_days: list[int] = Field(default_factory=lambda: [-1, 0, 1])
    screening_tutorial_days: list[int] = Field(default_factory=lambda: [-1, 0, 1])


class QuantSettings(BaseModel):
    session_name: str = "quant-main"
    state_path: str = "data/quant/state.json"
    report_dir: str = "artifacts/reports/quant"
    artifacts_dir: str = "artifacts/strategies/quant"
    fetch_remote: bool = True
    initial_git_scan_commits: int = 3
    max_changed_files_per_cycle: int = 40
    max_git_strategy_tests: int = 3
    max_alpha_strategies: int = 4
    top_alpha_features: int = 10
    alpha_horizons: list[int] = Field(default_factory=lambda: [1, 5, 20])
    git_budget_fraction: float = 0.15
    max_git_budget_fraction: float = 0.30
    raw_alpha_budget_fraction: float = 0.40
    champion_budget_fraction: float = 0.25
    structural_budget_fraction: float = 0.20
    min_git_direct_tests: int = 1
    min_git_variant_tests: int = 1
    champion_strategy_path: str | None = None
    auto_promote: bool = False
    promote_min_improvement: float = 5.0


class AutoResearchSettings(BaseModel):
    session_name: str = "autoresearch-main"
    state_path: str = "data/autoresearch/state.json"
    report_dir: str = "artifacts/reports/autoresearch"
    artifacts_dir: str = "artifacts/strategies/autoresearch"
    target_strategy_path: str | None = None
    experiments_per_cycle: int = 6
    train_days: list[int] = Field(default_factory=lambda: [-1, 0])
    validation_days: list[int] = Field(default_factory=lambda: [1])
    stress_queue_penetration: float = 0.35
    stress_price_slippage_bps: float = 2.0
    stress_trade_match_mode: str = "strict"
    promote_min_score_delta: float = 100.0
    promote_min_validation_delta: float = 0.0
    max_train_validation_gap: float = 50_000.0
    max_product_concentration: float = 0.92
    auto_promote: bool = False
    send_discord: bool = True
    write_reports: bool = False


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROSPERITY_",
        env_nested_delimiter="__",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    project_name: str = "prosperity-research-platform"
    repo_root: str = "."
    data_dir: str = "data"
    artifacts_dir: str = "artifacts"
    db_path: str = "data/db/prosperity.sqlite3"
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    backtester: BacktesterSettings = Field(default_factory=BacktesterSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)
    portal: PortalSettings = Field(default_factory=PortalSettings)
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    conversation: ConversationSettings = Field(default_factory=ConversationSettings)
    quant: QuantSettings = Field(default_factory=QuantSettings)
    autoresearch: AutoResearchSettings = Field(default_factory=AutoResearchSettings)


def _load_yaml_file(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def load_settings(
    paths: RepoPaths | None = None,
    settings_file: Path | None = None,
) -> AppSettings:
    repo_paths = paths or RepoPaths.discover()
    env_settings_file = os.environ.get("PROSPERITY_SETTINGS_FILE")
    if settings_file is not None:
        config_path = settings_file
    elif env_settings_file:
        config_path = Path(env_settings_file)
    else:
        config_path = repo_paths.config / "settings.yaml"
    yaml_values = _load_yaml_file(config_path)
    settings = AppSettings(**yaml_values)
    return settings
