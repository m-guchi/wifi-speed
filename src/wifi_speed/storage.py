from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union


@dataclass
class SpeedResult:
    measured_at: datetime
    download_mbps: float
    upload_mbps: float
    ping_ms: float
    server_name: Optional[str]
    server_id: Optional[str]
    ssid: Optional[str]
    signal_dbm: Optional[int]
    link_quality: Optional[str]
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class ResultStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS speed_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    measured_at TEXT NOT NULL,
                    download_mbps REAL,
                    upload_mbps REAL,
                    ping_ms REAL,
                    server_name TEXT,
                    server_id TEXT,
                    ssid TEXT,
                    signal_dbm INTEGER,
                    link_quality TEXT,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_speed_results_measured_at
                ON speed_results (measured_at DESC)
                """
            )

    def save(self, result: SpeedResult) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO speed_results (
                    measured_at, download_mbps, upload_mbps, ping_ms,
                    server_name, server_id, ssid, signal_dbm, link_quality, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _format_timestamp(result.measured_at),
                    result.download_mbps,
                    result.upload_mbps,
                    result.ping_ms,
                    result.server_name,
                    result.server_id,
                    result.ssid,
                    result.signal_dbm,
                    result.link_quality,
                    result.error,
                ),
            )
            return int(cursor.lastrowid)

    def recent(self, limit: int = 20, hours: Optional[int] = None) -> list[SpeedResult]:
        with self._connect() as conn:
            if hours is None:
                rows = conn.execute(
                    """
                    SELECT * FROM speed_results
                    ORDER BY measured_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM speed_results
                    WHERE measured_at >= datetime('now', ?)
                    ORDER BY measured_at DESC
                    LIMIT ?
                    """,
                    (f"-{hours} hours", limit),
                ).fetchall()

        return [_row_to_result(row) for row in rows]

    def series(self, hours: int = 24, limit: int = 200) -> list[SpeedResult]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM speed_results
                WHERE error IS NULL
                  AND measured_at >= datetime('now', ?)
                ORDER BY measured_at ASC
                LIMIT ?
                """,
                (f"-{hours} hours", limit),
            ).fetchall()

        return [_row_to_result(row) for row in rows]

    def summary(self, hours: int = 24) -> dict[str, Union[float, int, None]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN error IS NULL THEN 1 ELSE 0 END) AS success_count,
                    AVG(CASE WHEN error IS NULL THEN download_mbps END) AS avg_download,
                    AVG(CASE WHEN error IS NULL THEN upload_mbps END) AS avg_upload,
                    AVG(CASE WHEN error IS NULL THEN ping_ms END) AS avg_ping,
                    MIN(CASE WHEN error IS NULL THEN download_mbps END) AS min_download,
                    MAX(CASE WHEN error IS NULL THEN download_mbps END) AS max_download
                FROM speed_results
                WHERE measured_at >= datetime('now', ?)
                """,
                (f"-{hours} hours",),
            ).fetchone()

        if row is None:
            return {
                "total": 0,
                "success_count": 0,
                "avg_download": None,
                "avg_upload": None,
                "avg_ping": None,
                "min_download": None,
                "max_download": None,
            }

        return {
            "total": int(row["total"]),
            "success_count": int(row["success_count"] or 0),
            "avg_download": row["avg_download"],
            "avg_upload": row["avg_upload"],
            "avg_ping": row["avg_ping"],
            "min_download": row["min_download"],
            "max_download": row["max_download"],
        }


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_timestamp(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def result_to_dict(result: SpeedResult) -> dict[str, object]:
    return {
        "measured_at": result.measured_at.isoformat(),
        "download_mbps": result.download_mbps,
        "upload_mbps": result.upload_mbps,
        "ping_ms": result.ping_ms,
        "server_name": result.server_name,
        "ssid": result.ssid,
        "signal_dbm": result.signal_dbm,
        "link_quality": result.link_quality,
        "error": result.error,
        "success": result.success,
    }


def _row_to_result(row: sqlite3.Row) -> SpeedResult:
    measured_at = _parse_timestamp(row["measured_at"])

    return SpeedResult(
        measured_at=measured_at,
        download_mbps=row["download_mbps"] or 0.0,
        upload_mbps=row["upload_mbps"] or 0.0,
        ping_ms=row["ping_ms"] or 0.0,
        server_name=row["server_name"],
        server_id=row["server_id"],
        ssid=row["ssid"],
        signal_dbm=row["signal_dbm"],
        link_quality=row["link_quality"],
        error=row["error"],
    )
