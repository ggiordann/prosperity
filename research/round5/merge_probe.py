from datamodel import Order, TradingState
from typing import Dict, List
import importlib.util
import json
import os


def load_trader(name: str):
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(root, "traders", name)
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Trader


LatencyTrader = load_trader("r5_latency_trader.py")
BasketTrader = load_trader("r5_basket_trader.py")
RegimeTrader = load_trader("r5_regime_filter_trader.py")
TournamentTrader = load_trader("r5_strategy_tournament_trader.py")


CHOICES = {
    "latency": {},
    "basket_top3": {
        "PANEL_2X2": "basket",
        "PEBBLES_M": "basket",
        "ROBOT_MOPPING": "basket",
    },
    "basket_top4": {
        "PANEL_2X2": "basket",
        "PEBBLES_M": "basket",
        "ROBOT_MOPPING": "basket",
        "ROBOT_IRONING": "basket",
    },
    "basket_top4_regime3": {
        "PANEL_2X2": "basket",
        "PEBBLES_M": "basket",
        "ROBOT_MOPPING": "basket",
        "ROBOT_IRONING": "basket",
        "SLEEP_POD_SUEDE": "regime",
        "ROBOT_LAUNDRY": "regime",
        "PANEL_2X4": "regime",
    },
    "basket_top7": {
        "PANEL_2X2": "basket",
        "PEBBLES_M": "basket",
        "ROBOT_MOPPING": "basket",
        "ROBOT_IRONING": "basket",
        "MICROCHIP_RECTANGLE": "basket",
        "SNACKPACK_STRAWBERRY": "basket",
        "GALAXY_SOUNDS_SOLAR_WINDS": "basket",
    },
    "regime_stable": {
        "SLEEP_POD_SUEDE": "regime",
        "ROBOT_LAUNDRY": "regime",
        "PANEL_2X4": "regime",
    },
    "basket7_regime3": {
        "PANEL_2X2": "basket",
        "PEBBLES_M": "basket",
        "ROBOT_MOPPING": "basket",
        "ROBOT_IRONING": "basket",
        "MICROCHIP_RECTANGLE": "basket",
        "SNACKPACK_STRAWBERRY": "basket",
        "GALAXY_SOUNDS_SOLAR_WINDS": "basket",
        "SLEEP_POD_SUEDE": "regime",
        "ROBOT_LAUNDRY": "regime",
        "PANEL_2X4": "regime",
    },
    "all_product_best": {
        "PANEL_2X2": "basket",
        "PEBBLES_M": "basket",
        "ROBOT_MOPPING": "basket",
        "ROBOT_IRONING": "basket",
        "MICROCHIP_RECTANGLE": "basket",
        "SNACKPACK_STRAWBERRY": "basket",
        "GALAXY_SOUNDS_SOLAR_WINDS": "basket",
        "SLEEP_POD_SUEDE": "regime",
        "ROBOT_LAUNDRY": "regime",
        "PANEL_2X4": "regime",
        "PANEL_1X4": "tournament",
        "UV_VISOR_ORANGE": "tournament",
    },
}


class Trader:
    def __init__(self):
        self.latency = LatencyTrader()
        self.basket = BasketTrader()
        self.regime = RegimeTrader()
        self.tournament = TournamentTrader()
        self.choice = CHOICES.get(os.environ.get("MERGE_CHOICE", "latency"), {})

    def _run_one(self, state: TradingState, key: str, trader, data: dict):
        old = state.traderData
        state.traderData = data.get(key, "")
        orders, conversions, trader_data = trader.run(state)
        data[key] = trader_data
        state.traderData = old
        return orders

    def run(self, state: TradingState):
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        latency_orders = self._run_one(state, "latency", self.latency, data)
        needed = set(self.choice.values())
        basket_orders = self._run_one(state, "basket", self.basket, data) if "basket" in needed else {}
        regime_orders = self._run_one(state, "regime", self.regime, data) if "regime" in needed else {}
        tournament_orders = self._run_one(state, "tournament", self.tournament, data) if "tournament" in needed else {}

        result: Dict[str, List[Order]] = {}
        for product in state.order_depths:
            source = self.choice.get(product, "latency")
            if source == "basket":
                result[product] = basket_orders.get(product, [])
            elif source == "regime":
                result[product] = regime_orders.get(product, [])
            elif source == "tournament":
                result[product] = tournament_orders.get(product, [])
            else:
                result[product] = latency_orders.get(product, [])

        return result, 0, json.dumps(data, separators=(",", ":"))
