from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Dict, Iterable, List, Sequence, Tuple

from prosperity.backtest.fill_model import simulate_resting_fills
from prosperity.backtest.types import (
    BacktestConfig,
    BacktestResult,
    MarketFrame,
    RejectedOrderSet,
    RestingOrder,
    StepSummary,
)
from prosperity.datamodel import Observation, Order, OrderDepth, Trade, TradingState


@dataclass
class InventoryLedger:
    position: int = 0
    average_cost: float = 0.0
    realized_pnl: float = 0.0

    def transact(self, signed_quantity: int, price: int) -> None:
        if signed_quantity == 0:
            return

        if self.position == 0:
            self.position = signed_quantity
            self.average_cost = float(price)
            return

        if (self.position > 0 and signed_quantity > 0) or (self.position < 0 and signed_quantity < 0):
            total_qty = abs(self.position) + abs(signed_quantity)
            self.average_cost = (
                (self.average_cost * abs(self.position)) + (price * abs(signed_quantity))
            ) / total_qty
            self.position += signed_quantity
            return

        closing_quantity = min(abs(self.position), abs(signed_quantity))
        if self.position > 0:
            self.realized_pnl += (price - self.average_cost) * closing_quantity
        else:
            self.realized_pnl += (self.average_cost - price) * closing_quantity

        new_position = self.position + signed_quantity
        if new_position == 0:
            self.position = 0
            self.average_cost = 0.0
        elif (self.position > 0 and new_position > 0) or (self.position < 0 and new_position < 0):
            self.position = new_position
        else:
            self.position = new_position
            self.average_cost = float(price)

    def unrealized_pnl(self, mark_price: float) -> float:
        if self.position > 0:
            return (mark_price - self.average_cost) * self.position
        if self.position < 0:
            return (self.average_cost - mark_price) * abs(self.position)
        return 0.0


class BacktestEngine:
    def __init__(self, frames: Sequence[MarketFrame], config: BacktestConfig):
        if not frames:
            raise ValueError("Backtest requires at least one market frame.")
        self.frames = list(frames)
        self.config = config

    def run(self, trader) -> BacktestResult:
        positions: Dict[str, int] = defaultdict(int)
        ledgers: Dict[str, InventoryLedger] = defaultdict(InventoryLedger)
        own_trades_from_previous_step: Dict[str, List[Trade]] = defaultdict(list)
        trader_data = ""
        cash = 0.0
        fill_log: List[Trade] = []
        step_summaries: List[StepSummary] = []
        last_marks: Dict[str, float] = {}
        submitted_volume = 0
        filled_volume = 0

        known_products = set(self.config.position_limits)

        for index, frame in enumerate(self.frames):
            current_frame = frame.copy()
            known_products.update(current_frame.order_depths)
            known_products.update(current_frame.market_trades)

            state = TradingState(
                traderData=trader_data,
                timestamp=current_frame.timestamp,
                listings=current_frame.listings,
                order_depths={symbol: depth.copy() for symbol, depth in current_frame.order_depths.items()},
                own_trades={
                    product: list(own_trades_from_previous_step.get(product, []))
                    for product in known_products
                },
                market_trades={
                    product: list(current_frame.market_trades.get(product, []))
                    for product in known_products
                },
                position={product: positions.get(product, 0) for product in known_products},
                observations=current_frame.observations,
            )

            raw_output = trader.run(state)
            orders_by_product, conversions, next_trader_data = self._normalize_trader_output(raw_output)

            own_trades_this_step: Dict[str, List[Trade]] = defaultdict(list)
            rejected_orders: List[RejectedOrderSet] = []
            resting_orders: List[RestingOrder] = []

            for product, orders in orders_by_product.items():
                known_products.add(product)
                submitted_volume += sum(abs(order.quantity) for order in orders)
                if not self._orders_respect_position_limits(product, orders, positions):
                    rejected_orders.append(
                        RejectedOrderSet(
                            product=product,
                            reason="Aggregated order quantity would breach the product position limit.",
                            orders=orders,
                        )
                    )
                    continue

                depth = current_frame.order_depths.get(product, OrderDepth()).copy()
                immediate_fills, remaining_orders = self._match_immediately(
                    product=product,
                    orders=orders,
                    order_depth=depth,
                    timestamp=current_frame.timestamp,
                )
                current_frame.order_depths[product] = depth

                for trade in immediate_fills:
                    signed_quantity = self._signed_quantity(trade)
                    cash -= trade.price * signed_quantity
                    positions[trade.symbol] += signed_quantity
                    ledgers[trade.symbol].transact(signed_quantity, trade.price)
                    own_trades_this_step[trade.symbol].append(trade)
                    fill_log.append(trade)
                    filled_volume += trade.quantity

                resting_orders.extend(remaining_orders)

            if self.config.fill_model != "none" and resting_orders:
                next_frame = self.frames[index + 1].copy() if index + 1 < len(self.frames) else None
                passive_fills = simulate_resting_fills(
                    resting_orders=resting_orders,
                    current_depths=current_frame.order_depths,
                    next_depths=next_frame.order_depths if next_frame else None,
                    next_market_trades=next_frame.market_trades if next_frame else None,
                    timestamp=current_frame.timestamp,
                    submission_id=self.config.submission_id,
                    passive_fill_fraction=self.config.passive_fill_fraction,
                )
                for trade in passive_fills:
                    signed_quantity = self._signed_quantity(trade)
                    cash -= trade.price * signed_quantity
                    positions[trade.symbol] += signed_quantity
                    ledgers[trade.symbol].transact(signed_quantity, trade.price)
                    own_trades_this_step[trade.symbol].append(trade)
                    fill_log.append(trade)
                    filled_volume += trade.quantity

            if conversions:
                cash += self._apply_conversions(
                    conversions=conversions,
                    observations=current_frame.observations,
                    positions=positions,
                    ledgers=ledgers,
                )

            realized_pnl = sum(ledger.realized_pnl for ledger in ledgers.values())
            unrealized_pnl = 0.0
            for product in known_products:
                mark_price = self._mark_price(
                    product=product,
                    frame=current_frame,
                    last_marks=last_marks,
                )
                if mark_price is None:
                    continue
                last_marks[product] = mark_price
                unrealized_pnl += ledgers[product].unrealized_pnl(mark_price)

            total_pnl = cash + sum(
                positions[product] * last_marks.get(product, 0.0)
                for product in known_products
            )
            step_summaries.append(
                StepSummary(
                    timestamp=current_frame.timestamp,
                    cash=cash,
                    positions={product: positions.get(product, 0) for product in sorted(known_products)},
                    realized_pnl=realized_pnl,
                    unrealized_pnl=unrealized_pnl,
                    total_pnl=total_pnl,
                    own_trade_count=sum(len(trades) for trades in own_trades_this_step.values()),
                    rejected_orders=rejected_orders,
                )
            )

            own_trades_from_previous_step = own_trades_this_step
            trader_data = next_trader_data

        metrics = self._compute_metrics(step_summaries, submitted_volume, filled_volume)
        final_unrealized = step_summaries[-1].unrealized_pnl
        final_realized = step_summaries[-1].realized_pnl
        final_total = step_summaries[-1].total_pnl

        return BacktestResult(
            step_summaries=step_summaries,
            fills=fill_log,
            final_positions={product: positions.get(product, 0) for product in sorted(known_products)},
            total_pnl=final_total,
            realized_pnl=final_realized,
            unrealized_pnl=final_unrealized,
            metrics=metrics,
            submitted_volume=submitted_volume,
            filled_volume=filled_volume,
        )

    def _normalize_trader_output(self, raw_output) -> Tuple[Dict[str, List[Order]], object, str]:
        if isinstance(raw_output, tuple):
            if len(raw_output) == 3:
                orders_by_product, conversions, trader_data = raw_output
                return orders_by_product, conversions, trader_data
            if len(raw_output) == 2:
                orders_by_product, conversions = raw_output
                return orders_by_product, conversions, ""
            raise ValueError("Unsupported trader output tuple length.")
        if isinstance(raw_output, dict):
            return raw_output, 0, ""
        raise TypeError("Trader output must be a dict or a tuple.")

    def _orders_respect_position_limits(
        self,
        product: str,
        orders: Iterable[Order],
        positions: Dict[str, int],
    ) -> bool:
        position_limit = self.config.position_limits.get(product)
        if position_limit is None:
            return True

        current_position = positions.get(product, 0)
        total_buy_quantity = sum(order.quantity for order in orders if order.quantity > 0)
        total_sell_quantity = -sum(order.quantity for order in orders if order.quantity < 0)
        return (
            current_position + total_buy_quantity <= position_limit
            and current_position - total_sell_quantity >= -position_limit
        )

    def _match_immediately(
        self,
        product: str,
        orders: Iterable[Order],
        order_depth: OrderDepth,
        timestamp: int,
    ) -> Tuple[List[Trade], List[RestingOrder]]:
        fills: List[Trade] = []
        resting_orders: List[RestingOrder] = []

        for order in orders:
            if order.quantity == 0:
                continue

            if order.quantity > 0:
                remaining = order.quantity
                for ask_price in sorted(list(order_depth.sell_orders)):
                    ask_volume = -order_depth.sell_orders[ask_price]
                    if remaining <= 0 or ask_volume <= 0:
                        continue
                    if order.price < ask_price:
                        break
                    fill_quantity = min(remaining, ask_volume)
                    remaining -= fill_quantity
                    order_depth.sell_orders[ask_price] += fill_quantity
                    fills.append(
                        Trade(
                            symbol=product,
                            price=ask_price,
                            quantity=fill_quantity,
                            buyer=self.config.submission_id,
                            seller="",
                            timestamp=timestamp,
                        )
                    )
                    if order_depth.sell_orders[ask_price] == 0:
                        del order_depth.sell_orders[ask_price]
                if remaining > 0:
                    resting_orders.append(RestingOrder(symbol=product, price=order.price, quantity=remaining))
            else:
                remaining = -order.quantity
                for bid_price in sorted(list(order_depth.buy_orders), reverse=True):
                    bid_volume = order_depth.buy_orders[bid_price]
                    if remaining <= 0 or bid_volume <= 0:
                        continue
                    if order.price > bid_price:
                        break
                    fill_quantity = min(remaining, bid_volume)
                    remaining -= fill_quantity
                    order_depth.buy_orders[bid_price] -= fill_quantity
                    fills.append(
                        Trade(
                            symbol=product,
                            price=bid_price,
                            quantity=fill_quantity,
                            buyer="",
                            seller=self.config.submission_id,
                            timestamp=timestamp,
                        )
                    )
                    if order_depth.buy_orders[bid_price] == 0:
                        del order_depth.buy_orders[bid_price]
                if remaining > 0:
                    resting_orders.append(RestingOrder(symbol=product, price=order.price, quantity=-remaining))

        return fills, resting_orders

    def _apply_conversions(
        self,
        conversions,
        observations: Observation,
        positions: Dict[str, int],
        ledgers: Dict[str, InventoryLedger],
    ) -> float:
        cash_delta = 0.0
        if not observations.conversionObservations:
            return cash_delta

        if isinstance(conversions, int):
            if len(observations.conversionObservations) != 1:
                raise ValueError(
                    "Integer conversion requests are only supported when a single convertible product exists."
                )
            product = next(iter(observations.conversionObservations))
            conversion_map = {product: conversions}
        elif isinstance(conversions, dict):
            conversion_map = conversions
        else:
            raise TypeError("Conversions must be an int or a dict.")

        for product, requested_quantity in conversion_map.items():
            if requested_quantity is None or requested_quantity <= 0:
                continue
            observation = observations.conversionObservations.get(product)
            if observation is None:
                continue

            held_position = positions.get(product, 0)
            if held_position > 0:
                quantity = min(requested_quantity, held_position)
                conversion_price = (
                    observation.bidPrice - observation.transportFees - observation.exportTariff
                )
                signed_quantity = -quantity
                cash_delta += conversion_price * quantity
            elif held_position < 0:
                quantity = min(requested_quantity, abs(held_position))
                conversion_price = (
                    observation.askPrice + observation.transportFees + observation.importTariff
                )
                signed_quantity = quantity
                cash_delta -= conversion_price * quantity
            else:
                continue

            positions[product] += signed_quantity
            ledgers[product].transact(signed_quantity, int(round(conversion_price)))

        return cash_delta

    def _mark_price(
        self,
        product: str,
        frame: MarketFrame,
        last_marks: Dict[str, float],
    ) -> float | None:
        depth = frame.order_depths.get(product)
        if depth:
            best_bid = max(depth.buy_orders) if depth.buy_orders else None
            best_ask = min(depth.sell_orders) if depth.sell_orders else None
            if best_bid is not None and best_ask is not None:
                return (best_bid + best_ask) / 2.0
            if best_bid is not None:
                return float(best_bid)
            if best_ask is not None:
                return float(best_ask)

        trades = frame.market_trades.get(product, [])
        if trades:
            return float(trades[-1].price)

        return last_marks.get(product)

    def _signed_quantity(self, trade: Trade) -> int:
        if trade.buyer == self.config.submission_id:
            return trade.quantity
        if trade.seller == self.config.submission_id:
            return -trade.quantity
        raise ValueError("Trade does not belong to the configured submission id.")

    def _compute_metrics(
        self,
        step_summaries: Sequence[StepSummary],
        submitted_volume: int,
        filled_volume: int,
    ) -> Dict[str, float]:
        equity_curve = [step.total_pnl for step in step_summaries]
        returns = [equity_curve[index] - equity_curve[index - 1] for index in range(1, len(equity_curve))]
        avg_return = mean(returns) if returns else 0.0
        return_vol = pstdev(returns) if len(returns) > 1 else 0.0
        sharpe_like = (avg_return / return_vol * math.sqrt(len(returns))) if return_vol > 0 else 0.0

        running_peak = float("-inf")
        max_drawdown = 0.0
        for pnl in equity_curve:
            running_peak = max(running_peak, pnl)
            max_drawdown = max(max_drawdown, running_peak - pnl)

        return {
            "max_drawdown": max_drawdown,
            "mean_step_pnl_change": avg_return,
            "pnl_volatility": return_vol,
            "sharpe_like": sharpe_like,
            "fill_ratio": (filled_volume / submitted_volume) if submitted_volume else 0.0,
        }
