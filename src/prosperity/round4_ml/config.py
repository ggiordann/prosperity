from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DataConfig:
    """Inputs and feature engineering settings for the Round 4 data set."""

    data_dir: Path
    train_days: tuple[int, ...] = (1,)
    validation_days: tuple[int, ...] = (2,)
    test_days: tuple[int, ...] = (3,)
    price_pattern: str = "prices_round_4_day_{day}.csv"
    trade_pattern: str = "trades_round_4_day_{day}.csv"
    underlying_product: str = "VELVETFRUIT_EXTRACT"
    hydrogel_products: tuple[str, ...] = ("HYDROGEL", "HYDROGEL_PACK")
    voucher_prefix: str = "VEV"
    top_book_levels: int = 3
    rolling_windows: tuple[int, ...] = (5, 10, 20)
    momentum_windows: tuple[int, ...] = (1, 5, 10)
    price_horizons: tuple[int, ...] = (1, 2, 3, 4, 5)
    voucher_fair_horizon: int = 5
    realized_vol_horizon: int = 20
    sequence_length: int = 32
    top_traders: int = 16
    trader_activity_window: int = 20
    expiry_days: float = 5.0
    epsilon: float = 1e-8

    @property
    def all_days(self) -> tuple[int, ...]:
        return tuple(dict.fromkeys(self.train_days + self.validation_days + self.test_days))

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["data_dir"] = str(self.data_dir)
        return data


@dataclass(frozen=True)
class TrainingConfig:
    """PyTorch training settings."""

    output_dir: Path
    encoder_type: str = "lstm"
    hidden_size: int = 96
    dense_size: int = 128
    num_layers: int = 2
    dropout: float = 0.15
    batch_size: int = 512
    epochs: int = 30
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    patience: int = 6
    min_delta: float = 1e-5
    num_workers: int = 0
    max_train_samples: int | None = None
    max_eval_samples: int | None = None
    seed: int = 7
    device: str = "auto"
    price_loss_weight: float = 1.0
    voucher_loss_weight: float = 0.8
    volatility_loss_weight: float = 0.25
    gradient_clip_norm: float = 1.0

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["output_dir"] = str(self.output_dir)
        return data


@dataclass(frozen=True)
class BacktestConfig:
    """Signal conversion, risk, and execution settings."""

    position_limits: dict[str, int] = field(
        default_factory=lambda: {
            "HYDROGEL": 100,
            "HYDROGEL_PACK": 100,
            "VELVETFRUIT_EXTRACT": 100,
            "VEV_4000": 200,
            "VEV_4500": 200,
            "VEV_5000": 200,
            "VEV_5100": 200,
            "VEV_5200": 200,
            "VEV_5300": 200,
            "VEV_5400": 200,
            "VEV_5500": 200,
            "VEV_6000": 200,
            "VEV_6500": 200,
        }
    )
    asset_order_size: int = 8
    voucher_order_size: int = 12
    min_edge: float = 0.25
    asset_vol_threshold_multiplier: float = 0.35
    voucher_vol_threshold_multiplier: float = 0.08
    spread_threshold_multiplier: float = 0.65
    max_gross_exposure: float = 1_500_000.0
    stop_loss: float = 25_000.0
    risk_aversion: float = 0.15
    flatten_on_stop: bool = True
    maker_fee_per_unit: float = 0.0
    taker_fee_per_unit: float = 0.0

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)
