from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Job:
    name: str
    payload: dict
