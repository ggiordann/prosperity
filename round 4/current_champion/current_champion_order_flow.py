import json
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

class Logger:

    def __init__(self) -> None:
        self.logs = ''
        self.max_log_length = 3750

    def print(self, *v111: Any, v109: str=' ', v110: str='\n') -> None:
        self.logs += v109.join(map(str, v111)) + v110

    def flush(self, v107, v69, v112, v72):
        v54 = len(self.to_json([self.compress_state(v107, ''), self.compress_orders(v69), v112, '', '']))
        v55 = (self.max_log_length - v54) // 3
        print(self.to_json([self.compress_state(v107, self.truncate(v107.traderData, v55)), self.compress_orders(v69), v112, self.truncate(v72, v55), self.truncate(self.logs, v55)]))
        self.logs = ''

    def compress_state(self, v93, v91):
        return [v93.timestamp, v91, self.compress_listings(v93.listings), self.compress_order_depths(v93.order_depths), self.compress_trades(v93.own_trades), self.compress_trades(v93.market_trades), v93.position, self.compress_observations(v93.observations)]

    def compress_listings(self, v113):
        return [[v95.symbol, v95.product, v95.denomination] for v95 in v113.values()]

    def compress_order_depths(self, v114):
        return {v93: [v104.buy_orders, v104.sell_orders] for v93, v104 in v114.items()}

    def compress_trades(self, v103):
        return [[v59.symbol, v59.price, v59.quantity, v59.buyer, v59.seller, v59.timestamp] for v96 in v103.values() for v59 in v96]

    def compress_observations(self, v115):
        v56 = {v105: [v97.bidPrice, v97.askPrice, v97.transportFees, v97.exportTariff, v97.importTariff] for v105, v97 in v115.conversionObservations.items()}
        return [v115.plainValueObservations, v56]

    def compress_orders(self, v69):
        return [[v97.symbol, v97.price, v97.quantity] for v96 in v69.values() for v97 in v96]

    def to_json(self, v53):
        return json.dumps(v53, cls=ProsperityEncoder, separators=(',', ':'))

    def truncate(self, v116, v117):
        v73, v74 = (0, min(len(v116), v117))
        v31 = ''
        while v73 <= v74:
            v7 = (v73 + v74) // 2
            v75 = v116[:v7] + ('...' if v7 < len(v116) else '')
            if len(json.dumps(v75)) <= v117:
                v31 = v75
                v73 = v7 + 1
            else:
                v74 = v7 - 1
        return v31
v0 = Logger()
v1 = {'prefix': 'hp', 'symbol': 'HYDROGEL_PACK', 'limit': 200, 'fair': 10002, 'stdev_init': 33.0, 'var_alpha': 0.005, 'qsize': 35, 'flat_pull': 1.0, 'mr_thresh': 4, 'mr_boost': 1.5, 'z_min': 0.7, 'z_max': 2.0, 'ema_fast': 0.3, 'ema_slow': 0.05, 'ema_vslow': 0.02, 'ema_full': 1.5, 'informed_lookback': 8, 'informed_full': 30, 'w_z': 0.5, 'w_ema': 0.3, 'w_inf': 0.2, 'inf_opp_cut': 0.35, 'take_max': 80, 'take_offset': 4, 'base_cap_pct': 0.75, 'full_cap_pct': 1.0, 'hard_cap_pct': 1.0, 'mark_weights': {'Mark 14': +1.5, 'Mark 38': -1.0}}
v2 = {'prefix': 'vfe', 'symbol': 'VELVETFRUIT_EXTRACT', 'limit': 200, 'fair': 5251, 'stdev_init': 17.0, 'var_alpha': 0.005, 'qsize': 30, 'flat_pull': 1.0, 'mr_thresh': 3, 'mr_boost': 1.5, 'z_min': 0.7, 'z_max': 2.0, 'ema_fast': 0.3, 'ema_slow': 0.05, 'ema_vslow': 0.02, 'ema_full': 0.8, 'informed_lookback': 10, 'informed_full': 40, 'w_z': 0.5, 'w_ema': 0.3, 'w_inf': 0.2, 'inf_opp_cut': 0.45, 'inf_override_min': 0.7, 'take_max': 70, 'take_offset': 3, 'base_cap_pct': 0.75, 'full_cap_pct': 1.0, 'hard_cap_pct': 1.0, 'mark_weights': {'Mark 67': +1.955, 'Mark 49': -1.8693, 'Mark 22': -1.296, 'Mark 14': -0.1439, 'Mark 01': +0.1574, 'Mark 55': +0.0649}, 'lead_weights': {'VEV_4000': {'Mark 67': +1.8668, 'Mark 14': -0.4887, 'Mark 01': +0.1272, 'Mark 22': -0.1354}, 'VEV_5200': {'Mark 22': -0.437, 'Mark 14': -0.3693}, 'VEV_5300': {'Mark 55': +0.4947, 'Mark 22': -0.2453, 'Mark 01': -0.1904, 'Mark 14': -0.1312}, 'VEV_5400': {'Mark 22': -0.4465, 'Mark 14': -0.1533}, 'VEV_5500': {'Mark 22': -0.6155, 'Mark 01': +0.3551, 'Mark 38': -0.2612, 'Mark 14': +0.1615, 'Mark 55': +0.1106}, 'VEV_6000': {'Mark 01': +0.5824, 'Mark 38': +0.1995, 'Mark 22': -0.1637, 'Mark 14': +0.1175}, 'VEV_6500': {'Mark 01': +0.5782, 'Mark 55': +0.4917, 'Mark 22': -0.1413, 'Mark 14': +0.1088, 'Mark 38': +0.1185}}}
v3 = [{'symbol': 'VEV_4000', 'strike': 4000, 'limit': 300, 'soft_cap': 300, 'soft_cap_max': 300, 'offset': 2}, {'symbol': 'VEV_4500', 'strike': 4500, 'limit': 300, 'soft_cap': 300, 'soft_cap_max': 300, 'offset': 2}, {'symbol': 'VEV_5000', 'strike': 5000, 'limit': 300, 'soft_cap': 300, 'soft_cap_max': 300, 'offset': 8}, {'symbol': 'VEV_5100', 'strike': 5100, 'limit': 300, 'soft_cap': 300, 'soft_cap_max': 300, 'offset': 18}, {'symbol': 'VEV_5200', 'strike': 5200, 'limit': 300, 'soft_cap': 300, 'soft_cap_max': 300, 'offset': 38}, {'symbol': 'VEV_5300', 'strike': 5300, 'limit': 300, 'soft_cap': 300, 'soft_cap_max': 300, 'offset': 90}]
v4 = 2

def _conviction_signals(v92, v102, v91, v106, v70, v107=None):
    if not v92.buy_orders or not v92.sell_orders:
        return None
    v5 = max(v92.buy_orders)
    v6 = min(v92.sell_orders)
    v7 = (v5 + v6) / 2.0
    v8 = v70['prefix']
    v9 = v70['limit']
    v10 = v70['fair']
    v11 = v7 - v10
    v12 = v91.get(f'_{v8}_var', v70['stdev_init'] ** 2)
    v12 = (1.0 - v70['var_alpha']) * v12 + v70['var_alpha'] * (v11 * v11)
    v91[f'_{v8}_var'] = v12
    v13 = max(v70['stdev_init'] * 0.15, v12 ** 0.5)
    v14 = v11 / v13
    v15 = abs(v14)
    v16 = 0.0 if v15 < v70['z_min'] else min(1.0, (v15 - v70['z_min']) / (v70['z_max'] - v70['z_min']))
    v17 = +1 if v11 < 0 else -1
    v18 = v91.get(f'_{v8}_ef', v7)
    v19 = v91.get(f'_{v8}_es', v7)
    v20 = v91.get(f'_{v8}_evs', v7)
    v18 = v70['ema_fast'] * v7 + (1.0 - v70['ema_fast']) * v18
    v19 = v70['ema_slow'] * v7 + (1.0 - v70['ema_slow']) * v19
    v20 = v70['ema_vslow'] * v7 + (1.0 - v70['ema_vslow']) * v20
    v91[f'_{v8}_ef'] = v18
    v91[f'_{v8}_es'] = v19
    v91[f'_{v8}_evs'] = v20
    v21 = v18 - v19
    v22 = v19 - v20
    v23 = 1 if v21 > 0 else -1 if v21 < 0 else 0
    v24 = 1 if v22 > 0 else -1 if v22 < 0 else 0
    if v23 != 0 and v23 == v24 and (v23 == v17):
        v57 = min(1.0, abs(v21) / v70['ema_full'])
    else:
        v57 = 0.0
    v25 = 0.0
    if v106:
        v58 = v70['mark_weights']
        for v59 in v106[-v70['informed_lookback']:]:
            v76 = v59.buyer or ''
            v77 = v59.seller or ''
            v78 = int(v59.quantity)
            v25 += v58.get(v76, 0.0) * v78
            v25 -= v58.get(v77, 0.0) * v78
    v118 = v70.get('lead_weights', {})
    if v107 is not None and v118:
        for v61, v58 in v118.items():
            for v59 in v107.market_trades.get(v61, [])[-v70['informed_lookback']:]:
                v76 = v59.buyer or ''
                v77 = v59.seller or ''
                v78 = int(v59.quantity)
                v25 += v58.get(v76, 0.0) * v78
                v25 -= v58.get(v77, 0.0) * v78
    v26 = 1 if v25 > 0 else -1 if v25 < 0 else 0
    v119 = min(1.0, abs(v25) / v70['informed_full']) if v26 != 0 else 0.0
    if v26 != 0 and v119 >= v70.get('inf_override_min', 2.0):
        v17 = v26
    v27 = v119 if v26 != 0 and v26 == v17 else 0.0
    v119 = v119 if v26 != 0 and v26 != v17 else 0.0
    v120 = 1.0 - v70.get('inf_opp_cut', 0.0) * v119
    v28 = 0.0 if v16 == 0.0 else (v70['w_z'] * v16 + v70['w_ema'] * v57) * v120 + v70['w_inf'] * v27
    return {'bb': v5, 'ba': v6, 'mid': v7, 'direction': v17, 'conviction': v28}

def _conviction_orders_with_extension(v92, v102, v91, v106, v70, v107, v108):
    v29 = _conviction_signals(v92, v102, v91, v106, v70, v107)
    if v29 is None:
        return []
    v5 = v29['bb']
    v6 = v29['ba']
    v7 = v29['mid']
    v17 = v29['direction']
    v28 = v29['conviction']
    v30 = v70['symbol']
    v9 = v70['limit']
    v10 = v70['fair']
    v31 = []
    v32 = v33 = 0
    v34 = v70['hard_cap_pct'] * v9
    if v102 > v34:
        for bid in sorted(v92.buy_orders, reverse=True):
            if bid < v10 - 2:
                break
            v79 = v92.buy_orders[bid]
            v78 = min(v79, v102, v9 + v102 - v33)
            if v78 <= 0:
                break
            v31.append(Order(v30, bid, -v78))
            v33 += v78
            if v102 + v32 - v33 <= v34 * 0.5:
                break
    elif v102 < -v34:
        for v80 in sorted(v92.sell_orders):
            if v80 > v10 + 2:
                break
            v79 = -v92.sell_orders[v80]
            v78 = min(v79, -v102, v9 - v102 - v32)
            if v78 <= 0:
                break
            v31.append(Order(v30, v80, v78))
            v32 += v78
            if v102 + v32 - v33 >= -v34 * 0.5:
                break
    v35 = v102 + v32 - v33
    v36 = v70['base_cap_pct'] + (v70['full_cap_pct'] - v70['base_cap_pct']) * v28
    v37 = v36 * v9
    v38 = int(round(v70['take_max'] * v28)) if v28 > 0 else 0
    v39 = 0
    if v28 > 0:
        if v17 > 0 and v35 < v37:
            v81 = v10 + v70['take_offset']
            v82 = v38
            for v80 in sorted(v92.sell_orders):
                if v80 > v81 or v82 <= 0:
                    break
                v79 = -v92.sell_orders[v80]
                v98 = v9 - v102 - v32
                v99 = int(v37 - v35)
                v78 = min(v79, v98, v99, v82)
                if v78 <= 0:
                    break
                v31.append(Order(v30, v80, v78))
                v32 += v78
                v82 -= v78
                v39 += v78
                v35 = v102 + v32 - v33
        elif v17 < 0 and v35 > -v37:
            v100 = v10 - v70['take_offset']
            v82 = v38
            for bid in sorted(v92.buy_orders, reverse=True):
                if bid < v100 or v82 <= 0:
                    break
                v79 = v92.buy_orders[bid]
                v98 = v9 + v102 - v33
                v99 = int(v37 + v35)
                v78 = min(v79, v98, v99, v82)
                if v78 <= 0:
                    break
                v31.append(Order(v30, bid, -v78))
                v33 += v78
                v82 -= v78
                v39 += v78
                v35 = v102 + v32 - v33
    if v70['prefix'] == 'vfe' and v28 > 0 and (v38 > v39):
        v60 = v38 - v39
        v52 = int(round(v7))
        for v53 in v3:
            if v60 <= 0:
                break
            v61 = v53['symbol']
            v62 = v53['strike']
            v63 = v53['limit']
            v83 = v53['soft_cap']
            v84 = v53.get('soft_cap_max', v83)
            v85 = int(round(v83 + (v84 - v83) * v28))
            v65 = v107.order_depths.get(v61)
            if not v65 or not v65.buy_orders or (not v65.sell_orders):
                continue
            v64 = v107.position.get(v61, 0)
            v66 = v52 - v62
            v86 = []
            v87 = v88 = 0
            v89 = v53.get('offset', v4)
            if v17 > 0 and v64 < v85:
                v81 = v66 + v89
                v82 = v60
                for v80 in sorted(v65.sell_orders):
                    if v80 > v81 or v82 <= 0:
                        break
                    v79 = -v65.sell_orders[v80]
                    v98 = v63 - v64 - v87
                    v99 = max(0, v85 - v64)
                    v78 = min(v79, v98, v99, v82)
                    if v78 <= 0:
                        break
                    v86.append(Order(v61, v80, v78))
                    v87 += v78
                    v82 -= v78
                    v60 -= v78
            elif v17 < 0 and v64 > -v85:
                v100 = v66 - v89
                v82 = v60
                for bid in sorted(v65.buy_orders, reverse=True):
                    if bid < v100 or v82 <= 0:
                        break
                    v79 = v65.buy_orders[bid]
                    v98 = v63 + v64 - v88
                    v99 = max(0, v85 + v64)
                    v78 = min(v79, v98, v99, v82)
                    if v78 <= 0:
                        break
                    v86.append(Order(v61, bid, -v78))
                    v88 += v78
                    v82 -= v78
                    v60 -= v78
            if v86:
                v108[v61] = v86
    v35 = v102 + v32 - v33
    v40 = +1 if v7 < v10 - v70['mr_thresh'] else -1 if v7 > v10 + v70['mr_thresh'] else 0
    v41 = min(v5 + 1, v10 - 1)
    v42 = max(v6 - 1, v10 + 1)
    v43 = v35 / v9
    v44 = max(0.0, 1.0 - v70['flat_pull'] * v43)
    v45 = max(0.0, 1.0 + v70['flat_pull'] * v43)
    if v40 > 0:
        v44 *= v70['mr_boost']
    elif v40 < 0:
        v45 *= v70['mr_boost']
    v46 = 1.0
    if v28 > 0:
        if v17 > 0:
            v44 *= 1.0 + v46 * v28
        elif v17 < 0:
            v45 *= 1.0 + v46 * v28
    v47 = max(0, min(int(round(v70['qsize'] * v44)), v9 - v102 - v32))
    v48 = max(0, min(int(round(v70['qsize'] * v45)), v9 + v102 - v33))
    if v41 < v42:
        if v47 > 0:
            v31.append(Order(v30, int(v41), v47))
        if v48 > 0:
            v31.append(Order(v30, int(v42), -v48))
    return v31

def _vev_flatten_orders(v107, v91):
    v49 = {}
    v50 = v107.order_depths.get('VELVETFRUIT_EXTRACT')
    if not v50 or not v50.buy_orders or (not v50.sell_orders):
        return v49
    v51 = (max(v50.buy_orders) + min(v50.sell_orders)) / 2.0
    v52 = int(round(v51))
    for v53 in v3:
        v61 = v53['symbol']
        v62 = v53['strike']
        v63 = v53['limit']
        v64 = v107.position.get(v61, 0)
        if v64 == 0:
            continue
        v65 = v107.order_depths.get(v61)
        if not v65 or not v65.buy_orders or (not v65.sell_orders):
            continue
        v66 = v52 - v62
        v67 = max(v65.buy_orders)
        v68 = min(v65.sell_orders)
        v69 = []
        if v64 > 0:
            v42 = max(v66 + 1, v68 - 1)
            v90 = min(v64, 50, v63 + v64)
            if v90 > 0:
                v69.append(Order(v61, v42, -v90))
        elif v64 < 0:
            v41 = min(v66 - 1, v67 + 1)
            v101 = min(-v64, 50, v63 - v64)
            if v101 > 0:
                v69.append(Order(v61, v41, v101))
        if v69:
            v49[v61] = v69
    return v49

class Trader:

    def bid(self):
        return 0

    def run(self, v107: TradingState):
        try:
            v91 = json.loads(v107.traderData) if v107.traderData else {}
        except Exception:
            v91 = {}
        v69: dict[str, list[Order]] = {}
        for v70 in (v1, v2):
            v30 = v70['symbol']
            v92 = v107.order_depths.get(v30)
            if v92:
                v102 = v107.position.get(v30, 0)
                v103 = v107.market_trades.get(v30, [])
                v94 = _conviction_orders_with_extension(v92, v102, v91, v103, v70, v107, v69)
                if v94:
                    v69[v30] = v94
        v71 = _vev_flatten_orders(v107, v91)
        for v93, v94 in v71.items():
            if v93 not in v69:
                v69[v93] = v94
            else:
                v69[v93].extend(v94)
        v72 = json.dumps(v91)
        v0.flush(v107, v69, 0, v72)
        return (v69, 0, v72)
