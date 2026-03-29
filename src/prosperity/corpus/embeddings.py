from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

import numpy as np

from prosperity.settings import AppSettings

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


class EmbeddingProvider:
    def __init__(self, settings: AppSettings, dimensions: int = 256):
        self.settings = settings
        self.dimensions = dimensions

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        return [self._local_embedding(text) for text in texts]

    def embed_text(self, text: str) -> list[float]:
        return self._local_embedding(text)

    def _local_embedding(self, text: str) -> list[float]:
        vector = np.zeros(self.dimensions, dtype=float)
        counts = Counter(token.lower() for token in TOKEN_RE.findall(text))
        for token, value in counts.items():
            vector[hash(token) % self.dimensions] += value
        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        return vector.tolist()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    a = np.array(left, dtype=float)
    b = np.array(right, dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
