"""
routes_ranking.py â€” Rankings de Bate-Ponto e Pontos (FastAPI version).
"""
import sqlite3
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.audit import write_audit
from app.helpers import master_con, resolve_player

router = APIRouter(tags=["Ranking"])

_MASTER = "data/master_data.db"

def _build_active_list():
    """Retorna lista completa ordenada por horas DESC, com resoluÃ§Ã£o de jogador."""
    con = master_con()
    rows = con.execute(
        """
        SELECT p.id, p.playerName, p.playerLogin, p.playerID, p.discordUserID,
               COALESCE(h.total_hours, '0') AS total_hours
        FROM players p
        LEFT JOIN player_total_hours h ON h.user_id = p.discordUserID
        ORDER BY CAST(COALESCE(h.total_hours,'0') AS REAL) DESC
        """
    ).fetchall()
    con.close()
    result = []
    for i, r in enumerate(rows, 1):
        result.append({
            "posicao": i,
            "id": r["id"],
            "nome": r["playerName"],
            "login": r["playerLogin"],
            "game_id": r["playerID"],
            "discord_id": r["discordUserID"],
            "horas_totais": r["total_hours"],
        })
    return result

def _build_points_list():
    con = master_con()
    rows = con.execute(
        """
        SELECT p.id, p.playerName, p.playerLogin, p.playerID, p.discordUserID,
               COALESCE(pt.total_points, 0) AS total_points
        FROM players p
        LEFT JOIN player_points pt ON pt.discord_id = p.discordUserID
        ORDER BY COALESCE(pt.total_points,0) DESC
        """
    ).fetchall()
    con.close()
    result = []
    for i, r in enumerate(rows, 1):
        result.append({
            "posicao": i,
            "id": r["id"],
            "nome": r["playerName"],
            "login": r["playerLogin"],
            "game_id": r["playerID"],
            "discord_id": r["discordUserID"],
            "pontos": r["total_points"],
        })
    return result

# â”€â”€ ATIVOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/ranking/ativos")
async def ranking_ativos(_ = Depends(require_scope("references:read"))):
    try:
        lista = _build_active_list()
        top3  = lista[:3]
        res, status = ok({"top3": top3, "lista": lista})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ranking/inativos")
async def ranking_inativos(_ = Depends(require_scope("references:read"))):
    try:
        con = master_con()
        rows = con.execute(
            """
            SELECT p.id, p.playerName, p.playerLogin, p.playerID, p.discordUserID
            FROM players p
            LEFT JOIN player_total_hours h ON h.user_id = p.discordUserID
            WHERE h.total_hours IS NULL OR h.total_hours = '0'
            ORDER BY p.playerName ASC
            """
        ).fetchall()
        con.close()
        data = [{
            "id": r["id"],
            "nome": r["playerName"],
            "login": r["playerLogin"],
            "game_id": r["playerID"],
            "discord_id": r["discordUserID"]
        } for r in rows]
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# â”€â”€ PONTOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/ranking/pontos")
async def ranking_pontos(_ = Depends(require_scope("references:read"))):
    try:
        lista = _build_points_list()
        top3  = lista[:3]
        res, status = ok({"top3": top3, "lista": lista})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

