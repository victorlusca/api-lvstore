"""
Audit helpers for the standalone FastAPI service.
"""
import contextvars
import json
import sqlite3
from typing import Any, Optional

from app.settings import data_path

_MASTER_DB = data_path("master_data.db")
_ctx_actor = contextvars.ContextVar("audit_actor", default="unknown")
_ctx_actor_id = contextvars.ContextVar("audit_actor_id", default=None)
_ctx_ip = contextvars.ContextVar("audit_ip", default="unknown")
_ctx_method = contextvars.ContextVar("audit_method", default="")
_ctx_route = contextvars.ContextVar("audit_route", default="")


def _ensure() -> None:
    try:
        con = sqlite3.connect(_MASTER_DB)
        con.executescript("""
            CREATE TABLE IF NOT EXISTS audit_log ( 
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                created_at TEXT DEFAULT (datetime('now')), 
                event_type TEXT, 
                system_key TEXT, 
                action_key TEXT, 
                actor_discord_id INTEGER, 
                actor_name TEXT, 
                target_discord_id INTEGER, 
                target_game_id INTEGER, 
                target_name TEXT, 
                details_json TEXT, 
                status TEXT, 
                message TEXT, 
                channel_id INTEGER, 
                message_id INTEGER, 
                bot_id INTEGER, 
                source TEXT, 
                severity INTEGER, 
                site_user_id INTEGER 
            );
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(created_at);
            CREATE INDEX IF NOT EXISTS idx_audit_system ON audit_log(system_key);
            CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action_key);
        """)
        con.commit(); con.close()
    except Exception:
        pass

_ensure()

def set_request_context(*, actor: str, ip: str, method: str, route: str, actor_id: Optional[int] = None) -> None:
    _ctx_actor.set(actor or "unknown")
    _ctx_actor_id.set(actor_id)
    _ctx_ip.set(ip or "unknown")
    _ctx_method.set(method or "")
    _ctx_route.set(route or "")


def clear_request_context() -> None:
    _ctx_actor.set("unknown")
    _ctx_actor_id.set(None)
    _ctx_ip.set("unknown")
    _ctx_method.set("")
    _ctx_route.set("")


def write_audit(
    *,
    event_type: str = "API_ACTION",
    system_key: str = "API",
    action_key: str = "",
    actor_discord_id: Optional[int] = None,
    actor_name: Optional[str] = None,
    target_discord_id: Optional[int] = None,
    target_game_id: Optional[int] = None,
    target_name: Optional[str] = None,
    details_json: Any = None,
    status: str = "success",
    message: str = "",
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
    bot_id: Optional[int] = None,
    source: str = "WEB_API",
    severity: int = 1,
    site_user_id: Optional[int] = None
) -> None:
    """Writes an audit row using request context from middleware."""
    try:
        if not actor_discord_id:
            actor_discord_id = _ctx_actor_id.get()
        if not actor_name:
            actor_name = _ctx_actor.get()
            
        def _ser(v) -> Optional[str]:
            if v is None: return None
            if isinstance(v, str): return v
            try: return json.dumps(v, ensure_ascii=False)
            except Exception: return str(v)

        con = sqlite3.connect(_MASTER_DB)
        con.execute(
            """INSERT INTO audit_log
               (event_type, system_key, action_key, actor_discord_id, actor_name, 
                target_discord_id, target_game_id, target_name, details_json, 
                status, message, channel_id, message_id, bot_id, 
                source, severity, site_user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event_type, system_key, action_key, actor_discord_id, actor_name,
             target_discord_id, target_game_id, target_name, _ser(details_json),
             status, message, channel_id, message_id, bot_id,
             source, severity, site_user_id),
        )
        con.commit(); con.close()
    except Exception as e:
        print(f"Error writing audit: {e}")
        pass


def read_audit(
    *,
    limit: int = 50,
    offset: int = 0,
    system_key: Optional[str] = None,
    action_key: Optional[str] = None,
    actor_discord_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list:
    """Lê entradas de auditoria com filtros opcionais."""
    where, params = [], []
    if system_key:
        where.append("system_key = ?"); params.append(system_key)
    if action_key:
        where.append("action_key = ?"); params.append(action_key)
    if actor_discord_id:
        where.append("actor_discord_id = ?"); params.append(actor_discord_id)
    if status:
        where.append("status = ?"); params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    try:
        con = sqlite3.connect(_MASTER_DB)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            f"SELECT * FROM audit_log {clause} "
            f"ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [min(limit, 500), max(offset, 0)],
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def audit_stats() -> dict:
    """Retorna métricas simples da auditoria."""
    try:
        con = sqlite3.connect(_MASTER_DB)
        total   = con.execute("SELECT COUNT(1) FROM audit_log").fetchone()[0]
        today   = con.execute("SELECT COUNT(1) FROM audit_log WHERE DATE(created_at)=DATE('now')").fetchone()[0]
        errors  = con.execute("SELECT COUNT(1) FROM audit_log WHERE status != 'success'").fetchone()[0]
        actors  = con.execute("SELECT actor_name, COUNT(1) FROM audit_log GROUP BY actor_name ORDER BY 2 DESC LIMIT 10").fetchall()
        recent  = con.execute(
            "SELECT created_at, actor_name, action_key, status FROM audit_log ORDER BY id DESC LIMIT 5"
        ).fetchall()
        con.close()
        return {
            "total": total,
            "today": today,
            "errors": errors,
            "by_actor": {r[0]: r[1] for r in actors},
            "recent": [{"ts":r[0],"actor":r[1],"action":r[2],"status":r[3]} for r in recent],
        }
    except Exception:
        return {}

