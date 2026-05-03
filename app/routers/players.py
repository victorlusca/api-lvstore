from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
from app.core.security import get_api_key
from app.services.sqlite_engine import sqlite_service
from datetime import datetime
import logging

from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/players", tags=["Players"])

@router.get("/", dependencies=[Depends(get_api_key)])
async def get_all_players(app_id: str):
    audit_log(app_id, "GET_PLAYERS", "Fetching all players with hours and points")
    
    query = """
    SELECT 
        p.id, 
        p.playerName as nome, 
        p.playerLogin as login, 
        p.playerID as game_id, 
        p.discordUserID as discord_id,
        COALESCE(h.total_hours, 0) as horas_totais,
        COALESCE(pts.total_points, 0) as pontos
    FROM players p
    LEFT JOIN player_total_hours h ON p.playerID = h.user_id
    LEFT JOIN player_points pts ON p.playerID = pts.game_id
    """
    
    players = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": players}

@router.get("/{player_id}", dependencies=[Depends(get_api_key)])
async def get_player_by_id(app_id: str, player_id: int):
    audit_log(app_id, "GET_PLAYER_DETAIL", f"Player ID: {player_id}")
    
    query = """
    SELECT 
        p.id, 
        p.playerName as nome, 
        p.playerLogin as login, 
        p.playerID as game_id, 
        p.discordUserID as discord_id,
        COALESCE(h.total_hours, 0) as horas_totais,
        COALESCE(pts.total_points, 0) as pontos
    FROM players p
    LEFT JOIN player_total_hours h ON p.playerID = h.user_id
    LEFT JOIN player_points pts ON p.playerID = pts.game_id
    WHERE p.id = ?
    """
    
    results = await sqlite_service.execute_query(app_id, query, (player_id,))
    if not results:
        raise HTTPException(status_code=404, detail="Player not found")
        
    return {"ok": True, "data": results[0]}

class PlayerCreate(BaseModel):
    nome: str
    login: str
    game_id: str
    discord_id: str

@router.post("/", dependencies=[Depends(get_api_key)])
async def create_player(app_id: str, player: PlayerCreate):
    audit_log(app_id, "CREATE_PLAYER", f"Player: {player.nome} ({player.game_id})")
    
    query = """
    INSERT INTO players (playerName, playerLogin, playerID, discordUserID)
    VALUES (?, ?, ?, ?)
    """
    params = (
        player.nome,
        player.login,
        player.game_id,
        player.discord_id
    )
    
    await sqlite_service.execute_update(app_id, query, params)
    return {"ok": True, "message": f"Jogador {player.nome} cadastrado com sucesso e banco sincronizado."}

@router.put("/{player_id}", dependencies=[Depends(get_api_key)])
async def update_player(app_id: str, player_id: int, player: PlayerCreate):
    audit_log(app_id, "UPDATE_PLAYER", f"Player ID: {player_id} | New Data: {player.nome}")
    
    query = """
    UPDATE players 
    SET playerName = ?, playerLogin = ?, playerID = ?, discordUserID = ?
    WHERE id = ?
    """
    params = (
        player.nome,
        player.login,
        player.game_id,
        player.discord_id,
        player_id
    )
    
    await sqlite_service.execute_update(app_id, query, params)
    return {"ok": True, "message": f"Jogador ID {player_id} atualizado com sucesso."}

@router.delete("/{player_id}", dependencies=[Depends(get_api_key)])
async def delete_player(app_id: str, player_id: int):
    audit_log(app_id, "DELETE_PLAYER", f"Player ID: {player_id}")
    
    query = "DELETE FROM players WHERE id = ?"
    await sqlite_service.execute_update(app_id, query, (player_id,))
    
    return {"ok": True, "message": "Player deleted and database synced"}
