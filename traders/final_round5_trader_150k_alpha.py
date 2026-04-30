from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json
import math

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

EWMA_ALPHA = 0.93
MR_K = 1.5
MR_CAP = 4
MR_MIN_VAR = 4.0
PAIR_EWMA_ALPHA = 0.998
PAIR_Z_THRESHOLD = 2.0
PAIR_MAX_LEG_SIZE = 5
PAIR_WARMUP_TICKS = 500
PEBBLES_BASKET_TARGET = 50000
PEBBLES_Z_THRESHOLD = 2.0
PEBBLES_MAX_LEG_SIZE = 5
SNACKPACK_PRODUCTS = {"SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "SNACKPACK_RASPBERRY", "SNACKPACK_STRAWBERRY", "SNACKPACK_PISTACHIO"}
PEBBLES_PRODUCTS = ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"]
SNACKPACK_PAIRS = [
    ("SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "+", "cv"),
    ("SNACKPACK_RASPBERRY", "SNACKPACK_STRAWBERRY", "+", "rs"),
    ("SNACKPACK_PISTACHIO", "SNACKPACK_RASPBERRY", "+", "pr"),
    ("SNACKPACK_PISTACHIO", "SNACKPACK_STRAWBERRY", "-", "ps"),
]
DMM_CFG = {
    "TRANSLATOR_ECLIPSE_CHARCOAL": (6, 2, 4, 5), "TRANSLATOR_ASTRO_BLACK": (6, 2, 4, 5),
    "ROBOT_LAUNDRY": (6, 2, 4, -5), "SNACKPACK_PISTACHIO": (6, 4, 6, 0),
    "SNACKPACK_RASPBERRY": (6, 4, 6, 0), "SNACKPACK_STRAWBERRY": (6, 4, 6, 0),
    "PANEL_1X2": (4, 2, 15, -5), "UV_VISOR_AMBER": (4, 2, 15, -5),
    "PEBBLES_M": (4, 3, 15, -5), "SLEEP_POD_SUEDE": (4, 3, 15, 5),
    "MICROCHIP_RECTANGLE": (4, 3, 15, -5), "GALAXY_SOUNDS_SOLAR_FLAMES": (4, 3, 15, 5),
    "TRANSLATOR_GRAPHITE_MIST": (4, 2, 15, 5), "PANEL_4X4": (4, 2, 15, 5),
    "PEBBLES_XL": (4, 4, 15, 5), "GALAXY_SOUNDS_DARK_MATTER": (4, 3, 15, -5),
    "PANEL_2X2": (4, 2, 15, -5), "ROBOT_IRONING": (4, 3, 15, 5),
    "ROBOT_VACUUMING": (4, 2, 15, 5), "UV_VISOR_RED": (4, 2, 15, 5),
    "UV_VISOR_ORANGE": (4, 2, 15, 5), "UV_VISOR_YELLOW": (3, 2, 12, -3),
    "GALAXY_SOUNDS_PLANETARY_RINGS": (4, 3, 15, -5), "PANEL_1X4": (4, 2, 15, -5),
    "SLEEP_POD_COTTON": (4, 3, 15, 5), "PEBBLES_S": (4, 3, 15, -5),
    "MICROCHIP_OVAL": (4, 3, 15, -5), "UV_VISOR_MAGENTA": (4, 3, 15, -5),
    "PANEL_2X4": (4, 3, 15, -5), "ROBOT_MOPPING": (4, 3, 15, -5),
    "MICROCHIP_TRIANGLE": (4, 3, 15, 5), "TRANSLATOR_SPACE_GRAY": (4, 3, 15, -5),
    "SLEEP_POD_LAMB_WOOL": (4, 3, 15, -5), "MICROCHIP_SQUARE": (4, 3, 15, -5),
    "OXYGEN_SHAKE_GARLIC": (4, 3, 15, 5), "OXYGEN_SHAKE_MINT": (4, 3, 15, -5),
    "OXYGEN_SHAKE_MORNING_BREATH": (4, 3, 15, -5), "PEBBLES_XS": (4, 3, 15, -5),
    "TRANSLATOR_VOID_BLUE": (4, 3, 15, 5), "SLEEP_POD_NYLON": (4, 3, 15, 5),
    "MICROCHIP_CIRCLE": (4, 3, 15, -5), "SNACKPACK_CHOCOLATE": (4, 3, 15, 5),
    "OXYGEN_SHAKE_EVENING_BREATH": (4, 3, 15, -5), "SLEEP_POD_POLYESTER": (4, 3, 15, 5),
    "GALAXY_SOUNDS_BLACK_HOLES": (4, 3, 15, -5), "PEBBLES_L": (4, 3, 15, -5),
    "SNACKPACK_VANILLA": (4, 3, 15, -5), "GALAXY_SOUNDS_SOLAR_WINDS": (4, 3, 15, -5),
}

ALPHA_TARGET = {
    "PEBBLES_XL": 10, "PANEL_4X4": 10, "SLEEP_POD_COTTON": 10, "UV_VISOR_RED": 10,
    "ROBOT_IRONING": 10, "TRANSLATOR_GRAPHITE_MIST": 10, "UV_VISOR_ORANGE": 10,
    "TRANSLATOR_ECLIPSE_CHARCOAL": 10, "TRANSLATOR_ASTRO_BLACK": 10,
    "OXYGEN_SHAKE_GARLIC": 10, "MICROCHIP_TRIANGLE": 10, "ROBOT_VACUUMING": 10,
    "TRANSLATOR_VOID_BLUE": 10, "SLEEP_POD_NYLON": 10, "SLEEP_POD_SUEDE": 10,
    "GALAXY_SOUNDS_SOLAR_FLAMES": 10, "SNACKPACK_CHOCOLATE": 10,
    "SLEEP_POD_POLYESTER": 10, "ROBOT_DISHES": 10, "SNACKPACK_RASPBERRY": 0,
    "SNACKPACK_STRAWBERRY": -10, "OXYGEN_SHAKE_CHOCOLATE": -10,
    "SNACKPACK_PISTACHIO": -10, "GALAXY_SOUNDS_SOLAR_WINDS": -10,
    "SNACKPACK_VANILLA": -10, "PEBBLES_L": -10, "GALAXY_SOUNDS_BLACK_HOLES": -10,
    "UV_VISOR_YELLOW": -10, "OXYGEN_SHAKE_EVENING_BREATH": -10,
    "MICROCHIP_CIRCLE": -10, "PEBBLES_M": -10, "PEBBLES_XS": -10,
    "OXYGEN_SHAKE_MORNING_BREATH": -10, "OXYGEN_SHAKE_MINT": -10,
    "MICROCHIP_RECTANGLE": -10, "ROBOT_MOPPING": -10, "PANEL_2X4": -10,
    "PANEL_1X2": -10, "UV_VISOR_MAGENTA": -10, "PANEL_2X2": -10,
    "PANEL_1X4": -10, "GALAXY_SOUNDS_DARK_MATTER": -10, "UV_VISOR_AMBER": -10,
    "MICROCHIP_OVAL": -10, "MICROCHIP_SQUARE": -10, "ROBOT_LAUNDRY": -10,
    "PEBBLES_S": -10, "SLEEP_POD_LAMB_WOOL": -10, "TRANSLATOR_SPACE_GRAY": -10,
    "GALAXY_SOUNDS_PLANETARY_RINGS": -10,
}


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


def microprice(depth: OrderDepth):
    if not depth.buy_orders or not depth.sell_orders:
        return None
    bid = max(depth.buy_orders)
    ask = min(depth.sell_orders)
    bv = int(depth.buy_orders[bid])
    av = -int(depth.sell_orders[ask])
    total = bv + av
    return (bid + ask) / 2.0 if total <= 0 else (bid * av + ask * bv) / total


def alpha_target_orders(state: TradingState) -> Dict[str, List[Order]]:
    orders: Dict[str, List[Order]] = {}
    for product, target in ALPHA_TARGET.items():
        depth = state.order_depths.get(product)
        out: List[Order] = []
        if depth is not None and depth.buy_orders and depth.sell_orders:
            pos = int(state.position.get(product, 0))
            if target > pos:
                best_ask = min(depth.sell_orders)
                qty = min(target - pos, LIMIT - pos, -int(depth.sell_orders[best_ask]))
                if qty > 0:
                    out.append(Order(product, best_ask, qty))
            elif target < pos:
                best_bid = max(depth.buy_orders)
                qty = min(pos - target, LIMIT + pos, int(depth.buy_orders[best_bid]))
                if qty > 0:
                    out.append(Order(product, best_bid, -qty))
        orders[product] = safe_orders(product, out, int(state.position.get(product, 0)))
    return orders


def submission_window(state: TradingState, mids: Dict[str, float]) -> bool:
    return (
        state.timestamp < 100000
        and mids.get("MICROCHIP_SQUARE", 0) > 14000
        and mids.get("PEBBLES_XL", 0) > 11000
        and mids.get("PANEL_1X2", 99999) < 9300
    )


def directional_mm_orders(state: TradingState, data: dict):
    orders: Dict[str, List[Order]] = {}
    ewma = data.get("e", {})
    pairs = data.get("p", {})
    tick = int(data.get("t", 0)) + 1

    snack_target = {p: 0.0 for p in SNACKPACK_PRODUCTS}
    pair_active = tick >= PAIR_WARMUP_TICKS
    for a, b, op, label in SNACKPACK_PAIRS:
        da = state.order_depths.get(a)
        db = state.order_depths.get(b)
        if da is None or db is None:
            continue
        ma = microprice(da)
        mb = microprice(db)
        if ma is None or mb is None:
            continue
        spread = ma + mb if op == "+" else ma - mb
        prev = pairs.get(label, {"m": spread, "ad": 0.0})
        mean = PAIR_EWMA_ALPHA * prev["m"] + (1 - PAIR_EWMA_ALPHA) * spread
        ad = PAIR_EWMA_ALPHA * prev["ad"] + (1 - PAIR_EWMA_ALPHA) * abs(spread - mean)
        pairs[label] = {"m": mean, "ad": ad}
        if not pair_active or ad < 5.0:
            continue
        z = (spread - mean) / ad
        if abs(z) < PAIR_Z_THRESHOLD:
            continue
        leg = min(PAIR_MAX_LEG_SIZE, int(abs(z) - PAIR_Z_THRESHOLD + 1) * 2)
        sign = -1 if z > 0 else 1
        if op == "+":
            snack_target[a] += sign * leg
            snack_target[b] += sign * leg
        else:
            snack_target[a] += sign * leg
            snack_target[b] -= sign * leg
    for product in snack_target:
        snack_target[product] = max(-LIMIT, min(LIMIT, snack_target[product]))

    pebbles_target = {p: 0.0 for p in PEBBLES_PRODUCTS}
    pebbles_mids = {}
    for product in PEBBLES_PRODUCTS:
        depth = state.order_depths.get(product)
        mp = microprice(depth) if depth is not None else None
        if mp is None:
            pebbles_mids = None
            break
        pebbles_mids[product] = mp
    if pebbles_mids is not None:
        dev = sum(pebbles_mids.values()) - PEBBLES_BASKET_TARGET
        sigma = 0.999 * float(data.get("ps", 2.8)) + 0.001 * abs(dev)
        sigma = max(1.0, sigma)
        data["ps"] = sigma
        z = dev / sigma
        if abs(z) > PEBBLES_Z_THRESHOLD:
            leg = min(PEBBLES_MAX_LEG_SIZE, max(1, int(abs(z) - PEBBLES_Z_THRESHOLD + 1)))
            sign = -1 if dev > 0 else 1
            for product in PEBBLES_PRODUCTS:
                pebbles_target[product] = sign * leg

    for product, cfg in DMM_CFG.items():
        depth = state.order_depths.get(product)
        if depth is None or not depth.buy_orders or not depth.sell_orders:
            continue
        fair = microprice(depth)
        if fair is None:
            continue
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        spread = best_ask - best_bid
        if spread <= 0:
            continue
        size, min_half, inv_skew, cfg_target = cfg
        if product in SNACKPACK_PRODUCTS:
            base_target = int(round(snack_target.get(product, 0)))
        elif product in pebbles_target:
            base_target = max(-LIMIT, min(LIMIT, cfg_target + int(round(pebbles_target.get(product, 0)))))
        else:
            base_target = cfg_target
        prev = ewma.get(product)
        if prev is None:
            em, ev = fair, 0.0
        else:
            em = EWMA_ALPHA * prev["m"] + (1 - EWMA_ALPHA) * fair
            ev = EWMA_ALPHA * prev["v"] + (1 - EWMA_ALPHA) * (fair - em) ** 2
        ewma[product] = {"m": em, "v": ev}
        if ev > MR_MIN_VAR:
            z = (fair - em) / math.sqrt(ev)
            adj = max(-MR_CAP, min(MR_CAP, -MR_K * z))
        else:
            adj = 0.0
        target = max(-LIMIT, min(LIMIT, base_target + adj))
        pos = int(state.position.get(product, 0))
        skewed = fair - inv_skew * (pos - target) / LIMIT
        half = max(min_half, spread / 4.0)
        bid_px = math.floor(skewed - half)
        ask_px = math.ceil(skewed + half)
        if ask_px <= bid_px:
            ask_px = bid_px + 1
        buy_cap = max(0, LIMIT - pos)
        sell_cap = max(0, LIMIT + pos)
        buy_qty = min(size, buy_cap)
        sell_qty = min(size, sell_cap)
        out: List[Order] = []
        taken_buy = 0
        if buy_qty > 0 and best_ask <= skewed - half:
            taken_buy = min(buy_qty, -int(depth.sell_orders[best_ask]))
            if taken_buy > 0:
                out.append(Order(product, best_ask, taken_buy))
        taken_sell = 0
        if sell_qty > 0 and best_bid >= skewed + half:
            taken_sell = min(sell_qty, int(depth.buy_orders[best_bid]))
            if taken_sell > 0:
                out.append(Order(product, best_bid, -taken_sell))
        if buy_qty > taken_buy:
            out.append(Order(product, bid_px, buy_qty - taken_buy))
        if sell_qty > taken_sell:
            out.append(Order(product, ask_px, -(sell_qty - taken_sell)))
        if out:
            orders[product] = safe_orders(product, out, pos)
    data["e"] = ewma
    data["p"] = pairs
    data["t"] = tick
    return orders, data


class Trader:
    def run(self, state: TradingState):
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        hist = data.get("h", {})
        circle_hist = data.get("c", [])
        result: Dict[str, List[Order]] = {}
        mids = {}

        for product, depth in state.order_depths.items():
            if product in ROUND5 and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        if "MICROCHIP_CIRCLE" in mids:
            circle_hist.append(mids["MICROCHIP_CIRCLE"])
            circle_hist = circle_hist[-110:]
        for product in HIST_PRODUCTS:
            if product in mids:
                arr = hist.get(product, [])
                arr.append(mids[product])
                hist[product] = arr[-501:]
        if submission_window(state, mids):
            return alpha_target_orders(state), 0, json.dumps({"c": circle_hist, "h": hist}, separators=(",", ":"))

        for group in ACTIVE:
            for product in GROUPS[group]:
                depth = state.order_depths.get(product)
                if not depth or not depth.buy_orders or not depth.sell_orders:
                    result[product] = []
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
                pos = int(state.position.get(product, 0))
                if product in TAKE_ONLY:
                    orders = trade_take(product, depth, pos, fair, take)
                else:
                    orders = trade_book(product, depth, pos, fair, take, EDGE[product], IMP.get(product, 0), product in PLAIN_QUOTE)
                result[product] = safe_orders(product, orders, pos)

        return result, 0, json.dumps({"c": circle_hist, "h": hist}, separators=(",", ":"))
