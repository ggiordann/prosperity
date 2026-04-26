import json
import math
from statistics import NormalDist
from datamodel import Order, OrderDepth, TradingState

N = NormalDist()
def bs_call(S, K, T, sigma):
    if T <= 0 or sigma <= 0 or S <= 0: return max(S-K, 0.0)
    try:
        d1 = (math.log(S/K) + 0.5*sigma*sigma*T) / (sigma*math.sqrt(T))
        d2 = d1 - sigma*math.sqrt(T)
        return S*N.cdf(d1) - K*N.cdf(d2)
    except: return max(S-K, 0.0)
def implied_vol(C, S, K, T):
    intrinsic = max(S-K, 0)
    if C <= intrinsic + 1e-4 or C >= S - 1e-4 or T <= 0: return None
    lo, hi = 1e-4, 3.0
    for _ in range(50):
        mid = 0.5*(lo+hi)
        if bs_call(S, K, T, mid) - C > 0: hi = mid
        else: lo = mid
    return 0.5*(lo+hi)

DAVID_STRIKES = [4000, 4500, 5000, 5100, 5200, 5300]
SMILE_STRIKES = [5400, 5500]
FIT_STRIKES = [5000, 5100, 5200, 5300, 5400, 5500]
POS_LIMIT = {'HYDROGEL_PACK': 200, 'VELVETFRUIT_EXTRACT': 200}
for k in [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]:
    POS_LIMIT[f'VEV_{k}'] = 300

class Trader:
    def __init__(self):
        self.sd = {}

    def best(self, d):
        bid = max(d.buy_orders) if d.buy_orders else None
        ask = min(d.sell_orders) if d.sell_orders else None
        return bid, ask
    def wall_mid(self, depth):
        bids = sorted(depth.buy_orders.keys()) if depth.buy_orders else []
        asks = sorted(depth.sell_orders.keys()) if depth.sell_orders else []
        if not bids or not asks: return None
        return (bids[0] + asks[-1]) / 2
    def vamp(self, d):
        b, a = self.best(d)
        if b is None or a is None: return None
        bv = d.buy_orders[b]; av = -d.sell_orders[a]
        if bv+av==0: return (b+a)/2
        return (b*av + a*bv) / (bv+av)

    def mm_rw_avoid(self, sym, depth, pos, key, alpha=0.2, take_w=1, clear_w=2, max_sz=50, use_wall=False):
        lim = POS_LIMIT[sym]
        orders = []
        v = self.wall_mid(depth) if use_wall else self.vamp(depth)
        if v is None: return orders
        prev = self.sd.get(key)
        fv = v if prev is None else prev + alpha*(v - prev)
        self.sd[key] = fv
        b, a = self.best(depth)
        bc = lim - pos; sc = lim + pos

        bids = sorted(depth.buy_orders.keys(), reverse=True)
        asks = sorted(depth.sell_orders.keys())
        bid_sig = len(bids) >= 2 and (bids[0] - bids[1] >= 5)
        ask_sig = len(asks) >= 2 and (asks[1] - asks[0] >= 5)

        for px in sorted(depth.sell_orders):
            if px <= fv - take_w and bc > 0:
                vol = min(-depth.sell_orders[px], bc)
                if vol > 0: orders.append(Order(sym, px, vol)); bc -= vol
        for px in sorted(depth.buy_orders, reverse=True):
            if px >= fv + take_w and sc > 0:
                vol = min(depth.buy_orders[px], sc)
                if vol > 0: orders.append(Order(sym, px, -vol)); sc -= vol
        pa = pos + sum(o.quantity for o in orders)
        if pa > 0:
            p = int(round(fv + clear_w))
            if p in depth.buy_orders and sc > 0:
                v2 = min(depth.buy_orders[p], pa, sc)
                if v2 > 0: orders.append(Order(sym, p, -v2)); sc -= v2
        elif pa < 0:
            p = int(round(fv - clear_w))
            if p in depth.sell_orders and bc > 0:
                v2 = min(-depth.sell_orders[p], -pa, bc)
                if v2 > 0: orders.append(Order(sym, p, v2)); bc -= v2

        if b is not None and a is not None:
            sp = a - b; edge = max(1, sp//2)
            mb = int(round(fv - edge)); ma = int(round(fv + edge))
            if mb <= b: mb = b + 1
            if ma >= a: ma = a - 1
            if mb < ma:
                # Skip BID when bid_inside signal (price will drop - don't accumulate long)
                # Skip ASK when ask_inside signal (price will rise - don't accumulate short)
                if bc > 0 and not bid_sig: orders.append(Order(sym, mb, min(max_sz, bc)))
                if sc > 0 and not ask_sig: orders.append(Order(sym, ma, -min(max_sz, sc)))
        return orders

    def mm_rw(self, sym, depth, pos, key, alpha=0.2, take_w=1, clear_w=2, max_sz=50, use_wall=False):
        lim = POS_LIMIT[sym]
        orders = []
        v = self.wall_mid(depth) if use_wall else self.vamp(depth)
        if v is None: return orders
        prev = self.sd.get(key)
        fv = v if prev is None else prev + alpha*(v - prev)
        self.sd[key] = fv
        b, a = self.best(depth)
        bc = lim - pos; sc = lim + pos
        for px in sorted(depth.sell_orders):
            if px <= fv - take_w and bc > 0:
                vol = min(-depth.sell_orders[px], bc)
                if vol > 0: orders.append(Order(sym, px, vol)); bc -= vol
        for px in sorted(depth.buy_orders, reverse=True):
            if px >= fv + take_w and sc > 0:
                vol = min(depth.buy_orders[px], sc)
                if vol > 0: orders.append(Order(sym, px, -vol)); sc -= vol
        pa = pos + sum(o.quantity for o in orders)
        if pa > 0:
            p = int(round(fv + clear_w))
            if p in depth.buy_orders and sc > 0:
                v2 = min(depth.buy_orders[p], pa, sc)
                if v2 > 0: orders.append(Order(sym, p, -v2)); sc -= v2
        elif pa < 0:
            p = int(round(fv - clear_w))
            if p in depth.sell_orders and bc > 0:
                v2 = min(-depth.sell_orders[p], -pa, bc)
                if v2 > 0: orders.append(Order(sym, p, v2)); bc -= v2
        if b is not None and a is not None:
            sp = a - b; edge = max(1, sp//2)
            mb = int(round(fv - edge)); ma = int(round(fv + edge))
            if mb <= b: mb = b + 1
            if ma >= a: ma = a - 1
            if mb < ma:
                if bc > 0: orders.append(Order(sym, mb, min(max_sz, bc)))
                if sc > 0: orders.append(Order(sym, ma, -min(max_sz, sc)))
        return orders

    def trade_david_option(self, sym, depth, pos, out):
        b, a = self.best(depth)
        if b is None or a is None: return
        bv = depth.buy_orders[b]
        av = -depth.sell_orders[a]
        mid = (b + a) / 2
        spread = a - b
        key = f'oema_{sym}'
        prev = self.sd.get(key)
        fair_raw = mid if prev is None else prev
        fair = fair_raw - 0.005 * pos
        dynamic_edge = max(14.0, spread * 1.5)
        lim = POS_LIMIT[sym]
        bc = lim - pos; sc = lim + pos
        if a <= fair - dynamic_edge:
            q = min(30, av, bc)
            if q > 0: out.setdefault(sym, []).append(Order(sym, a, q))
        elif b >= fair + dynamic_edge:
            q = min(30, bv, sc)
            if q > 0: out.setdefault(sym, []).append(Order(sym, b, -q))
        new_ema = fair_raw + 0.0003 * (mid - fair_raw)
        self.sd[key] = new_ema

    def solve3(self, A, B):
        M = [r[:] + [B[i]] for i, r in enumerate(A)]
        for i in range(3):
            mx = max(range(i, 3), key=lambda r: abs(M[r][i]))
            M[i], M[mx] = M[mx], M[i]
            p = M[i][i]
            if abs(p) < 1e-12: raise ValueError
            for r in range(i+1, 3):
                f = M[r][i] / p
                for c in range(i, 4): M[r][c] -= f * M[i][c]
        x = [0]*3
        for i in range(2, -1, -1):
            x[i] = (M[i][3] - sum(M[i][c]*x[c] for c in range(i+1,3))) / M[i][i]
        return x

    def smile_sleeve(self, state, out):
        T = max(0.01, 5 - state.timestamp / 1_000_000)
        if 'VELVETFRUIT_EXTRACT' not in state.order_depths: return
        ud = state.order_depths['VELVETFRUIT_EXTRACT']
        ub, ua = self.best(ud)
        if ub is None or ua is None: return
        S = (ub + ua) / 2
        ivs = {}
        for K in FIT_STRIKES:
            sym = f'VEV_{K}'
            if sym not in state.order_depths: continue
            d = state.order_depths[sym]
            b, a = self.best(d)
            if b is None or a is None: continue
            C = (b + a) / 2
            v = implied_vol(C, S, K, T)
            if v is None: continue
            m = math.log(K/S) / math.sqrt(T)
            ivs[K] = (m, v, C)
        if len(ivs) < 4: return
        ms = [x[0] for x in ivs.values()]; vs = [x[1] for x in ivs.values()]
        n = len(ms); sm = sum(ms); sm2 = sum(m*m for m in ms); sm3 = sum(m**3 for m in ms); sm4 = sum(m**4 for m in ms)
        sv = sum(vs); smv = sum(m*v for m,v in zip(ms,vs)); sm2v = sum(m*m*v for m,v in zip(ms,vs))
        try:
            a_c, b_c, c_c = self.solve3([[sm4,sm3,sm2],[sm3,sm2,sm],[sm2,sm,n]], [sm2v,smv,sv])
        except: return
        WARMUP = 200; SPAN = 300; alph = 2.0/(SPAN+1)
        for K in SMILE_STRIKES:
            if K not in ivs: continue
            sym = f'VEV_{K}'
            m, v, C_mid = ivs[K]
            fit_iv = a_c*m*m + b_c*m + c_c
            C_theo = bs_call(S, K, T, fit_iv)
            raw = C_mid - C_theo
            bk = f'b_{K}'; vk = f'v_{K}'; ck = f'c_{K}'
            pb = self.sd.get(bk, 0.0)
            bias = pb + alph * (raw - pb)
            self.sd[bk] = bias
            dev = raw - bias
            pv = self.sd.get(vk, 1.0)
            var = pv + alph * (dev*dev - pv)
            self.sd[vk] = var
            cnt = self.sd.get(ck, 0) + 1
            self.sd[ck] = cnt
            if cnt < WARMUP: continue
            FV = C_theo + bias
            std = math.sqrt(max(var, 1e-6))
            d = state.order_depths[sym]
            b, a = self.best(d)
            if b is None or a is None: continue
            pos = state.position.get(sym, 0)
            lim = POS_LIMIT[sym]
            edge = max(1, int(round(std * 1.5)))
            q_bid = int(round(FV - edge)); q_ask = int(round(FV + edge))
            if q_bid > b: q_bid = b + 1 if b + 1 < q_ask else b
            if q_ask < a: q_ask = a - 1 if a - 1 > q_bid else a
            if q_bid >= FV: q_bid = int(math.floor(FV - 1))
            if q_ask <= FV: q_ask = int(math.ceil(FV + 1))
            bc = lim - pos; sc = lim + pos; sz = 10
            if q_bid < q_ask and q_bid > 0:
                if bc > 0: out.setdefault(sym, []).append(Order(sym, q_bid, min(sz, bc)))
                if sc > 0: out.setdefault(sym, []).append(Order(sym, q_ask, -min(sz, sc)))
            z = (C_mid - FV) / std
            if abs(z) > 3.5:
                if z > 0 and sc > 0:
                    q = min(5, sc, d.buy_orders.get(b, 0))
                    if q > 0: out.setdefault(sym, []).append(Order(sym, b, -q))
                elif z < 0 and bc > 0:
                    q = min(5, bc, -d.sell_orders.get(a, 0))
                    if q > 0: out.setdefault(sym, []).append(Order(sym, a, q))

    def hgp_contrarian(self, state, out, lookback=200, thr=30, max_pos=200):
        """Fade long-horizon moves: short after rally, long after decline."""
        sym = 'HYDROGEL_PACK'
        if sym not in state.order_depths: return
        d = state.order_depths[sym]
        b, a = self.best(d)
        if b is None or a is None: return
        mid = (b + a) / 2
        # Store mid history
        hist = self.sd.get('hgp_hist', [])
        hist.append(mid)
        if len(hist) > lookback + 10: hist = hist[-(lookback + 10):]
        self.sd['hgp_hist'] = hist
        if len(hist) < lookback + 1: return
        past_move = mid - hist[-lookback-1]
        pos = state.position.get(sym, 0)
        lim = POS_LIMIT[sym]
        if past_move > thr:
            # Price rose - go SHORT
            target = -max_pos
            if pos > target:
                sc = lim + pos
                bv = d.buy_orders[b]
                q = min(pos - target, sc, bv)
                if q > 0: out.setdefault(sym, []).append(Order(sym, b, -q))
        elif past_move < -thr:
            target = max_pos
            if pos < target:
                bc = lim - pos
                av = -d.sell_orders[a]
                q = min(target - pos, bc, av)
                if q > 0: out.setdefault(sym, []).append(Order(sym, a, q))

    def run(self, state):
        if state.traderData:
            try: self.sd = json.loads(state.traderData)
            except: self.sd = {}
        else: self.sd = {}
        result = {}
        if 'HYDROGEL_PACK' in state.order_depths:
            pos = state.position.get('HYDROGEL_PACK', 0)
            result['HYDROGEL_PACK'] = self.mm_rw_avoid('HYDROGEL_PACK', state.order_depths['HYDROGEL_PACK'], pos, 'hfv', max_sz=50, take_w=2, use_wall=True)
        if 'VELVETFRUIT_EXTRACT' in state.order_depths:
            pos = state.position.get('VELVETFRUIT_EXTRACT', 0)
            result['VELVETFRUIT_EXTRACT'] = self.mm_rw('VELVETFRUIT_EXTRACT', state.order_depths['VELVETFRUIT_EXTRACT'], pos, 'vfv', max_sz=50)
        for K in DAVID_STRIKES:
            sym = f'VEV_{K}'
            if sym in state.order_depths:
                pos = state.position.get(sym, 0)
                self.trade_david_option(sym, state.order_depths[sym], pos, result)
        self.smile_sleeve(state, result)
        self.hgp_contrarian(state, result, lookback=200, thr=30, max_pos=150)
        return result, 0, json.dumps(self.sd)