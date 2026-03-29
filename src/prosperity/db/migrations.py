from __future__ import annotations

import sqlite3

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS documents (
        document_id TEXT PRIMARY KEY,
        corpus_name TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        embedding_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategies (
        strategy_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        family TEXT NOT NULL,
        stage TEXT NOT NULL,
        spec_json TEXT NOT NULL,
        code_path TEXT,
        submission_path TEXT,
        created_at TEXT NOT NULL,
        score REAL,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        strategy_id TEXT,
        dataset_id TEXT NOT NULL,
        trader_path TEXT NOT NULL,
        status TEXT NOT NULL,
        final_pnl_total REAL,
        own_trade_count INTEGER,
        tick_count INTEGER,
        summary_json TEXT,
        stdout_path TEXT,
        stderr_path TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evaluations (
        evaluation_id TEXT PRIMARY KEY,
        strategy_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        score REAL NOT NULL,
        robustness_score REAL,
        novelty_score REAL,
        similarity_score REAL,
        plagiarism_score REAL,
        metrics_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS similarities (
        similarity_id TEXT PRIMARY KEY,
        strategy_id TEXT NOT NULL,
        neighbor_id TEXT NOT NULL,
        neighbor_source TEXT NOT NULL,
        modality TEXT NOT NULL,
        score REAL NOT NULL,
        details_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS promotions (
        promotion_id TEXT PRIMARY KEY,
        strategy_id TEXT NOT NULL,
        decision TEXT NOT NULL,
        reason TEXT NOT NULL,
        package_dir TEXT,
        created_at TEXT NOT NULL
    )
    """,
]


def apply_migrations(connection: sqlite3.Connection) -> None:
    for statement in SCHEMA:
        connection.execute(statement)
    connection.commit()
