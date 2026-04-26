from datamodel import Order, TradingState


class Trader:
    TARGET_PRODUCT = "HYDROGEL_PACK"
    LIMIT = 200
    K_MICRO = 1.0
    K_IMBALANCE = 1.5
    THRESHOLD = 0.2
    MAX_ORDER_CLIP = 20
    PASSIVE_OFFSET = 0

    def run(self, state: TradingState):
        orders_by_product = {product: [] for product in state.order_depths}
        depth = state.order_depths.get(self.TARGET_PRODUCT)
        if depth is not None:
            orders_by_product[self.TARGET_PRODUCT] = self.trade_hydrogel(
                depth,
                int(state.position.get(self.TARGET_PRODUCT, 0)),
            )
        return orders_by_product, 0, ""

    def trade_hydrogel(self, order_depth, position):
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
        microprice = (
            (best_ask * bid_vol_1 + best_bid * ask_vol_1) / top_total
            if top_total > 0
            else mid
        )

        bid_vol_sum = sum(max(0, int(volume)) for volume in buys.values())
        ask_vol_sum = sum(abs(int(volume)) for volume in sells.values())
        total_vol = bid_vol_sum + ask_vol_sum
        imbalance = (bid_vol_sum - ask_vol_sum) / total_vol if total_vol else 0.0

        fair = mid + self.K_MICRO * (microprice - mid) - self.K_IMBALANCE * imbalance
        threshold = self.THRESHOLD
        orders = []

        buy_room = max(0, self.LIMIT - position)
        sell_room = max(0, self.LIMIT + position)

        for ask_price, ask_volume in sorted(sells.items()):
            if buy_room <= 0:
                break
            available = abs(int(ask_volume))
            if available <= 0 or ask_price > fair - threshold:
                continue
            qty = min(available, buy_room, self.MAX_ORDER_CLIP)
            if qty > 0:
                orders.append(Order(self.TARGET_PRODUCT, int(ask_price), int(qty)))
                buy_room -= qty

        for bid_price, bid_volume in sorted(buys.items(), reverse=True):
            if sell_room <= 0:
                break
            available = max(0, int(bid_volume))
            if available <= 0 or bid_price < fair + threshold:
                continue
            qty = min(available, sell_room, self.MAX_ORDER_CLIP)
            if qty > 0:
                orders.append(Order(self.TARGET_PRODUCT, int(bid_price), -int(qty)))
                sell_room -= qty

        edge = fair - mid
        if edge > threshold and buy_room > 0:
            bid_price = self.passive_bid(best_bid, best_ask)
            if bid_price < best_ask:
                qty = min(self.MAX_ORDER_CLIP, buy_room)
                orders.append(Order(self.TARGET_PRODUCT, int(bid_price), int(qty)))
        elif edge < -threshold and sell_room > 0:
            ask_price = self.passive_ask(best_bid, best_ask)
            if ask_price > best_bid:
                qty = min(self.MAX_ORDER_CLIP, sell_room)
                orders.append(Order(self.TARGET_PRODUCT, int(ask_price), -int(qty)))

        return orders

    def passive_bid(self, best_bid, best_ask):
        if self.PASSIVE_OFFSET <= 0:
            return best_bid
        return min(best_ask - 1, best_bid + self.PASSIVE_OFFSET)

    def passive_ask(self, best_bid, best_ask):
        if self.PASSIVE_OFFSET <= 0:
            return best_ask
        return max(best_bid + 1, best_ask - self.PASSIVE_OFFSET)
