from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np

from prosperity.backtester.discovery import discover_backtester_path
from prosperity.paths import RepoPaths
from prosperity.quant.models import AlphaMiningResult, AlphaSignal
from prosperity.settings import AppSettings


def _float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _load_price_rows(dataset_root: Path) -> dict[str, list[dict[str, float]]]:
    rows_by_product: dict[str, list[dict[str, float]]] = defaultdict(list)
    for csv_path in sorted(dataset_root.glob("prices_*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                product = row.get("product")
                if not product or product == "product":
                    continue
                rows_by_product[product].append(
                    {
                        "day": _float(row.get("day")),
                        "timestamp": _float(row.get("timestamp")),
                        "bid1": _float(row.get("bid_price_1")),
                        "ask1": _float(row.get("ask_price_1")),
                        "bid2": _float(row.get("bid_price_2")),
                        "ask2": _float(row.get("ask_price_2")),
                        "bid3": _float(row.get("bid_price_3")),
                        "ask3": _float(row.get("ask_price_3")),
                        "bidv1": abs(_float(row.get("bid_volume_1"))),
                        "askv1": abs(_float(row.get("ask_volume_1"))),
                        "bidv2": abs(_float(row.get("bid_volume_2"))),
                        "askv2": abs(_float(row.get("ask_volume_2"))),
                        "bidv3": abs(_float(row.get("bid_volume_3"))),
                        "askv3": abs(_float(row.get("ask_volume_3"))),
                        "mid": _float(row.get("mid_price")),
                    }
                )
    for product_rows in rows_by_product.values():
        product_rows.sort(key=lambda item: (item["day"], item["timestamp"]))
    return rows_by_product


def _corr(x_values: np.ndarray, y_values: np.ndarray) -> float:
    if len(x_values) < 10 or len(y_values) < 10:
        return 0.0
    x_std = float(np.std(x_values))
    y_std = float(np.std(y_values))
    if x_std == 0.0 or y_std == 0.0:
        return 0.0
    return float(np.corrcoef(x_values, y_values)[0, 1])


def _directional_accuracy(x_values: np.ndarray, y_values: np.ndarray, corr: float) -> float:
    direction = 1.0 if corr >= 0 else -1.0
    predicted = np.sign(x_values * direction)
    actual = np.sign(y_values)
    mask = (predicted != 0) & (actual != 0)
    if int(np.sum(mask)) == 0:
        return 0.5
    return float(np.mean(predicted[mask] == actual[mask]))


def _feature_matrix(product_rows: list[dict[str, float]]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    mids = np.array([row["mid"] for row in product_rows], dtype=float)
    bid1 = np.array([row["bid1"] for row in product_rows], dtype=float)
    ask1 = np.array([row["ask1"] for row in product_rows], dtype=float)
    bid2 = np.array([row["bid2"] for row in product_rows], dtype=float)
    ask2 = np.array([row["ask2"] for row in product_rows], dtype=float)
    bidv1 = np.array([row["bidv1"] for row in product_rows], dtype=float)
    askv1 = np.array([row["askv1"] for row in product_rows], dtype=float)
    bidv2 = np.array([row["bidv2"] for row in product_rows], dtype=float)
    askv2 = np.array([row["askv2"] for row in product_rows], dtype=float)
    bidv3 = np.array([row["bidv3"] for row in product_rows], dtype=float)
    askv3 = np.array([row["askv3"] for row in product_rows], dtype=float)

    spread = ask1 - bid1
    top_total = np.maximum(bidv1 + askv1, 1.0)
    book_total = np.maximum(bidv1 + bidv2 + bidv3 + askv1 + askv2 + askv3, 1.0)
    microprice = (ask1 * bidv1 + bid1 * askv1) / top_total
    return_1 = np.concatenate([[0.0], np.diff(mids)])
    return_5 = np.concatenate([np.zeros(5), mids[5:] - mids[:-5]]) if len(mids) > 5 else np.zeros_like(mids)

    features = {
        "spread": spread,
        "top_imbalance": (bidv1 - askv1) / top_total,
        "book_imbalance": (bidv1 + bidv2 + bidv3 - askv1 - askv2 - askv3) / book_total,
        "micro_delta": microprice - mids,
        "gap_asymmetry": np.where((bid2 > 0) & (ask2 > 0), (ask2 - ask1) - (bid1 - bid2), 0.0),
        "return_1_fade": -return_1,
        "return_5_fade": -return_5,
        "return_1_momentum": return_1,
        "depth_pressure": np.log1p(bidv1 + bidv2 + bidv3) - np.log1p(askv1 + askv2 + askv3),
        "ema_reversion": _ema_reversion(mids, alpha=0.04),
    }
    return mids, features


def _ema_reversion(values: np.ndarray, *, alpha: float) -> np.ndarray:
    if len(values) == 0:
        return values
    ema = np.empty_like(values)
    current = float(values[0])
    for index, value in enumerate(values):
        current = (1.0 - alpha) * current + alpha * float(value)
        ema[index] = current
    return ema - values


def _interpret(product: str, feature: str, horizon: int, corr: float) -> str:
    direction = "positive" if corr > 0 else "negative"
    if corr == 0:
        direction = "flat"
    return f"{product}: {feature} has {direction} predictive correlation to {horizon}-tick future mid move."


def mine_alpha_signals(
    paths: RepoPaths,
    settings: AppSettings,
    *,
    horizons: Iterable[int],
    top_n: int,
) -> AlphaMiningResult:
    backtester_root = discover_backtester_path(paths, settings.backtester.path)
    dataset = settings.backtester.default_dataset
    dataset_root = backtester_root / "datasets" / dataset
    rows_by_product = _load_price_rows(dataset_root)
    signals: list[AlphaSignal] = []
    rows_analyzed = 0
    notes: list[str] = []

    for product, product_rows in rows_by_product.items():
        if len(product_rows) < 50:
            notes.append(f"Skipped {product}: not enough rows.")
            continue
        rows_analyzed += len(product_rows)
        mids, features = _feature_matrix(product_rows)
        for horizon in horizons:
            if horizon <= 0 or len(mids) <= horizon + 10:
                continue
            y_values = mids[horizon:] - mids[:-horizon]
            for feature_name, feature_values in features.items():
                x_values = feature_values[:-horizon]
                corr = _corr(x_values, y_values)
                accuracy = _directional_accuracy(x_values, y_values, corr)
                observations = int(len(y_values))
                sample_weight = min(1.0, math.sqrt(observations / 3000.0))
                score = sample_weight * abs(corr) + max(0.0, accuracy - 0.5) * 0.5
                signals.append(
                    AlphaSignal(
                        product=product,
                        feature=feature_name,
                        horizon=horizon,
                        correlation=corr,
                        directional_accuracy=accuracy,
                        observations=observations,
                        score=score,
                        interpretation=_interpret(product, feature_name, horizon, corr),
                    )
                )

    signals.sort(key=lambda signal: signal.score, reverse=True)
    return AlphaMiningResult(
        dataset=dataset,
        products=sorted(rows_by_product),
        top_signals=signals[:top_n],
        rows_analyzed=rows_analyzed,
        notes=notes,
    )
