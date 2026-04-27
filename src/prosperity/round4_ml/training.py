from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from prosperity.round4_ml.config import DataConfig, TrainingConfig
from prosperity.round4_ml.features import (
    PRICE_TARGET_PREFIX,
    VOLATILITY_TARGET,
    VOUCHER_TARGET,
    FeatureBundle,
)
from prosperity.round4_ml.models import MultiOutputTradingModel


@dataclass
class TargetScalers:
    price_mean: np.ndarray
    price_scale: np.ndarray
    voucher_mean: float
    voucher_scale: float
    volatility_mean: float
    volatility_scale: float

    @classmethod
    def fit(cls, frame: pd.DataFrame, price_target_columns: list[str]) -> TargetScalers:
        price_values = frame[price_target_columns].replace([np.inf, -np.inf], np.nan).to_numpy(float)
        price_mean = np.nanmean(price_values, axis=0)
        price_scale = np.nanstd(price_values, axis=0)
        price_mean = np.where(np.isfinite(price_mean), price_mean, 0.0)
        price_scale = np.where(np.isfinite(price_scale) & (price_scale > 1e-12), price_scale, 1.0)

        voucher_values = frame[VOUCHER_TARGET].replace([np.inf, -np.inf], np.nan).to_numpy(float)
        volatility_values = frame[VOLATILITY_TARGET].replace([np.inf, -np.inf], np.nan).to_numpy(float)
        voucher_mean, voucher_scale = _nan_mean_scale(voucher_values)
        volatility_mean, volatility_scale = _nan_mean_scale(volatility_values)
        return cls(
            price_mean=price_mean.astype(np.float32),
            price_scale=price_scale.astype(np.float32),
            voucher_mean=voucher_mean,
            voucher_scale=voucher_scale,
            volatility_mean=volatility_mean,
            volatility_scale=volatility_scale,
        )

    def transform_price(self, values: np.ndarray) -> np.ndarray:
        return (values - self.price_mean) / self.price_scale

    def inverse_price(self, values: np.ndarray) -> np.ndarray:
        return values * self.price_scale + self.price_mean

    def transform_voucher(self, values: np.ndarray) -> np.ndarray:
        return (values - self.voucher_mean) / self.voucher_scale

    def inverse_voucher(self, values: np.ndarray) -> np.ndarray:
        return values * self.voucher_scale + self.voucher_mean

    def transform_volatility(self, values: np.ndarray) -> np.ndarray:
        return (values - self.volatility_mean) / self.volatility_scale

    def inverse_volatility(self, values: np.ndarray) -> np.ndarray:
        return values * self.volatility_scale + self.volatility_mean

    def to_json_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["price_mean"] = self.price_mean.astype(float).tolist()
        payload["price_scale"] = self.price_scale.astype(float).tolist()
        return payload

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> TargetScalers:
        return cls(
            price_mean=np.asarray(payload["price_mean"], dtype=np.float32),
            price_scale=np.asarray(payload["price_scale"], dtype=np.float32),
            voucher_mean=float(payload["voucher_mean"]),
            voucher_scale=float(payload["voucher_scale"]),
            volatility_mean=float(payload["volatility_mean"]),
            volatility_scale=float(payload["volatility_scale"]),
        )


@dataclass
class TrainingArtifacts:
    model: MultiOutputTradingModel
    target_scalers: TargetScalers
    history: pd.DataFrame
    train_dataset: Round4SequenceDataset
    validation_dataset: Round4SequenceDataset
    test_dataset: Round4SequenceDataset
    model_path: Path


class Round4SequenceDataset(Dataset):
    def __init__(
        self,
        *,
        bundle: FeatureBundle,
        days: tuple[int, ...],
        target_scalers: TargetScalers,
        sequence_length: int,
        max_samples: int | None = None,
        seed: int = 0,
    ) -> None:
        self.bundle = bundle
        self.frame = bundle.frame
        self.features = bundle.feature_matrix
        self.target_scalers = target_scalers
        self.sequence_length = sequence_length
        self.price_target_columns = bundle.price_target_columns
        self.sequence_indices, self.current_indices = self._build_indices(days)
        if max_samples is not None and len(self.current_indices) > max_samples:
            rng = np.random.default_rng(seed)
            keep = np.sort(rng.choice(len(self.current_indices), size=max_samples, replace=False))
            self.sequence_indices = self.sequence_indices[keep]
            self.current_indices = self.current_indices[keep]

    def _build_indices(self, days: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
        split = self.frame[self.frame["day"].isin(days)]
        sequence_rows: list[np.ndarray] = []
        current_rows: list[int] = []
        price_targets = self.frame[self.price_target_columns].to_numpy(float)
        vol_targets = self.frame[VOLATILITY_TARGET].to_numpy(float)

        for _, group in split.groupby(["day", "product"], sort=False):
            positions = group.index.to_numpy(dtype=np.int64)
            for end_offset in range(self.sequence_length - 1, len(positions)):
                end_position = int(positions[end_offset])
                target_ok = np.isfinite(price_targets[end_position]).all() and np.isfinite(
                    vol_targets[end_position]
                )
                if not target_ok:
                    continue
                sequence_rows.append(positions[end_offset - self.sequence_length + 1 : end_offset + 1])
                current_rows.append(end_position)

        if not current_rows:
            raise ValueError(f"No valid sequence samples for days={days}")
        return np.vstack(sequence_rows).astype(np.int64), np.asarray(current_rows, dtype=np.int64)

    def __len__(self) -> int:
        return len(self.current_indices)

    def __getitem__(self, item: int) -> dict[str, torch.Tensor]:
        sequence_index = self.sequence_indices[item]
        current_index = int(self.current_indices[item])
        row = self.frame.iloc[current_index]
        price_target = row[self.price_target_columns].to_numpy(dtype=np.float32)
        price_mask = np.isfinite(price_target).astype(np.float32)
        price_target = np.nan_to_num(
            self.target_scalers.transform_price(price_target), nan=0.0, posinf=0.0, neginf=0.0
        ).astype(np.float32)

        voucher_value = np.asarray([row[VOUCHER_TARGET]], dtype=np.float32)
        voucher_mask = np.asarray([np.isfinite(voucher_value[0])], dtype=np.float32)
        voucher_value = np.nan_to_num(
            self.target_scalers.transform_voucher(voucher_value), nan=0.0, posinf=0.0, neginf=0.0
        ).astype(np.float32)

        volatility_value = np.asarray([row[VOLATILITY_TARGET]], dtype=np.float32)
        volatility_mask = np.asarray([np.isfinite(volatility_value[0])], dtype=np.float32)
        volatility_value = np.nan_to_num(
            self.target_scalers.transform_volatility(volatility_value),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        ).astype(np.float32)

        return {
            "sequence": torch.from_numpy(self.features[sequence_index]),
            "current": torch.from_numpy(self.features[current_index]),
            "price_target": torch.from_numpy(price_target),
            "price_mask": torch.from_numpy(price_mask),
            "voucher_target": torch.from_numpy(voucher_value),
            "voucher_mask": torch.from_numpy(voucher_mask),
            "volatility_target": torch.from_numpy(volatility_value),
            "volatility_mask": torch.from_numpy(volatility_mask),
            "index": torch.tensor(current_index, dtype=torch.long),
        }


def train_model(
    bundle: FeatureBundle,
    data_config: DataConfig,
    training_config: TrainingConfig,
) -> TrainingArtifacts:
    set_seeds(training_config.seed)
    output_dir = training_config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    target_scalers = TargetScalers.fit(bundle.split_frame(data_config.train_days), bundle.price_target_columns)

    train_dataset = Round4SequenceDataset(
        bundle=bundle,
        days=data_config.train_days,
        target_scalers=target_scalers,
        sequence_length=data_config.sequence_length,
        max_samples=training_config.max_train_samples,
        seed=training_config.seed,
    )
    validation_dataset = Round4SequenceDataset(
        bundle=bundle,
        days=data_config.validation_days,
        target_scalers=target_scalers,
        sequence_length=data_config.sequence_length,
        max_samples=training_config.max_eval_samples,
        seed=training_config.seed + 1,
    )
    test_dataset = Round4SequenceDataset(
        bundle=bundle,
        days=data_config.test_days,
        target_scalers=target_scalers,
        sequence_length=data_config.sequence_length,
        max_samples=training_config.max_eval_samples,
        seed=training_config.seed + 2,
    )

    device = resolve_device(training_config.device)
    model = MultiOutputTradingModel(
        feature_count=len(bundle.feature_columns),
        price_horizon_count=len(bundle.price_target_columns),
        encoder_type=training_config.encoder_type,
        hidden_size=training_config.hidden_size,
        dense_size=training_config.dense_size,
        num_layers=training_config.num_layers,
        dropout=training_config.dropout,
    ).to(device)

    train_loader = DataLoader(
        train_dataset,
        batch_size=training_config.batch_size,
        shuffle=True,
        num_workers=training_config.num_workers,
        drop_last=True,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=training_config.batch_size,
        shuffle=False,
        num_workers=training_config.num_workers,
    )

    optimizer = AdamLite(
        model.parameters(),
        lr=training_config.learning_rate,
        weight_decay=training_config.weight_decay,
    )
    scheduler = ReduceLROnPlateauLite(
        optimizer,
        factor=0.5,
        patience=max(1, training_config.patience // 2),
    )

    history_rows: list[dict[str, float]] = []
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    epochs_without_improvement = 0

    for epoch in range(1, training_config.epochs + 1):
        train_losses = run_epoch(model, train_loader, training_config, optimizer, device)
        validation_losses = evaluate_epoch(model, validation_loader, training_config, device)
        scheduler.step(validation_losses["loss"])

        row = {"epoch": float(epoch), **prefixed("train", train_losses), **prefixed("validation", validation_losses)}
        row["learning_rate"] = float(optimizer.param_groups[0]["lr"])
        history_rows.append(row)

        if validation_losses["loss"] < best_loss - training_config.min_delta:
            best_loss = validation_losses["loss"]
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= training_config.patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    history = pd.DataFrame(history_rows)
    model_path = output_dir / "round4_multi_output_model.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "feature_columns": bundle.feature_columns,
            "price_target_columns": bundle.price_target_columns,
            "target_scalers": target_scalers.to_json_dict(),
            "data_config": data_config.to_json_dict(),
            "training_config": training_config.to_json_dict(),
            "model_config": {
                "feature_count": len(bundle.feature_columns),
                "price_horizon_count": len(bundle.price_target_columns),
                "encoder_type": training_config.encoder_type,
                "hidden_size": training_config.hidden_size,
                "dense_size": training_config.dense_size,
                "num_layers": training_config.num_layers,
                "dropout": training_config.dropout,
            },
        },
        model_path,
    )
    history.to_csv(output_dir / "training_history.csv", index=False)
    target_scaler_path = output_dir / "target_scalers.json"
    target_scaler_path.write_text(json.dumps(target_scalers.to_json_dict(), indent=2), encoding="utf-8")
    return TrainingArtifacts(
        model=model,
        target_scalers=target_scalers,
        history=history,
        train_dataset=train_dataset,
        validation_dataset=validation_dataset,
        test_dataset=test_dataset,
        model_path=model_path,
    )


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    config: TrainingConfig,
    optimizer: "AdamLite",
    device: torch.device,
) -> dict[str, float]:
    model.train()
    totals = LossAccumulator()
    for batch in loader:
        optimizer.zero_grad(set_to_none=True)
        loss, components = compute_loss(model, batch, config, device)
        loss.backward()
        if config.gradient_clip_norm > 0.0:
            nn.utils.clip_grad_norm_(model.parameters(), config.gradient_clip_norm)
        optimizer.step()
        totals.update(components, batch_size=batch["sequence"].shape[0])
    return totals.average()


def evaluate_epoch(
    model: nn.Module, loader: DataLoader, config: TrainingConfig, device: torch.device
) -> dict[str, float]:
    model.eval()
    totals = LossAccumulator()
    with torch.no_grad():
        for batch in loader:
            _, components = compute_loss(model, batch, config, device)
            totals.update(components, batch_size=batch["sequence"].shape[0])
    return totals.average()


def compute_loss(
    model: nn.Module, batch: dict[str, torch.Tensor], config: TrainingConfig, device: torch.device
) -> tuple[torch.Tensor, dict[str, float]]:
    sequence = batch["sequence"].to(device)
    current = batch["current"].to(device)
    outputs = model(sequence, current)
    price_target = batch["price_target"].to(device)
    price_mask = batch["price_mask"].to(device)
    voucher_target = batch["voucher_target"].squeeze(-1).to(device)
    voucher_mask = batch["voucher_mask"].squeeze(-1).to(device)
    volatility_target = batch["volatility_target"].squeeze(-1).to(device)
    volatility_mask = batch["volatility_mask"].squeeze(-1).to(device)

    price_loss = masked_mse(outputs["price_change"], price_target, price_mask)
    voucher_loss = masked_mse(outputs["voucher_fair_price"], voucher_target, voucher_mask)
    volatility_loss = masked_mse(outputs["future_volatility"], volatility_target, volatility_mask)
    loss = (
        config.price_loss_weight * price_loss
        + config.voucher_loss_weight * voucher_loss
        + config.volatility_loss_weight * volatility_loss
    )
    return loss, {
        "loss": float(loss.detach().cpu()),
        "price_loss": float(price_loss.detach().cpu()),
        "voucher_loss": float(voucher_loss.detach().cpu()),
        "volatility_loss": float(volatility_loss.detach().cpu()),
    }


def masked_mse(prediction: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    squared = (prediction - target) ** 2 * mask
    denominator = mask.sum().clamp_min(1.0)
    return squared.sum() / denominator


class LossAccumulator:
    def __init__(self) -> None:
        self.weighted: dict[str, float] = {}
        self.count = 0

    def update(self, values: dict[str, float], batch_size: int) -> None:
        for key, value in values.items():
            self.weighted[key] = self.weighted.get(key, 0.0) + value * batch_size
        self.count += batch_size

    def average(self) -> dict[str, float]:
        if self.count <= 0:
            return {key: float("nan") for key in self.weighted}
        return {key: value / self.count for key, value in self.weighted.items()}


class AdamLite:
    """Small Adam optimizer used to avoid optional torch.optim import-time dependencies."""

    def __init__(
        self,
        parameters,
        *,
        lr: float,
        weight_decay: float = 0.0,
        betas: tuple[float, float] = (0.9, 0.999),
        eps: float = 1e-8,
    ) -> None:
        self.params = [parameter for parameter in parameters if parameter.requires_grad]
        self.lr = lr
        self.weight_decay = weight_decay
        self.beta1, self.beta2 = betas
        self.eps = eps
        self.state: dict[int, dict[str, torch.Tensor | int]] = {}
        self.param_groups = [{"lr": self.lr}]

    def zero_grad(self, set_to_none: bool = True) -> None:
        for parameter in self.params:
            if parameter.grad is None:
                continue
            if set_to_none:
                parameter.grad = None
            else:
                parameter.grad.zero_()

    @torch.no_grad()
    def step(self) -> None:
        self.lr = float(self.param_groups[0]["lr"])
        for parameter in self.params:
            if parameter.grad is None:
                continue
            grad = parameter.grad
            if grad.is_sparse:
                raise RuntimeError("AdamLite does not support sparse gradients.")
            if self.weight_decay:
                grad = grad.add(parameter, alpha=self.weight_decay)
            state = self.state.setdefault(
                id(parameter),
                {
                    "step": 0,
                    "exp_avg": torch.zeros_like(parameter),
                    "exp_avg_sq": torch.zeros_like(parameter),
                },
            )
            state["step"] = int(state["step"]) + 1
            exp_avg = state["exp_avg"]
            exp_avg_sq = state["exp_avg_sq"]
            if not isinstance(exp_avg, torch.Tensor) or not isinstance(exp_avg_sq, torch.Tensor):
                raise RuntimeError("Corrupt AdamLite optimizer state.")
            exp_avg.mul_(self.beta1).add_(grad, alpha=1.0 - self.beta1)
            exp_avg_sq.mul_(self.beta2).addcmul_(grad, grad, value=1.0 - self.beta2)
            step = int(state["step"])
            bias_correction1 = 1.0 - self.beta1**step
            bias_correction2 = 1.0 - self.beta2**step
            step_size = self.lr * (bias_correction2**0.5) / bias_correction1
            parameter.addcdiv_(exp_avg, exp_avg_sq.sqrt().add_(self.eps), value=-step_size)


class ReduceLROnPlateauLite:
    def __init__(
        self,
        optimizer: AdamLite,
        *,
        factor: float,
        patience: int,
        min_lr: float = 1e-6,
        threshold: float = 1e-6,
    ) -> None:
        self.optimizer = optimizer
        self.factor = factor
        self.patience = patience
        self.min_lr = min_lr
        self.threshold = threshold
        self.best = float("inf")
        self.bad_epochs = 0

    def step(self, metric: float) -> None:
        if metric < self.best - self.threshold:
            self.best = metric
            self.bad_epochs = 0
            return
        self.bad_epochs += 1
        if self.bad_epochs < self.patience:
            return
        self.bad_epochs = 0
        current_lr = float(self.optimizer.param_groups[0]["lr"])
        self.optimizer.param_groups[0]["lr"] = max(self.min_lr, current_lr * self.factor)


def predict_dataset(
    model: MultiOutputTradingModel,
    dataset: Round4SequenceDataset,
    target_scalers: TargetScalers,
    *,
    batch_size: int,
    device: torch.device | str,
) -> pd.DataFrame:
    resolved_device = resolve_device(str(device)) if not isinstance(device, torch.device) else device
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    model.eval()
    rows = []
    with torch.no_grad():
        for batch in loader:
            outputs = model(batch["sequence"].to(resolved_device), batch["current"].to(resolved_device))
            price = target_scalers.inverse_price(outputs["price_change"].detach().cpu().numpy())
            voucher = target_scalers.inverse_voucher(
                outputs["voucher_fair_price"].detach().cpu().numpy()
            )
            volatility = target_scalers.inverse_volatility(
                outputs["future_volatility"].detach().cpu().numpy()
            )
            indices = batch["index"].detach().cpu().numpy()
            for local_row, frame_index in enumerate(indices):
                rows.append(
                    {
                        "frame_index": int(frame_index),
                        **{
                            f"predicted_price_change_{target_column.removeprefix(PRICE_TARGET_PREFIX)}": float(
                                price[local_row, column_index]
                            )
                            for column_index, target_column in enumerate(dataset.price_target_columns)
                        },
                        "predicted_voucher_fair_price": float(voucher[local_row]),
                        "predicted_future_volatility": float(volatility[local_row]),
                    }
                )
    predictions = pd.DataFrame(rows)
    meta = dataset.frame.iloc[predictions["frame_index"].to_numpy()].reset_index(drop=True)
    return pd.concat([meta.reset_index(drop=True), predictions.drop(columns=["frame_index"])], axis=1)


def set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def resolve_device(device: str) -> torch.device:
    if device != "auto":
        return torch.device(device)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def prefixed(prefix: str, values: dict[str, float]) -> dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def _nan_mean_scale(values: np.ndarray) -> tuple[float, float]:
    mean = float(np.nanmean(values)) if np.isfinite(values).any() else 0.0
    scale = float(np.nanstd(values)) if np.isfinite(values).any() else 1.0
    if not np.isfinite(mean):
        mean = 0.0
    if not np.isfinite(scale) or scale < 1e-12:
        scale = 1.0
    return mean, scale
