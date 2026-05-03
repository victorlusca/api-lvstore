from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.core.security import get_api_key
from app.services.sqlite_engine import sqlite_service
from datetime import datetime
import logging

from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/ranking", tags=["Ranking"])

class RankingUpdate(BaseModel):
    discord_id: Optional[str] = None
    game_id: Optional[str] = None
    operacao: str # 'adicionar' ou 'setar'
    valor: float

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

@router.post("/horas", dependencies=[Depends(get_api_key)])
async def update_ranking_hours(app_id: str, update: RankingUpdate):
    audit_log(app_id, "UPDATE_RANKING_HOURS", f"Player: {update.game_id} | Op: {update.operacao} | Val: {update.valor}")
    
    target_id = update.game_id
    if not target_id:
        raise HTTPException(status_code=400, detail="game_id is required")

    if update.operacao == "setar":
        query = "INSERT OR REPLACE INTO player_total_hours (user_id, total_hours) VALUES (?, ?)"
        params = (target_id, str(update.valor))
    else: # adicionar
        query = """
        INSERT INTO player_total_hours (user_id, total_hours) 
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET total_hours = CAST(total_hours AS REAL) + ?
        """
        params = (target_id, str(update.valor), update.valor)
    
    await sqlite_service.execute_update(app_id, query, params)
    return {"ok": True, "message": "Horas atualizadas com sucesso"}

@router.post("/pontos", dependencies=[Depends(get_api_key)])
async def update_ranking_points(app_id: str, update: RankingUpdate):
    audit_log(app_id, "UPDATE_RANKING_POINTS", f"Player: {update.game_id} | Discord: {update.discord_id} | Op: {update.operacao} | Val: {update.valor}")
    
    # Precisamos de pelo menos um ID
    if not update.game_id and not update.discord_id:
        raise HTTPException(status_code=400, detail="game_id or discord_id is required")

    # Tentamos descobrir ambos os IDs para garantir compatibilidade com qualquer schema
    game_id = update.game_id
    discord_id = update.discord_id
    
    # Se faltar um deles, tentamos buscar na tabela players
    if not game_id or not discord_id:
        try:
            if game_id:
                query_lookup = "SELECT discordUserID FROM players WHERE playerID = ?"
                res = await sqlite_service.execute_query(app_id, query_lookup, (game_id,))
                if res and res[0].get("discordUserID"):
                    discord_id = res[0]["discordUserID"]
            else: # temos discord_id
                query_lookup = "SELECT playerID FROM players WHERE discordUserID = ?"
                res = await sqlite_service.execute_query(app_id, query_lookup, (discord_id,))
                if res and res[0].get("playerID"):
                    game_id = res[0]["playerID"]
        except Exception:
            pass # Se falhar a busca, continuamos com o que temos

    try:
        # Lógica de atualização resiliente
        if update.operacao == "setar":
            # 1. Tenta INSERT OR REPLACE com game_id (schema novo)
            try:
                query = "INSERT OR REPLACE INTO player_points (game_id, total_points, discord_id) VALUES (?, ?, ?)"
                params = (game_id or discord_id, int(update.valor), discord_id or game_id)
                await sqlite_service.execute_update(app_id, query, params)
            except HTTPException:
                # 2. Tenta com discord_id (schema antigo)
                query = "INSERT OR REPLACE INTO player_points (discord_id, total_points) VALUES (?, ?)"
                params = (discord_id or game_id, int(update.valor))
                await sqlite_service.execute_update(app_id, query, params)
        else: # adicionar
            try:
                # Tenta o ON CONFLICT com game_id
                query = """
                INSERT INTO player_points (game_id, total_points, discord_id) 
                VALUES (?, ?, ?)
                ON CONFLICT(game_id) DO UPDATE SET total_points = total_points + ?
                """
                params = (game_id or discord_id, int(update.valor), discord_id or game_id, int(update.valor))
                await sqlite_service.execute_update(app_id, query, params)
            except HTTPException:
                try:
                    # Tenta o ON CONFLICT com discord_id
                    query = """
                    INSERT INTO player_points (discord_id, total_points) 
                    VALUES (?, ?)
                    ON CONFLICT(discord_id) DO UPDATE SET total_points = total_points + ?
                    """
                    params = (discord_id or game_id, int(update.valor), int(update.valor))
                    await sqlite_service.execute_update(app_id, query, params)
                except HTTPException:
                    # Fallback final: INSERT OR IGNORE + UPDATE manual
                    # Tenta ambos os campos no WHERE para garantir
                    key_field = "game_id" if game_id else "discord_id"
                    key_val = game_id or discord_id
                    
                    query_insert = f"INSERT OR IGNORE INTO player_points ({key_field}, total_points) VALUES (?, 0)"
                    await sqlite_service.execute_update(app_id, query_insert, (key_val,))
                    
                    query_update = f"UPDATE player_points SET total_points = total_points + ? WHERE {key_field} = ?"
                    await sqlite_service.execute_update(app_id, query_update, (int(update.valor), key_val))
                
        return {"ok": True, "message": "Pontos atualizados com sucesso"}
    except Exception as e:
        logging.error(f"Erro fatal ao atualizar pontos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco de dados: {str(e)}")

@router.post("/reset-hours", dependencies=[Depends(get_api_key)])
async def reset_ranking_hours(app_id: str):
    audit_log(app_id, "RESET_RANKING_HOURS", "Resetting all player hours")
    query = "UPDATE player_total_hours SET total_hours = '0'"
    await sqlite_service.execute_update(app_id, query)
    return {"ok": True, "message": "Todas as horas foram zeradas."}

@router.post("/reset-points", dependencies=[Depends(get_api_key)])
async def reset_ranking_points(app_id: str):
    audit_log(app_id, "RESET_RANKING_POINTS", "Resetting all player points")
    query = "UPDATE player_points SET total_points = 0"
    await sqlite_service.execute_update(app_id, query)
    return {"ok": True, "message": "Todos os pontos foram zerados."}
