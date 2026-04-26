from datamodel import Order, TradingState


class Trader:
    def run(self, state: TradingState):
        orders = {}

        if "EMERALDS" in state.order_depths:
            orders["EMERALDS"] = [Order("EMERALDS", 100000, 20)]

        if "TOMATOES" in state.order_depths:
            orders["TOMATOES"] = [Order("TOMATOES", 1, -20)]

        return orders, 0, ""
