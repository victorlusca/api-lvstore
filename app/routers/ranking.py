from fastapi import APIRouter, Depends
from app.core.security import get_api_key
from app.services.sqlite_engine import sqlite_service
from datetime import datetime
import logging

from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/ranking", tags=["Ranking"])

@router.get("/", dependencies=[Depends(get_api_key)])
async def get_ranking(app_id: str):
    audit_log(app_id, "GET_RANKING", "Fetching top players by points")
    
    query = """
    SELECT 
        p.playerName as nome,
        COALESCE(pts.total_points, 0) as pontos
    FROM players p
    LEFT JOIN player_points pts ON p.playerID = pts.playerID
    ORDER BY pontos DESC
    LIMIT 10
    """
    
    ranking = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": ranking}
