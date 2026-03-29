from __future__ import annotations

import json
import sqlite3
from typing import Iterable

from prosperity.db.models import (
    ConversationCycleRecord,
    ConversationMessageRecord,
    DocumentRecord,
    EvaluationRecord,
    MemoryNoteRecord,
    PromotionRecord,
    RunRecord,
    SimilarityRecord,
    StrategyRecord,
)


class ExperimentRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def upsert_document(self, record: DocumentRecord) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO documents
            (document_id, corpus_name, title, content, metadata_json, embedding_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.document_id,
                record.corpus_name,
                record.title,
                record.content,
                json.dumps(record.metadata, sort_keys=True),
                json.dumps(record.embedding),
                record.created_at,
            ),
        )

    def upsert_strategy(self, record: StrategyRecord) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO strategies
            (strategy_id, name, family, stage, spec_json, code_path, submission_path, created_at, score, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.strategy_id,
                record.name,
                record.family,
                record.stage,
                record.spec_json,
                record.code_path,
                record.submission_path,
                record.created_at,
                record.score,
                record.notes,
            ),
        )

    def insert_run(self, record: RunRecord) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO runs
            (run_id, strategy_id, dataset_id, trader_path, status, final_pnl_total, own_trade_count, tick_count,
             summary_json, stdout_path, stderr_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.run_id,
                record.strategy_id,
                record.dataset_id,
                record.trader_path,
                record.status,
                record.final_pnl_total,
                record.own_trade_count,
                record.tick_count,
                record.summary_json,
                record.stdout_path,
                record.stderr_path,
                record.created_at,
            ),
        )

    def insert_evaluation(self, record: EvaluationRecord) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO evaluations
            (evaluation_id, strategy_id, run_id, score, robustness_score, novelty_score,
             similarity_score, plagiarism_score, metrics_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.evaluation_id,
                record.strategy_id,
                record.run_id,
                record.score,
                record.robustness_score,
                record.novelty_score,
                record.similarity_score,
                record.plagiarism_score,
                record.metrics_json,
                record.created_at,
            ),
        )

    def insert_similarity_records(self, records: Iterable[SimilarityRecord]) -> None:
        for record in records:
            self.connection.execute(
                """
                INSERT OR REPLACE INTO similarities
                (similarity_id, strategy_id, neighbor_id, neighbor_source, modality, score, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.similarity_id,
                    record.strategy_id,
                    record.neighbor_id,
                    record.neighbor_source,
                    record.modality,
                    record.score,
                    record.details_json,
                    record.created_at,
                ),
            )

    def insert_promotion(self, record: PromotionRecord) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO promotions
            (promotion_id, strategy_id, decision, reason, package_dir, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.promotion_id,
                record.strategy_id,
                record.decision,
                record.reason,
                record.package_dir,
                record.created_at,
            ),
        )

    def upsert_conversation_cycle(self, record: ConversationCycleRecord) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO conversation_cycles
            (cycle_id, session_name, iteration, champion_strategy_id, promoted_strategy_id, status,
             summary_json, created_at, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.cycle_id,
                record.session_name,
                record.iteration,
                record.champion_strategy_id,
                record.promoted_strategy_id,
                record.status,
                record.summary_json,
                record.created_at,
                record.finished_at,
            ),
        )

    def insert_conversation_messages(self, records: Iterable[ConversationMessageRecord]) -> None:
        for record in records:
            self.connection.execute(
                """
                INSERT OR REPLACE INTO conversation_messages
                (message_id, cycle_id, session_name, role, content_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.message_id,
                    record.cycle_id,
                    record.session_name,
                    record.role,
                    record.content_json,
                    record.created_at,
                ),
            )

    def insert_memory_note(self, record: MemoryNoteRecord) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO memory_notes
            (note_id, session_name, cycle_id, strategy_id, note_kind, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.note_id,
                record.session_name,
                record.cycle_id,
                record.strategy_id,
                record.note_kind,
                record.content,
                record.created_at,
            ),
        )

    def list_strategies(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM strategies ORDER BY created_at DESC"
        ).fetchall()

    def list_runs(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM runs ORDER BY created_at DESC"
        ).fetchall()

    def list_promotions(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM promotions ORDER BY created_at DESC"
        ).fetchall()

    def list_recent_conversation_cycles(self, session_name: str, limit: int = 20) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT * FROM conversation_cycles
            WHERE session_name = ?
            ORDER BY iteration DESC, created_at DESC
            LIMIT ?
            """,
            (session_name, limit),
        ).fetchall()

    def list_recent_conversation_messages(self, session_name: str, limit: int = 50) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT * FROM conversation_messages
            WHERE session_name = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_name, limit),
        ).fetchall()

    def list_memory_notes(self, session_name: str, limit: int = 50) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT * FROM memory_notes
            WHERE session_name = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_name, limit),
        ).fetchall()

    def get_latest_evaluation(self, strategy_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT * FROM evaluations
            WHERE strategy_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (strategy_id,),
        ).fetchone()

    def get_latest_run(self, strategy_id: str, dataset_id: str | None = None) -> sqlite3.Row | None:
        if dataset_id is None:
            return self.connection.execute(
                """
                SELECT * FROM runs
                WHERE strategy_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (strategy_id,),
            ).fetchone()
        return self.connection.execute(
            """
            SELECT * FROM runs
            WHERE strategy_id = ? AND dataset_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (strategy_id, dataset_id),
        ).fetchone()

    def get_best_strategy_by_submission_pnl(self) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT s.*, MAX(r.final_pnl_total) AS best_submission_pnl
            FROM strategies s
            JOIN runs r ON r.strategy_id = s.strategy_id
            WHERE r.dataset_id = 'submission'
            GROUP BY s.strategy_id
            ORDER BY best_submission_pnl DESC, s.created_at DESC
            LIMIT 1
            """
        ).fetchone()

    def next_cycle_iteration(self, session_name: str) -> int:
        row = self.connection.execute(
            "SELECT COALESCE(MAX(iteration), 0) AS iteration FROM conversation_cycles WHERE session_name = ?",
            (session_name,),
        ).fetchone()
        return int(row["iteration"]) + 1 if row is not None else 1

    def get_strategy(self, strategy_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM strategies WHERE strategy_id = ?",
            (strategy_id,),
        ).fetchone()
