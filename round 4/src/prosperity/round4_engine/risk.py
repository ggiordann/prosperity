from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from prosperity.round4_engine.config import RiskConfig


@dataclass
class PortfolioState:
    cash: float = 0.0
    positions: dict[str, int] = field(default_factory=dict)
    realized_pnl: float = 0.0
    stopped: bool = False
    daily_start_equity: dict[int, float] = field(default_factory=dict)
    peak_equity: float = 0.0

    def position(self, product: str) -> int:
        return int(self.positions.get(product, 0))

    def set_position(self, product: str, quantity: int) -> None:
        if quantity:
            self.positions[product] = int(quantity)
        elif product in self.positions:
            del self.positions[product]


class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config

    def limit_for(self, product: str) -> int:
        return int(self.config.position_limits.get(product, 100))

    def clip_quantity(
        self,
        product: str,
        side: int,
        requested_quantity: int,
        portfolio: PortfolioState,
        mid_prices: dict[str, float],
        price: float,
    ) -> int:
        if requested_quantity <= 0 or side == 0 or not np.isfinite(price):
            return 0

        position = portfolio.position(product)
        limit = self.limit_for(product)
        capacity = limit - position if side > 0 else limit + position
        quantity = min(int(requested_quantity), max(0, int(capacity)))
        if quantity <= 0:
            return 0

        projected_positions = dict(portfolio.positions)
        projected_positions[product] = position + side * quantity
        if abs(projected_positions[product]) > limit:
            return 0

        projected_gross = self.gross_exposure(projected_positions, mid_prices)
        current_gross = self.gross_exposure(portfolio.positions, mid_prices)
        if projected_gross > self.config.max_gross_exposure and projected_gross > current_gross:
            return 0

        product_notional = abs(projected_positions[product]) * abs(float(mid_prices.get(product, price)))
        if product_notional > self.config.max_product_notional:
            current_notional = abs(position) * abs(float(mid_prices.get(product, price)))
            if product_notional > current_notional:
                return 0
        return quantity

    def update_stop_state(self, day: int, equity: float, portfolio: PortfolioState) -> None:
        if day not in portfolio.daily_start_equity:
            portfolio.daily_start_equity[day] = equity
        portfolio.peak_equity = max(portfolio.peak_equity, equity)
        drawdown = portfolio.peak_equity - equity
        daily_loss = portfolio.daily_start_equity[day] - equity
        if drawdown >= self.config.stop_loss or daily_loss >= self.config.max_daily_loss:
            portfolio.stopped = True

    @staticmethod
    def mark_to_market(cash: float, positions: dict[str, int], mid_prices: dict[str, float]) -> float:
        equity = cash
        for product, position in positions.items():
            mid = mid_prices.get(product)
            if mid is not None and np.isfinite(mid):
                equity += position * float(mid)
        return float(equity)

    @staticmethod
    def gross_exposure(positions: dict[str, int], mid_prices: dict[str, float]) -> float:
        gross = 0.0
        for product, position in positions.items():
            mid = mid_prices.get(product)
            if mid is not None and np.isfinite(mid):
                gross += abs(position) * abs(float(mid))
        return float(gross)
