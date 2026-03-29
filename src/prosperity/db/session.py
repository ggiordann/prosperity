from __future__ import annotations

import sqlite3
from pathlib import Path

from prosperity.db.migrations import apply_migrations
from prosperity.utils import ensure_dir


class DatabaseSession:
    def __init__(self, db_path: Path):
        ensure_dir(db_path.parent)
        self.db_path = db_path
        self.connection = sqlite3.connect(db_path, timeout=30.0)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA busy_timeout=30000")
        apply_migrations(self.connection)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "DatabaseSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.close()
