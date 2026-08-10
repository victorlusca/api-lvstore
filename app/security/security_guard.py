import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.core.audit import log_audit
from app.security.security_whitelist import is_allowed as wl_is_allowed
from app.settings import data_path
from app.services.sqlite_engine import sqlite_service, reference_service

DB_PATH = data_path("master_data.db")

ANTI_BAN = "ANTI_BAN"
ANTI_KICK = "ANTI_KICK"
ANTI_ROLE_CREATE = "ANTI_ROLE_CREATE"
ANTI_ROLE_DELETE = "ANTI_ROLE_DELETE"
ANTI_INVITE_LINK = "ANTI_INVITE_LINK"
ANTI_ROLE_PERMISSION_UPDATE = "ANTI_ROLE_PERMISSION_UPDATE"
ANTI_ROLE_ADD = "ANTI_ROLE_ADD"
ANTI_SERVER_RENAME = "ANTI_SERVER_RENAME"
ANTI_SERVER_ICON_CHANGE = "ANTI_SERVER_ICON_CHANGE"

SYSTEM_NAMES: Tuple[str, ...] = (
    ANTI_BAN,
    ANTI_KICK,
    ANTI_ROLE_CREATE,
    ANTI_ROLE_DELETE,
    ANTI_INVITE_LINK,
    ANTI_ROLE_PERMISSION_UPDATE,
    ANTI_ROLE_ADD,
    ANTI_SERVER_RENAME,
    ANTI_SERVER_ICON_CHANGE,
)

ACTION_TO_SYSTEM: Dict[str, str] = {
    "anti_ban": ANTI_BAN,
    "anti_kick": ANTI_KICK,
    "anti_role_create": ANTI_ROLE_CREATE,
    "anti_role_delete": ANTI_ROLE_DELETE,
    "anti_invite_link": ANTI_INVITE_LINK,
    "anti_role_permission_update": ANTI_ROLE_PERMISSION_UPDATE,
    "anti_dangerous_role_permission_update": ANTI_ROLE_PERMISSION_UPDATE,
    "anti_role_add": ANTI_ROLE_ADD,
    "anti_dangerous_role_add": ANTI_ROLE_ADD,
    "anti_server_rename": ANTI_SERVER_RENAME,
    "anti_server_icon_change": ANTI_SERVER_ICON_CHANGE,
}

SYSTEM_TO_ACTION: Dict[str, str] = {
    ANTI_BAN: "anti_ban",
    ANTI_KICK: "anti_kick",
    ANTI_ROLE_CREATE: "anti_role_create",
    ANTI_ROLE_DELETE: "anti_role_delete",
    ANTI_INVITE_LINK: "anti_invite_link",
    ANTI_ROLE_PERMISSION_UPDATE: "anti_role_permission_update",
    ANTI_ROLE_ADD: "anti_role_add",
    ANTI_SERVER_RENAME: "anti_server_rename",
    ANTI_SERVER_ICON_CHANGE: "anti_server_icon_change",
}

DEFAULT_LIMITS: Dict[str, int] = {
    ANTI_BAN: 1,
    ANTI_KICK: 2,
    ANTI_ROLE_CREATE: 3,
    ANTI_ROLE_DELETE: 2,
    ANTI_INVITE_LINK: 3,
    ANTI_ROLE_PERMISSION_UPDATE: 1,
    ANTI_ROLE_ADD: 2,
    ANTI_SERVER_RENAME: 1,
    ANTI_SERVER_ICON_CHANGE: 1,
}

DEFAULT_PUNISHMENTS: Dict[str, str] = {
    ANTI_BAN: "remove_roles",
    ANTI_KICK: "remove_roles",
    ANTI_ROLE_CREATE: "remove_roles",
    ANTI_ROLE_DELETE: "remove_roles",
    ANTI_INVITE_LINK: "kick",
    ANTI_ROLE_PERMISSION_UPDATE: "ban",
    ANTI_ROLE_ADD: "remove_roles",
    ANTI_SERVER_RENAME: "remove_roles",
    ANTI_SERVER_ICON_CHANGE: "remove_roles",
}

VALID_PUNISHMENTS = {"kick", "ban", "remove_roles"}
ACTION_KEYS: Tuple[str, ...] = tuple(SYSTEM_TO_ACTION.values())
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS security_systems (
    system_name TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS security_limits (
    system_name TEXT PRIMARY KEY,
    infraction_limit INTEGER NOT NULL,
    punishment_type TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_security_limits_system_name
    ON security_limits(system_name);
CREATE TABLE IF NOT EXISTS security_infractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    system_name TEXT NOT NULL,
    event_ts TEXT DEFAULT (datetime('now')),
    details_json TEXT
);
CREATE TABLE IF NOT EXISTS security_punishments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    system_name TEXT NOT NULL,
    punishment_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS security_processed_events (
    event_key TEXT PRIMARY KEY,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sec_inf_user_action
    ON security_infractions(user_id, action_type);
CREATE INDEX IF NOT EXISTS idx_sec_inf_system
    ON security_infractions(system_name);
CREATE INDEX IF NOT EXISTS idx_sec_punish_user
    ON security_punishments(user_id, created_at);
"""


def _safe_close(con: Optional[sqlite3.Connection]) -> None:
    try:
        if con:
            con.close()
    except Exception:
        pass


def _ser(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        return v[:3000]
    try:
        return json.dumps(v, ensure_ascii=False)[:3000]
    except Exception:
        return str(v)[:3000]


def _norm_action(action_key: str) -> str:
    return (action_key or "").strip().lower()


def _to_system_name(action_or_system: str) -> Optional[str]:
    if not action_or_system:
        return None
    raw = (action_or_system or "").strip()
    up = raw.upper()
    if up in SYSTEM_NAMES:
        return up
    low = raw.lower()
    return ACTION_TO_SYSTEM.get(low)


def _to_action_key(action_or_system: str) -> Optional[str]:
    sys_name = _to_system_name(action_or_system)
    if not sys_name:
        return None
    return SYSTEM_TO_ACTION.get(sys_name)


@dataclass
class EventDecision:
    ignored_system_disabled: bool
    ignored_whitelist: bool
    duplicate_event: bool
    infraction_count: int
    limit: int
    punish: bool
    punishment_type: Optional[str]
    system_name: Optional[str]
    action_key: Optional[str]


class DatabaseService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._schema_ready = False
        # Tenta criar o schema no cold-start, mas não bloqueia se falhar
        # (ex: diretório ainda não existe no primeiro import).
        # set_limit_config e set_system_enabled re-tentam antes de escrever.
        try:
            self.ensure_schema()
            self._schema_ready = True
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"[SecurityGuard] ensure_schema no __init__ falhou (será re-tentado na primeira escrita): {e}"
            )

    def _connect(self) -> sqlite3.Connection:
        # Garante que o diretório existe — crítico no cold-start do SquareCloud
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(db_dir, exist_ok=True)
        con = sqlite3.connect(self.db_path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    def ensure_schema(self) -> None:
        con = None
        try:
            con = self._connect()
            con.executescript(SCHEMA_SQL)
            self._migrate_limits_uniqueness(con)
            self._migrate_legacy_limit_configs_uniqueness(con)
            for sys_name in SYSTEM_NAMES:
                con.execute(
                    """
                    INSERT OR IGNORE INTO security_systems (system_name, enabled, updated_at)
                    VALUES (?, 1, datetime('now'))
                    """,
                    (sys_name,),
                )
            con.commit()
        except Exception as e:
            # Não engole — deixa subir para que o chamador saiba o que falhou
            raise RuntimeError(f"[SecurityGuard] ensure_schema falhou: {e}") from e
        finally:
            _safe_close(con)

    def _migrate_limits_uniqueness(self, con: sqlite3.Connection) -> None:
        rows = con.execute(
            """
            SELECT rowid, system_name, infraction_limit, punishment_type
            FROM security_limits
            """
        ).fetchall()
        for row in rows:
            raw_system = str(row["system_name"] or "").strip()
            sys_name = _to_system_name(raw_system) or raw_system.upper()
            if not sys_name:
                continue
            punishment = str(row["punishment_type"] or "remove_roles").strip().lower()
            if punishment not in VALID_PUNISHMENTS:
                punishment = "remove_roles"
            limit = max(1, int(row["infraction_limit"] or 1))
            if (
                sys_name != row["system_name"]
                or punishment != row["punishment_type"]
                or limit != int(row["infraction_limit"] or 1)
            ):
                con.execute(
                    """
                    UPDATE security_limits
                    SET system_name = ?, infraction_limit = ?, punishment_type = ?, updated_at = datetime('now')
                    WHERE rowid = ?
                    """,
                    (sys_name, limit, punishment, int(row["rowid"])),
                )
        con.execute("DELETE FROM security_limits WHERE system_name IS NULL OR TRIM(system_name) = ''")
        con.execute(
            """
            DELETE FROM security_limits
            WHERE rowid NOT IN (
                SELECT MAX(rowid)
                FROM security_limits
                GROUP BY system_name
            )
            """
        )
        con.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_security_limits_system_name
            ON security_limits(system_name)
            """
        )

    def _migrate_legacy_limit_configs_uniqueness(self, con: sqlite3.Connection) -> None:
        tbl = con.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'security_limit_configs'
            LIMIT 1
            """
        ).fetchone()
        if not tbl:
            return

        cols = {
            str(r["name"]).lower()
            for r in con.execute("PRAGMA table_info('security_limit_configs')").fetchall()
        }
        if "action_key" not in cols:
            return

        con.execute(
            """
            UPDATE security_limit_configs
            SET action_key = LOWER(TRIM(action_key))
            WHERE action_key IS NOT NULL
            """
        )
        if "punishment_type" in cols:
            con.execute(
                """
                UPDATE security_limit_configs
                SET punishment_type = LOWER(TRIM(punishment_type))
                WHERE punishment_type IS NOT NULL
                """
            )
        con.execute(
            """
            DELETE FROM security_limit_configs
            WHERE action_key IS NULL OR TRIM(action_key) = ''
            """
        )

        if "bot_id" in cols:
            con.execute(
                """
                DELETE FROM security_limit_configs
                WHERE rowid NOT IN (
                    SELECT MAX(rowid)
                    FROM security_limit_configs
                    GROUP BY bot_id, action_key
                )
                """
            )
            con.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_security_limit_configs_bot_action
                ON security_limit_configs(bot_id, action_key)
                """
            )
        else:
            con.execute(
                """
                DELETE FROM security_limit_configs
                WHERE rowid NOT IN (
                    SELECT MAX(rowid)
                    FROM security_limit_configs
                    GROUP BY action_key
                )
                """
            )
            con.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_security_limit_configs_action_key
                ON security_limit_configs(action_key)
                """
            )

    def ensure_default_limits(self) -> None:
        con = None
        try:
            self.ensure_schema()
            con = self._connect()
            for sys_name in SYSTEM_NAMES:
                con.execute(
                    """
                    INSERT OR IGNORE INTO security_limits
                    (system_name, infraction_limit, punishment_type, updated_at)
                    VALUES (?, ?, ?, datetime('now'))
                    """,
                    (
                        sys_name,
                        int(DEFAULT_LIMITS.get(sys_name, 1)),
                        str(DEFAULT_PUNISHMENTS.get(sys_name, "remove_roles")),
                    ),
                )
            con.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[SecurityGuard] ensure_default_limits falhou: {e}")
        finally:
            _safe_close(con)

    def is_system_enabled(self, system_name: str) -> bool:
        con = None
        try:
            sys_name = _to_system_name(system_name)
            if not sys_name:
                return False
            con = self._connect()
            row = con.execute(
                "SELECT enabled FROM security_systems WHERE system_name = ? LIMIT 1",
                (sys_name,),
            ).fetchone()
            if not row:
                return False
            return int(row["enabled"] or 0) == 1
        except Exception:
            return False
        finally:
            _safe_close(con)

    def set_system_enabled(self, system_name: str, enabled: int) -> bool:
        con = None
        try:
            sys_name = _to_system_name(system_name)
            if not sys_name:
                raise ValueError(f"Sistema inválido: {system_name!r}")
            # Garante que as tabelas existem antes de escrever
            self.ensure_schema()
            con = self._connect()
            con.execute(
                """
                INSERT INTO security_systems (system_name, enabled, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(system_name)
                DO UPDATE SET enabled=excluded.enabled, updated_at=datetime('now')
                """,
                (sys_name, 1 if int(enabled) else 0),
            )
            con.commit()
            return True
        except Exception as e:
            raise RuntimeError(f"[SecurityGuard] set_system_enabled({system_name!r}) falhou: {e}") from e
        finally:
            _safe_close(con)

    def list_systems(self) -> List[Dict[str, Any]]:
        con = None
        try:
            con = self._connect()
            rows = con.execute(
                "SELECT system_name, enabled, updated_at FROM security_systems ORDER BY system_name ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
        finally:
            _safe_close(con)

    def get_limit_config(self, action_or_system: str) -> Dict[str, Any]:
        con = None
        try:
            sys_name = _to_system_name(action_or_system)
            action_key = _to_action_key(action_or_system)
            if not sys_name or not action_key:
                return {"system_name": None, "action_key": None, "infraction_limit": 1, "punishment_type": "remove_roles"}
            self.ensure_default_limits()
            con = self._connect()
            row = con.execute(
                """
                SELECT infraction_limit, punishment_type
                FROM security_limits
                WHERE system_name = ?
                LIMIT 1
                """,
                (sys_name,),
            ).fetchone()
            if not row:
                return {
                    "system_name": sys_name,
                    "action_key": action_key,
                    "infraction_limit": int(DEFAULT_LIMITS.get(sys_name, 1)),
                    "punishment_type": str(DEFAULT_PUNISHMENTS.get(sys_name, "remove_roles")),
                }
            punishment = str(row["punishment_type"] or "remove_roles").lower()
            if punishment not in VALID_PUNISHMENTS:
                punishment = "remove_roles"
            return {
                "system_name": sys_name,
                "action_key": action_key,
                "infraction_limit": max(1, int(row["infraction_limit"] or 1)),
                "punishment_type": punishment,
            }
        except Exception:
            return {"system_name": None, "action_key": None, "infraction_limit": 1, "punishment_type": "remove_roles"}
        finally:
            _safe_close(con)

    def set_limit_config(self, action_or_system: str, infraction_limit: int, punishment_type: str) -> bool:
        con = None
        try:
            sys_name = _to_system_name(action_or_system)
            if not sys_name:
                raise ValueError(f"Chave de ação/sistema inválida: {action_or_system!r}")
            punishment = (punishment_type or "").strip().lower()
            if punishment not in VALID_PUNISHMENTS:
                raise ValueError(f"Tipo de punição inválido: {punishment!r}. Opções: {sorted(VALID_PUNISHMENTS)}")
            # Garante que as tabelas existem antes de escrever
            self.ensure_schema()
            con = self._connect()
            con.execute(
                """
                INSERT INTO security_limits
                (system_name, infraction_limit, punishment_type, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(system_name)
                DO UPDATE SET
                    infraction_limit=excluded.infraction_limit,
                    punishment_type=excluded.punishment_type,
                    updated_at=datetime('now')
                """,
                (sys_name, max(1, int(infraction_limit)), punishment),
            )
            con.commit()
            return True
        except Exception as e:
            raise RuntimeError(f"[SecurityGuard] set_limit_config({action_or_system!r}) falhou: {e}") from e
        finally:
            _safe_close(con)

    def register_infraction(
        self,
        *,
        user_id: int,
        action_type: str,
        system_name: str,
        details: Any = None,
    ) -> None:
        con = None
        try:
            con = self._connect()
            con.execute(
                """
                INSERT INTO security_infractions
                (user_id, action_type, system_name, event_ts, details_json)
                VALUES (?, ?, ?, datetime('now'), ?)
                """,
                (
                    int(user_id),
                    _norm_action(action_type),
                    _to_system_name(system_name),
                    _ser(details),
                ),
            )
            con.commit()
        except Exception:
            pass
        finally:
            _safe_close(con)

    def get_infraction_count(self, *, user_id: int, action_type: str) -> int:
        con = None
        try:
            con = self._connect()
            row = con.execute(
                """
                SELECT COUNT(1) AS n
                FROM security_infractions
                WHERE user_id = ? AND action_type = ?
                """,
                (int(user_id), _norm_action(action_type)),
            ).fetchone()
            return int((row["n"] if row else 0) or 0)
        except Exception:
            return 0
        finally:
            _safe_close(con)

    def register_punishment(
        self,
        *,
        user_id: int,
        action_type: str,
        system_name: str,
        punishment_type: str,
        reason: str,
        status: str,
        details: Any = None,
    ) -> None:
        con = None
        try:
            con = self._connect()
            con.execute(
                """
                INSERT INTO security_punishments
                (user_id, action_type, system_name, punishment_type, reason, status, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    int(user_id),
                    _norm_action(action_type),
                    _to_system_name(system_name),
                    (punishment_type or "")[:32],
                    (reason or "")[:500],
                    (status or "")[:32],
                    _ser(details),
                ),
            )
            con.commit()
        except Exception:
            pass
        finally:
            _safe_close(con)

    def mark_event_once(self, event_key: str) -> bool:
        if not event_key:
            return True
        con = None
        try:
            con = self._connect()
            cur = con.execute(
                "INSERT OR IGNORE INTO security_processed_events (event_key, created_at) VALUES (?, datetime('now'))",
                ((event_key or "")[:250],),
            )
            con.commit()
            return int(cur.rowcount or 0) > 0
        except Exception:
            # NÃ£o bloqueia o fluxo caso o registro idempotente falhe.
            return True
        finally:
            _safe_close(con)

    def has_recent_punishment(
        self,
        *,
        user_id: int,
        action_type: str,
        punishment_type: str,
        within_seconds: int = 30,
    ) -> bool:
        con = None
        try:
            con = self._connect()
            row = con.execute(
                """
                SELECT 1
                FROM security_punishments
                WHERE user_id = ?
                  AND action_type = ?
                  AND punishment_type = ?
                  AND status = 'success'
                  AND created_at >= datetime('now', ?)
                LIMIT 1
                """,
                (
                    int(user_id),
                    _norm_action(action_type),
                    (punishment_type or "").strip().lower(),
                    f"-{max(1, int(within_seconds))} seconds",
                ),
            ).fetchone()
            return bool(row)
        except Exception:
            return False
        finally:
            _safe_close(con)

    def list_limits(self) -> List[Dict[str, Any]]:
        con = None
        try:
            self.ensure_default_limits()
            con = self._connect()
            rows = con.execute(
                """
                SELECT system_name, infraction_limit, punishment_type, updated_at
                FROM security_limits
                ORDER BY system_name ASC
                """
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                d["action_key"] = SYSTEM_TO_ACTION.get(d["system_name"])
                out.append(d)
            return out
        except Exception:
            return []
        finally:
            _safe_close(con)

    def list_infractions(
        self,
        *,
        action_type: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        con = None
        where = []
        params: List[Any] = []
        if action_type:
            where.append("action_type = ?")
            params.append(_norm_action(action_type))
        if user_id is not None:
            where.append("user_id = ?")
            params.append(int(user_id))
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        try:
            con = self._connect()
            rows = con.execute(
                f"""
                SELECT id, user_id, action_type, system_name, event_ts, details_json
                FROM security_infractions
                {clause}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, min(max(1, int(limit)), 500), max(0, int(offset))),
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                raw = d.get("details_json")
                if raw:
                    try:
                        d["details"] = json.loads(raw)
                    except Exception:
                        d["details"] = raw
                else:
                    d["details"] = None
                out.append(d)
            return out
        except Exception:
            return []
        finally:
            _safe_close(con)


class SecurityService:
    def __init__(self, db: Optional[DatabaseService] = None):
        self.db = db or DatabaseService()

    def check_whitelist(self, action_type: str, user_id: int, role_ids: Iterable[int]) -> bool:
        return bool(wl_is_allowed(_norm_action(action_type), int(user_id), [int(r) for r in role_ids or []]))

    def is_system_enabled(self, action_or_system: str) -> bool:
        sys_name = _to_system_name(action_or_system)
        if not sys_name:
            return False
        return self.db.is_system_enabled(sys_name)

    def register_infraction(self, user_id: int, action_type: str, system_name: str, details: Any = None) -> int:
        self.db.register_infraction(
            user_id=int(user_id),
            action_type=_norm_action(action_type),
            system_name=system_name,
            details=details,
        )
        return self.db.get_infraction_count(user_id=int(user_id), action_type=_norm_action(action_type))

    def get_infraction_count(self, user_id: int, action_type: str) -> int:
        return self.db.get_infraction_count(user_id=int(user_id), action_type=_norm_action(action_type))

    def evaluate_event(
        self,
        *,
        user_id: int,
        action_type: str,
        role_ids: Iterable[int],
        details: Any = None,
        event_key: Optional[str] = None,
    ) -> EventDecision:
        system_name = _to_system_name(action_type)
        action_key = _to_action_key(action_type)
        if not system_name or not action_key:
            return EventDecision(True, False, False, 0, 0, False, None, None, None)

        if not self.is_system_enabled(system_name):
            return EventDecision(True, False, False, 0, 0, False, None, system_name, action_key)

        if not self.db.mark_event_once(event_key or ""):
            return EventDecision(False, False, True, 0, 0, False, None, system_name, action_key)

        if self.check_whitelist(action_key, int(user_id), role_ids):
            return EventDecision(False, True, False, 0, 0, False, None, system_name, action_key)

        inf_count = self.register_infraction(
            user_id=int(user_id),
            action_type=action_key,
            system_name=system_name,
            details=details,
        )
        cfg = self.db.get_limit_config(system_name)
        limit = max(1, int(cfg.get("infraction_limit") or 1))
        punishment_type = str(cfg.get("punishment_type") or "remove_roles")
        return EventDecision(
            ignored_system_disabled=False,
            ignored_whitelist=False,
            duplicate_event=False,
            infraction_count=inf_count,
            limit=limit,
            punish=inf_count >= limit,
            punishment_type=punishment_type,
            system_name=system_name,
            action_key=action_key,
        )


class PunishmentService:
    def __init__(self, db: Optional[DatabaseService] = None):
        self.db = db or DatabaseService()

    def register_result(
        self,
        *,
        user_id: int,
        action_type: str,
        system_name: str,
        punishment_type: str,
        reason: str,
        status: str,
        details: Any = None,
    ) -> None:
        self.db.register_punishment(
            user_id=int(user_id),
            action_type=action_type,
            system_name=system_name,
            punishment_type=punishment_type,
            reason=reason,
            status=status,
            details=details,
        )

    def should_skip_duplicate(
        self,
        *,
        user_id: int,
        action_type: str,
        punishment_type: str,
        within_seconds: int = 30,
    ) -> bool:
        return self.db.has_recent_punishment(
            user_id=int(user_id),
            action_type=_norm_action(action_type),
            punishment_type=(punishment_type or "").strip().lower(),
            within_seconds=max(1, int(within_seconds)),
        )


def audit_security_event(
    *,
    action_key: str,
    actor_discord_id: int,
    status: str,
    message: str,
    details: Any = None,
) -> None:
    try:
        log_audit(
            event_type="security",
            system_key="Seguranca",
            action=_norm_action(action_key),
            actor_discord_id=int(actor_discord_id),
            details=details,
            status=(status or "info")[:32],
            message=(message or "")[:500],
            source="bot",
        )
    except Exception:
        pass


# Backward-compatible function API (used by commands/api already in project)
_DB = DatabaseService()
_SEC = SecurityService(_DB)


def ensure_default_settings() -> None:
    _DB.ensure_schema()
    _DB.ensure_default_limits()


def get_action_config(action_key: str) -> Dict[str, Any]:
    return _DB.get_limit_config(action_key)


async def _get_guild_id(app_id: str) -> int:
    """Resolve o guild_id do bot para este app_id, lendo `configuracoes_servidor`
    (linha única, id=1) em `reference_data.db`. `security_limits` no banco real
    do bot usa chave composta `(guild_id, system_name)` — ver
    `APP/utils/security_guard.py::SCHEMA_SQL`, a definição autoritativa (o
    schema embutido aqui só espelha o formato real para montar as queries).
    """
    rows = await reference_service.execute_query(
        app_id, "SELECT guild_id FROM configuracoes_servidor WHERE id = 1 LIMIT 1"
    )
    if not rows or not rows[0].get("guild_id"):
        raise RuntimeError(f"guild_id não configurado para app_id={app_id!r} (configuracoes_servidor)")
    return int(rows[0]["guild_id"])


async def upsert_action_config(
    app_id: str,
    action_key: str,
    *,
    infraction_limit: int,
    punishment_type: str,
    is_enabled: int = 1,
) -> bool:
    """Grava a configuração de segurança no banco real do bot (via Square Cloud,
    por app_id) — não no arquivo local do processo da API. Ver `sqlite_service`.
    """
    sys_name = _to_system_name(action_key)
    if not sys_name:
        raise ValueError(f"Chave de ação inválida: {action_key!r}")
    punishment = (punishment_type or "").strip().lower()
    if punishment not in VALID_PUNISHMENTS:
        raise ValueError(f"Tipo de punição inválido: {punishment!r}. Opções: {sorted(VALID_PUNISHMENTS)}")
    guild_id = await _get_guild_id(app_id)
    await sqlite_service.execute_update(
        app_id,
        """
        INSERT INTO security_limits (guild_id, system_name, infraction_limit, punishment_type, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(guild_id, system_name) DO UPDATE SET
            infraction_limit=excluded.infraction_limit,
            punishment_type=excluded.punishment_type,
            updated_at=datetime('now')
        """,
        (guild_id, sys_name, max(1, int(infraction_limit)), punishment),
    )
    await sqlite_service.execute_update(
        app_id,
        """
        INSERT INTO security_systems (system_name, enabled, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(system_name) DO UPDATE SET enabled=excluded.enabled, updated_at=datetime('now')
        """,
        (sys_name, 1 if int(is_enabled) else 0),
    )
    return True


async def list_action_configs(app_id: str) -> List[Dict[str, Any]]:
    guild_id = await _get_guild_id(app_id)
    rows = await sqlite_service.execute_query(
        app_id,
        "SELECT system_name, infraction_limit, punishment_type, updated_at FROM security_limits WHERE guild_id = ? ORDER BY system_name ASC",
        (guild_id,),
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        d["action_key"] = SYSTEM_TO_ACTION.get(d["system_name"])
        out.append(d)
    return out


def check_whitelist(action_key: str, user_id: int, role_ids: Iterable[int]) -> bool:
    return _SEC.check_whitelist(action_key, int(user_id), role_ids)


def is_system_enabled(action_or_system: str) -> bool:
    return _SEC.is_system_enabled(action_or_system)


def register_infraction(
    *,
    user_id: int,
    action_key: str,
    details: Any = None,
) -> int:
    system_name = _to_system_name(action_key) or ""
    action_type = _to_action_key(action_key) or _norm_action(action_key)
    return _SEC.register_infraction(int(user_id), action_type, system_name, details=details)


def get_infraction_count(*, user_id: int, action_key: str) -> int:
    action_type = _to_action_key(action_key) or _norm_action(action_key)
    return _SEC.get_infraction_count(int(user_id), action_type)


def process_security_event(
    *,
    action_key: str,
    actor_user_id: int,
    actor_role_ids: Iterable[int],
    details: Any = None,
    event_key: Optional[str] = None,
) -> Dict[str, Any]:
    decision = _SEC.evaluate_event(
        user_id=int(actor_user_id),
        action_type=action_key,
        role_ids=actor_role_ids,
        details=details,
        event_key=event_key,
    )
    return {
        "ignored_system_disabled": decision.ignored_system_disabled,
        "ignored_whitelist": decision.ignored_whitelist,
        "duplicate_event": decision.duplicate_event,
        "infraction_count": int(decision.infraction_count),
        "limit": int(decision.limit),
        "punish": bool(decision.punish),
        "punishment_type": decision.punishment_type,
        "system_name": decision.system_name,
        "action_key": decision.action_key,
    }


async def list_recent_infractions(
    app_id: str,
    *,
    action_key: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    action_type = _to_action_key(action_key) if action_key else None
    where = []
    params: List[Any] = []
    if action_type:
        where.append("action_type = ?")
        params.append(action_type)
    if user_id is not None:
        where.append("user_id = ?")
        params.append(int(user_id))
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = await sqlite_service.execute_query(
        app_id,
        f"""
        SELECT id, user_id, action_type, system_name, event_ts, details_json
        FROM security_infractions
        {clause}
        ORDER BY event_ts DESC
        LIMIT ? OFFSET ?
        """,
        (*params, int(limit), int(offset)),
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        raw = d.get("details_json")
        if raw:
            try:
                d["details"] = json.loads(raw)
            except Exception:
                d["details"] = raw
        else:
            d["details"] = None
        out.append(d)
    return out


async def list_system_states(app_id: str) -> List[Dict[str, Any]]:
    rows = await sqlite_service.execute_query(
        app_id, "SELECT system_name, enabled, updated_at FROM security_systems ORDER BY system_name ASC"
    )
    return [dict(r) for r in rows]


async def set_system_state(app_id: str, system_name: str, enabled: int) -> bool:
    sys_name = _to_system_name(system_name)
    if not sys_name:
        raise ValueError(f"Sistema inválido: {system_name!r}")
    await sqlite_service.execute_update(
        app_id,
        """
        INSERT INTO security_systems (system_name, enabled, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(system_name) DO UPDATE SET enabled=excluded.enabled, updated_at=datetime('now')
        """,
        (sys_name, 1 if int(enabled) else 0),
    )
    return True


def get_schema_sql() -> str:
    return SCHEMA_SQL
