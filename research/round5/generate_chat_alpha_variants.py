from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
BASE = ROOT / "prosperity_rust_backtester" / "traders" / "latest_trader.py"
OUT = ROOT / "research" / "round5" / "generated_traders_chat"

CATEGORIES = {
    "galaxy": [
        "GALAXY_SOUNDS_DARK_MATTER",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
    ],
    "sleep": [
        "SLEEP_POD_SUEDE",
        "SLEEP_POD_LAMB_WOOL",
        "SLEEP_POD_POLYESTER",
        "SLEEP_POD_NYLON",
        "SLEEP_POD_COTTON",
    ],
    "microchip": [
        "MICROCHIP_CIRCLE",
        "MICROCHIP_OVAL",
        "MICROCHIP_SQUARE",
        "MICROCHIP_RECTANGLE",
        "MICROCHIP_TRIANGLE",
    ],
    "pebbles": ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"],
    "robot": [
        "ROBOT_VACUUMING",
        "ROBOT_MOPPING",
        "ROBOT_DISHES",
        "ROBOT_LAUNDRY",
        "ROBOT_IRONING",
    ],
    "visor": ["UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"],
    "translator": [
        "TRANSLATOR_SPACE_GRAY",
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_VOID_BLUE",
    ],
    "panel": ["PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"],
    "oxygen": [
        "OXYGEN_SHAKE_MORNING_BREATH",
        "OXYGEN_SHAKE_EVENING_BREATH",
        "OXYGEN_SHAKE_MINT",
        "OXYGEN_SHAKE_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC",
    ],
    "snack": [
        "SNACKPACK_CHOCOLATE",
        "SNACKPACK_VANILLA",
        "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY",
        "SNACKPACK_RASPBERRY",
    ],
}

NAMED_PAIRS = [
    ("MICROCHIP_RECTANGLE", "MICROCHIP_SQUARE"),
    ("SNACKPACK_RASPBERRY", "SNACKPACK_VANILLA"),
    ("GALAXY_SOUNDS_SOLAR_FLAMES", "GALAXY_SOUNDS_SOLAR_WINDS"),
    ("SLEEP_POD_LAMB_WOOL", "SLEEP_POD_NYLON"),
]


def load_mid() -> pd.DataFrame:
    frames = [pd.read_csv(p, sep=";") for p in sorted(DATA.glob("prices_round_5_day_*.csv"))]
    df = pd.concat(frames, ignore_index=True)
    df["global_time"] = (df["day"] - df["day"].min()) * 1_000_000 + df["timestamp"]
    return df.pivot(index="global_time", columns="product", values="mid_price").sort_index()


def spread_stats(mid: pd.DataFrame, a: str, b: str) -> tuple[float, float]:
    spread = (mid[a] - mid[b]).dropna()
    return float(spread.mean()), float(spread.std(ddof=0))


def make_variant(base: str, *, pairs=None, hedges=None, cats=None) -> str:
    pairs = pairs or []
    hedges = hedges or []
    cats = cats or []
    constants = "\n"
    if pairs:
        constants += "PAIR=" + repr(pairs) + "\n"
    else:
        constants += "PAIR=[]\n"
    if hedges:
        constants += "HEDGE=" + repr(hedges) + "\n"
    else:
        constants += "HEDGE=[]\n"
    if cats:
        constants += "CAT=" + repr(cats) + "\n"
    else:
        constants += "CAT=[]\n"
    text = base.replace("\nclass Trader:", constants + "class Trader:")
    marker = "  if 'MICROCHIP_CIRCLE' in mids:\n"
    overlay = (
        "  sh={}\n"
        "  for a,b,m,s,c,t in PAIR:\n"
        "   if a in mids and b in mids:\n"
        "    r=mids[a]-mids[b]-m\n"
        "    if abs(r)>t*s:\n"
        "     v=c*r;sh[a]=sh.get(a,0)-v;sh[b]=sh.get(b,0)+v\n"
        "  for a,b,beta,inter,s,c,t in HEDGE:\n"
        "   if a in mids and b in mids:\n"
        "    r=mids[a]-inter-beta*mids[b]\n"
        "    if abs(r)>t*s:\n"
        "     v=c*r;sh[a]=sh.get(a,0)-v;sh[b]=sh.get(b,0)+beta*v\n"
        "  for ps,c,t in CAT:\n"
        "   zs=[]\n"
        "   for pp in ps:\n"
        "    if pp in mids and pp in M and pp in S:zs.append((pp,(mids[pp]-M[pp]-SHIFT.get(pp,0))/S[pp]))\n"
        "   if len(zs)>1:\n"
        "    avg=sum(z for _,z in zs)/len(zs)\n"
        "    for pp,z in zs:\n"
        "     r=z-avg\n"
        "     if abs(r)>t:sh[pp]=sh.get(pp,0)-c*r*S[pp]\n"
    )
    text = text.replace(marker, overlay + marker)
    text = text.replace("fair=M[p]+SHIFT.get(p,0);take=Z[p]*S[p];edge=EDGE[p]", "fair=M[p]+SHIFT.get(p,0)+sh.get(p,0);take=Z[p]*S[p];edge=EDGE[p]")
    text = text.replace("fair=mids[p]+SHIFT.get(p,0);take=10**9;edge=EDGE[p]", "fair=mids[p]+SHIFT.get(p,0)+sh.get(p,0);take=10**9;edge=EDGE[p]")
    return text


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = BASE.read_text()
    mid = load_mid()
    spreads = {pair: spread_stats(mid, *pair) for pair in NAMED_PAIRS}
    stationary = pd.read_csv(ROOT / "research" / "round5" / "stationary_spread_pairs.csv")
    hedges = []
    for row in stationary.head(12).itertuples(index=False):
        hedges.append((row.a, row.b, round(float(row.hedge_beta), 6), round(float(row.hedge_intercept), 3), round(float(row.hedged_resid_std), 3)))

    specs = []

    def write(name: str, *, pairs=None, hedge_rows=None, cat_rows=None) -> None:
        path = OUT / f"{name}.py"
        path.write_text(make_variant(base, pairs=pairs, hedges=hedge_rows, cats=cat_rows))
        specs.append({"name": name, "path": str(path.relative_to(ROOT)), "n_products": 50})

    for c in [0.05, 0.1, 0.2, 0.5, 1.0]:
        for t in [0.0, 0.5, 1.0]:
            pairs = [(a, b, round(m, 3), round(s, 3), c, t) for (a, b), (m, s) in spreads.items()]
            write(f"chat_named_pairs_c{str(c).replace('.','p')}_t{str(t).replace('.','p')}", pairs=pairs)

    for c in [0.05, 0.1, 0.2, 0.5]:
        for t in [0.0, 0.75, 1.25]:
            hedge_rows = [(a, b, beta, inter, s, c, t) for a, b, beta, inter, s in hedges]
            write(f"chat_hedged12_c{str(c).replace('.','p')}_t{str(t).replace('.','p')}", hedge_rows=hedge_rows)

    cat_sets = {
        "micro": ["microchip"],
        "snack": ["snack"],
        "panel": ["panel"],
        "pebbles": ["pebbles"],
        "chat4": ["microchip", "snack", "panel", "pebbles"],
        "all": list(CATEGORIES),
    }
    for label, cats in cat_sets.items():
        for c in [0.05, 0.1, 0.2, 0.5, 1.0]:
            for t in [0.0, 0.5, 1.0]:
                cat_rows = [(tuple(CATEGORIES[x]), c, t) for x in cats]
                write(f"chat_catz_{label}_c{str(c).replace('.','p')}_t{str(t).replace('.','p')}", cat_rows=cat_rows)

    manifest = OUT / "manifest.json"
    manifest.write_text(json.dumps(specs, indent=2))
    print(f"wrote {len(specs)} variants to {OUT}")


if __name__ == "__main__":
    main()
