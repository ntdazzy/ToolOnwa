"""Quan ly nhat ky thao tac noi bo bang SQLite."""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "configs" / "history.db"

_LOCK = RLock()
_INITIALIZED = False

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    action_type TEXT,
    object_name TEXT,
    row_count INTEGER,
    status TEXT,
    message TEXT,
    sql_text TEXT
)
"""


def _ensure_db() -> None:
    """Tao tep co so du lieu va bang hanh dong neu chua co."""
    global _INITIALIZED
    with _LOCK:
        if _INITIALIZED and DB_PATH.exists():
            return
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(TABLE_SQL)
            conn.commit()
        finally:
            conn.close()
        _INITIALIZED = True


def _connect() -> sqlite3.Connection:
    """Mo ket noi SQLite da duoc dam bao khoi tao."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def log_action(
    action_type: str,
    object_name: str,
    row_count: int,
    status: str,
    message: str = "",
    sql_text: str = "",
) -> Optional[int]:
    """Ghi mot dong lich su, tra ve id vua them hoac None neu loi."""
    try:
        conn = _connect()
    except Exception:
        return None
    try:
        ts = datetime.utcnow().isoformat(timespec="seconds")
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO actions (timestamp, action_type, object_name, row_count, status, message, sql_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                action_type,
                object_name,
                int(row_count) if row_count is not None else 0,
                status,
                message or "",
                sql_text or "",
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_actions(action_type: str | None = None, limit: int | None = None) -> List[Dict[str, Any]]:
    """Lay danh sach hanh dong theo loai va gioi han tuy chon."""
    try:
        conn = _connect()
    except Exception:
        return []
    try:
        params: List[Any] = []
        sql = "SELECT id, timestamp, action_type, object_name, row_count, status, message, sql_text FROM actions"
        if action_type:
            sql += " WHERE action_type = ?"
            params.append(action_type)
        sql += " ORDER BY id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "action_type": row["action_type"],
                    "object_name": row["object_name"],
                    "row_count": row["row_count"],
                    "status": row["status"],
                    "message": row["message"],
                    "sql_text": row["sql_text"],
                }
            )
        return results
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def export_csv(filepath: str | Path) -> bool:
    """Xuat toan bo lich su ra tep CSV, tra ve True neu thanh cong."""
    path = Path(filepath)
    try:
        actions = get_actions()
        if not actions:
            headers = ["id", "timestamp", "action_type", "object_name", "row_count", "status", "message", "sql_text"]
        else:
            headers = list(actions[0].keys())
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in actions:
                writer.writerow(row)
        return True
    except Exception:
        return False


def mark_action_status(
    action_id: int,
    status: str,
    message: str | None = None,
    *,
    row_count: int | None = None,
    sql_text: str | None = None,
) -> bool:
    """Cap nhat trang thai cho mot dong lich su da co."""
    try:
        conn = _connect()
    except Exception:
        return False
    try:
        fields: List[str] = ["status = ?"]
        params: List[Any] = [status]
        if message is not None:
            fields.append("message = ?")
            params.append(message)
        if row_count is not None:
            fields.append("row_count = ?")
            params.append(int(row_count))
        if sql_text is not None:
            fields.append("sql_text = ?")
            params.append(sql_text)
        params.append(action_id)
        sql = f"UPDATE actions SET {', '.join(fields)} WHERE id = ?"
        conn.execute(sql, params)
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def mark_success(action_id: int, message: str | None = None, row_count: int | None = None) -> bool:
    """Danh dau mot dong lich su la thanh cong."""
    return mark_action_status(action_id, "success", message, row_count=row_count)


def iter_actions(action_type: str | None = None) -> Iterable[Dict[str, Any]]:
    """Tao dong bo qua tat ca lich su de su dung dong bo hoa."""
    for record in get_actions(action_type=action_type):
        yield record
