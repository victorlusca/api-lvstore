"""
Audit helpers for the standalone FastAPI service.
"""
import contextvars
import json
import sqlite3
from typing import Any, Optional

from app.settings import data_path

_REFERENCE_DB = data_path("reference_data.db")
_ctx_actor = contextvars.ContextVar("audit_actor", default="unknown")
_ctx_ip = contextvars.ContextVar("audit_ip", default="unknown")
_ctx_method = contextvars.ContextVar("audit_method", default="")
_ctx_route = contextvars.ContextVar("audit_route", default="")


def _ensure() -> None:
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        con.executescript("""
            CREATE TABLE IF NOT EXISTS api_audit_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ts            TEXT    DEFAULT (datetime('now')),
                actor         TEXT,
                ip            TEXT,
                method        TEXT,
                route         TEXT,
                resource_type TEXT,
                resource_key  TEXT,
                old_value     TEXT,
                new_value     TEXT,
                status        INTEGER,
                message       TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_audit_ts   ON api_audit_log(ts);
            CREATE INDEX IF NOT EXISTS idx_audit_actor ON api_audit_log(actor);
            CREATE INDEX IF NOT EXISTS idx_audit_res   ON api_audit_log(resource_type, resource_key);
        """)
        con.commit(); con.close()
    except Exception:
        pass

_ensure()

def set_request_context(*, actor: str, ip: str, method: str, route: str) -> None:
    _ctx_actor.set(actor or "unknown")
    _ctx_ip.set(ip or "unknown")
    _ctx_method.set(method or "")
    _ctx_route.set(route or "")


def clear_request_context() -> None:
    _ctx_actor.set("unknown")
    _ctx_ip.set("unknown")
    _ctx_method.set("")
    _ctx_route.set("")


def write_audit(
    *,
    status: int,
    resource_type: str = "",
    resource_key:  str = "",
    old_value:     Any = None,
    new_value:     Any = None,
    message:       str = "",
) -> None:
    """Writes an audit row using request context from middleware."""
    try:
        actor = _ctx_actor.get()
        ip = _ctx_ip.get()
        route = _ctx_route.get()
        method = _ctx_method.get()

        def _ser(v) -> Optional[str]:
            if v is None: return None
            if isinstance(v, str): return v[:2000]
            try: return json.dumps(v, ensure_ascii=False)[:2000]
            except Exception: return str(v)[:2000]

        con = sqlite3.connect(_REFERENCE_DB)
        con.execute(
            """INSERT INTO api_audit_log
               (actor,ip,method,route,resource_type,resource_key,old_value,new_value,status,message)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (actor, ip, method, route,
             resource_type[:128], resource_key[:256],
             _ser(old_value), _ser(new_value),
             status, message[:500]),
        )
        con.commit(); con.close()
    except Exception:
        pass


def read_audit(
    *,
    limit: int = 50,
    offset: int = 0,
    resource_type: Optional[str] = None,
    actor: Optional[str] = None,
    status: Optional[int] = None,
) -> list:
    """LÃª entradas de auditoria com filtros opcionais."""
    where, params = [], []
    if resource_type:
        where.append("resource_type = ?"); params.append(resource_type)
    if actor:
        where.append("actor = ?"); params.append(actor)
    if status is not None:
        where.append("status = ?"); params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        rows = con.execute(
            f"SELECT id,ts,actor,ip,method,route,resource_type,resource_key,"
            f"old_value,new_value,status,message FROM api_audit_log {clause} "
            f"ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [min(limit, 500), max(offset, 0)],
        ).fetchall()
        con.close()
        keys = ["id","ts","actor","ip","method","route","resource_type","resource_key",
                "old_value","new_value","status","message"]
        return [dict(zip(keys, r)) for r in rows]
    except Exception:
        return []


def audit_stats() -> dict:
    """Retorna mÃ©tricas simples da auditoria."""
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        total   = con.execute("SELECT COUNT(1) FROM api_audit_log").fetchone()[0]
        today   = con.execute("SELECT COUNT(1) FROM api_audit_log WHERE DATE(ts)=DATE('now')").fetchone()[0]
        errors  = con.execute("SELECT COUNT(1) FROM api_audit_log WHERE status>=400").fetchone()[0]
        actors  = con.execute("SELECT actor,COUNT(1) FROM api_audit_log GROUP BY actor ORDER BY 2 DESC LIMIT 10").fetchall()
        recent  = con.execute(
            "SELECT ts,actor,method,route,status FROM api_audit_log ORDER BY id DESC LIMIT 5"
        ).fetchall()
        con.close()
        return {
            "total": total,
            "today": today,
            "errors": errors,
            "by_actor": {r[0]: r[1] for r in actors},
            "recent": [{"ts":r[0],"actor":r[1],"method":r[2],"route":r[3],"status":r[4]} for r in recent],
        }
    except Exception:
        return {}

