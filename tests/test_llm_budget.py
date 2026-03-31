from __future__ import annotations

import json

from prosperity.llm.budget import BudgetTracker


def test_budget_tracker_resets_when_budget_date_changes(tmp_path):
    path = tmp_path / "llm_budget.json"
    path.write_text(
        json.dumps(
            {
                "budget_date": "1999-01-01",
                "spent_usd": 19.5,
                "events": [{"at": "1999-01-01T00:00:00+00:00", "amount_usd": 19.5}],
            }
        ),
        encoding="utf-8",
    )
    tracker = BudgetTracker(path, daily_budget_usd=50.0)
    status = tracker.status()
    assert status["spent_usd"] == 0.0
    assert status["remaining_usd"] == 50.0
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["spent_usd"] == 0.0
    assert reloaded["events"] == []
