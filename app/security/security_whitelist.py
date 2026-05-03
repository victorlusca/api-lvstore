import sqlite3
from typing import Iterable, List, Tuple

from app.settings import data_path

DB_PATH = data_path("master_data.db")
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS security_whitelist_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_key TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS security_whitelist_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_key TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sec_user_action ON security_whitelist_users(action_key, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sec_role_action ON security_whitelist_roles(action_key, role_id);
CREATE TABLE IF NOT EXISTS security_whitelist_global_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS security_whitelist_global_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sec_g_user ON security_whitelist_global_users(user_id);
CREATE INDEX IF NOT EXISTS idx_sec_g_role ON security_whitelist_global_roles(role_id);
"""


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def _ensure_schema():
    try:
        con = _connect()
        cur = con.cursor()
        cur.executescript(SCHEMA_SQL)
        con.commit(); con.close()
    except Exception:
        pass


_ensure_schema()


def _norm_action(action_key: str) -> str:
    return (action_key or "").strip().lower()


def add_user(action_key: str, user_id: int) -> None:
    try:
        con = _connect()
        con.execute(
            "INSERT OR IGNORE INTO security_whitelist_users (action_key, user_id) VALUES (?, ?)",
            (_norm_action(action_key), int(user_id)),
        )
        con.commit(); con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass


def remove_user(action_key: str, user_id: int) -> None:
    try:
        con = _connect()
        con.execute(
            "DELETE FROM security_whitelist_users WHERE action_key = ? AND user_id = ?",
            (_norm_action(action_key), int(user_id)),
        )
        con.commit(); con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass


def add_role(action_key: str, role_id: int) -> None:
    try:
        con = _connect()
        con.execute(
            "INSERT OR IGNORE INTO security_whitelist_roles (action_key, role_id) VALUES (?, ?)",
            (_norm_action(action_key), int(role_id)),
        )
        con.commit(); con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass


def remove_role(action_key: str, role_id: int) -> None:
    try:
        con = _connect()
        con.execute(
            "DELETE FROM security_whitelist_roles WHERE action_key = ? AND role_id = ?",
            (_norm_action(action_key), int(role_id)),
        )
        con.commit(); con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass


def is_allowed(action_key: str, user_id: int, role_ids: Iterable[int]) -> bool:
    try:
        con = _connect()
        cur = con.cursor()
        norm_action = _norm_action(action_key)

        # global user whitelist
        row_global_user = cur.execute(
            "SELECT 1 FROM security_whitelist_global_users WHERE user_id = ? LIMIT 1",
            (int(user_id),),
        ).fetchone()
        if row_global_user:
            con.close()
            return True

        # user check
        row = cur.execute(
            "SELECT 1 FROM security_whitelist_users WHERE action_key = ? AND user_id = ? LIMIT 1",
            (norm_action, int(user_id)),
        ).fetchone()
        if row:
            con.close()
            return True

        # role checks
        role_ids = list(set(int(r) for r in role_ids or []))
        if not role_ids:
            con.close()
            return False

        qmarks = ",".join(["?"] * len(role_ids))
        row_global_role = cur.execute(
            f"SELECT 1 FROM security_whitelist_global_roles WHERE role_id IN ({qmarks}) LIMIT 1",
            tuple(role_ids),
        ).fetchone()
        if row_global_role:
            con.close()
            return True

        qmarks = ",".join(["?"] * len(role_ids))
        sql = f"SELECT 1 FROM security_whitelist_roles WHERE action_key = ? AND role_id IN ({qmarks}) LIMIT 1"
        row2 = cur.execute(sql, (norm_action, *role_ids)).fetchone()
        con.close()
        return bool(row2)
    except Exception:
        try:
            con.close()
        except Exception:
            pass
        return False


def list_action_whitelist(action_key: str) -> Tuple[List[int], List[int]]:
    users: List[int] = []
    roles: List[int] = []
    try:
        con = _connect()
        cur = con.cursor()
        norm_action = _norm_action(action_key)
        for (uid,) in cur.execute(
            "SELECT user_id FROM security_whitelist_users WHERE action_key = ? ORDER BY user_id ASC",
            (norm_action,),
        ).fetchall():
            users.append(int(uid))
        for (rid,) in cur.execute(
            "SELECT role_id FROM security_whitelist_roles WHERE action_key = ? ORDER BY role_id ASC",
            (norm_action,),
        ).fetchall():
            roles.append(int(rid))
        con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass
    return users, roles


def add_global_user(user_id: int) -> None:
    try:
        con = _connect()
        con.execute(
            "INSERT OR IGNORE INTO security_whitelist_global_users (user_id) VALUES (?)",
            (int(user_id),),
        )
        con.commit(); con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass


def remove_global_user(user_id: int) -> None:
    try:
        con = _connect()
        con.execute("DELETE FROM security_whitelist_global_users WHERE user_id = ?", (int(user_id),))
        con.commit(); con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass


def add_global_role(role_id: int) -> None:
    try:
        con = _connect()
        con.execute(
            "INSERT OR IGNORE INTO security_whitelist_global_roles (role_id) VALUES (?)",
            (int(role_id),),
        )
        con.commit(); con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass


def remove_global_role(role_id: int) -> None:
    try:
        con = _connect()
        con.execute("DELETE FROM security_whitelist_global_roles WHERE role_id = ?", (int(role_id),))
        con.commit(); con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass


def list_global_whitelist() -> Tuple[List[int], List[int]]:
    users: List[int] = []
    roles: List[int] = []
    try:
        con = _connect()
        cur = con.cursor()
        for (uid,) in cur.execute(
            "SELECT user_id FROM security_whitelist_global_users ORDER BY user_id ASC"
        ).fetchall():
            users.append(int(uid))
        for (rid,) in cur.execute(
            "SELECT role_id FROM security_whitelist_global_roles ORDER BY role_id ASC"
        ).fetchall():
            roles.append(int(rid))
        con.close()
    except Exception:
        try:
            con.close()
        except Exception:
            pass
    return users, roles


def get_schema_sql() -> str:
    return SCHEMA_SQL

