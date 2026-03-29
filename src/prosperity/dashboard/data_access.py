from __future__ import annotations

import sqlite3
from pathlib import Path


def open_db(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def fetch_table(connection: sqlite3.Connection, table: str):
    return connection.execute(f"SELECT * FROM {table} ORDER BY created_at DESC").fetchall()
