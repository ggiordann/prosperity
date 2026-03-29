from __future__ import annotations

from prosperity.db import DatabaseSession, ExperimentRepository
from prosperity.db.models import StrategyRecord


def test_repository_can_roundtrip_strategy(tmp_path):
    db_path = tmp_path / "db" / "test.sqlite3"
    with DatabaseSession(db_path) as db:
        repo = ExperimentRepository(db.connection)
        repo.upsert_strategy(
            StrategyRecord(
                strategy_id="demo",
                name="Demo",
                family="unit",
                stage="compiled",
                spec_json="{}",
                code_path="/tmp/demo.py",
                created_at="2026-03-29T00:00:00Z",
            )
        )
    with DatabaseSession(db_path) as db:
        repo = ExperimentRepository(db.connection)
        row = repo.get_strategy("demo")
        assert row is not None
        assert row["family"] == "unit"
