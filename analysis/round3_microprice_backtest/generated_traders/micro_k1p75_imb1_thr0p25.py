import math
from datamodel import Order, TradingState


class Trader:
    TARGET_PRODUCTS = ['HYDROGEL_PACK', 'VELVETFRUIT_EXTRACT']
    LIMITS = {'HYDROGEL_PACK': 200, 'VELVETFRUIT_EXTRACT': 200}
    K_MICRO = 1.75
    K_IMBALANCE = 1.0
    THRESHOLD = 0.25
    MAX_TAKE_SIZE = 40
    MAX_QUOTE_SIZE = 10

    def run(self, state: TradingState):
        orders_by_product = {product: [] for product in state.order_depths}
        for product in self.TARGET_PRODUCTS:
            depth = state.order_depths.get(product)
            if depth is None:
                continue
            orders_by_product[product] = self.trade_product(
                product,
                depth,
                int(state.position.get(product, 0)),
            )
        return orders_by_product, 0, ""

    def trade_product(self, product, order_depth, position):
        buys = order_depth.buy_orders
        sells = order_depth.sell_orders
        if not buys or not sells:
            return []

        best_bid = max(buys)
        best_ask = min(sells)
        if best_bid >= best_ask:
            return []

        mid = 0.5 * (best_bid + best_ask)
        bid_vol_1 = max(0, int(buys.get(best_bid, 0)))
        ask_vol_1 = abs(int(sells.get(best_ask, 0)))
        top_total = bid_vol_1 + ask_vol_1
        if top_total > 0:
            microprice = (best_ask * bid_vol_1 + best_bid * ask_vol_1) / top_total
        else:
            microprice = mid

        bid_vol_sum = sum(max(0, int(volume)) for volume in buys.values())
        ask_vol_sum = sum(abs(int(volume)) for volume in sells.values())
        total_vol = bid_vol_sum + ask_vol_sum
        imbalance = (bid_vol_sum - ask_vol_sum) / total_vol if total_vol else 0.0

        micro_edge = microprice - mid
        fair = mid + self.K_MICRO * micro_edge - self.K_IMBALANCE * imbalance
        threshold = self.THRESHOLD
        orders = []

        limit = self.LIMITS[product]
        buy_room = max(0, limit - position)
        sell_room = max(0, limit + position)

        for ask_price, ask_volume in sorted(sells.items()):
            if buy_room <= 0:
                break
            ask_qty = abs(int(ask_volume))
            if ask_qty <= 0 or ask_price > fair - threshold:
                continue
            qty = min(ask_qty, buy_room, self.MAX_TAKE_SIZE)
            if qty > 0:
                orders.append(Order(product, int(ask_price), int(qty)))
                buy_room -= qty

        for bid_price, bid_volume in sorted(buys.items(), reverse=True):
            if sell_room <= 0:
                break
            bid_qty = max(0, int(bid_volume))
            if bid_qty <= 0 or bid_price < fair + threshold:
                continue
            qty = min(bid_qty, sell_room, self.MAX_TAKE_SIZE)
            if qty > 0:
                orders.append(Order(product, int(bid_price), -int(qty)))
                sell_room -= qty

        edge = fair - mid
        if edge > threshold and buy_room > 0:
            bid_price = self.directional_bid(best_bid, best_ask, fair, threshold)
            if bid_price < best_ask:
                orders.append(Order(product, int(bid_price), int(min(self.MAX_QUOTE_SIZE, buy_room))))
        elif edge < -threshold and sell_room > 0:
            ask_price = self.directional_ask(best_bid, best_ask, fair, threshold)
            if ask_price > best_bid:
                orders.append(Order(product, int(ask_price), -int(min(self.MAX_QUOTE_SIZE, sell_room))))

        return orders

    @staticmethod
    def directional_bid(best_bid, best_ask, fair, threshold):
        if best_ask - best_bid > 1:
            inside = best_bid + 1
        else:
            inside = best_bid
        fair_bid = int(math.floor(fair - threshold))
        return max(best_bid, min(best_ask - 1, max(inside, fair_bid)))

    @staticmethod
    def directional_ask(best_bid, best_ask, fair, threshold):
        if best_ask - best_bid > 1:
            inside = best_ask - 1
        else:
            inside = best_ask
        fair_ask = int(math.ceil(fair + threshold))
        return min(best_ask, max(best_bid + 1, min(inside, fair_ask)))
