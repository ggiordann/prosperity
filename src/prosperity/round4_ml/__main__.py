from __future__ import annotations

import argparse
import json
from pathlib import Path

from prosperity.round4_ml.config import BacktestConfig, DataConfig, TrainingConfig
from prosperity.round4_ml.pipeline import run_round4_ml_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train and backtest the Round 4 neural price/voucher trading model."
    )
    parser.add_argument(
        "--data-dir",
        default=str(Path.home() / "Downloads" / "ROUND_4"),
        help="Directory containing prices_round_4_day_*.csv and trades_round_4_day_*.csv.",
    )
    parser.add_argument(
        "--output-dir",
        default="round 4/ml_artifacts/baseline",
        help="Directory for model, predictions, signals, metrics, and plots.",
    )
    parser.add_argument("--encoder", default="lstm", choices=["lstm", "tcn", "transformer"])
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--sequence-length", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--max-train-samples", type=int, default=None)
    parser.add_argument("--max-eval-samples", type=int, default=None)
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda, or mps")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data_config = DataConfig(
        data_dir=Path(args.data_dir).expanduser().resolve(),
        sequence_length=args.sequence_length,
    )
    training_config = TrainingConfig(
        output_dir=Path(args.output_dir).expanduser().resolve(),
        encoder_type=args.encoder,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_train_samples=args.max_train_samples,
        max_eval_samples=args.max_eval_samples,
        device=args.device,
    )
    result = run_round4_ml_pipeline(
        data_config=data_config,
        training_config=training_config,
        backtest_config=BacktestConfig(),
    )
    print(
        json.dumps(
            {
                "model_path": str(result.model_path),
                "output_dir": str(result.output_dir),
                "metrics": result.metrics,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
