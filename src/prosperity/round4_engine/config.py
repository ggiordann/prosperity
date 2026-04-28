from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

VOUCHER_PRODUCTS: tuple[str, ...] = (
    "VEV_4000",
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
    "VEV_6000",
    "VEV_6500",
)


@dataclass(frozen=True)
class Round4DataConfig:
    data_dir: Path
    price_pattern: str = "prices_round_4_day_{day}.csv"
    trade_pattern: str = "trades_round_4_day_{day}.csv"
    train_days: tuple[int, ...] = (1,)
    validation_days: tuple[int, ...] = (2,)
    test_days: tuple[int, ...] = (3,)
    hydrogel_product: str = "HYDROGEL_PACK"
    underlying_product: str = "VELVETFRUIT_EXTRACT"
    voucher_products: tuple[str, ...] = VOUCHER_PRODUCTS
    top_book_levels: int = 3
    rolling_windows: tuple[int, ...] = (5, 10, 20)
    momentum_windows: tuple[int, ...] = (1, 5, 10)
    trader_alpha_horizon: int = 5
    trader_activity_window: int = 20
    expiry_days_at_round4: float = 4.0
    ticks_per_day: int = 10_000
    epsilon: float = 1e-9

    @property
    def all_days(self) -> tuple[int, ...]:
        return tuple(dict.fromkeys(self.train_days + self.validation_days + self.test_days))

    @property
    def traded_products(self) -> tuple[str, ...]:
        return (self.hydrogel_product, self.underlying_product, *self.voucher_products)

    def with_days(
        self,
        *,
        train_days: tuple[int, ...] | None = None,
        validation_days: tuple[int, ...] | None = None,
        test_days: tuple[int, ...] | None = None,
    ) -> Round4DataConfig:
        return replace(
            self,
            train_days=train_days if train_days is not None else self.train_days,
            validation_days=validation_days if validation_days is not None else self.validation_days,
            test_days=test_days if test_days is not None else self.test_days,
        )

    def to_json_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["data_dir"] = str(self.data_dir)
        return payload


@dataclass(frozen=True)
class StrategyWeights:
    mean_reversion: float = 0.85
    imbalance: float = 0.95
    trader: float = 0.55
    market_making_inventory: float = 0.20

    def to_json_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyConfig:
    weights: StrategyWeights = field(default_factory=StrategyWeights)
    mean_reversion_window: int = 20
    mean_reversion_vol_multiplier: float = 1.15
    mean_reversion_min_edge: float = 0.5
    imbalance_threshold: float = 0.18
    imbalance_momentum_window: int = 1
    trader_alpha_threshold: float = 0.08
    trader_reliability_floor: float = 0.28
    combined_signal_threshold: float = 0.82
    execution_cost_multiplier: float = 5.0
    voucher_intrinsic_edge: float = 0.4
    voucher_cross_edge: float = 0.45
    voucher_delta_hedge: float = 1.0
    directional_voucher_trading_enabled: bool = False
    market_making_base_spread: float = 2.5
    market_making_vol_multiplier: float = 0.85
    market_making_inventory_multiplier: float = 0.65
    market_making_min_spread: float = 2.0
    market_making_max_spread: float = 12.0
    market_making_enabled: bool = False

    def with_weights(self, weights: StrategyWeights) -> StrategyConfig:
        return replace(self, weights=weights)

    def to_json_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["weights"] = self.weights.to_json_dict()
        return payload


@dataclass(frozen=True)
class RiskConfig:
    position_limits: dict[str, int] = field(
        default_factory=lambda: {
            "HYDROGEL_PACK": 200,
            "VELVETFRUIT_EXTRACT": 200,
            "VEV_4000": 300,
            "VEV_4500": 300,
            "VEV_5000": 300,
            "VEV_5100": 300,
            "VEV_5200": 300,
            "VEV_5300": 300,
            "VEV_5400": 300,
            "VEV_5500": 300,
            "VEV_6000": 300,
            "VEV_6500": 300,
        }
    )
    market_order_size: int = 10
    voucher_order_size: int = 18
    market_making_quote_size: int = 2
    arbitrage_order_size: int = 16
    max_gross_exposure: float = 2_200_000.0
    max_product_notional: float = 1_250_000.0
    max_daily_loss: float = 30_000.0
    stop_loss: float = 45_000.0
    taker_fee_per_unit: float = 0.0
    maker_fee_per_unit: float = 0.0
    flatten_on_stop: bool = True

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EngineConfig:
    data: Round4DataConfig
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    output_dir: Path = Path("analysis/round4_engine_outputs")

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "data": self.data.to_json_dict(),
            "strategy": self.strategy.to_json_dict(),
            "risk": self.risk.to_json_dict(),
            "output_dir": str(self.output_dir),
        }
