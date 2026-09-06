from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.services.sqlite_engine import sqlite_service
from app.responses import com_horas_normalizadas, horas_hhmm, minutos_de_horas
from datetime import datetime
import logging

from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/ranking", tags=["Ranking"])

class RankingUpdate(BaseModel):
    discord_id: Optional[str] = None
    game_id: Optional[str] = None
    operacao: str # 'adicionar' ou 'setar'
    valor: float

@router.get("/points", dependencies=[Depends(require_scope("admin:*"))])
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

@router.get("/total", dependencies=[Depends(require_scope("admin:*"))])
async def get_ranking_total(app_id: str):
    audit_log(app_id, "GET_RANKING_TOTAL", "Fetching all players by total hours")
    
    query = """
    SELECT 
        p.playerName as nome,
        p.playerLogin as login,
        p.playerID as game_id,
        p.discordUserID as discord_id,
        COALESCE(h.total_hours, 0) as horas_totais
    FROM players p
    LEFT JOIN player_total_hours h ON p.discordUserID = h.user_id
    """

    # A ordenação sai do SQL: `CAST('12:30' AS REAL)` vale 12 — descarta os
    # minutos e coloca "9:59" acima de "10:00". Ordenar por minutos é exato.
    ranking = com_horas_normalizadas(await sqlite_service.execute_query(app_id, query))
    ranking.sort(key=lambda r: r.get("horas_totais_minutos", 0), reverse=True)
    return {"ok": True, "data": ranking}

@router.get("/active", dependencies=[Depends(require_scope("admin:*"))])
async def get_ranking_active(app_id: str):
    audit_log(app_id, "GET_RANKING_ACTIVE", "Fetching active players (in sessions)")
    
    # Jogadores ativos são aqueles que possuem uma entrada na tabela active_sessions
    query = """
    SELECT 
        p.playerName as nome,
        p.playerLogin as login,
        p.playerID as game_id,
        p.discordUserID as discord_id,
        COALESCE(h.total_hours, 0) as horas_totais,
        s.status as sessao_status
    FROM players p
    JOIN active_sessions s ON p.playerID = s.user_id
    LEFT JOIN player_total_hours h ON p.discordUserID = h.user_id
    """

    active_players = com_horas_normalizadas(await sqlite_service.execute_query(app_id, query))
    active_players.sort(key=lambda r: r.get("horas_totais_minutos", 0), reverse=True)
    return {"ok": True, "data": active_players}

@router.get("/inactive", dependencies=[Depends(require_scope("admin:*"))])
async def get_ranking_inactive(app_id: str):
    audit_log(app_id, "GET_RANKING_INACTIVE", "Fetching inactive players (not in sessions)")
    
    # Jogadores inativos são aqueles que NÃO possuem entrada na tabela active_sessions
    query = """
    SELECT 
        p.playerName as nome,
        p.playerLogin as login,
        p.playerID as game_id,
        p.discordUserID as discord_id,
        COALESCE(h.total_hours, 0) as horas_totais
    FROM players p
    LEFT JOIN player_total_hours h ON p.discordUserID = h.user_id
    WHERE p.playerID NOT IN (SELECT user_id FROM active_sessions)
    """

    inactive_players = com_horas_normalizadas(await sqlite_service.execute_query(app_id, query))
    inactive_players.sort(key=lambda r: r.get("horas_totais_minutos", 0), reverse=True)
    return {"ok": True, "data": inactive_players}

@router.get("/supervisors", dependencies=[Depends(require_scope("admin:*"))])
async def get_ranking_supervisors(app_id: str):
    audit_log(app_id, "GET_RANKING_SUPERVISORS", "Fetching supervisor actions ranking")
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

@router.post("/horas", dependencies=[Depends(require_scope("admin:*"))])
async def update_ranking_hours(app_id: str, update: RankingUpdate):
    audit_log(app_id, "UPDATE_RANKING_HOURS", f"Player: {update.game_id} | Discord: {update.discord_id} | Op: {update.operacao} | Val: {update.valor}")
    
    # Precisamos de pelo menos um ID
    if not update.game_id and not update.discord_id:
        raise HTTPException(status_code=400, detail="game_id or discord_id is required")

    game_id = update.game_id
    discord_id = update.discord_id
    
    # Se faltar o discord_id, tentamos buscar na tabela players
    if not discord_id and game_id:
        try:
            query_lookup = "SELECT discordUserID FROM players WHERE playerID = ?"
            res = await sqlite_service.execute_query(app_id, query_lookup, (game_id,))
            if res and res[0].get("discordUserID"):
                discord_id = res[0]["discordUserID"]
        except Exception:
            pass

    # O usuário informou que a tabela player_total_hours usa o Discord ID como user_id
    target_id = discord_id or game_id

    # `valor` vem do painel em HORAS decimais; o banco do bot guarda "HH:MM".
    # Gravar o decimal cru fazia o bot ler ZERO — o membro ficava com as horas
    # no site e nenhuma na hierarquia/upamento.
    minutos = max(0, int(round(float(update.valor) * 60)))

    if update.operacao != "setar":  # adicionar
        # Soma feita aqui, não em SQL: `CAST('12:30' AS REAL) + x` descarta os
        # minutos e corrompe o acumulado.
        atual = await sqlite_service.execute_query(
            app_id, "SELECT total_hours FROM player_total_hours WHERE user_id = ?", (target_id,)
        )
        if atual:
            minutos += minutos_de_horas(atual[0].get("total_hours"))

    query = """
    INSERT INTO player_total_hours (user_id, total_hours)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET total_hours = excluded.total_hours
    """
    await sqlite_service.execute_update(app_id, query, (target_id, horas_hhmm(minutos)))
    return {"ok": True, "message": "Horas atualizadas com sucesso", "total_hours": horas_hhmm(minutos)}

@router.post("/pontos", dependencies=[Depends(require_scope("admin:*"))])
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
        # 1. Obter pontos atuais se for 'adicionar'
        current_points = 0
        if update.operacao == "adicionar":
            # Tenta buscar por qualquer um dos IDs
            query_get = "SELECT total_points FROM player_points WHERE game_id = ? OR discord_id = ? LIMIT 1"
            res_pts = await sqlite_service.execute_query(app_id, query_get, (game_id or "NONE", discord_id or "NONE"))
            if res_pts:
                current_points = res_pts[0].get("total_points", 0)
        
        new_total = current_points + update.valor if update.operacao == "adicionar" else update.valor

        # 2. LIMPEZA: Remove QUALQUER registro duplicado para este jogador
        # Usamos game_id e discord_id para garantir que limpamos tudo
        query_del = "DELETE FROM player_points WHERE (game_id IS NOT NULL AND game_id = ?) OR (discord_id IS NOT NULL AND discord_id = ?)"
        await sqlite_service.execute_update(app_id, query_del, (game_id or "NONE", discord_id or "NONE"))

        # 3. INSERÇÃO: Insere um registro único e limpo
        # Tentamos o schema mais completo primeiro
        try:
            query_ins = "INSERT INTO player_points (game_id, total_points, discord_id) VALUES (?, ?, ?)"
            await sqlite_service.execute_update(app_id, query_ins, (game_id or discord_id, int(new_total), discord_id or game_id))
        except HTTPException:
            # Se falhar, tenta o schema reduzido (apenas discord_id)
            query_ins = "INSERT INTO player_points (discord_id, total_points) VALUES (?, ?)"
            await sqlite_service.execute_update(app_id, query_ins, (discord_id or game_id, int(new_total)))
                
        return {"ok": True, "message": "Pontos atualizados com sucesso (substituído)"}
    except Exception as e:
        logging.error(f"Erro fatal ao atualizar pontos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco de dados: {str(e)}")

@router.post("/reset-hours", dependencies=[Depends(require_scope("admin:*"))])
async def reset_ranking_hours(app_id: str):
    audit_log(app_id, "RESET_RANKING_HOURS", "Resetting all player hours")
    # "00:00" e não "0": o formato canônico do bot é sempre HH:MM.
    query = "UPDATE player_total_hours SET total_hours = '00:00'"
    await sqlite_service.execute_update(app_id, query)
    return {"ok": True, "message": "Todas as horas foram zeradas."}

@router.post("/reset-points", dependencies=[Depends(require_scope("admin:*"))])
async def reset_ranking_points(app_id: str):
    audit_log(app_id, "RESET_RANKING_POINTS", "Resetting all player points")
    query = "UPDATE player_points SET total_points = 0"
    await sqlite_service.execute_update(app_id, query)
    return {"ok": True, "message": "Todos os pontos foram zerados."}
