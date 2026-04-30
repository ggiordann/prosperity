from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json

BIG = 10**9
LIMIT = 10
SIZE = 20

GROUPS = {
    "pebbles": ("PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"),
    "microchips": ("MICROCHIP_CIRCLE", "MICROCHIP_OVAL", "MICROCHIP_SQUARE", "MICROCHIP_RECTANGLE", "MICROCHIP_TRIANGLE"),
    "galaxy": ("GALAXY_SOUNDS_DARK_MATTER", "GALAXY_SOUNDS_BLACK_HOLES", "GALAXY_SOUNDS_PLANETARY_RINGS", "GALAXY_SOUNDS_SOLAR_WINDS", "GALAXY_SOUNDS_SOLAR_FLAMES"),
    "sleeping": ("SLEEP_POD_SUEDE", "SLEEP_POD_LAMB_WOOL", "SLEEP_POD_POLYESTER", "SLEEP_POD_NYLON", "SLEEP_POD_COTTON"),
    "translators": ("TRANSLATOR_SPACE_GRAY", "TRANSLATOR_ASTRO_BLACK", "TRANSLATOR_ECLIPSE_CHARCOAL", "TRANSLATOR_GRAPHITE_MIST", "TRANSLATOR_VOID_BLUE"),
    "uv": ("UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"),
    "oxygen": ("OXYGEN_SHAKE_MORNING_BREATH", "OXYGEN_SHAKE_EVENING_BREATH", "OXYGEN_SHAKE_MINT", "OXYGEN_SHAKE_CHOCOLATE", "OXYGEN_SHAKE_GARLIC"),
    "panels": ("PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"),
    "snackpacks": ("SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "SNACKPACK_PISTACHIO", "SNACKPACK_STRAWBERRY", "SNACKPACK_RASPBERRY"),
    "robotics": ("ROBOT_VACUUMING", "ROBOT_MOPPING", "ROBOT_DISHES", "ROBOT_LAUNDRY", "ROBOT_IRONING"),
}
ACTIVE = ("pebbles", "microchips", "galaxy", "sleeping", "translators", "uv", "oxygen", "panels", "snackpacks", "robotics")
ROUND5 = {p for products in GROUPS.values() for p in products}

MID = {"PEBBLES_S", "MICROCHIP_OVAL", "MICROCHIP_SQUARE", "MICROCHIP_TRIANGLE", "GALAXY_SOUNDS_BLACK_HOLES", "SLEEP_POD_NYLON", "OXYGEN_SHAKE_CHOCOLATE"}
SHIFT = {
    "PEBBLES_S": 1.0, "MICROCHIP_OVAL": -1.0, "MICROCHIP_SQUARE": 2.0, "MICROCHIP_TRIANGLE": -50.0,
    "GALAXY_SOUNDS_BLACK_HOLES": 2.0, "OXYGEN_SHAKE_CHOCOLATE": 0.0, "SLEEP_POD_NYLON": 0.0,
}
FAIR = {
    "PEBBLES_XS": 7404.64 - 1014.683, "PEBBLES_M": 10263.243 - 17.195, "PEBBLES_L": 10174.111 - 31.117, "PEBBLES_XL": 13225.589,
    "MICROCHIP_CIRCLE": 9214.885, "MICROCHIP_RECTANGLE": 8732.439 - 470.012,
    "GALAXY_SOUNDS_DARK_MATTER": 10226.662 + 41.338, "GALAXY_SOUNDS_PLANETARY_RINGS": 10766.673 - 172.313, "GALAXY_SOUNDS_SOLAR_FLAMES": 11092.572 - 33.761, "GALAXY_SOUNDS_SOLAR_WINDS": 10437.544,
    "SLEEP_POD_SUEDE": 11397.42 + 697.458, "SLEEP_POD_LAMB_WOOL": 10701.442 + 10.329, "SLEEP_POD_POLYESTER": 11840.561 + 171.07, "SLEEP_POD_COTTON": 11527.614 + 554.808,
    "TRANSLATOR_ASTRO_BLACK": 9385.219 - 48.975, "TRANSLATOR_ECLIPSE_CHARCOAL": 9813.742 - 26.673, "TRANSLATOR_GRAPHITE_MIST": 10084.64 - 199.816, "TRANSLATOR_SPACE_GRAY": 9431.902 + 263.921, "TRANSLATOR_VOID_BLUE": 10858.579 + 376.515,
    "UV_VISOR_YELLOW": 10991.551, "UV_VISOR_AMBER": 6864.932, "UV_VISOR_ORANGE": 10275.09, "UV_VISOR_RED": 10784.129, "UV_VISOR_MAGENTA": 11617.975,
    "OXYGEN_SHAKE_MORNING_BREATH": 10000.453 - 48.960, "OXYGEN_SHAKE_EVENING_BREATH": 9271.895, "OXYGEN_SHAKE_MINT": 9838.394 + 38.110, "OXYGEN_SHAKE_GARLIC": 11925.640 - 47.667,
    "PANEL_1X2": 8982.0, "PANEL_2X2": 9593.0, "PANEL_1X4": 9523.0, "PANEL_2X4": 11312.0, "PANEL_4X4": 9879.0,
    "SNACKPACK_CHOCOLATE": 9843.372 + 115.421, "SNACKPACK_VANILLA": 10097.302 - 22.314, "SNACKPACK_PISTACHIO": 9495.844, "SNACKPACK_STRAWBERRY": 10706.609 + 163.608, "SNACKPACK_RASPBERRY": 10077.812,
    "ROBOT_DISHES": 9962.651, "ROBOT_IRONING": 8450.985, "ROBOT_LAUNDRY": 9930.268, "ROBOT_MOPPING": 11157.750, "ROBOT_VACUUMING": 9153.395,
}
TAKE = {
    "PEBBLES_XS": 0.35 * 1449.547, "PEBBLES_M": 0.15 * 687.817, "PEBBLES_L": 0.35 * 622.332, "PEBBLES_XL": 0.35 * 1776.546,
    "MICROCHIP_CIRCLE": 0.75 * 532.512, "MICROCHIP_RECTANGLE": 1.0 * 752.019,
    "GALAXY_SOUNDS_DARK_MATTER": 0.35 * 330.701, "GALAXY_SOUNDS_PLANETARY_RINGS": 0.8 * 765.837, "GALAXY_SOUNDS_SOLAR_FLAMES": 0.8 * 450.15, "GALAXY_SOUNDS_SOLAR_WINDS": 1.0 * 541.111,
    "SLEEP_POD_SUEDE": 0.4 * 899.946, "SLEEP_POD_LAMB_WOOL": 1.25 * 413.169, "SLEEP_POD_POLYESTER": 0.25 * 977.54, "SLEEP_POD_COTTON": 1.5 * 887.693,
    "TRANSLATOR_ASTRO_BLACK": 0.1 * 489.746, "TRANSLATOR_ECLIPSE_CHARCOAL": 0.5 * 355.637, "TRANSLATOR_GRAPHITE_MIST": 0.15 * 499.541, "TRANSLATOR_SPACE_GRAY": 1.1 * 502.706, "TRANSLATOR_VOID_BLUE": 0.15 * 579.254,
    "UV_VISOR_YELLOW": 1.75 * 681.808, "UV_VISOR_AMBER": 0.3 * 996.918, "UV_VISOR_ORANGE": 1.55 * 550.603, "UV_VISOR_RED": 0.1 * 587.715, "UV_VISOR_MAGENTA": 0.35 * 613.554,
    "OXYGEN_SHAKE_MORNING_BREATH": 1305.610, "OXYGEN_SHAKE_EVENING_BREATH": 219.902, "OXYGEN_SHAKE_MINT": 254.066, "OXYGEN_SHAKE_GARLIC": 333.672,
    "PANEL_1X2": 560.0, "PANEL_2X2": 1215.0, "PANEL_1X4": 1501.0, "PANEL_2X4": 470.0, "PANEL_4X4": 571.0,
    "SNACKPACK_CHOCOLATE": 0.50 * 200.733, "SNACKPACK_VANILLA": 0.65 * 178.515, "SNACKPACK_PISTACHIO": 0.25 * 187.495, "SNACKPACK_STRAWBERRY": 0.20 * 363.573, "SNACKPACK_RASPBERRY": 1.15 * 169.814,
    "ROBOT_DISHES": 194.824, "ROBOT_IRONING": 963.788, "ROBOT_LAUNDRY": 767.903, "ROBOT_MOPPING": 1150.742, "ROBOT_VACUUMING": 909.940,
}
EDGE = {
    "PEBBLES_XS": 2.0, "PEBBLES_S": 3.0, "PEBBLES_M": 20.0, "PEBBLES_L": 0.0, "PEBBLES_XL": 0.0,
    "MICROCHIP_CIRCLE": 6.0, "MICROCHIP_OVAL": 1.5, "MICROCHIP_SQUARE": 15.0, "MICROCHIP_RECTANGLE": 0.0, "MICROCHIP_TRIANGLE": 0.0,
    "GALAXY_SOUNDS_BLACK_HOLES": 1.5, "GALAXY_SOUNDS_DARK_MATTER": 0.0, "GALAXY_SOUNDS_PLANETARY_RINGS": 12.0, "GALAXY_SOUNDS_SOLAR_FLAMES": 2.0, "GALAXY_SOUNDS_SOLAR_WINDS": 2.0,
    "SLEEP_POD_SUEDE": 6.0, "SLEEP_POD_LAMB_WOOL": 2.0, "SLEEP_POD_POLYESTER": 6.0, "SLEEP_POD_NYLON": 1.5, "SLEEP_POD_COTTON": 0.0,
    "UV_VISOR_YELLOW": 6.0, "UV_VISOR_AMBER": 15.0, "UV_VISOR_ORANGE": 0.0, "UV_VISOR_RED": 30.0, "UV_VISOR_MAGENTA": 6.0,
    "OXYGEN_SHAKE_MORNING_BREATH": 6.0, "OXYGEN_SHAKE_EVENING_BREATH": 15.0, "OXYGEN_SHAKE_MINT": 2.0, "OXYGEN_SHAKE_CHOCOLATE": 5.0, "OXYGEN_SHAKE_GARLIC": 25.0,
    "PANEL_1X2": 2.0, "PANEL_2X2": 6.0, "PANEL_1X4": 2.0, "PANEL_2X4": 6.0, "PANEL_4X4": 2.0,
    "SNACKPACK_CHOCOLATE": 8.0, "SNACKPACK_VANILLA": 8.0, "SNACKPACK_PISTACHIO": 30.0, "SNACKPACK_STRAWBERRY": 36.0, "SNACKPACK_RASPBERRY": 1.0,
    "ROBOT_DISHES": 1.0, "ROBOT_IRONING": 0.0, "ROBOT_LAUNDRY": 2.0, "ROBOT_MOPPING": 8.0, "ROBOT_VACUUMING": 6.0,
}
IMP = {
    "PEBBLES_XS": 0, "PEBBLES_S": 1, "PEBBLES_M": 4, "PEBBLES_L": 1, "PEBBLES_XL": 0,
    "MICROCHIP_CIRCLE": 5, "MICROCHIP_OVAL": 4, "MICROCHIP_SQUARE": 1, "MICROCHIP_RECTANGLE": 0, "MICROCHIP_TRIANGLE": 1,
    "GALAXY_SOUNDS_BLACK_HOLES": 4, "GALAXY_SOUNDS_DARK_MATTER": 1, "GALAXY_SOUNDS_PLANETARY_RINGS": 0, "GALAXY_SOUNDS_SOLAR_FLAMES": 0, "GALAXY_SOUNDS_SOLAR_WINDS": 0,
    "SLEEP_POD_SUEDE": 0, "SLEEP_POD_LAMB_WOOL": 0, "SLEEP_POD_POLYESTER": 0, "SLEEP_POD_NYLON": 5, "SLEEP_POD_COTTON": 0,
    "UV_VISOR_YELLOW": 0, "UV_VISOR_AMBER": 1, "UV_VISOR_ORANGE": 0, "UV_VISOR_RED": 1, "UV_VISOR_MAGENTA": 1,
    "OXYGEN_SHAKE_MORNING_BREATH": 0, "OXYGEN_SHAKE_EVENING_BREATH": 1, "OXYGEN_SHAKE_MINT": 0, "OXYGEN_SHAKE_CHOCOLATE": 6, "OXYGEN_SHAKE_GARLIC": 5,
    "SNACKPACK_CHOCOLATE": 0, "SNACKPACK_VANILLA": 0, "SNACKPACK_PISTACHIO": 1, "SNACKPACK_STRAWBERRY": 4, "SNACKPACK_RASPBERRY": 0,
}
WALK = {"PEBBLES_M", "MICROCHIP_SQUARE", "SLEEP_POD_SUEDE", "SLEEP_POD_COTTON", "OXYGEN_SHAKE_GARLIC", "PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4", "ROBOT_DISHES", "ROBOT_LAUNDRY"}
PLAIN_QUOTE = {"PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4", "ROBOT_DISHES", "ROBOT_IRONING", "ROBOT_LAUNDRY", "ROBOT_MOPPING", "ROBOT_VACUUMING"}
TAKE_ONLY = set(GROUPS["translators"])
PRODUCT_GROUP = {p: g for g, products in GROUPS.items() for p in products}
BASKET_SELECTED = {"PANEL_2X2", "PEBBLES_M", "ROBOT_MOPPING", "ROBOT_IRONING"}
REGIME_SELECTED = {"SLEEP_POD_SUEDE", "ROBOT_LAUNDRY", "PANEL_2X4"}
EXIT_Z = 0.10
SOFT = 0.72
CAT_LIM = 5
ENTRY_SCALE = 0.35
EDGE_MULT = 1.15
TAKE_MULT = 1.05

BASKET_MODELS = [
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

SIG = {
    "PEBBLES_XS": (("PEBBLES_XL", 200, 0.1), ("PEBBLES_XL", 500, 0.25)), "PEBBLES_S": (("PEBBLES_XS", 500, 0.1), ("PEBBLES_L", 10, -0.1)), "PEBBLES_M": (("PEBBLES_XS", 200, -0.0625), ("PEBBLES_XL", 200, 0.625)), "PEBBLES_L": (("PEBBLES_S", 500, 0.5), ("PEBBLES_XL", 5, 0.5)), "PEBBLES_XL": (("PEBBLES_M", 20, -1.0), ("PEBBLES_M", 500, -0.1)),
    "MICROCHIP_CIRCLE": (("MICROCHIP_SQUARE", 100, 1.0), ("MICROCHIP_RECTANGLE", 100, 1.0)), "MICROCHIP_OVAL": (("MICROCHIP_RECTANGLE", 2, -0.05), ("MICROCHIP_RECTANGLE", 1, 0.1)), "MICROCHIP_RECTANGLE": (("MICROCHIP_SQUARE", 200, -0.1), ("MICROCHIP_SQUARE", 200, -1.0)), "MICROCHIP_SQUARE": (("MICROCHIP_OVAL", 10, 0.05), ("MICROCHIP_TRIANGLE", 5, 0.05)), "MICROCHIP_TRIANGLE": (("MICROCHIP_OVAL", 200, 1.0), ("MICROCHIP_OVAL", 100, 0.25)),
    "GALAXY_SOUNDS_BLACK_HOLES": (("GALAXY_SOUNDS_PLANETARY_RINGS", 1, 0.1), ("GALAXY_SOUNDS_PLANETARY_RINGS", 10, -0.05)), "GALAXY_SOUNDS_DARK_MATTER": (("GALAXY_SOUNDS_BLACK_HOLES", 1, 0.05), ("GALAXY_SOUNDS_BLACK_HOLES", 50, 0.05)), "GALAXY_SOUNDS_PLANETARY_RINGS": (("GALAXY_SOUNDS_SOLAR_FLAMES", 500, 0.1), ("GALAXY_SOUNDS_SOLAR_WINDS", 100, -0.1)), "GALAXY_SOUNDS_SOLAR_FLAMES": (("GALAXY_SOUNDS_BLACK_HOLES", 500, -1.25), ("GALAXY_SOUNDS_SOLAR_WINDS", 78, 0.15)), "GALAXY_SOUNDS_SOLAR_WINDS": (("GALAXY_SOUNDS_BLACK_HOLES", 50, -0.2),),
    "SLEEP_POD_SUEDE": (("SLEEP_POD_LAMB_WOOL", 200, 0.1), ("SLEEP_POD_COTTON", 200, -0.5)), "SLEEP_POD_LAMB_WOOL": (("SLEEP_POD_COTTON", 500, -1.0), ("SLEEP_POD_POLYESTER", 50, 1.0)), "SLEEP_POD_POLYESTER": (("SLEEP_POD_SUEDE", 200, -0.05), ("SLEEP_POD_NYLON", 1, 1.0)), "SLEEP_POD_NYLON": (("SLEEP_POD_COTTON", 100, 1.0), ("SLEEP_POD_SUEDE", 100, -0.5)), "SLEEP_POD_COTTON": (("SLEEP_POD_LAMB_WOOL", 500, 0.25),),
    "TRANSLATOR_ASTRO_BLACK": (("TRANSLATOR_VOID_BLUE", 200, 0.1), ("TRANSLATOR_GRAPHITE_MIST", 200, 0.1)), "TRANSLATOR_ECLIPSE_CHARCOAL": (("TRANSLATOR_GRAPHITE_MIST", 100, 0.5), ("TRANSLATOR_SPACE_GRAY", 100, -0.25), ("TRANSLATOR_SPACE_GRAY", 5, 0.2)), "TRANSLATOR_GRAPHITE_MIST": (("TRANSLATOR_VOID_BLUE", 500, 0.5), ("TRANSLATOR_ECLIPSE_CHARCOAL", 20, 0.1)), "TRANSLATOR_SPACE_GRAY": (("TRANSLATOR_ECLIPSE_CHARCOAL", 500, 0.5), ("TRANSLATOR_GRAPHITE_MIST", 200, -0.25)), "TRANSLATOR_VOID_BLUE": (("TRANSLATOR_ECLIPSE_CHARCOAL", 200, -0.1), ("TRANSLATOR_ASTRO_BLACK", 20, -0.1)),
    "UV_VISOR_YELLOW": (("UV_VISOR_AMBER", 500, 0.15), ("UV_VISOR_RED", 500, -0.05)), "UV_VISOR_AMBER": (("UV_VISOR_RED", 500, 0.25), ("UV_VISOR_ORANGE", 100, 0.25)), "UV_VISOR_ORANGE": (("UV_VISOR_YELLOW", 200, -0.25),), "UV_VISOR_RED": (("UV_VISOR_YELLOW", 50, 0.1), ("UV_VISOR_ORANGE", 1, -0.25)), "UV_VISOR_MAGENTA": (("UV_VISOR_AMBER", 500, 1.0), ("UV_VISOR_YELLOW", 20, -0.25)),
    "OXYGEN_SHAKE_MORNING_BREATH": (("OXYGEN_SHAKE_MINT", 500, 1.0), ("OXYGEN_SHAKE_MINT", 10, -1.0)), "OXYGEN_SHAKE_EVENING_BREATH": (("OXYGEN_SHAKE_MORNING_BREATH", 200, 0.5), ("OXYGEN_SHAKE_CHOCOLATE", 5, -0.5)), "OXYGEN_SHAKE_MINT": (("OXYGEN_SHAKE_GARLIC", 200, -0.05),), "OXYGEN_SHAKE_CHOCOLATE": (("OXYGEN_SHAKE_EVENING_BREATH", 50, -0.1), ("OXYGEN_SHAKE_GARLIC", 2, -0.05)), "OXYGEN_SHAKE_GARLIC": (("OXYGEN_SHAKE_MINT", 500, -1.0), ("OXYGEN_SHAKE_MINT", 200, 1.0)),
    "PANEL_1X2": (("PANEL_2X2", 200, -1.0),), "PANEL_2X2": (("PANEL_1X2", 50, 0.5),), "PANEL_1X4": (("PANEL_1X2", 500, 1.0), ("PANEL_4X4", 200, 0.25)), "PANEL_2X4": (("PANEL_1X4", 500, -0.1), ("PANEL_1X4", 100, 0.5), ("PANEL_1X2", 200, 0.2)), "PANEL_4X4": (("PANEL_2X2", 100, -1.0), ("PANEL_2X4", 500, 0.25)),
    "SNACKPACK_CHOCOLATE": (("SNACKPACK_STRAWBERRY", 50, 0.25), ("SNACKPACK_PISTACHIO", 100, -0.05)), "SNACKPACK_VANILLA": (("SNACKPACK_CHOCOLATE", 100, -0.05), ("SNACKPACK_CHOCOLATE", 2, -0.25)), "SNACKPACK_PISTACHIO": (("SNACKPACK_RASPBERRY", 20, -0.10), ("SNACKPACK_RASPBERRY", 500, 0.05)), "SNACKPACK_STRAWBERRY": (("SNACKPACK_CHOCOLATE", 100, 1.0), ("SNACKPACK_PISTACHIO", 10, -0.50)), "SNACKPACK_RASPBERRY": (("SNACKPACK_PISTACHIO", 50, -0.25), ("SNACKPACK_PISTACHIO", 200, -0.10)),
    "ROBOT_DISHES": (("ROBOT_IRONING", 200, -0.5), ("ROBOT_IRONING", 200, -0.05)), "ROBOT_IRONING": (("ROBOT_MOPPING", 20, -0.25), ("ROBOT_VACUUMING", 2, -0.25)), "ROBOT_LAUNDRY": (("ROBOT_MOPPING", 500, 1.0), ("ROBOT_VACUUMING", 500, 1.0)), "ROBOT_MOPPING": (("ROBOT_DISHES", 500, -0.05), ("ROBOT_VACUUMING", 20, -0.1)), "ROBOT_VACUUMING": (("ROBOT_MOPPING", 100, 0.05), ("ROBOT_LAUNDRY", 200, -0.25)),
}
HIST_PRODUCTS = {leader for signals in SIG.values() for leader, _, _ in signals}


def trade_take(product: str, depth: OrderDepth, pos: int, fair: float, take: float) -> List[Order]:
    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    buy_cap = max(0, LIMIT - pos)
    sell_cap = max(0, LIMIT + pos)
    orders: List[Order] = []
    if buy_cap > 0 and best_ask <= fair - take:
        qty = min(buy_cap, SIZE, -int(depth.sell_orders[best_ask]))
        if qty > 0:
            orders.append(Order(product, best_ask, qty))
    if sell_cap > 0 and best_bid >= fair + take:
        qty = min(sell_cap, SIZE, int(depth.buy_orders[best_bid]))
        if qty > 0:
            orders.append(Order(product, best_bid, -qty))
    return orders


def trade_book(product: str, depth: OrderDepth, pos: int, fair: float, take: float, edge: float, improve: int, plain: bool) -> List[Order]:
    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    buy_cap = max(0, LIMIT - pos)
    sell_cap = max(0, LIMIT + pos)
    orders: List[Order] = []
    if product in WALK and buy_cap > 0:
        for price in sorted(depth.sell_orders):
            if price > fair - take or buy_cap <= 0:
                break
            qty = min(buy_cap, SIZE, -int(depth.sell_orders[price]))
            if qty > 0:
                orders.append(Order(product, price, qty))
                buy_cap -= qty
    elif buy_cap > 0 and best_ask <= fair - take:
        qty = min(buy_cap, SIZE, -int(depth.sell_orders[best_ask]))
        if qty > 0:
            orders.append(Order(product, best_ask, qty))
            buy_cap -= qty
    if product in WALK and sell_cap > 0:
        for price in sorted(depth.buy_orders, reverse=True):
            if price < fair + take or sell_cap <= 0:
                break
            qty = min(sell_cap, SIZE, int(depth.buy_orders[price]))
            if qty > 0:
                orders.append(Order(product, price, -qty))
                sell_cap -= qty
    elif sell_cap > 0 and best_bid >= fair + take:
        qty = min(sell_cap, SIZE, int(depth.buy_orders[best_bid]))
        if qty > 0:
            orders.append(Order(product, best_bid, -qty))
            sell_cap -= qty
    if plain:
        bid, ask = best_bid, best_ask
    elif best_ask - best_bid > 2 * improve:
        bid, ask = best_bid + improve, best_ask - improve
    elif best_ask - best_bid > 1:
        bid, ask = best_bid + 1, best_ask - 1
    else:
        bid, ask = best_bid, best_ask
    if buy_cap > 0 and bid <= fair - edge:
        orders.append(Order(product, bid, min(SIZE, buy_cap)))
    if sell_cap > 0 and ask >= fair + edge:
        orders.append(Order(product, ask, -min(SIZE, sell_cap)))
    return orders


def trade_take_sized(product: str, depth: OrderDepth, pos: int, fair: float, take: float, size: int) -> List[Order]:
    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    buy_cap = max(0, LIMIT - pos)
    sell_cap = max(0, LIMIT + pos)
    orders: List[Order] = []
    if buy_cap > 0 and best_ask <= fair - take:
        qty = min(buy_cap, size, -int(depth.sell_orders[best_ask]))
        if qty > 0:
            orders.append(Order(product, best_ask, qty))
    if sell_cap > 0 and best_bid >= fair + take:
        qty = min(sell_cap, size, int(depth.buy_orders[best_bid]))
        if qty > 0:
            orders.append(Order(product, best_bid, -qty))
    return orders


def trade_book_sized(product: str, depth: OrderDepth, pos: int, fair: float, take: float, edge: float, improve: int, plain: bool, size: int, passive: bool) -> List[Order]:
    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    buy_cap = max(0, LIMIT - pos)
    sell_cap = max(0, LIMIT + pos)
    orders: List[Order] = []
    if product in WALK and buy_cap > 0:
        for price in sorted(depth.sell_orders):
            if price > fair - take or buy_cap <= 0:
                break
            qty = min(buy_cap, size, -int(depth.sell_orders[price]))
            if qty > 0:
                orders.append(Order(product, price, qty))
                buy_cap -= qty
    elif buy_cap > 0 and best_ask <= fair - take:
        qty = min(buy_cap, size, -int(depth.sell_orders[best_ask]))
        if qty > 0:
            orders.append(Order(product, best_ask, qty))
            buy_cap -= qty
    if product in WALK and sell_cap > 0:
        for price in sorted(depth.buy_orders, reverse=True):
            if price < fair + take or sell_cap <= 0:
                break
            qty = min(sell_cap, size, int(depth.buy_orders[price]))
            if qty > 0:
                orders.append(Order(product, price, -qty))
                sell_cap -= qty
    elif sell_cap > 0 and best_bid >= fair + take:
        qty = min(sell_cap, size, int(depth.buy_orders[best_bid]))
        if qty > 0:
            orders.append(Order(product, best_bid, -qty))
            sell_cap -= qty
    if not passive:
        return orders
    if plain:
        bid, ask = best_bid, best_ask
    elif best_ask - best_bid > 2 * improve:
        bid, ask = best_bid + improve, best_ask - improve
    elif best_ask - best_bid > 1:
        bid, ask = best_bid + 1, best_ask - 1
    else:
        bid, ask = best_bid, best_ask
    if buy_cap > 0 and bid <= fair - edge:
        orders.append(Order(product, bid, min(size, buy_cap)))
    if sell_cap > 0 and ask >= fair + edge:
        orders.append(Order(product, ask, -min(size, sell_cap)))
    return orders


def safe_orders(product: str, orders: List[Order], pos: int) -> List[Order]:
    if product not in ROUND5:
        return []
    buy_left = max(0, LIMIT - pos)
    sell_left = max(0, LIMIT + pos)
    clipped: List[Order] = []
    for order in orders:
        qty = int(order.quantity)
        if qty > 0:
            qty = min(qty, buy_left)
            if qty > 0:
                clipped.append(Order(product, int(order.price), qty))
                buy_left -= qty
        elif qty < 0:
            qty = min(-qty, sell_left)
            if qty > 0:
                clipped.append(Order(product, int(order.price), -qty))
                sell_left -= qty
    return clipped


def cat(product: str) -> str:
    if product.startswith("GALAXY"): return "GALAXY"
    if product.startswith("MICROCHIP"): return "MICROCHIP"
    if product.startswith("OXYGEN"): return "OXYGEN"
    if product.startswith("PANEL"): return "PANEL"
    if product.startswith("PEBBLES"): return "PEBBLES"
    if product.startswith("ROBOT"): return "ROBOT"
    if product.startswith("SLEEP"): return "SLEEP"
    if product.startswith("SNACKPACK"): return "SNACKPACK"
    if product.startswith("TRANSLATOR"): return "TRANSLATOR"
    return "UV"


def clip_add(out: List[Order], product: str, price: int, qty: int, buy_left: int, sell_left: int) -> int:
    if qty > 0:
        clipped = min(qty, buy_left)
    else:
        clipped = -min(-qty, sell_left)
    if clipped:
        out.append(Order(product, price, clipped))
    return clipped


def avg(values) -> float:
    return sum(values) / len(values) if values else 0.0


def final_safety(result: Dict[str, List[Order]], position: Dict[str, int]) -> Dict[str, List[Order]]:
    safe: Dict[str, List[Order]] = {}
    for product, orders in result.items():
        pos = int(position.get(product, 0))
        buy_left = max(0, LIMIT - pos)
        sell_left = max(0, LIMIT + pos)
        out: List[Order] = []
        for order in orders:
            qty = int(order.quantity)
            if qty > 0:
                qty = min(qty, buy_left)
                if qty > 0:
                    out.append(Order(product, int(order.price), qty))
                    buy_left -= qty
            elif qty < 0:
                qty = min(-qty, sell_left)
                if qty > 0:
                    out.append(Order(product, int(order.price), -qty))
                    sell_left -= qty
        safe[product] = out
    return safe


def regime_scale(product: str, mid: float, fair: float, spread: float, depth_total: int, mids: Dict[str, float], mid_hist) -> float:
    edge = fair - mid
    abs_edge = abs(edge)
    scale = 1.0
    if spread >= 18 and abs_edge < 4.0 * max(spread, 1.0):
        scale *= 0.55
    if spread >= 22 and abs_edge < 5.0 * max(spread, 1.0):
        return 0.0
    if depth_total < 14:
        scale *= 0.65
    if depth_total < 9 and abs_edge < 3.0 * max(spread, 1.0):
        return 0.0
    if len(mid_hist) >= 25:
        short_trend = mid_hist[-1] - mid_hist[-6]
        trend_len = min(40, len(mid_hist) - 1)
        trend = mid_hist[-1] - mid_hist[-1 - trend_len]
        if abs(short_trend) > 3.0 * max(spread, 1.0) and abs_edge < 4.0 * max(spread, 1.0):
            scale *= 0.65
        if edge * trend < 0 and abs(trend) > 4.0 * max(spread, 1.0) and abs_edge < 5.0 * max(spread, 1.0):
            return 0.0
        if edge * trend < 0 and abs(trend) > 2.5 * max(spread, 1.0):
            scale *= 0.80
    group = PRODUCT_GROUP.get(product)
    if group:
        peers = [p for p in GROUPS[group] if p != product and p in mids]
        if len(peers) >= 2:
            residual = mid - avg([mids[p] for p in peers])
            if edge * residual > 0 and abs(residual) > 2.0 * max(spread, 1.0):
                if abs_edge < 3.0 * max(spread, 1.0):
                    return 0.0
                scale *= 0.65
    if abs_edge < 0.75 * max(spread, 1.0):
        scale *= 0.75
    if scale < 0.25:
        return 0.0
    return min(1.0, scale)


class Trader:
    def basket_orders(self, state: TradingState, mids: Dict[str, float]) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {p: [] for p in state.order_depths}
        open_cat = {}
        for product, pos in state.position.items():
            if pos:
                c = cat(product)
                open_cat[c] = open_cat.get(c, 0) + 1
        for product, intercept, sd, entry, margin, legs in BASKET_MODELS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders or product not in mids:
                continue
            fair = intercept
            ok = True
            for other, weight in legs:
                mid = mids.get(other)
                if mid is None:
                    ok = False
                    break
                fair += weight * mid
            if not ok:
                continue
            pos = int(state.position.get(product, 0))
            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            buy_left = max(0, LIMIT - pos)
            sell_left = max(0, LIMIT + pos)
            z = (mids[product] - fair) / sd
            orders: List[Order] = []
            if pos > 0 and z > -EXIT_Z and sell_left:
                clip_add(orders, product, best_bid, -min(pos, int(depth.buy_orders[best_bid])), buy_left, sell_left)
            elif pos < 0 and z < EXIT_Z and buy_left:
                clip_add(orders, product, best_ask, min(-pos, -int(depth.sell_orders[best_ask])), buy_left, sell_left)
            else:
                c = cat(product)
                allowed = pos != 0 or open_cat.get(c, 0) < CAT_LIM
                entry *= ENTRY_SCALE
                if allowed and z > entry and best_bid - fair > margin and sell_left:
                    done = clip_add(orders, product, best_bid, -min(sell_left, int(depth.buy_orders[best_bid])), buy_left, sell_left)
                    if done:
                        open_cat[c] = open_cat.get(c, 0) + 1
                elif allowed and z < -entry and fair - best_ask > margin and buy_left:
                    done = clip_add(orders, product, best_ask, min(buy_left, -int(depth.sell_orders[best_ask])), buy_left, sell_left)
                    if done:
                        open_cat[c] = open_cat.get(c, 0) + 1
                elif allowed and z > entry * SOFT and sell_left:
                    price = max(best_bid + 1, best_ask - 1)
                    if price > fair + margin and price < best_ask:
                        clip_add(orders, product, price, -min(5, sell_left), buy_left, sell_left)
                elif allowed and z < -entry * SOFT and buy_left:
                    price = min(best_ask - 1, best_bid + 1)
                    if price < fair - margin and price > best_bid:
                        clip_add(orders, product, price, min(5, buy_left), buy_left, sell_left)
            result[product] = orders
        return result

    def run(self, state: TradingState):
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        hist = data.get("h", {})
        circle_hist = data.get("c", [])
        result: Dict[str, List[Order]] = {}
        mids = {}
        spreads = {}
        depths = {}

        for product, depth in state.order_depths.items():
            if product in ROUND5 and depth.buy_orders and depth.sell_orders:
                best_bid = max(depth.buy_orders)
                best_ask = min(depth.sell_orders)
                mids[product] = (best_bid + best_ask) / 2.0
                spreads[product] = best_ask - best_bid
                depths[product] = max(0, int(depth.buy_orders[best_bid])) + max(0, -int(depth.sell_orders[best_ask]))
        basket_result = self.basket_orders(state, mids)
        if "MICROCHIP_CIRCLE" in mids:
            circle_hist.append(mids["MICROCHIP_CIRCLE"])
            circle_hist = circle_hist[-110:]
        for product in HIST_PRODUCTS | REGIME_SELECTED:
            if product in mids:
                arr = hist.get(product, [])
                arr.append(mids[product])
                hist[product] = arr[-501:]

        for group in ACTIVE:
            for product in GROUPS[group]:
                depth = state.order_depths.get(product)
                if not depth or not depth.buy_orders or not depth.sell_orders:
                    result[product] = []
                    continue
                pos = int(state.position.get(product, 0))
                if product in BASKET_SELECTED:
                    result[product] = basket_result.get(product, [])
                    continue
                if product in MID:
                    fair = mids[product] + SHIFT.get(product, 0.0)
                    take = BIG
                    if product == "MICROCHIP_OVAL" and len(circle_hist) > 50:
                        fair += 1.25 * 0.067 * (circle_hist[-1] - circle_hist[-51])
                        take = 5.5
                    elif product == "MICROCHIP_SQUARE" and len(circle_hist) > 100:
                        fair += 0.75 * 0.138 * (circle_hist[-1] - circle_hist[-101])
                        take = 6.0
                else:
                    fair = FAIR[product]
                    take = TAKE[product]
                for leader, lag, weight in SIG.get(product, ()):
                    arr = hist.get(leader, [])
                    if len(arr) > lag:
                        fair += weight * (arr[-1] - arr[-1 - lag])
                if product in REGIME_SELECTED:
                    scale = regime_scale(product, mids[product], fair, spreads[product], depths[product], mids, hist.get(product, []))
                    if scale <= 0:
                        result[product] = []
                        continue
                    size = max(1, min(LIMIT, int(10 * scale)))
                    if take < BIG / 2:
                        take = take * TAKE_MULT + (1.0 - scale) * max(spreads[product], 1.0)
                    if product in TAKE_ONLY:
                        orders = trade_take_sized(product, depth, pos, fair, take, size)
                    else:
                        edge = EDGE[product] * EDGE_MULT + (1.0 - scale) * max(spreads[product], 1.0)
                        orders = trade_book_sized(product, depth, pos, fair, take, edge, IMP.get(product, 0), product in PLAIN_QUOTE, size, scale >= 0.75)
                    result[product] = safe_orders(product, orders, pos)
                    continue
                if product in TAKE_ONLY:
                    orders = trade_take(product, depth, pos, fair, take)
                else:
                    orders = trade_book(product, depth, pos, fair, take, EDGE[product], IMP.get(product, 0), product in PLAIN_QUOTE)
                result[product] = safe_orders(product, orders, pos)

        return final_safety(result, state.position), 0, json.dumps({"c": circle_hist, "h": hist}, separators=(",", ":"))
