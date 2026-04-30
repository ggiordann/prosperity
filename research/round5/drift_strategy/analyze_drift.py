from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = Path(__file__).resolve().parent

CATEGORIES = {
    "galaxy": [
        "GALAXY_SOUNDS_DARK_MATTER",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
    ],
    "sleep": ["SLEEP_POD_SUEDE", "SLEEP_POD_LAMB_WOOL", "SLEEP_POD_POLYESTER", "SLEEP_POD_NYLON", "SLEEP_POD_COTTON"],
    "microchip": ["MICROCHIP_CIRCLE", "MICROCHIP_OVAL", "MICROCHIP_SQUARE", "MICROCHIP_RECTANGLE", "MICROCHIP_TRIANGLE"],
    "pebbles": ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"],
    "robot": ["ROBOT_VACUUMING", "ROBOT_MOPPING", "ROBOT_DISHES", "ROBOT_LAUNDRY", "ROBOT_IRONING"],
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
    "snack": ["SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "SNACKPACK_PISTACHIO", "SNACKPACK_STRAWBERRY", "SNACKPACK_RASPBERRY"],
}

PRODUCT_TO_CATEGORY = {product: category for category, products in CATEGORIES.items() for product in products}
FINAL_LONG = {
    "OXYGEN_SHAKE_GARLIC",
    "GALAXY_SOUNDS_BLACK_HOLES",
    "PANEL_2X4",
    "UV_VISOR_RED",
    "SNACKPACK_STRAWBERRY",
    "SLEEP_POD_LAMB_WOOL",
}
FINAL_SHORT = {
    "MICROCHIP_OVAL",
    "PEBBLES_XS",
    "UV_VISOR_AMBER",
    "PEBBLES_S",
    "SNACKPACK_PISTACHIO",
    "SNACKPACK_CHOCOLATE",
}


def load_prices() -> pd.DataFrame:
    frames = [pd.read_csv(path, sep=";") for path in sorted(DATA.glob("prices_round_5_day_*.csv"))]
    df = pd.concat(frames, ignore_index=True)
    df["category"] = df["product"].map(PRODUCT_TO_CATEGORY)
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    return df


def product_day_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (day, product), g in df.groupby(["day", "product"], sort=True):
        mid = g["mid_price"].to_numpy(float)
        ret = np.diff(mid)
        t = np.arange(len(mid), dtype=float)
        corr = np.corrcoef(t, mid)[0, 1] if np.std(mid) else 0.0
        rows.append(
            {
                "day": int(day),
                "product": product,
                "category": PRODUCT_TO_CATEGORY[product],
                "start": float(mid[0]),
                "end": float(mid[-1]),
                "net_move": float(mid[-1] - mid[0]),
                "trend_r2": float(corr * corr),
                "up_tick_rate": float(np.mean(ret > 0)),
                "down_tick_rate": float(np.mean(ret < 0)),
                "zero_tick_rate": float(np.mean(ret == 0)),
                "avg_spread": float(g["spread"].mean()),
                "ret_std": float(np.std(ret)),
                "max_abs_jump": float(np.max(np.abs(ret))),
                "opening_100_move": float(mid[min(100, len(mid) - 1)] - mid[0]),
                "end_100_move": float(mid[-1] - mid[-101]),
                "buy_hold_long_pnl": float(10 * (g["bid_price_1"].iloc[-1] - g["ask_price_1"].iloc[0])),
                "buy_hold_short_pnl": float(10 * (g["bid_price_1"].iloc[0] - g["ask_price_1"].iloc[-1])),
            }
        )
    return pd.DataFrame(rows)


def product_summary(day_metrics: pd.DataFrame) -> pd.DataFrame:
    summary = (
        day_metrics.groupby(["category", "product"])
        .agg(
            net_mean=("net_move", "mean"),
            net_min=("net_move", "min"),
            net_max=("net_move", "max"),
            trend_r2_mean=("trend_r2", "mean"),
            avg_spread=("avg_spread", "mean"),
            max_abs_jump=("max_abs_jump", "max"),
            opening_100_mean=("opening_100_move", "mean"),
            end_100_mean=("end_100_move", "mean"),
            buy_hold_long_total=("buy_hold_long_pnl", "sum"),
            buy_hold_short_total=("buy_hold_short_pnl", "sum"),
        )
        .reset_index()
    )
    summary["same_sign_all_days"] = (summary["net_min"] > 0) | (summary["net_max"] < 0)
    summary["drift_direction"] = np.where(summary["net_min"] > 0, 1, np.where(summary["net_max"] < 0, -1, 0))
    summary["final_static_drift"] = summary["product"].isin(FINAL_LONG | FINAL_SHORT)
    summary["avoid_mean_reverting"] = summary["same_sign_all_days"] & (summary["net_mean"].abs() > 75)
    return summary.sort_values(["same_sign_all_days", "net_mean"], ascending=[False, False])


def step_events(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (day, product), g in df.groupby(["day", "product"], sort=True):
        mid = g["mid_price"].to_numpy(float)
        timestamps = g["timestamp"].to_numpy(int)
        ret = np.diff(mid)
        med = np.median(ret)
        mad = np.median(np.abs(ret - med))
        sigma = 1.4826 * mad if mad else np.std(ret)
        threshold = max(4 * sigma, 2.5 * g["spread"].mean(), 25)
        for i, move in enumerate(ret):
            if abs(move) < threshold:
                continue
            j = i + 1
            after_50 = mid[min(len(mid) - 1, j + 50)] - mid[i]
            after_200 = mid[min(len(mid) - 1, j + 200)] - mid[i]
            persistent = (
                np.sign(after_50) == np.sign(move)
                and abs(after_50) > 0.5 * abs(move)
            ) or (
                np.sign(after_200) == np.sign(move)
                and abs(after_200) > 0.5 * abs(move)
            )
            if persistent:
                rows.append(
                    {
                        "day": int(day),
                        "product": product,
                        "category": PRODUCT_TO_CATEGORY[product],
                        "timestamp": int(timestamps[j]),
                        "jump": float(move),
                        "threshold": float(threshold),
                        "after_50": float(after_50),
                        "after_200": float(after_200),
                    }
                )
    return pd.DataFrame(rows).sort_values("jump", key=lambda s: s.abs(), ascending=False)


def category_drift_and_leadership(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    drift_rows = []
    lead_rows = []
    for day, gday in df.groupby("day", sort=True):
        piv = gday.pivot(index="timestamp", columns="product", values="mid_price").sort_index()
        category_index = pd.DataFrame({category: piv[products].mean(axis=1) for category, products in CATEGORIES.items()})
        for category in CATEGORIES:
            series = category_index[category]
            drift_rows.append({"day": int(day), "category": category, "net_move": float(series.iloc[-1] - series.iloc[0])})
        for lag in (100, 200, 500):
            past = category_index.diff(lag)
            future = category_index.shift(-lag) - category_index
            valid = slice(lag, -lag)
            for leader in CATEGORIES:
                x = past[leader].iloc[valid].to_numpy()
                if np.std(x) == 0:
                    continue
                for follower in CATEGORIES:
                    if leader == follower:
                        continue
                    y = future[follower].iloc[valid].to_numpy()
                    if np.std(y):
                        lead_rows.append(
                            {
                                "day": int(day),
                                "lag": lag,
                                "leader": leader,
                                "follower": follower,
                                "corr": float(np.corrcoef(x, y)[0, 1]),
                            }
                        )
    drift = pd.DataFrame(drift_rows)
    leadership = (
        pd.DataFrame(lead_rows)
        .groupby(["lag", "leader", "follower"])
        .agg(corr_mean=("corr", "mean"), corr_min=("corr", "min"), same_sign_days=("corr", lambda s: int((np.sign(s) == np.sign(s.mean())).sum())))
        .reset_index()
        .sort_values("corr_mean", ascending=False)
    )
    return drift, leadership


def validation(day_metrics: pd.DataFrame) -> pd.DataFrame:
    cases = [
        ("train_day2_test_3_4", (2,), (3, 4)),
        ("train_day3_test_4", (3,), (4,)),
        ("train_2_3_test_4", (2, 3), (4,)),
        ("loo_train_3_4_test_2", (3, 4), (2,)),
        ("loo_train_2_4_test_3", (2, 4), (3,)),
        ("loo_train_2_3_test_4", (2, 3), (4,)),
        ("no_day2_train_3_4_test_2", (3, 4), (2,)),
    ]
    rows = []
    wide_net = day_metrics.pivot(index="product", columns="day", values="net_move")
    wide_long = day_metrics.pivot(index="product", columns="day", values="buy_hold_long_pnl")
    wide_short = day_metrics.pivot(index="product", columns="day", values="buy_hold_short_pnl")
    for threshold in (0, 50, 100, 200, 500, 750):
        for name, train_days, test_days in cases:
            selected = []
            pnl = 0.0
            for product, row in wide_net.iterrows():
                train = row.loc[list(train_days)]
                direction = int(np.sign(train.mean()))
                if direction == 0:
                    continue
                if not (np.sign(train) == direction).all():
                    continue
                if train.abs().min() < threshold:
                    continue
                selected.append(product)
                if direction > 0:
                    pnl += wide_long.loc[product, list(test_days)].sum()
                else:
                    pnl += wide_short.loc[product, list(test_days)].sum()
            rows.append(
                {
                    "case": name,
                    "threshold": threshold,
                    "selected_count": len(selected),
                    "selected_products": ",".join(selected),
                    "test_pnl": float(pnl),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_prices()
    day_metrics = product_day_metrics(df)
    summary = product_summary(day_metrics)
    steps = step_events(df)
    category_drift, leadership = category_drift_and_leadership(df)
    val = validation(day_metrics)

    day_metrics.to_csv(OUT / "product_day_metrics.csv", index=False)
    summary.to_csv(OUT / "product_drift_summary.csv", index=False)
    steps.to_csv(OUT / "step_events.csv", index=False)
    category_drift.to_csv(OUT / "category_drift.csv", index=False)
    leadership.to_csv(OUT / "category_leadership.csv", index=False)
    val.to_csv(OUT / "validation_summary.csv", index=False)

    final = summary[summary["final_static_drift"]]
    print(f"final drift products: {len(final)}")
    print(final[["product", "drift_direction", "net_mean", "net_min", "net_max", "buy_hold_long_total", "buy_hold_short_total"]].to_string(index=False))
    print(f"persistent step events: {len(steps)}")
    print(val[(val["threshold"] == 0)].to_string(index=False))


if __name__ == "__main__":
    main()
