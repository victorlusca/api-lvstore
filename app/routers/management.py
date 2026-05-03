from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
from app.core.security import get_api_key
from app.services.sqlite_engine import sqlite_service, reference_service
from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/management", tags=["Management"])

# --- HIERARQUIA E PROGRESSO ---

@router.get("/hierarchy", dependencies=[Depends(get_api_key)])
async def get_hierarchy_list(app_id: str):
    audit_log(app_id, "GET_HIERARCHY_LIST", "Fetching hierarchy roles definition")
    query = """
    SELECT 
        id, 
        hierarchy_index, 
        cargo_id, 
        nome, 
        sigla, 
        horas, 
        is_superior, 
        is_active 
    FROM hierarquia
    ORDER BY hierarchy_index ASC
    """
    data = await reference_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.get("/hierarchy/progress", dependencies=[Depends(get_api_key)])
async def get_hierarchy_progress(app_id: str):
    audit_log(app_id, "GET_HIERARCHY_PROGRESS", "Fetching player hierarchy progress")
    query = """
    SELECT 
        p.playerName as nome,
        p.playerID as game_id,
        hp.total_hours as horas_progresso,
        hp.role as cargo_id
    FROM players p
    JOIN player_hierarchy_progress hp ON p.playerID = hp.user_id
    """
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

# --- ADVERTÊNCIAS ---

@router.get("/warnings", dependencies=[Depends(get_api_key)])
async def get_all_warnings(app_id: str):
    audit_log(app_id, "GET_WARNINGS", "Fetching all player warnings")
    query = """
    SELECT 
        w.*,
        p.playerName as nome,
        p.playerLogin as login,
        p.playerID as game_id
    FROM player_warnings w
    LEFT JOIN players p ON w.user_id_save = p.discordUserID
    ORDER BY w.id DESC
    """
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

# --- AUSÊNCIAS ---

@router.get("/absences", dependencies=[Depends(get_api_key)])
async def get_all_absences(app_id: str):
    audit_log(app_id, "GET_ABSENCES", "Fetching all player absences")
    query = """
    SELECT 
        a.*,
        p.playerName as nome,
        p.playerLogin as login,
        p.playerID as game_id
    FROM player_absences a
    LEFT JOIN players p ON a.user_id_save = p.discordUserID
    ORDER BY a.id DESC
    """
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

# --- ROTAS ---

@router.get("/routes/daily", dependencies=[Depends(get_api_key)])
async def get_daily_routes(app_id: str):
    audit_log(app_id, "GET_DAILY_ROUTES", "Fetching daily routes")
    query = """
    SELECT 
        d.*,
        p.playerName as nome,
        p.playerLogin as login,
        p.playerID as game_id
    FROM daily_routes d
    LEFT JOIN players p ON d.user_id = p.discordUserID
    """
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.get("/routes/total", dependencies=[Depends(get_api_key)])
async def get_total_routes(app_id: str):
    audit_log(app_id, "GET_TOTAL_ROUTES", "Fetching total routes summary")
    query = """
    SELECT 
        t.*,
        p.playerName as nome,
        p.playerLogin as login,
        p.playerID as game_id
    FROM total_routes t
    LEFT JOIN players p ON t.user_id = p.discordUserID
    ORDER BY t.total_routes DESC
    """
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

# --- RANKING DE SUPERIORES ---

@router.get("/supervisors/ranking", dependencies=[Depends(get_api_key)])
async def get_supervisors_ranking(app_id: str):
    audit_log(app_id, "GET_SUPERVISORS_RANKING", "Fetching supervisor ranking")
    query = """
    SELECT 
        s.*,
        p.playerName as nome,
        p.playerLogin as login,
        p.playerID as game_id
    FROM staff_actions_summary s
    LEFT JOIN players p ON s.discord_user_id = p.discordUserID
    ORDER BY s.pontos_totais DESC
    """
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}
