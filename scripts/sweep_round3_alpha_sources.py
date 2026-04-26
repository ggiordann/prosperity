from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUND3_DIR = REPO_ROOT / "prosperity_rust_backtester" / "datasets" / "round3"
OUT_DIR = REPO_ROOT / "analysis" / "round3_alpha_sweep"
ROUND3_DAYS = (0, 1, 2)
UNDERLYING = "VELVETFRUIT_EXTRACT"
OPTION_RE = re.compile(r"VEV_(\d+)")
OPTION_TTE_YEARS = 5.0 / 365.0

PRICE_COLS = [
    "bid_price_1",
    "bid_price_2",
    "bid_price_3",
    "ask_price_1",
    "ask_price_2",
    "ask_price_3",
]
VOL_COLS = [
    "bid_volume_1",
    "bid_volume_2",
    "bid_volume_3",
    "ask_volume_1",
    "ask_volume_2",
    "ask_volume_3",
]


@dataclass(frozen=True)
class SignalSpec:
    name: str
    source_family: str
    description: str


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes_call(spot: float, strike: float, volatility: float, tte_years: float) -> float:
    if spot <= 0.0 or strike <= 0.0 or tte_years <= 0.0:
        return float("nan")
    intrinsic = max(spot - strike, 0.0)
    if volatility <= 0.0:
        return intrinsic
    vol_sqrt_t = volatility * math.sqrt(tte_years)
    if vol_sqrt_t <= 0.0:
        return intrinsic
    d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * tte_years) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return spot * normal_cdf(d1) - strike * normal_cdf(d2)


def implied_volatility(
    call_price: float,
    spot: float,
    strike: float,
    tte_years: float,
    *,
    low: float = 1e-6,
    high: float = 5.0,
    tolerance: float = 1e-7,
) -> float:
    if not all(math.isfinite(v) for v in (call_price, spot, strike, tte_years)):
        return float("nan")
    if call_price < 0.0 or spot <= 0.0 or strike <= 0.0 or tte_years <= 0.0:
        return float("nan")
    intrinsic = max(spot - strike, 0.0)
    if call_price < intrinsic - tolerance or call_price > spot + tolerance:
        return float("nan")
    if abs(call_price - intrinsic) <= tolerance:
        return 0.0

    upper_price = black_scholes_call(spot, strike, high, tte_years)
    while math.isfinite(upper_price) and upper_price < call_price and high < 20.0:
        high *= 2.0
        upper_price = black_scholes_call(spot, strike, high, tte_years)
    if not math.isfinite(upper_price) or upper_price < call_price:
        return float("nan")

    for _ in range(80):
        mid = 0.5 * (low + high)
        mid_price = black_scholes_call(spot, strike, mid, tte_years)
        if abs(mid_price - call_price) <= tolerance:
            return mid
        if mid_price < call_price:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def load_prices() -> pd.DataFrame:
    frames = []
    for day in ROUND3_DAYS:
        path = ROUND3_DIR / f"prices_round_3_day_{day}.csv"
        frame = pd.read_csv(path, sep=";")
        frame["day"] = day
        frames.append(frame)
    prices = pd.concat(frames, ignore_index=True)
    prices = prices.sort_values(["product", "day", "timestamp"]).reset_index(drop=True)
    for col in VOL_COLS:
        prices[col] = prices[col].fillna(0.0)
    for col in PRICE_COLS:
        prices[col] = prices[col].astype(float)
    prices["mid_price"] = prices["mid_price"].astype(float)
    return prices


def load_trades() -> pd.DataFrame:
    frames = []
    for day in ROUND3_DAYS:
        path = ROUND3_DIR / f"trades_round_3_day_{day}.csv"
        frame = pd.read_csv(path, sep=";")
        frame["day"] = day
        frames.append(frame)
    trades = pd.concat(frames, ignore_index=True)
    trades = trades.sort_values(["symbol", "day", "timestamp"]).reset_index(drop=True)
    return trades


def zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if not math.isfinite(float(std)) or std == 0:
        return pd.Series(np.nan, index=series.index)
    return (series - series.mean()) / std


def corr(a: pd.Series, b: pd.Series) -> float:
    valid = a.notna() & b.notna()
    if int(valid.sum()) < 20:
        return float("nan")
    av = a[valid]
    bv = b[valid]
    if av.nunique(dropna=True) < 2 or bv.nunique(dropna=True) < 2:
        return float("nan")
    return float(av.corr(bv))


def sign_hit_rate(signal: pd.Series, future_return: pd.Series) -> float:
    valid = signal.notna() & future_return.notna() & (signal != 0) & (future_return != 0)
    if int(valid.sum()) < 20:
        return float("nan")
    s = signal[valid]
    r = future_return[valid]
    return float((((s > 0) & (r > 0)) | ((s < 0) & (r < 0))).mean())


def quantile_edge(signal: pd.Series, future_return: pd.Series, direction: float) -> float:
    signed = direction * signal
    valid = signed.notna() & future_return.notna()
    if int(valid.sum()) < 100:
        return float("nan")
    x = signed[valid]
    y = future_return[valid]
    low = x.quantile(0.2)
    high = x.quantile(0.8)
    top = y[x >= high]
    bottom = y[x <= low]
    if top.empty or bottom.empty:
        return float("nan")
    return float(top.mean() - bottom.mean())


def parse_strike(product: str) -> float:
    match = OPTION_RE.fullmatch(product)
    if match is None:
        return float("nan")
    return float(match.group(1))


def add_book_features(prices: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, SignalSpec]]:
    df = prices.copy()
    specs: dict[str, SignalSpec] = {}

    for i in (1, 2, 3):
        df[f"bid_volume_{i}_abs"] = df[f"bid_volume_{i}"].abs()
        df[f"ask_volume_{i}_abs"] = df[f"ask_volume_{i}"].abs()

    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    df["rel_spread"] = df["spread"] / df["mid_price"].replace(0, np.nan)
    df["bid_depth_1"] = df["bid_volume_1_abs"]
    df["ask_depth_1"] = df["ask_volume_1_abs"]
    df["bid_depth_3"] = df[["bid_volume_1_abs", "bid_volume_2_abs", "bid_volume_3_abs"]].sum(axis=1)
    df["ask_depth_3"] = df[["ask_volume_1_abs", "ask_volume_2_abs", "ask_volume_3_abs"]].sum(axis=1)
    df["total_depth_1"] = df["bid_depth_1"] + df["ask_depth_1"]
    df["total_depth_3"] = df["bid_depth_3"] + df["ask_depth_3"]
    df["imbalance_l1"] = (df["bid_depth_1"] - df["ask_depth_1"]) / df["total_depth_1"].replace(0, np.nan)
    df["imbalance_l3"] = (df["bid_depth_3"] - df["ask_depth_3"]) / df["total_depth_3"].replace(0, np.nan)
    df["microprice_l1"] = (
        df["ask_price_1"] * df["bid_depth_1"] + df["bid_price_1"] * df["ask_depth_1"]
    ) / df["total_depth_1"].replace(0, np.nan)
    df["micro_edge_l1"] = df["microprice_l1"] - df["mid_price"]

    bid_notional = sum(df[f"bid_price_{i}"].fillna(0) * df[f"bid_volume_{i}_abs"] for i in (1, 2, 3))
    ask_notional = sum(df[f"ask_price_{i}"].fillna(0) * df[f"ask_volume_{i}_abs"] for i in (1, 2, 3))
    df["weighted_bid_price_3"] = bid_notional / df["bid_depth_3"].replace(0, np.nan)
    df["weighted_ask_price_3"] = ask_notional / df["ask_depth_3"].replace(0, np.nan)
    df["microprice_l3"] = (
        df["weighted_ask_price_3"] * df["bid_depth_3"] + df["weighted_bid_price_3"] * df["ask_depth_3"]
    ) / df["total_depth_3"].replace(0, np.nan)
    df["micro_edge_l3"] = df["microprice_l3"] - df["mid_price"]
    df["book_pressure_3"] = df["imbalance_l3"] * df["spread"]
    df["depth_ratio_l3"] = np.log((df["bid_depth_3"] + 1.0) / (df["ask_depth_3"] + 1.0))
    df["bid_wall_1"] = df["bid_depth_1"] / df["bid_depth_3"].replace(0, np.nan)
    df["ask_wall_1"] = df["ask_depth_1"] / df["ask_depth_3"].replace(0, np.nan)
    df["wall_skew_1"] = df["bid_wall_1"] - df["ask_wall_1"]
    df["bid_gap_12"] = df["bid_price_1"] - df["bid_price_2"]
    df["ask_gap_12"] = df["ask_price_2"] - df["ask_price_1"]
    df["book_slope_skew"] = df["bid_gap_12"].fillna(0) - df["ask_gap_12"].fillna(0)

    base_specs = {
        "spread": ("spread_regime", "Visible best spread."),
        "rel_spread": ("spread_regime", "Best spread scaled by mid."),
        "imbalance_l1": ("book_imbalance", "Top-of-book volume imbalance."),
        "imbalance_l3": ("book_imbalance", "Three-level volume imbalance."),
        "micro_edge_l1": ("microprice", "Level-1 microprice minus mid."),
        "micro_edge_l3": ("microprice", "Three-level microprice minus mid."),
        "book_pressure_3": ("book_imbalance", "Three-level imbalance scaled by spread."),
        "depth_ratio_l3": ("book_depth", "Log bid/ask depth ratio across three levels."),
        "total_depth_1": ("liquidity_depth", "Top level displayed depth."),
        "total_depth_3": ("liquidity_depth", "Displayed depth across three levels."),
        "wall_skew_1": ("book_walls", "Top-level wall concentration skew."),
        "book_slope_skew": ("book_shape", "Bid-side versus ask-side level spacing."),
    }
    for name, (family, desc) in base_specs.items():
        specs[name] = SignalSpec(name, family, desc)

    grouped = df.groupby(["product", "day"], sort=False)
    df["spread_change_1"] = grouped["spread"].diff()
    df["depth_change_l3"] = grouped["total_depth_3"].diff()
    df["imbalance_change_l3"] = grouped["imbalance_l3"].diff()
    for name, family, desc in [
        ("spread_change_1", "spread_regime", "One-tick spread change."),
        ("depth_change_l3", "liquidity_depth", "One-tick displayed depth change."),
        ("imbalance_change_l3", "book_imbalance", "One-tick three-level imbalance change."),
    ]:
        specs[name] = SignalSpec(name, family, desc)

    prev_bid = grouped["bid_price_1"].shift(1)
    prev_ask = grouped["ask_price_1"].shift(1)
    prev_bid_vol = grouped["bid_depth_1"].shift(1)
    prev_ask_vol = grouped["ask_depth_1"].shift(1)
    bid_now = df["bid_price_1"]
    ask_now = df["ask_price_1"]
    bid_vol_now = df["bid_depth_1"]
    ask_vol_now = df["ask_depth_1"]
    bid_ofi = np.select(
        [bid_now > prev_bid, bid_now == prev_bid, bid_now < prev_bid],
        [bid_vol_now, bid_vol_now - prev_bid_vol, -prev_bid_vol],
        default=np.nan,
    )
    ask_ofi = np.select(
        [ask_now < prev_ask, ask_now == prev_ask, ask_now > prev_ask],
        [-ask_vol_now, -(ask_vol_now - prev_ask_vol), prev_ask_vol],
        default=np.nan,
    )
    df["ofi_l1"] = pd.Series(bid_ofi + ask_ofi, index=df.index)
    specs["ofi_l1"] = SignalSpec("ofi_l1", "book_order_flow", "Cont-style top-of-book order-flow imbalance.")
    for window in (3, 5, 10, 20):
        name = f"ofi_l1_roll_{window}"
        df[name] = grouped["ofi_l1"].transform(lambda s, w=window: s.rolling(w, min_periods=1).sum())
        specs[name] = SignalSpec(name, "book_order_flow", f"Rolling {window}-tick top-of-book order-flow imbalance.")

    return df, specs


def add_return_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, SignalSpec]]:
    out = df.copy()
    specs: dict[str, SignalSpec] = {}
    grouped = out.groupby(["product", "day"], sort=False)
    for lag in (1, 2, 3, 5, 10, 20, 50):
        name = f"mid_momentum_{lag}"
        out[name] = out["mid_price"] - grouped["mid_price"].shift(lag)
        specs[name] = SignalSpec(name, "price_momentum", f"Mid-price momentum over {lag} ticks.")
        inv_name = f"mid_reversion_{lag}"
        out[inv_name] = -out[name]
        specs[inv_name] = SignalSpec(inv_name, "price_reversion", f"Negative {lag}-tick mid-price momentum.")

    for window in (5, 10, 20, 50, 100):
        mean_name = f"mid_zscore_{window}"
        rolling_mean = grouped["mid_price"].transform(lambda s, w=window: s.rolling(w, min_periods=max(3, w // 3)).mean())
        rolling_std = grouped["mid_price"].transform(lambda s, w=window: s.rolling(w, min_periods=max(3, w // 3)).std(ddof=0))
        out[mean_name] = (out["mid_price"] - rolling_mean) / rolling_std.replace(0, np.nan)
        specs[mean_name] = SignalSpec(mean_name, "price_reversion", f"Mid-price z-score over {window} ticks.")

        vol_name = f"realized_abs_ret_{window}"
        out[vol_name] = grouped["mid_price"].diff().abs().groupby([out["product"], out["day"]]).transform(
            lambda s, w=window: s.rolling(w, min_periods=max(3, w // 3)).mean()
        )
        specs[vol_name] = SignalSpec(vol_name, "volatility_regime", f"Rolling absolute return over {window} ticks.")

    return out, specs


def add_trade_features(df: pd.DataFrame, trades: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, SignalSpec]]:
    specs: dict[str, SignalSpec] = {}
    quote = df[["day", "timestamp", "product", "mid_price", "bid_price_1", "ask_price_1"]]
    trade_mid = trades.merge(
        quote,
        left_on=["day", "timestamp", "symbol"],
        right_on=["day", "timestamp", "product"],
        how="left",
    )
    trade_mid["trade_sign"] = np.where(
        trade_mid["price"] > trade_mid["mid_price"],
        1.0,
        np.where(trade_mid["price"] < trade_mid["mid_price"], -1.0, 0.0),
    )
    trade_mid["signed_qty"] = trade_mid["trade_sign"] * trade_mid["quantity"]
    trade_mid["signed_notional"] = trade_mid["signed_qty"] * trade_mid["price"]
    trade_mid["price_edge"] = trade_mid["price"] - trade_mid["mid_price"]

    agg = (
        trade_mid.groupby(["day", "timestamp", "symbol"], as_index=False)
        .agg(
            trade_count=("quantity", "count"),
            trade_qty=("quantity", "sum"),
            signed_trade_qty=("signed_qty", "sum"),
            signed_trade_notional=("signed_notional", "sum"),
            avg_trade_price_edge=("price_edge", "mean"),
        )
        .rename(columns={"symbol": "product"})
    )
    out = df.merge(agg, on=["day", "timestamp", "product"], how="left")
    for col in ["trade_count", "trade_qty", "signed_trade_qty", "signed_trade_notional", "avg_trade_price_edge"]:
        out[col] = out[col].fillna(0.0)

    out["trade_qty_imbalance"] = out["signed_trade_qty"] / out["trade_qty"].replace(0, np.nan)
    for name, family, desc in [
        ("trade_count", "trade_flow", "Public trade count at this timestamp."),
        ("trade_qty", "trade_flow", "Public traded quantity at this timestamp."),
        ("signed_trade_qty", "trade_flow", "Signed public traded quantity at this timestamp."),
        ("signed_trade_notional", "trade_flow", "Signed public traded notional at this timestamp."),
        ("avg_trade_price_edge", "trade_flow", "Average trade price minus contemporaneous mid."),
        ("trade_qty_imbalance", "trade_flow", "Signed quantity divided by total trade quantity."),
    ]:
        specs[name] = SignalSpec(name, family, desc)

    grouped = out.groupby(["product", "day"], sort=False)
    for window in (3, 5, 10, 20, 50):
        for base in ("trade_count", "trade_qty", "signed_trade_qty"):
            name = f"{base}_roll_{window}"
            out[name] = grouped[base].transform(lambda s, w=window: s.rolling(w, min_periods=1).sum())
            specs[name] = SignalSpec(name, "trade_flow", f"Rolling {window}-tick {base.replace('_', ' ')}.")

    out["time_since_trade"] = grouped["trade_count"].transform(
        lambda s: s.ne(0).cumsum().groupby(s.ne(0).cumsum()).cumcount()
    )
    specs["time_since_trade"] = SignalSpec("time_since_trade", "trade_flow", "Ticks since the latest public trade.")
    return out, specs


def add_time_of_day_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, SignalSpec]]:
    out = df.copy()
    specs: dict[str, SignalSpec] = {}
    out["time_bucket_20"] = pd.cut(out["timestamp"], bins=20, labels=False, include_lowest=True).astype(int)
    out["time_bucket_50"] = pd.cut(out["timestamp"], bins=50, labels=False, include_lowest=True).astype(int)
    for buckets in (20, 50):
        bucket_col = f"time_bucket_{buckets}"
        signal_col = f"tod_lodo_mean_ret_{buckets}"
        out[signal_col] = np.nan
        for day in ROUND3_DAYS:
            train = out[out["day"] != day]
            means = train.groupby(["product", bucket_col])["ret_fwd_1"].mean()
            test_idx = out.index[out["day"] == day]
            keys = list(zip(out.loc[test_idx, "product"], out.loc[test_idx, bucket_col]))
            out.loc[test_idx, signal_col] = [means.get(key, np.nan) for key in keys]
        specs[signal_col] = SignalSpec(
            signal_col,
            "time_seasonality",
            f"Leave-one-day-out time-of-day mean next return over {buckets} buckets.",
        )
    return out, specs


def add_option_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, SignalSpec], pd.DataFrame]:
    out = df.copy()
    specs: dict[str, SignalSpec] = {}
    out["strike"] = out["product"].map(parse_strike)
    under = out[out["product"] == UNDERLYING][["day", "timestamp", "mid_price", "micro_edge_l1", "imbalance_l3"]].rename(
        columns={
            "mid_price": "underlying_mid",
            "micro_edge_l1": "underlying_micro_edge_l1",
            "imbalance_l3": "underlying_imbalance_l3",
        }
    )
    out = out.merge(under, on=["day", "timestamp"], how="left")
    out["moneyness"] = np.where(out["strike"].notna(), out["underlying_mid"] - out["strike"], np.nan)
    out["log_moneyness"] = np.log(out["underlying_mid"] / out["strike"]).replace([np.inf, -np.inf], np.nan)
    specs["moneyness"] = SignalSpec("moneyness", "options_moneyness", "Underlying mid minus option strike.")
    specs["log_moneyness"] = SignalSpec("log_moneyness", "options_moneyness", "Log underlying/strike moneyness.")
    specs["underlying_micro_edge_l1"] = SignalSpec(
        "underlying_micro_edge_l1",
        "cross_underlying",
        "Underlying microprice edge aligned to each product timestamp.",
    )
    specs["underlying_imbalance_l3"] = SignalSpec(
        "underlying_imbalance_l3",
        "cross_underlying",
        "Underlying three-level book imbalance aligned to each product timestamp.",
    )

    out["intrinsic_value"] = np.maximum(out["underlying_mid"] - out["strike"], 0.0)
    out["option_time_value"] = out["mid_price"] - out["intrinsic_value"]
    out["option_time_value_pct_spot"] = out["option_time_value"] / out["underlying_mid"].replace(0, np.nan)
    for name, desc in [
        ("intrinsic_value", "Call intrinsic value from underlying mid and strike."),
        ("option_time_value", "Option mid minus intrinsic value."),
        ("option_time_value_pct_spot", "Option time value scaled by underlying spot."),
    ]:
        specs[name] = SignalSpec(name, "options_value", desc)

    option_mask = out["strike"].notna()
    option_rows = out.loc[
        option_mask,
        ["day", "timestamp", "product", "strike", "mid_price", "underlying_mid", "log_moneyness"],
    ].copy()
    option_rows = option_rows[(option_rows["mid_price"] > 0) & option_rows["underlying_mid"].notna()]
    option_rows = option_rows.replace([np.inf, -np.inf], np.nan).dropna(subset=["log_moneyness"])

    fits = []
    for _, group in option_rows.groupby(["day", "timestamp"], sort=False):
        valid = group.dropna(subset=["mid_price", "log_moneyness"])
        if len(valid) < 3:
            continue
        x = valid["log_moneyness"].to_numpy(dtype=float)
        y = valid["mid_price"].to_numpy(dtype=float)
        try:
            coeff = np.polyfit(x, y, 2)
            fitted = np.polyval(coeff, x)
        except np.linalg.LinAlgError:
            continue
        temp = valid[["day", "timestamp", "product"]].copy()
        temp["option_price_fit"] = fitted
        temp["option_price_resid"] = valid["mid_price"].to_numpy(dtype=float) - fitted
        temp["option_price_resid_pct"] = temp["option_price_resid"] / valid["underlying_mid"].to_numpy(dtype=float)
        fits.append(temp)

    if fits:
        option_fit = pd.concat(fits, ignore_index=True)
        out = out.merge(option_fit, on=["day", "timestamp", "product"], how="left")
    else:
        out["option_price_fit"] = np.nan
        out["option_price_resid"] = np.nan
        out["option_price_resid_pct"] = np.nan
        option_fit = pd.DataFrame()

    for name, desc in [
        ("option_price_fit", "Timestamp cross-sectional fitted option mid."),
        ("option_price_resid", "Option mid residual versus timestamp price smile fit."),
        ("option_price_resid_pct", "Option price residual scaled by underlying spot."),
    ]:
        specs[name] = SignalSpec(name, "options_relative_value", desc)
    return out, specs, option_fit


def add_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    grouped = out.groupby(["product", "day"], sort=False)
    for horizon in (1, 2, 3, 5, 10, 20):
        out[f"mid_fwd_{horizon}"] = grouped["mid_price"].shift(-horizon)
        out[f"ret_fwd_{horizon}"] = out[f"mid_fwd_{horizon}"] - out["mid_price"]
        out[f"ret_fwd_pct_{horizon}"] = out[f"ret_fwd_{horizon}"] / out["mid_price"].replace(0, np.nan)
        out[f"abs_ret_fwd_{horizon}"] = out[f"ret_fwd_{horizon}"].abs()
    return out


def build_cross_product_signals(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, SignalSpec]]:
    out = df.copy()
    specs: dict[str, SignalSpec] = {}
    products = sorted(out["product"].unique())
    base = out[["day", "timestamp", "product", "ret_fwd_1", "micro_edge_l1", "imbalance_l3"]].copy()
    pivot_ret = base.pivot_table(index=["day", "timestamp"], columns="product", values="ret_fwd_1", aggfunc="first")
    pivot_micro = base.pivot_table(index=["day", "timestamp"], columns="product", values="micro_edge_l1", aggfunc="first")
    pivot_imb = base.pivot_table(index=["day", "timestamp"], columns="product", values="imbalance_l3", aggfunc="first")

    cross_cols = []
    for source in products:
        if source == UNDERLYING:
            continue
        for lag in (1, 3, 5):
            col = f"xprod_{source}_ret_lag_{lag}"
            signal = pivot_ret.groupby(level=0)[source].shift(lag)
            signal.name = col
            cross_cols.append(signal)
            specs[col] = SignalSpec(col, "cross_product_lead_lag", f"{source} one-step return lagged {lag} ticks.")

    for source in (UNDERLYING, "HYDROGEL_PACK"):
        if source not in products:
            continue
        for frame, suffix, family in [
            (pivot_micro, "micro_edge_l1", "cross_product_book"),
            (pivot_imb, "imbalance_l3", "cross_product_book"),
        ]:
            col = f"xprod_{source}_{suffix}"
            signal = frame[source]
            signal.name = col
            cross_cols.append(signal)
            specs[col] = SignalSpec(col, family, f"{source} {suffix} aligned to all products.")

    if not cross_cols:
        return out, specs
    cross = pd.concat(cross_cols, axis=1).reset_index()
    out = out.merge(cross, on=["day", "timestamp"], how="left")
    return out, specs


def evaluate_signal(df: pd.DataFrame, signal_name: str, spec: SignalSpec, product: str) -> dict[str, object]:
    signal = df[signal_name]
    ret = df["ret_fwd_1"]
    c1 = corr(signal, ret)
    direction = 1.0 if not math.isfinite(c1) or c1 >= 0 else -1.0
    signed = direction * signal
    daily_corrs = []
    for _, day_df in df.groupby("day", sort=True):
        day_corr = corr(direction * day_df[signal_name], day_df["ret_fwd_1"])
        if math.isfinite(day_corr):
            daily_corrs.append(day_corr)

    valid = signal.notna() & ret.notna()
    nonzero = valid & (signal != 0)
    signed_z = signed.groupby([df["product"], df["day"]]).transform(zscore)
    return {
        "product": product,
        "signal": signal_name,
        "source_family": spec.source_family,
        "description": spec.description,
        "n": int(valid.sum()),
        "nonzero_n": int(nonzero.sum()),
        "coverage": float(valid.mean()) if len(valid) else float("nan"),
        "corr_fwd1": c1,
        "abs_corr_fwd1": abs(c1) if math.isfinite(c1) else float("nan"),
        "direction": "positive" if direction > 0 else "inverted",
        "directed_corr_fwd1": corr(signed, ret),
        "directed_corr_fwd5": corr(signed, df["ret_fwd_5"]),
        "directed_corr_fwd10": corr(signed, df["ret_fwd_10"]),
        "directed_hit_rate": sign_hit_rate(signed, ret),
        "directed_quantile_edge": quantile_edge(signal, ret, direction),
        "directed_z_proxy_pnl": float((signed_z.fillna(0) * ret.fillna(0)).sum()),
        "mean_signal": float(signal.mean()) if valid.any() else float("nan"),
        "std_signal": float(signal.std()) if valid.any() else float("nan"),
        "positive_day_fraction": float(np.mean([value > 0 for value in daily_corrs])) if daily_corrs else float("nan"),
        "day_corr_min": float(np.min(daily_corrs)) if daily_corrs else float("nan"),
        "day_corr_median": float(np.median(daily_corrs)) if daily_corrs else float("nan"),
    }


def evaluate_vol_signal(df: pd.DataFrame, signal_name: str, spec: SignalSpec, product: str) -> dict[str, object]:
    signal = df[signal_name]
    abs_ret = df["abs_ret_fwd_5"]
    c = corr(signal, abs_ret)
    direction = 1.0 if not math.isfinite(c) or c >= 0 else -1.0
    valid = signal.notna() & abs_ret.notna()
    return {
        "product": product,
        "signal": signal_name,
        "source_family": spec.source_family,
        "description": spec.description,
        "n": int(valid.sum()),
        "corr_abs_fwd5": c,
        "abs_corr_abs_fwd5": abs(c) if math.isfinite(c) else float("nan"),
        "direction": "positive" if direction > 0 else "inverted",
        "directed_corr_abs_fwd5": corr(direction * signal, abs_ret),
        "coverage": float(valid.mean()) if len(valid) else float("nan"),
    }


def source_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    frame = pd.DataFrame(rows)
    frame = frame.replace([np.inf, -np.inf], np.nan)
    out = []
    for family, group in frame.groupby("source_family", sort=True):
        viable = group[(group["n"] >= 1000) & (group["directed_corr_fwd1"] >= 0.03)]
        top = group.sort_values(["directed_corr_fwd1", "directed_z_proxy_pnl"], ascending=False).head(5)
        out.append(
            {
                "source_family": family,
                "signals_tested": int(group["signal"].nunique()),
                "product_signal_rows": int(len(group)),
                "median_directed_corr_fwd1": float(group["directed_corr_fwd1"].median()),
                "max_directed_corr_fwd1": float(group["directed_corr_fwd1"].max()),
                "median_positive_day_fraction": float(group["positive_day_fraction"].median()),
                "viable_rows_corr_ge_0p03": int(len(viable)),
                "top_examples": "; ".join(f"{r.product}:{r.signal}={r.directed_corr_fwd1:.3f}" for r in top.itertuples()),
            }
        )
    return out


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_report(
    signal_rows: list[dict[str, object]],
    vol_rows: list[dict[str, object]],
    summary_rows: list[dict[str, object]],
) -> str:
    signal_frame = pd.DataFrame(signal_rows).replace([np.inf, -np.inf], np.nan)
    vol_frame = pd.DataFrame(vol_rows).replace([np.inf, -np.inf], np.nan)
    summary_frame = pd.DataFrame(summary_rows).replace([np.inf, -np.inf], np.nan)

    top = signal_frame[signal_frame["n"] >= 1000].sort_values(
        ["directed_corr_fwd1", "positive_day_fraction", "directed_z_proxy_pnl"],
        ascending=False,
    ).head(30)
    top_vol = vol_frame[vol_frame["n"] >= 1000].sort_values("directed_corr_abs_fwd5", ascending=False).head(12)
    viable = summary_frame.sort_values("max_directed_corr_fwd1", ascending=False)

    lines = [
        "# Round 3 Alpha Source Sweep",
        "",
        "Signals are evaluated per product against next-tick mid-price return. Negative raw correlations are automatically marked as `inverted` so contrarian versions are not thrown away.",
        "",
        "## Source Family Summary",
        "",
        "| source_family | signals_tested | median_corr | max_corr | viable_rows | top_examples |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in viable.itertuples(index=False):
        lines.append(
            f"| {row.source_family} | {row.signals_tested} | {row.median_directed_corr_fwd1:.4f} | "
            f"{row.max_directed_corr_fwd1:.4f} | {row.viable_rows_corr_ge_0p03} | {row.top_examples} |"
        )

    lines.extend(
        [
            "",
            "## Top Directional Signals",
            "",
            "| product | signal | family | direction | corr_fwd1 | corr_fwd5 | hit_rate | day_frac |",
            "|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in top.itertuples(index=False):
        lines.append(
            f"| {row.product} | {row.signal} | {row.source_family} | {row.direction} | "
            f"{row.directed_corr_fwd1:.4f} | {row.directed_corr_fwd5:.4f} | "
            f"{row.directed_hit_rate:.4f} | {row.positive_day_fraction:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Top Volatility/Regime Signals",
            "",
            "| product | signal | family | direction | corr_abs_fwd5 |",
            "|---|---|---|---|---:|",
        ]
    )
    for row in top_vol.itertuples(index=False):
        lines.append(
            f"| {row.product} | {row.signal} | {row.source_family} | {row.direction} | {row.directed_corr_abs_fwd5:.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prices = add_forward_returns(load_prices())
    trades = load_trades()

    specs: dict[str, SignalSpec] = {}
    prices, new_specs = add_book_features(prices)
    specs.update(new_specs)
    prices, new_specs = add_return_features(prices)
    specs.update(new_specs)
    prices, new_specs = add_trade_features(prices, trades)
    specs.update(new_specs)
    prices, new_specs = add_time_of_day_features(prices)
    specs.update(new_specs)
    prices, new_specs, option_fit = add_option_features(prices)
    specs.update(new_specs)
    prices, new_specs = build_cross_product_signals(prices)
    specs.update(new_specs)

    # Keep forward returns after merges, and create a few composite signals once all inputs exist.
    composite_specs = {
        "micro_l1_plus_inv_imb_l3": SignalSpec(
            "micro_l1_plus_inv_imb_l3",
            "composite_book",
            "Level-1 microprice edge plus inverted three-level imbalance.",
        ),
        "micro_l3_plus_ofi_10": SignalSpec(
            "micro_l3_plus_ofi_10",
            "composite_book",
            "Three-level microprice edge plus rolling top-of-book OFI.",
        ),
        "under_micro_plus_option_price_resid": SignalSpec(
            "under_micro_plus_option_price_resid",
            "composite_options",
            "Underlying microprice plus option price-smile residual.",
        ),
    }
    prices["micro_l1_plus_inv_imb_l3"] = zscore(prices["micro_edge_l1"].fillna(0)) - zscore(prices["imbalance_l3"].fillna(0))
    prices["micro_l3_plus_ofi_10"] = zscore(prices["micro_edge_l3"].fillna(0)) + zscore(prices["ofi_l1_roll_10"].fillna(0))
    prices["under_micro_plus_option_price_resid"] = zscore(prices["underlying_micro_edge_l1"].fillna(0)) - zscore(
        prices["option_price_resid"].fillna(0)
    )
    specs.update(composite_specs)

    vol_signal_names = [name for name, spec in specs.items() if spec.source_family in {"volatility_regime", "spread_regime", "liquidity_depth"}]
    signal_names = sorted(specs)
    signal_rows: list[dict[str, object]] = []
    vol_rows: list[dict[str, object]] = []
    for product, product_df in prices.groupby("product", sort=True):
        product_df = product_df.sort_values(["day", "timestamp"]).reset_index(drop=True)
        for signal_name in signal_names:
            if signal_name not in product_df.columns:
                continue
            if product_df[signal_name].notna().sum() < 20:
                continue
            signal_rows.append(evaluate_signal(product_df, signal_name, specs[signal_name], product))
            if signal_name in vol_signal_names:
                vol_rows.append(evaluate_vol_signal(product_df, signal_name, specs[signal_name], product))

    signal_rows = sorted(
        signal_rows,
        key=lambda r: (
            float(r["directed_corr_fwd1"]) if math.isfinite(float(r["directed_corr_fwd1"])) else -999.0,
            float(r["directed_z_proxy_pnl"]) if math.isfinite(float(r["directed_z_proxy_pnl"])) else -999.0,
        ),
        reverse=True,
    )
    summary_rows = source_summary(signal_rows)
    top_rows = [r for r in signal_rows if int(r["n"]) >= 1000][:200]

    write_csv(OUT_DIR / "signal_product_metrics.csv", signal_rows)
    write_csv(OUT_DIR / "top_signal_product_metrics.csv", top_rows)
    write_csv(OUT_DIR / "source_family_summary.csv", summary_rows)
    write_csv(OUT_DIR / "volatility_regime_metrics.csv", vol_rows)
    if not option_fit.empty:
        option_fit.to_csv(OUT_DIR / "option_price_residuals.csv", index=False)

    payload = {
        "source_family_summary": summary_rows,
        "top_signal_product_metrics": top_rows[:50],
        "top_volatility_regime_metrics": sorted(
            vol_rows,
            key=lambda r: float(r["directed_corr_abs_fwd5"])
            if math.isfinite(float(r["directed_corr_abs_fwd5"]))
            else -999.0,
            reverse=True,
        )[:50],
    }
    (OUT_DIR / "alpha_sweep_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (OUT_DIR / "alpha_sweep_report.md").write_text(make_report(signal_rows, vol_rows, summary_rows), encoding="utf-8")

    print(f"Wrote alpha sweep outputs to {OUT_DIR}")
    print(f"Evaluated {len(signal_rows)} product/signal rows across {len(specs)} signals.")


if __name__ == "__main__":
    main()
