from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
from app.auth import require_scope
from app.services.sqlite_engine import sqlite_service, reference_service
from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/management", tags=["Management"])

class HierarchyUpdate(BaseModel):
    hierarchy_index: int
    cargo_id: int
    nome: str
    sigla: str
    horas: int
    is_superior: int
    is_active: int

# --- HIERARQUIA E PROGRESSO ---

@router.get("/hierarchy", dependencies=[Depends(require_scope("admin:*"))])
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

@router.put("/hierarchy/{item_id}", dependencies=[Depends(require_scope("admin:*"))])
async def update_hierarchy_item(app_id: str, item_id: int, item: HierarchyUpdate):
    audit_log(app_id, "UPDATE_HIERARCHY", f"Updating hierarchy item ID: {item_id}")
    query = """
    UPDATE hierarquia SET 
        hierarchy_index = ?, 
        cargo_id = ?, 
        nome = ?, 
        sigla = ?, 
        horas = ?, 
        is_superior = ?, 
        is_active = ?
    WHERE id = ?
    """
    params = (
        item.hierarchy_index, item.cargo_id, item.nome, 
        item.sigla, item.horas, item.is_superior, 
        item.is_active, item_id
    )
    await reference_service.execute_update(app_id, query, params)
    return {"ok": True, "message": "Item da hierarquia atualizado"}

@router.post("/hierarchy", dependencies=[Depends(require_scope("admin:*"))])
async def create_hierarchy_item(app_id: str, item: HierarchyUpdate):
    audit_log(app_id, "CREATE_HIERARCHY", f"Creating hierarchy item: {item.nome}")
    query = """
    INSERT INTO hierarquia (hierarchy_index, cargo_id, nome, sigla, horas, is_superior, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        item.hierarchy_index, item.cargo_id, item.nome, 
        item.sigla, item.horas, item.is_superior, item.is_active
    )
    await reference_service.execute_update(app_id, query, params)
    return {"ok": True, "message": "Item da hierarquia criado"}

@router.get("/hierarchy/progress", dependencies=[Depends(require_scope("admin:*"))])
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

@router.get("/warnings", dependencies=[Depends(require_scope("admin:*"))])
async def get_all_warnings(app_id: str):
    """Advertências com os dois lados resolvidos.

    Nomes enganosos no schema do bot (`APP/commands/advertencia.py`):
    `game_user_id` é quem **levou** a advertência e `user_id_save` é quem a
    **aplicou**. A consulta antiga fazia um join só, pelo `user_id_save`, e
    devolvia o responsável nos campos `nome/login/game_id` — ou seja, o painel
    mostrava o responsável no lugar do advertido.
    """
    audit_log(app_id, "GET_WARNINGS", "Fetching all player warnings")
    query = """
    SELECT
        w.*,
        adv.playerName as nome,
        adv.playerLogin as login,
        adv.playerID as game_id,
        resp.playerName as resp_nome,
        resp.playerLogin as resp_login,
        resp.playerID as resp_game_id
    FROM player_warnings w
    LEFT JOIN players adv ON w.game_user_id = adv.discordUserID
    LEFT JOIN players resp ON w.user_id_save = resp.discordUserID
    ORDER BY w.id DESC
    """
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}


class WarningExpiry(BaseModel):
    """Ajuste do vencimento em dias — o painel só oferece +1/-1 por clique."""
    dias: int


@router.patch("/warnings/{warning_id}", dependencies=[Depends(require_scope("admin:*"))])
async def update_warning_expiry(app_id: str, warning_id: int, item: WarningExpiry):
    """Soma (ou subtrai) dias no vencimento de uma advertência.

    `expires_at` é texto no formato `dd/mm/aaaa`, gravado assim pelo bot. A
    rotina diária de `advertencia.py` relê essa data, reescreve a mensagem no
    canal de advertidos com os dias restantes e apaga a advertência quando o
    prazo vence — por isso alterar a data aqui se reconcilia sozinho no bot.
    Não existe rota de exclusão: apagar a linha deixaria a mensagem e o cargo
    para trás, já que quem os remove é o botão do próprio bot.
    """
    audit_log(app_id, "UPDATE_WARNING_EXPIRY", f"Warning {warning_id}: {item.dias:+d} dia(s)")

    linhas = await sqlite_service.execute_query(
        app_id,
        "SELECT expires_at FROM player_warnings WHERE id = ?",
        (warning_id,),
    )
    if not linhas:
        raise HTTPException(status_code=404, detail="Advertência não encontrada.")

    atual = str(linhas[0].get("expires_at") or "").strip()
    try:
        data = datetime.strptime(atual, "%d/%m/%Y")
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail=f"Vencimento em formato inesperado ({atual or 'vazio'}); esperado dd/mm/aaaa.",
        )

    nova = (data + timedelta(days=int(item.dias))).strftime("%d/%m/%Y")
    await sqlite_service.execute_update(
        app_id,
        "UPDATE player_warnings SET expires_at = ? WHERE id = ?",
        (nova, warning_id),
    )
    return {"ok": True, "data": {"id": warning_id, "expires_at": nova}}

# --- AUSÊNCIAS ---

@router.get("/absences", dependencies=[Depends(require_scope("admin:*"))])
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

@router.get("/routes/daily", dependencies=[Depends(require_scope("admin:*"))])
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

@router.get("/routes/total", dependencies=[Depends(require_scope("admin:*"))])
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

@router.get("/supervisors/ranking", dependencies=[Depends(require_scope("admin:*"))])
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
