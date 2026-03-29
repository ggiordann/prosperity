from __future__ import annotations

import json
from pathlib import Path

from prosperity.utils import ensure_dir, utcnow_iso


class BudgetTracker:
    def __init__(self, path: Path, daily_budget_usd: float):
        self.path = path
        self.daily_budget_usd = daily_budget_usd
        ensure_dir(path.parent)

    def load(self) -> dict:
        if not self.path.exists():
            return {"spent_usd": 0.0, "events": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def can_spend(self, amount_usd: float) -> bool:
        return self.load().get("spent_usd", 0.0) + amount_usd <= self.daily_budget_usd

    def record(self, amount_usd: float, role: str, model: str) -> None:
        payload = self.load()
        payload["spent_usd"] = payload.get("spent_usd", 0.0) + amount_usd
        payload.setdefault("events", []).append(
            {"at": utcnow_iso(), "amount_usd": amount_usd, "role": role, "model": model}
        )
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
