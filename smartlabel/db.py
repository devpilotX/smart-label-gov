"""SQLite persistence for inspection results."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import InspectionResult


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS inspections (
                    inspection_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    product_context TEXT NOT NULL,
                    sold_by TEXT NOT NULL,
                    rule_set TEXT NOT NULL,
                    source TEXT NOT NULL,
                    overall_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_inspections_created_at ON inspections(created_at);
                """
            )

    def save(self, result: InspectionResult) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO inspections
                (inspection_id, created_at, product_context, sold_by, rule_set, source, overall_status, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.inspection_id,
                    result.created_at,
                    result.product_context,
                    result.sold_by,
                    result.rule_set,
                    result.source,
                    result.overall_status,
                    json.dumps(result.to_dict(), ensure_ascii=False),
                ),
            )

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT inspection_id, created_at, product_context, sold_by, source, overall_status "
                "FROM inspections ORDER BY created_at DESC, inspection_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_payloads(self, limit: int = 500) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM inspections ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        payloads = []
        for row in rows:
            try:
                payloads.append(json.loads(row[0]))
            except (TypeError, ValueError):
                continue
        return payloads

    def status_counts(self) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT overall_status, COUNT(*) AS total FROM inspections GROUP BY overall_status"
            ).fetchall()
        return {str(row["overall_status"]): int(row["total"]) for row in rows}

    def count(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM inspections").fetchone()[0])

    def get(self, inspection_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM inspections WHERE inspection_id = ?", (inspection_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def clear(self) -> int:
        with self.connect() as connection:
            deleted = connection.execute("DELETE FROM inspections").rowcount
        return int(deleted)
