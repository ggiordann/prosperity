from __future__ import annotations

from prosperity.dashboard.data_access import fetch_table, open_db
from prosperity.db import DatabaseSession


def test_dashboard_data_access_reads_table(tmp_path):
    db_path = tmp_path / "db" / "dashboard.sqlite3"
    with DatabaseSession(db_path) as db:
        db.connection.execute(
            "INSERT INTO promotions (promotion_id, strategy_id, decision, reason, package_dir, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", "s1", "promote", "ok", "/tmp/pkg", "2026-03-29T00:00:00Z"),
        )

    connection = open_db(db_path)
    rows = fetch_table(connection, "promotions")
    assert rows[0]["strategy_id"] == "s1"
