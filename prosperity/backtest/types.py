from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from prosperity.datamodel import Listing, Observation, Order, OrderDepth, Trade


@dataclass
class MarketFrame:
    timestamp: int
    listings: Dict[str, Listing]
    order_depths: Dict[str, OrderDepth]
    market_trades: Dict[str, List[Trade]] = field(default_factory=dict)
    observations: Observation = field(default_factory=Observation)

    def copy(self) -> "MarketFrame":
        return MarketFrame(
            timestamp=self.timestamp,
            listings=dict(self.listings),
            order_depths={symbol: depth.copy() for symbol, depth in self.order_depths.items()},
            market_trades={
                symbol: [
                    Trade(
                        symbol=trade.symbol,
                        price=trade.price,
                        quantity=trade.quantity,
                        buyer=trade.buyer,
                        seller=trade.seller,
                        timestamp=trade.timestamp,
                    )
                    for trade in trades
                ]
                for symbol, trades in self.market_trades.items()
            },
            observations=Observation(
                plainValueObservations=dict(self.observations.plainValueObservations),
                conversionObservations=dict(self.observations.conversionObservations),
            ),
        )


@dataclass
class BacktestConfig:
    position_limits: Dict[str, int]
    submission_id: str = "SUBMISSION"
    fill_model: str = "queue_reactive"
    passive_fill_fraction: float = 0.5


@dataclass
class RejectedOrderSet:
    product: str
    reason: str
    orders: List[Order]


@dataclass
class RestingOrder:
    symbol: str
    price: int
    quantity: int


@dataclass
class StepSummary:
    timestamp: int
    cash: float
    positions: Dict[str, int]
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    own_trade_count: int
    rejected_orders: List[RejectedOrderSet] = field(default_factory=list)


@dataclass
class BacktestResult:
    step_summaries: List[StepSummary]
    fills: List[Trade]
    final_positions: Dict[str, int]
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    metrics: Dict[str, float]
    submitted_volume: int
    filled_volume: int

