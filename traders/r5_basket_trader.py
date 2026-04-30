from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List

LIM = 10
EXIT_Z = 0.10
SOFT = 0.72
CAT_LIM = 5
ENTRY_SCALE = 0.35

MODELS = [
    ("PEBBLES_XS",4935.841930,340.387047,2.20,2.0,(("PANEL_2X4",-0.55816749),("UV_VISOR_AMBER",1.10871004))),
    ("SLEEP_POD_SUEDE",9707.140389,299.030690,1.65,2.0,(("GALAXY_SOUNDS_PLANETARY_RINGS",0.39058195),("MICROCHIP_SQUARE",0.09927248),("UV_VISOR_AMBER",-0.49020316))),
    ("PEBBLES_M",14353.310596,327.046468,2.20,2.0,(("OXYGEN_SHAKE_MORNING_BREATH",-0.47805721),("ROBOT_IRONING",-0.25322662),("PANEL_1X4",-0.00346022),("GALAXY_SOUNDS_SOLAR_WINDS",0.27320289),("ROBOT_MOPPING",0.00906568))),
    ("SLEEP_POD_POLYESTER",11781.132222,246.520429,2.20,2.0,(("SLEEP_POD_COTTON",0.30561856),("UV_VISOR_AMBER",-0.68238490),("UV_VISOR_YELLOW",0.17544483))),
    ("PEBBLES_L",19285.040845,500.512889,2.20,2.0,(("MICROCHIP_CIRCLE",-0.70375837),("TRANSLATOR_SPACE_GRAY",-0.27422584))),
    ("PEBBLES_S",21829.243187,289.098055,1.65,2.0,(("OXYGEN_SHAKE_GARLIC",-0.32691333),("PANEL_2X4",-0.25016598),("GALAXY_SOUNDS_BLACK_HOLES",-0.31645316),("OXYGEN_SHAKE_EVENING_BREATH",-0.15269858),("MICROCHIP_CIRCLE",-0.12295828))),
    ("ROBOT_MOPPING",18302.198884,344.693137,1.85,2.0,(("PANEL_1X4",-0.55343339),("OXYGEN_SHAKE_MORNING_BREATH",-0.18073233),("MICROCHIP_SQUARE",0.03647907),("MICROCHIP_RECTANGLE",-0.11594915),("PEBBLES_M",0.03153161))),
    ("SLEEP_POD_COTTON",1887.246674,514.412288,2.20,2.0,(("MICROCHIP_SQUARE",0.19688503),("MICROCHIP_CIRCLE",0.05993035),("ROBOT_MOPPING",0.57311811))),
    ("MICROCHIP_RECTANGLE",14310.527363,345.045449,1.30,2.0,(("ROBOT_MOPPING",-0.09941603),("MICROCHIP_SQUARE",-0.33237199))),
    ("GALAXY_SOUNDS_SOLAR_WINDS",12414.780366,291.480936,1.85,2.0,(("TRANSLATOR_GRAPHITE_MIST",0.69643448),("SNACKPACK_CHOCOLATE",-0.58974495),("UV_VISOR_YELLOW",-0.29362815))),
    ("TRANSLATOR_ECLIPSE_CHARCOAL",-3733.124841,208.442873,1.20,2.0,(("SNACKPACK_PISTACHIO",-0.07443174),("SNACKPACK_STRAWBERRY",0.56954370),("UV_VISOR_MAGENTA",0.30872237),("SNACKPACK_CHOCOLATE",0.09747382),("ROBOT_IRONING",0.43284299))),
    ("TRANSLATOR_VOID_BLUE",9904.224268,265.303923,2.20,2.0,(("TRANSLATOR_GRAPHITE_MIST",-0.29426590),("PEBBLES_XS",-0.44716998),("SNACKPACK_PISTACHIO",0.76321118))),
    ("ROBOT_IRONING",10141.374841,312.480139,2.20,2.0,(("OXYGEN_SHAKE_MORNING_BREATH",0.02380822),("ROBOT_MOPPING",-0.21520701),("PEBBLES_M",-0.20724548),("PANEL_1X4",0.08283635),("MICROCHIP_OVAL",0.24785699))),
    ("UV_VISOR_MAGENTA",9910.915339,338.608085,2.00,2.0,(("SNACKPACK_PISTACHIO",-0.69565629),("SNACKPACK_STRAWBERRY",0.23775507),("SNACKPACK_VANILLA",0.08661698),("SLEEP_POD_POLYESTER",0.37222832))),
    ("GALAXY_SOUNDS_DARK_MATTER",7317.285567,196.419535,2.20,2.0,(("PANEL_2X4",0.03049085),("SNACKPACK_CHOCOLATE",-0.16932429),("UV_VISOR_YELLOW",0.38576548))),
    ("TRANSLATOR_ASTRO_BLACK",2345.584026,300.785286,2.20,2.0,(("PEBBLES_XS",0.07885144),("ROBOT_VACUUMING",0.27773382),("MICROCHIP_RECTANGLE",0.28056875),("SLEEP_POD_NYLON",0.14969943))),
    ("PANEL_2X2",19179.767155,442.349777,0.80,2.0,(("TRANSLATOR_GRAPHITE_MIST",-0.69113969),("PANEL_4X4",-0.26107840))),
    ("SLEEP_POD_LAMB_WOOL",13179.423691,278.335479,2.00,2.0,(("TRANSLATOR_ECLIPSE_CHARCOAL",-0.47563701),("PANEL_1X2",0.24683940))),
    ("SNACKPACK_STRAWBERRY",11146.485719,162.293026,2.00,2.0,(("UV_VISOR_AMBER",-0.22327339),("SLEEP_POD_POLYESTER",0.11123662))),
    ("TRANSLATOR_GRAPHITE_MIST",2484.597785,288.399187,1.50,2.0,(("GALAXY_SOUNDS_SOLAR_WINDS",0.60574723),("SNACKPACK_CHOCOLATE",0.12300508))),
    ("TRANSLATOR_SPACE_GRAY",16016.489965,293.143483,2.00,2.0,(("PEBBLES_XL",-0.06459432),("MICROCHIP_CIRCLE",-0.35357801),("OXYGEN_SHAKE_GARLIC",-0.20695230))),
    ("PANEL_1X4",13391.245143,379.107116,2.20,2.0,(("ROBOT_MOPPING",-0.69642766),("OXYGEN_SHAKE_MORNING_BREATH",0.36666600))),
    ("SNACKPACK_RASPBERRY",6808.823827,155.579039,2.20,2.0,(("SLEEP_POD_LAMB_WOOL",0.16709153),("OXYGEN_SHAKE_MINT",0.15052780),("PANEL_1X2",0.00135881))),
]


def cat(p: str) -> str:
    if p.startswith("GALAXY"): return "GALAXY"
    if p.startswith("MICROCHIP"): return "MICROCHIP"
    if p.startswith("OXYGEN"): return "OXYGEN"
    if p.startswith("PANEL"): return "PANEL"
    if p.startswith("PEBBLES"): return "PEBBLES"
    if p.startswith("ROBOT"): return "ROBOT"
    if p.startswith("SLEEP"): return "SLEEP"
    if p.startswith("SNACKPACK"): return "SNACKPACK"
    if p.startswith("TRANSLATOR"): return "TRANSLATOR"
    return "UV"


def clip_add(out: List[Order], p: str, px: int, qty: int, buy_left: int, sell_left: int):
    if qty > 0:
        q = min(qty, buy_left)
    else:
        q = -min(-qty, sell_left)
    if q:
        out.append(Order(p, px, q))
    return q


class Trader:
    def run(self, state: TradingState):
        mids = {}
        for p, d in state.order_depths.items():
            if d.buy_orders and d.sell_orders:
                mids[p] = (max(d.buy_orders) + min(d.sell_orders)) / 2.0

        result: Dict[str, List[Order]] = {p: [] for p in state.order_depths}
        open_cat = {}
        for p, pos in state.position.items():
            if pos:
                c = cat(p)
                open_cat[c] = open_cat.get(c, 0) + 1

        for p, intercept, sd, entry, margin, legs in MODELS:
            d: OrderDepth = state.order_depths.get(p)
            if not d or not d.buy_orders or not d.sell_orders or p not in mids:
                continue
            fair = intercept
            ok = True
            for q, w in legs:
                m = mids.get(q)
                if m is None:
                    ok = False
                    break
                fair += w * m
            if not ok:
                continue

            pos = int(state.position.get(p, 0))
            bb, ba = max(d.buy_orders), min(d.sell_orders)
            buy_left, sell_left = max(0, LIM - pos), max(0, LIM + pos)
            z = (mids[p] - fair) / sd
            orders: List[Order] = []

            if pos > 0 and z > -EXIT_Z and sell_left:
                clip_add(orders, p, bb, -min(pos, int(d.buy_orders[bb])), buy_left, sell_left)
            elif pos < 0 and z < EXIT_Z and buy_left:
                clip_add(orders, p, ba, min(-pos, -int(d.sell_orders[ba])), buy_left, sell_left)
            else:
                c = cat(p)
                allowed = pos != 0 or open_cat.get(c, 0) < CAT_LIM
                entry *= ENTRY_SCALE
                if allowed and z > entry and bb - fair > margin and sell_left:
                    q = min(sell_left, int(d.buy_orders[bb]))
                    done = clip_add(orders, p, bb, -q, buy_left, sell_left)
                    if done:
                        open_cat[c] = open_cat.get(c, 0) + 1
                elif allowed and z < -entry and fair - ba > margin and buy_left:
                    q = min(buy_left, -int(d.sell_orders[ba]))
                    done = clip_add(orders, p, ba, q, buy_left, sell_left)
                    if done:
                        open_cat[c] = open_cat.get(c, 0) + 1
                elif allowed and z > entry * SOFT and sell_left:
                    px = max(bb + 1, ba - 1)
                    if px > fair + margin and px < ba:
                        clip_add(orders, p, px, -min(5, sell_left), buy_left, sell_left)
                elif allowed and z < -entry * SOFT and buy_left:
                    px = min(ba - 1, bb + 1)
                    if px < fair - margin and px > bb:
                        clip_add(orders, p, px, min(5, buy_left), buy_left, sell_left)

            result[p] = orders
        return result, 0, ""
