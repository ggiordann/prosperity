from __future__ import annotations

import json
from dataclasses import dataclass, field
from json import JSONEncoder
from typing import Dict, List, Optional

try:
    import jsonpickle
except ImportError:  # pragma: no cover - local fallback for lightweight setups
    class _JsonPickleFallback:
        @staticmethod
        def encode(value):
            return json.dumps(value, default=lambda o: o.__dict__, sort_keys=True)

    jsonpickle = _JsonPickleFallback()

Time = int
Symbol = str
Product = str
Position = int
UserId = str
ObservationValue = int


@dataclass
class Listing:
    symbol: Symbol
    product: Product
    denomination: Product


@dataclass
class ConversionObservation:
    bidPrice: float
    askPrice: float
    transportFees: float
    exportTariff: float
    importTariff: float
    sunlight: float
    humidity: float


@dataclass
class Observation:
    plainValueObservations: Dict[Product, ObservationValue] = field(default_factory=dict)
    conversionObservations: Dict[Product, ConversionObservation] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            "(plainValueObservations: "
            + jsonpickle.encode(self.plainValueObservations)
            + ", conversionObservations: "
            + jsonpickle.encode(self.conversionObservations)
            + ")"
        )


@dataclass
class Order:
    symbol: Symbol
    price: int
    quantity: int

    def __str__(self) -> str:
        return f"({self.symbol}, {self.price}, {self.quantity})"

    def __repr__(self) -> str:
        return str(self)


@dataclass
class OrderDepth:
    buy_orders: Dict[int, int] = field(default_factory=dict)
    sell_orders: Dict[int, int] = field(default_factory=dict)

    def copy(self) -> "OrderDepth":
        return OrderDepth(buy_orders=dict(self.buy_orders), sell_orders=dict(self.sell_orders))


@dataclass
class Trade:
    symbol: Symbol
    price: int
    quantity: int
    buyer: Optional[UserId] = None
    seller: Optional[UserId] = None
    timestamp: int = 0

    def __str__(self) -> str:
        return (
            f"({self.symbol}, {self.buyer or ''} << {self.seller or ''}, "
            f"{self.price}, {self.quantity}, {self.timestamp})"
        )

    def __repr__(self) -> str:
        return str(self)


@dataclass
class TradingState:
    traderData: str
    timestamp: Time
    listings: Dict[Symbol, Listing]
    order_depths: Dict[Symbol, OrderDepth]
    own_trades: Dict[Symbol, List[Trade]]
    market_trades: Dict[Symbol, List[Trade]]
    position: Dict[Product, Position]
    observations: Observation

    def toJSON(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True)


class ProsperityEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__
