from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from prosperity.round4_ml.backtest import (
    BacktestResult,
    generate_signals,
    optimize_backtest_config,
    run_backtest,
)
from prosperity.round4_ml.config import BacktestConfig, DataConfig, TrainingConfig
from prosperity.round4_ml.features import build_feature_bundle
from prosperity.round4_ml.training import (
    TrainingArtifacts,
    predict_dataset,
    resolve_device,
    train_model,
)


@dataclass
class PipelineResult:
    output_dir: Path
    training: TrainingArtifacts
    backtest: BacktestResult
    validation_predictions: pd.DataFrame
    test_predictions: pd.DataFrame

    @property
    def model_path(self) -> Path:
        return self.training.model_path

    @property
    def metrics(self) -> dict[str, float]:
        return self.backtest.metrics


def run_round4_ml_pipeline(
    *,
    data_config: DataConfig,
    training_config: TrainingConfig,
    backtest_config: BacktestConfig,
) -> PipelineResult:
    output_dir = training_config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle = build_feature_bundle(data_config)
    save_feature_artifacts(bundle, data_config, output_dir)

    training = train_model(bundle, data_config, training_config)
    device = resolve_device(training_config.device)
    validation_predictions = predict_dataset(
        training.model,
        training.validation_dataset,
        training.target_scalers,
        batch_size=training_config.batch_size,
        device=device,
    )
    test_predictions = predict_dataset(
        training.model,
        training.test_dataset,
        training.target_scalers,
        batch_size=training_config.batch_size,
        device=device,
    )
    validation_predictions.to_csv(output_dir / "validation_predictions.csv", index=False)
    test_predictions.to_csv(output_dir / "test_predictions.csv", index=False)

    optimization = optimize_backtest_config(validation_predictions, backtest_config)
    optimization.sweep.to_csv(output_dir / "pnl_threshold_sweep.csv", index=False)
    selected_config = optimization.config
    (output_dir / "selected_backtest_config.json").write_text(
        json.dumps(selected_config.to_json_dict(), indent=2),
        encoding="utf-8",
    )

    signals = generate_signals(test_predictions, selected_config)
    backtest = run_backtest(signals, selected_config)
    backtest.save(output_dir)
    plot_training_history(training.history, output_dir / "training_history.png")
    plot_equity_curve(backtest.equity_curve, output_dir / "equity_curve.png")
    plot_trade_distribution(backtest.trades, output_dir / "trade_distribution.png")
    plot_prediction_diagnostics(test_predictions, bundle.price_target_columns, output_dir)

    summary = {
        "model_path": str(training.model_path),
        "output_dir": str(output_dir),
        "feature_count": len(bundle.feature_columns),
        "train_samples": len(training.train_dataset),
        "validation_samples": len(training.validation_dataset),
        "test_samples": len(training.test_dataset),
        "backtest_metrics": backtest.metrics,
        "validation_pnl_sweep_best": optimization.best_row,
        "data_config": data_config.to_json_dict(),
        "training_config": training_config.to_json_dict(),
        "backtest_config": selected_config.to_json_dict(),
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return PipelineResult(
        output_dir=output_dir,
        training=training,
        backtest=backtest,
        validation_predictions=validation_predictions,
        test_predictions=test_predictions,
    )


def save_feature_artifacts(bundle, data_config: DataConfig, output_dir: Path) -> None:
    (output_dir / "data_config.json").write_text(
        json.dumps(data_config.to_json_dict(), indent=2),
        encoding="utf-8",
    )
    (output_dir / "feature_columns.json").write_text(
        json.dumps(bundle.feature_columns, indent=2),
        encoding="utf-8",
    )
    bundle.scaler.save(output_dir / "feature_scaler.json")
    bundle.trader_profiles.to_csv(output_dir / "trader_profiles.csv", index=False)
    bundle.frame.head(10_000).to_csv(output_dir / "processed_feature_sample.csv", index=False)


def plot_training_history(history: pd.DataFrame, output_path: Path) -> None:
    if history.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(history["epoch"], history["train_loss"], label="Train loss")
    ax.plot(history["epoch"], history["validation_loss"], label="Validation loss")
    ax.set_title("Round 4 Multi-Output Model Loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Weighted loss")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_equity_curve(equity_curve: pd.DataFrame, output_path: Path) -> None:
    if equity_curve.empty:
        return
    x = np.arange(len(equity_curve))
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(x, equity_curve["equity"], color="#19535f", linewidth=1.6)
    ax.fill_between(x, equity_curve["equity"], equity_curve["equity"].cummax(), color="#b23a48", alpha=0.15)
    ax.set_title("Round 4 ML Backtest Equity Curve")
    ax.set_xlabel("Test tick")
    ax.set_ylabel("PnL")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_trade_distribution(trades: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    if trades.empty:
        ax.text(0.5, 0.5, "No trades generated", ha="center", va="center")
        ax.set_axis_off()
    else:
        signed_notional = trades["side"] * trades["quantity"] * trades["price"]
        ax.hist(signed_notional, bins=40, color="#427aa1", alpha=0.85)
        ax.set_title("Signed Trade Notional Distribution")
        ax.set_xlabel("Signed notional")
        ax.set_ylabel("Trade count")
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_prediction_diagnostics(
    predictions: pd.DataFrame,
    price_target_columns: list[str],
    output_dir: Path,
) -> None:
    if predictions.empty:
        return
    horizon = price_target_columns[-1].removeprefix("target_price_change_h")
    pred_column = f"predicted_price_change_{horizon}"
    target_column = f"target_price_change_h{horizon}"
    sample = predictions[[pred_column, target_column, "product", "day", "timestamp"]].dropna().head(10_000)
    if sample.empty:
        return

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(sample[target_column], sample[pred_column], s=5, alpha=0.25, color="#2a9d8f")
    lim = max(float(sample[target_column].abs().max()), float(sample[pred_column].abs().max()), 1.0)
    ax.plot([-lim, lim], [-lim, lim], color="#333333", linewidth=1.0)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_title(f"Predicted vs Actual {horizon}-Tick Price Change")
    ax.set_xlabel("Actual")
    ax.set_ylabel("Predicted")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "prediction_scatter.png", dpi=160)
    plt.close(fig)

    first_product = sample["product"].iloc[0]
    series = predictions[predictions["product"] == first_product].head(1_500)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(series["timestamp"], series[target_column], label="Actual", linewidth=1.1)
    ax.plot(series["timestamp"], series[pred_column], label="Predicted", linewidth=1.1)
    ax.set_title(f"{first_product} {horizon}-Tick Price Change Forecast")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Price change")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "prediction_timeseries.png", dpi=160)
    plt.close(fig)
