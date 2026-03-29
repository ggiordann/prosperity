from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeState:
    last_mid: float = 0.0
    fair_ema: float = 0.0
    volatility_ema: float = 0.0
    trade_pressure: float = 0.0
