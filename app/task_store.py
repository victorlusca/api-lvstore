import hashlib
import json
import secrets
import sqlite3
from typing import Any, Dict, List, Optional

from app.settings import data_path

_DB_PATH = data_path("reference_data.db")


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _ensure_schema() -> None:
    con = _con()
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id TEXT NOT NULL UNIQUE,
                token_hash TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                last_seen TEXT,
                last_ip TEXT
            );

            CREATE TABLE IF NOT EXISTS api_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                payload_json TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER NOT NULL DEFAULT 100,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                available_at TEXT DEFAULT (datetime('now')),
                locked_at TEXT,
                locked_by TEXT,
                idempotency_key TEXT,
                result_json TEXT,
                last_error TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_api_tasks_idem
                ON api_tasks(bot_id, idempotency_key)
                WHERE idempotency_key IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_api_tasks_poll
                ON api_tasks(bot_id, status, available_at, priority, id);
            """
        )
        con.commit()
    finally:
        con.close()


_ensure_schema()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def register_bot(bot_id: str, label: str = "") -> Dict[str, Any]:
    token = secrets.token_hex(32)
    token_hash = _hash_token(token)
    con = _con()
    try:
        con.execute("UPDATE api_bots SET is_active=0 WHERE bot_id=?", (bot_id,))
        con.execute(
            "INSERT INTO api_bots (bot_id, token_hash, label, is_active) VALUES (?, ?, ?, 1)",
            (bot_id, token_hash, label[:120]),
        )
        con.commit()
    finally:
        con.close()
    return {"bot_id": bot_id, "label": label, "token": token}


def revoke_bot(bot_id: str) -> int:
    con = _con()
    try:
        n = con.execute("UPDATE api_bots SET is_active=0 WHERE bot_id=?", (bot_id,)).rowcount
        con.commit()
        return int(n or 0)
    finally:
        con.close()


def list_bots() -> List[Dict[str, Any]]:
    con = _con()
    try:
        rows = con.execute(
            "SELECT bot_id,label,created_at,last_seen,last_ip FROM api_bots WHERE is_active=1 ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def validate_bot(bot_id: str, token: str, ip: str = "") -> bool:
    token_hash = _hash_token(token)
    con = _con()
    try:
        row = con.execute(
            "SELECT 1 FROM api_bots WHERE bot_id=? AND token_hash=? AND is_active=1",
            (bot_id, token_hash),
        ).fetchone()
        if not row:
            return False
        con.execute(
            "UPDATE api_bots SET last_seen=datetime('now'), last_ip=? WHERE bot_id=?",
            (ip[:64], bot_id),
        )
        con.commit()
        return True
    finally:
        con.close()


def create_task(
    *,
    bot_id: str,
    task_type: str,
    payload: Any,
    created_by: str = "api",
    priority: int = 100,
    max_attempts: int = 3,
    available_in_secs: int = 0,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    con = _con()
    try:
        if idempotency_key:
            existing = con.execute(
                "SELECT id, status FROM api_tasks WHERE bot_id=? AND idempotency_key=? LIMIT 1",
                (bot_id, idempotency_key[:120]),
            ).fetchone()
            if existing:
                return {"task_id": existing["id"], "status": existing["status"], "deduplicated": True}

        cur = con.execute(
            """
            INSERT INTO api_tasks (
                bot_id, task_type, payload_json, status, priority, max_attempts,
                available_at, idempotency_key, created_by, updated_at
            )
            VALUES (?, ?, ?, 'pending', ?, ?, datetime('now', ?), ?, ?, datetime('now'))
            """,
            (
                bot_id,
                task_type[:120],
                payload_json,
                int(priority),
                max(1, int(max_attempts)),
                f"+{max(0, int(available_in_secs))} seconds",
                idempotency_key[:120] if idempotency_key else None,
                created_by[:120],
            ),
        )
        con.commit()
        return {"task_id": int(cur.lastrowid), "status": "pending", "deduplicated": False}
    finally:
        con.close()


def poll_tasks(bot_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    n = max(1, min(100, int(limit)))
    con = _con()
    try:
        rows = con.execute(
            """
            SELECT id, task_type, payload_json, attempts, max_attempts, priority, created_at
            FROM api_tasks
            WHERE bot_id=?
              AND status='pending'
              AND available_at <= datetime('now')
            ORDER BY priority ASC, id ASC
            LIMIT ?
            """,
            (bot_id, n),
        ).fetchall()

        ids = [int(r["id"]) for r in rows]
        if ids:
            placeholders = ",".join(["?"] * len(ids))
            con.execute(
                f"""
                UPDATE api_tasks
                SET status='in_progress',
                    attempts=attempts+1,
                    locked_at=datetime('now'),
                    locked_by=?,
                    updated_at=datetime('now')
                WHERE id IN ({placeholders})
                """,
                (bot_id, *ids),
            )
            con.commit()

        out = []
        for r in rows:
            payload = {}
            raw = r["payload_json"]
            if raw:
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {"raw": raw}
            out.append(
                {
                    "task_id": r["id"],
                    "task_type": r["task_type"],
                    "payload": payload,
                    "attempt": int(r["attempts"]) + 1,
                    "max_attempts": int(r["max_attempts"]),
                    "priority": int(r["priority"]),
                    "created_at": r["created_at"],
                }
            )
        return out
    finally:
        con.close()


def ack_task(
    *,
    bot_id: str,
    task_id: int,
    status: str,
    result: Any = None,
    error: Optional[str] = None,
    retry_in_secs: int = 30,
) -> bool:
    status = (status or "").strip().lower()
    if status not in {"done", "failed", "retry"}:
        return False

    con = _con()
    try:
        row = con.execute(
            "SELECT attempts,max_attempts,status FROM api_tasks WHERE id=? AND bot_id=? LIMIT 1",
            (int(task_id), bot_id),
        ).fetchone()
        if not row:
            return False
        if row["status"] not in {"in_progress", "pending"}:
            return False

        result_json = json.dumps(result, ensure_ascii=False)[:8000] if result is not None else None
        error = (error or "")[:500]

        if status == "retry":
            if int(row["attempts"]) >= int(row["max_attempts"]):
                con.execute(
                    """
                    UPDATE api_tasks
                    SET status='failed', last_error=?, result_json=?, locked_at=NULL, locked_by=NULL, updated_at=datetime('now')
                    WHERE id=? AND bot_id=?
                    """,
                    ("max attempts reached", result_json, int(task_id), bot_id),
                )
            else:
                con.execute(
                    """
                    UPDATE api_tasks
                    SET status='pending', last_error=?, result_json=?, locked_at=NULL, locked_by=NULL,
                        available_at=datetime('now', ?), updated_at=datetime('now')
                    WHERE id=? AND bot_id=?
                    """,
                    (error or "retry requested", result_json, f"+{max(0, int(retry_in_secs))} seconds", int(task_id), bot_id),
                )
        elif status == "done":
            con.execute(
                """
                UPDATE api_tasks
                SET status='done', result_json=?, last_error=NULL, locked_at=NULL, locked_by=NULL, updated_at=datetime('now')
                WHERE id=? AND bot_id=?
                """,
                (result_json, int(task_id), bot_id),
            )
        else:
            con.execute(
                """
                UPDATE api_tasks
                SET status='failed', last_error=?, result_json=?, locked_at=NULL, locked_by=NULL, updated_at=datetime('now')
                WHERE id=? AND bot_id=?
                """,
                (error or "failed", result_json, int(task_id), bot_id),
            )
        con.commit()
        return True
    finally:
        con.close()


def list_tasks(bot_id: Optional[str], status: Optional[str], limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    where = []
    params: List[Any] = []
    if bot_id:
        where.append("bot_id=?")
        params.append(bot_id)
    if status:
        where.append("status=?")
        params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    con = _con()
    try:
        rows = con.execute(
            f"""
            SELECT id,bot_id,task_type,status,attempts,max_attempts,priority,last_error,created_by,created_at,updated_at
            FROM api_tasks
            {clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, max(1, min(500, int(limit))), max(0, int(offset))),
        ).fetchall()
        total = con.execute(f"SELECT COUNT(1) FROM api_tasks {clause}", params).fetchone()[0]
        return {"total": int(total or 0), "tasks": [dict(r) for r in rows]}
    finally:
        con.close()
