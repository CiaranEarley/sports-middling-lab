"""SQLite persistence for saved sports market observations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OBSERVATION_COLUMNS: dict[str, str] = {
    "created_at": "TEXT NOT NULL",
    "scan_id": "TEXT NOT NULL",
    "sport_key": "TEXT NOT NULL DEFAULT ''",
    "sport_label": "TEXT NOT NULL DEFAULT ''",
    "regions": "TEXT NOT NULL DEFAULT ''",
    "market_mode": "TEXT NOT NULL DEFAULT ''",
    "market_keys": "TEXT NOT NULL DEFAULT ''",
    "opportunity_type": "TEXT NOT NULL",
    "signal": "TEXT NOT NULL DEFAULT ''",
    "event_id": "TEXT NOT NULL DEFAULT ''",
    "event_label": "TEXT NOT NULL DEFAULT ''",
    "commence_time": "TEXT NOT NULL DEFAULT ''",
    "market_key": "TEXT NOT NULL DEFAULT ''",
    "participant": "TEXT NOT NULL DEFAULT ''",
    "group_label": "TEXT NOT NULL DEFAULT ''",
    "books": "TEXT NOT NULL DEFAULT ''",
    "lines": "TEXT NOT NULL DEFAULT ''",
    "odds": "TEXT NOT NULL DEFAULT ''",
    "stakes": "TEXT NOT NULL DEFAULT ''",
    "model_probability": "REAL",
    "break_even_probability": "REAL",
    "edge": "REAL",
    "expected_value": "REAL",
    "implied_probability": "REAL",
    "overround": "REAL",
    "max_loss": "REAL",
    "profit_if_hit": "REAL",
    "return_if_hit": "REAL",
    "middle_width": "REAL",
    "total_stake": "REAL",
    "legs_json": "TEXT NOT NULL DEFAULT '[]'",
    "raw_json": "TEXT NOT NULL DEFAULT '{}'",
    "review_status": "TEXT NOT NULL DEFAULT 'New'",
    "notes": "TEXT NOT NULL DEFAULT ''",
    "final_result": "TEXT NOT NULL DEFAULT ''",
    "settled_at": "TEXT NOT NULL DEFAULT ''",
    "candidate_hash": "TEXT NOT NULL UNIQUE",
}

REVIEW_STATUSES = ("New", "Watched", "Taken", "Ignored", "Settled")
TEXT_COLUMNS = {
    "created_at",
    "scan_id",
    "sport_key",
    "sport_label",
    "regions",
    "market_mode",
    "market_keys",
    "opportunity_type",
    "signal",
    "event_id",
    "event_label",
    "commence_time",
    "market_key",
    "participant",
    "group_label",
    "books",
    "lines",
    "odds",
    "stakes",
    "legs_json",
    "raw_json",
    "review_status",
    "notes",
    "final_result",
    "settled_at",
    "candidate_hash",
}


def default_database_path(base_dir: Path | None = None) -> Path:
    """Return the local SQLite path used by the Streamlit app."""

    root = base_dir or Path.cwd()
    return root / "local_outputs" / "sports_middling_research.sqlite3"


def initialize_database(db_path: Path) -> None:
    """Create the research log schema if it does not exist."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    column_sql = ",\n            ".join(
        f"{name} {definition}"
        for name, definition in OBSERVATION_COLUMNS.items()
    )
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {column_sql}
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_created_at "
            "ON observations(created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_signal "
            "ON observations(signal)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_type "
            "ON observations(opportunity_type)"
        )
        connection.commit()


def save_observations(db_path: Path, observations: list[dict[str, Any]]) -> int:
    """Insert observations and return the number of newly saved rows."""

    if not observations:
        return 0
    initialize_database(db_path)
    columns = list(OBSERVATION_COLUMNS)
    placeholders = ", ".join(["?"] * len(columns))
    insert_sql = (
        f"INSERT OR IGNORE INTO observations ({', '.join(columns)}) "
        f"VALUES ({placeholders})"
    )
    before = count_observations(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.executemany(
            insert_sql,
            [
                [_coerce_value(_complete_observation(observation).get(column)) for column in columns]
                for observation in observations
            ],
        )
        connection.commit()
    after = count_observations(db_path)
    return after - before


def fetch_observations(
    db_path: Path,
    *,
    limit: int = 500,
    signal: str | None = None,
    opportunity_type: str | None = None,
    review_status: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch saved observations, newest first."""

    initialize_database(db_path)
    conditions: list[str] = []
    params: list[Any] = []
    if signal:
        conditions.append("signal = ?")
        params.append(signal)
    if opportunity_type:
        conditions.append("opportunity_type = ?")
        params.append(opportunity_type)
    if review_status:
        conditions.append("review_status = ?")
        params.append(review_status)
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = (
        f"SELECT id, {', '.join(OBSERVATION_COLUMNS)} "
        f"FROM observations {where_sql} "
        "ORDER BY created_at DESC, id DESC LIMIT ?"
    )
    params.append(max(int(limit), 1))
    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query, params).fetchall()]


def count_observations(db_path: Path) -> int:
    """Return the number of saved observations."""

    initialize_database(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0])


def update_observation_review(
    db_path: Path,
    observation_id: int,
    *,
    review_status: str,
    notes: str = "",
    final_result: str = "",
    settled_at: str = "",
) -> None:
    """Update manual review fields for one saved observation."""

    initialize_database(db_path)
    status = review_status if review_status in REVIEW_STATUSES else "New"
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            UPDATE observations
            SET review_status = ?,
                notes = ?,
                final_result = ?,
                settled_at = ?
            WHERE id = ?
            """,
            (status, notes, final_result, settled_at, int(observation_id)),
        )
        connection.commit()


def make_candidate_hash(parts: list[Any]) -> str:
    """Create a stable hash for one candidate inside one scan."""

    payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    """Return a compact UTC timestamp for saved observations."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _complete_observation(observation: dict[str, Any]) -> dict[str, Any]:
    record = {column: None for column in OBSERVATION_COLUMNS}
    record.update(observation)
    record["created_at"] = record.get("created_at") or utc_now_iso()
    record["scan_id"] = str(record.get("scan_id") or record["created_at"])
    record["opportunity_type"] = str(record.get("opportunity_type") or "unknown")
    if not record.get("candidate_hash"):
        record["candidate_hash"] = make_candidate_hash(
            [
                record.get("scan_id"),
                record.get("opportunity_type"),
                record.get("event_id"),
                record.get("market_key"),
                record.get("participant"),
                record.get("group_label"),
                record.get("books"),
                record.get("lines"),
                record.get("odds"),
                record.get("legs_json"),
            ]
        )
    record["review_status"] = record.get("review_status") or "New"
    record["legs_json"] = _json_text(record.get("legs_json"), default="[]")
    record["raw_json"] = _json_text(record.get("raw_json"), default="{}")
    for column in TEXT_COLUMNS:
        if record.get(column) is None:
            record[column] = ""
    return record


def _json_text(value: Any, *, default: str) -> str:
    if value in (None, ""):
        return default
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def _coerce_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, default=str)
    return value
