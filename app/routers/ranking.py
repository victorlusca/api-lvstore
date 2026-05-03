from fastapi import APIRouter, Depends
from app.core.security import get_api_key
from app.services.sqlite_engine import sqlite_service
from datetime import datetime
import logging

from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/ranking", tags=["Ranking"])

@router.get("/points", dependencies=[Depends(get_api_key)])
async def get_ranking_points(app_id: str):
    audit_log(app_id, "GET_RANKING_POINTS", "Fetching top players by points")
    
    query = """
    SELECT 
        p.playerName as nome,
        p.playerID as game_id,
        COALESCE(pts.total_points, 0) as pontos
    FROM players p
    LEFT JOIN player_points pts ON p.playerID = pts.game_id
    ORDER BY pontos DESC
    """
    
    ranking = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": ranking}

@router.get("/active", dependencies=[Depends(get_api_key)])
async def get_ranking_active(app_id: str):
    audit_log(app_id, "GET_RANKING_ACTIVE", "Fetching active players (in sessions)")
    
    # Jogadores ativos são aqueles que possuem uma entrada na tabela active_sessions
    query = """
    SELECT 
        p.playerName as nome,
        p.playerID as game_id,
        COALESCE(h.total_hours, 0) as horas_totais,
        s.status as sessao_status
    FROM players p
    JOIN active_sessions s ON p.playerID = s.user_id
    LEFT JOIN player_total_hours h ON p.playerID = h.user_id
    ORDER BY h.total_hours DESC
    """
    
    active_players = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": active_players}

@router.get("/inactive", dependencies=[Depends(get_api_key)])
async def get_ranking_inactive(app_id: str):
    audit_log(app_id, "GET_RANKING_INACTIVE", "Fetching inactive players (not in sessions)")
    
    # Jogadores inativos são aqueles que NÃO possuem entrada na tabela active_sessions
    query = """
    SELECT 
        p.playerName as nome,
        p.playerID as game_id,
        COALESCE(h.total_hours, 0) as horas_totais
    FROM players p
    LEFT JOIN player_total_hours h ON p.playerID = h.user_id
    WHERE p.playerID NOT IN (SELECT user_id FROM active_sessions)
    ORDER BY h.total_hours DESC
    """
    
    inactive_players = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": inactive_players}
