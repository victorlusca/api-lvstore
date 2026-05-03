import json
import sqlite3
from typing import Any, Optional


from app.settings import data_path

DB_PATH = data_path("master_data.db")


def _ensure_schema() -> None:
    try:
        con = sqlite3.connect(DB_PATH)
        con.executescript(
            """
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
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                bot_id INTEGER,
                source TEXT,
                severity INTEGER,
                site_user_id INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at);
            CREATE INDEX IF NOT EXISTS idx_audit_system_key ON audit_log(system_key);
            CREATE INDEX IF NOT EXISTS idx_audit_action_key ON audit_log(action_key);
            CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor_discord_id);
            CREATE INDEX IF NOT EXISTS idx_audit_target_discord ON audit_log(target_discord_id);
            CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_log(status);
            CREATE INDEX IF NOT EXISTS idx_audit_guild ON audit_log(guild_id);
            CREATE INDEX IF NOT EXISTS idx_audit_sys_action_created ON audit_log(system_key, action_key, created_at);
            """
        )
        con.commit()
        con.close()
    except Exception:
        pass


_ensure_schema()


def _ser_details(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        return v[:4000]
    try:
        return json.dumps(v, ensure_ascii=False)[:4000]
    except Exception:
        try:
            return str(v)[:4000]
        except Exception:
            return None


def log_audit(
    *,
    event_type: str,
    system_key: str,
    action_key: str,
    actor_discord_id: Optional[int] = None,
    actor_name: Optional[str] = None,
    target_discord_id: Optional[int] = None,
    target_game_id: Optional[int] = None,
    target_name: Optional[str] = None,
    details: Any = None,
    status: str = "success",
    message: Optional[str] = None,
    guild_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    message_id: Optional[int] = None,
    bot_id: Optional[int] = None,
    source: str = "bot",
    severity: int = 0,
    site_user_id: Optional[int] = None,
) -> None:
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute(
            """
            INSERT INTO audit_log (
                event_type, system_key, action_key,
                actor_discord_id, actor_name,
                target_discord_id, target_game_id, target_name,
                details_json, status, message,
                guild_id, channel_id, message_id,
                bot_id, source, severity, site_user_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                (event_type or "")[:64],
                (system_key or "")[:64],
                (action_key or "")[:64],
                int(actor_discord_id) if actor_discord_id is not None else None,
                (actor_name or None),
                int(target_discord_id) if target_discord_id is not None else None,
                int(target_game_id) if target_game_id is not None else None,
                (target_name or None),
                _ser_details(details),
                (status or "")[:32],
                (message or None),
                int(guild_id) if guild_id is not None else None,
                int(channel_id) if channel_id is not None else None,
                int(message_id) if message_id is not None else None,
                int(bot_id) if bot_id is not None else None,
                (source or "bot")[:32],
                int(severity) if severity is not None else 0,
                int(site_user_id) if site_user_id is not None else None,
            ),
        )
        con.commit()
        con.close()
    except Exception as e:
        try:
            pass
        except Exception:
            pass


def register_audit_event(**kwargs) -> None:
    log_audit(**kwargs)


