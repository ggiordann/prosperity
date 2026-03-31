from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from prosperity.utils import ensure_dir, utcnow_iso


class BudgetTracker:
    def __init__(self, path: Path, daily_budget_usd: float):
        self.path = path
        self.daily_budget_usd = daily_budget_usd
        ensure_dir(path.parent)

    def _today_key(self) -> str:
        return datetime.now().astimezone().date().isoformat()

    def _normalize(self, payload: dict) -> dict:
        today = self._today_key()
        if payload.get("budget_date") != today:
            return {
                "budget_date": today,
                "spent_usd": 0.0,
                "events": [],
            }
        payload.setdefault("spent_usd", 0.0)
        payload.setdefault("events", [])
        payload.setdefault("budget_date", today)
        return payload

    def load(self) -> dict:
        if not self.path.exists():
            return self._normalize({})
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        payload = self._normalize(raw)
        if payload != raw:
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def status(self) -> dict:
        payload = self.load()
        spent = float(payload.get("spent_usd", 0.0))
        remaining = max(0.0, self.daily_budget_usd - spent)
        return {
            "budget_date": payload.get("budget_date"),
            "spent_usd": spent,
            "remaining_usd": remaining,
            "daily_budget_usd": self.daily_budget_usd,
            "exhausted": remaining <= 1e-9,
            "event_count": len(payload.get("events", [])),
        }

    def can_spend(self, amount_usd: float) -> bool:
        return self.load().get("spent_usd", 0.0) + amount_usd <= self.daily_budget_usd

    def record(self, amount_usd: float, role: str, model: str) -> None:
        payload = self.load()
        payload["spent_usd"] = payload.get("spent_usd", 0.0) + amount_usd
        payload.setdefault("events", []).append(
            {"at": utcnow_iso(), "amount_usd": amount_usd, "role": role, "model": model}
        )
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
