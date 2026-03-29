from __future__ import annotations

from pathlib import Path
from typing import Dict

from baselines import BASELINES


def list_baselines() -> Dict[str, Path]:
    return dict(BASELINES)


def get_baseline_path(name: str) -> Path:
    if name not in BASELINES:
        available = ", ".join(sorted(BASELINES))
        raise KeyError(f"Unknown baseline '{name}'. Available: {available}")
    return BASELINES[name]
