"""
helpers.py â€” utilitÃ¡rios compartilhados entre os blueprints da API.
"""
import sqlite3
from typing import Optional, Dict, Any

_MASTER_DB    = "data/master_data.db"
_REFERENCE_DB = "data/reference_data.db"


def master_con() -> sqlite3.Connection:
    c = sqlite3.connect(_MASTER_DB)
    c.row_factory = sqlite3.Row
    return c


def ref_con() -> sqlite3.Connection:
    c = sqlite3.connect(_REFERENCE_DB)
    c.row_factory = sqlite3.Row
    return c


def resolve_player(discord_id: Optional[int]) -> Dict[str, Any]:
    """Converte discord_id para {nome, login, game_id}. Retorna fallback se nÃ£o encontrar."""
    if not discord_id:
        return {"nome": "â€”", "login": "â€”", "game_id": None}
    try:
        con = master_con()
        row = con.execute(
            "SELECT playerName, playerLogin, playerID FROM players WHERE discordUserID = ?",
            (int(discord_id),),
        ).fetchone()
        con.close()
        if row:
            return {"nome": row["playerName"], "login": row["playerLogin"], "game_id": row["playerID"]}
    except Exception:
        pass
    return {"nome": str(discord_id), "login": str(discord_id), "game_id": None}


def resolve_player_by_game_id(game_id: Optional[int]) -> Dict[str, Any]:
    if not game_id:
        return {"nome": "â€”", "login": "â€”", "discord_id": None}
    try:
        con = master_con()
        row = con.execute(
            "SELECT playerName, playerLogin, discordUserID FROM players WHERE playerID = ?",
            (int(game_id),),
        ).fetchone()
        con.close()
        if row:
            return {"nome": row["playerName"], "login": row["playerLogin"], "discord_id": row["discordUserID"]}
    except Exception:
        pass
    return {"nome": str(game_id), "login": str(game_id), "discord_id": None}

