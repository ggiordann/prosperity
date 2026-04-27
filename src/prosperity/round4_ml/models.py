from __future__ import annotations

import math

import torch
from torch import nn


class LSTMEncoder(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (hidden, _) = self.lstm(x)
        return hidden[-1]


class TemporalCNNEncoder(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        in_channels = input_size
        for layer in range(num_layers):
            dilation = 2**layer
            layers.extend(
                [
                    nn.Conv1d(
                        in_channels,
                        hidden_size,
                        kernel_size=3,
                        padding=dilation,
                        dilation=dilation,
                    ),
                    nn.BatchNorm1d(hidden_size),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                ]
            )
            in_channels = hidden_size
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.network(x.transpose(1, 2))
        return encoded[:, :, -1]


class PositionalEncoding(nn.Module):
    def __init__(self, hidden_size: int, max_length: int = 512) -> None:
        super().__init__()
        position = torch.arange(max_length).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, hidden_size, 2) * (-math.log(10_000.0) / hidden_size)
        )
        pe = torch.zeros(max_length, hidden_size)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term[: pe[:, 1::2].shape[1]])
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class TransformerTimeSeriesEncoder(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float) -> None:
        super().__init__()
        heads = 4 if hidden_size % 4 == 0 else 2
        self.input_projection = nn.Linear(input_size, hidden_size)
        self.position = PositionalEncoding(hidden_size)
        layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=heads,
            dim_feedforward=hidden_size * 4,
            dropout=dropout,
            activation="relu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        projected = self.position(self.input_projection(x))
        encoded = self.encoder(projected)
        return encoded[:, -1, :]


class MultiOutputTradingModel(nn.Module):
    """Sequence encoder plus dense feature branch with three prediction heads."""

    def __init__(
        self,
        *,
        feature_count: int,
        price_horizon_count: int,
        encoder_type: str,
        hidden_size: int,
        dense_size: int,
        num_layers: int,
        dropout: float,
    ) -> None:
        super().__init__()
        if encoder_type == "lstm":
            self.encoder = LSTMEncoder(feature_count, hidden_size, num_layers, dropout)
        elif encoder_type == "tcn":
            self.encoder = TemporalCNNEncoder(feature_count, hidden_size, num_layers, dropout)
        elif encoder_type == "transformer":
            self.encoder = TransformerTimeSeriesEncoder(feature_count, hidden_size, num_layers, dropout)
        else:
            raise ValueError(f"Unsupported encoder_type: {encoder_type}")

        self.feature_branch = nn.Sequential(
            nn.Linear(feature_count, dense_size),
            nn.BatchNorm1d(dense_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(dense_size, dense_size),
            nn.BatchNorm1d(dense_size),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        combined_size = hidden_size + dense_size
        self.shared = nn.Sequential(
            nn.Linear(combined_size, dense_size),
            nn.BatchNorm1d(dense_size),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.price_head = nn.Linear(dense_size, price_horizon_count)
        self.voucher_head = nn.Linear(dense_size, 1)
        self.volatility_head = nn.Sequential(nn.Linear(dense_size, 1), nn.Softplus())

    def forward(self, sequence: torch.Tensor, current_features: torch.Tensor) -> dict[str, torch.Tensor]:
        encoded = self.encoder(sequence)
        dense = self.feature_branch(current_features)
        shared = self.shared(torch.cat([encoded, dense], dim=1))
        return {
            "price_change": self.price_head(shared),
            "voucher_fair_price": self.voucher_head(shared).squeeze(-1),
            "future_volatility": self.volatility_head(shared).squeeze(-1),
        }
