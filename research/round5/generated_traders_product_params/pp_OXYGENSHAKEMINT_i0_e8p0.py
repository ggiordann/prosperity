from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json

class Trader:
    LIMIT = 10
    Q = 20
    P = "OXYGEN_SHAKE_MINT"
    IMP = 0
    EDGE = 8.0
    MICRO = False

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        hist = data.get("c", [])
        mids = {}
        for p, d in state.order_depths.items():
            if d.buy_orders and d.sell_orders:
                mids[p] = (max(d.buy_orders) + min(d.sell_orders)) / 2.0
        if "MICROCHIP_CIRCLE" in mids:
            hist.append(mids["MICROCHIP_CIRCLE"])
            hist = hist[-110:]
        for p, d in state.order_depths.items():
            if p != self.P or not d.buy_orders or not d.sell_orders:
                result[p] = []
                continue
            fair = mids[p]
            take = 10**9
            edge = self.EDGE
            if self.MICRO and p == "MICROCHIP_OVAL" and len(hist) > 50:
                fair += 1.25 * 0.067 * (hist[-1] - hist[-51])
                take = 5.5
                edge = 1.0
            elif self.MICRO and p == "MICROCHIP_SQUARE" and len(hist) > 100:
                fair += 0.75 * 0.138 * (hist[-1] - hist[-101])
                take = 6.0
                edge = 0.5
            result[p] = self.trade(p, d, int(state.position.get(p, 0)), fair, take, edge)
        return result, 0, json.dumps({"c": hist}, separators=(",", ":"))

    def trade(self, p: str, d: OrderDepth, pos: int, fair: float, take: float, edge: float) -> List[Order]:
        bb = max(d.buy_orders)
        ba = min(d.sell_orders)
        bc = max(0, self.LIMIT - pos)
        sc = max(0, self.LIMIT + pos)
        out: List[Order] = []
        if bc > 0 and ba <= fair - take:
            q = min(bc, self.Q, -int(d.sell_orders[ba]))
            if q > 0:
                out.append(Order(p, ba, q))
                bc -= q
        if sc > 0 and bb >= fair + take:
            q = min(sc, self.Q, int(d.buy_orders[bb]))
            if q > 0:
                out.append(Order(p, bb, -q))
                sc -= q
        if bb >= ba:
            return out
        if self.IMP <= 0:
            bid, ask = bb, ba
        elif ba - bb > 2 * self.IMP:
            bid, ask = bb + self.IMP, ba - self.IMP
        elif ba - bb > 1:
            bid, ask = bb + 1, ba - 1
        else:
            bid, ask = bb, ba
        if bc > 0 and bid <= fair - edge:
            out.append(Order(p, bid, min(self.Q, bc)))
        if sc > 0 and ask >= fair + edge:
            out.append(Order(p, ask, -min(self.Q, sc)))
        return out
