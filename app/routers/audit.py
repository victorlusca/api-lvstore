"""
routes_audit.py â€” Auditoria do bot (logs de aÃ§Ãµes in-game e discord) (FastAPI version).
Este arquivo expÃµe os logs gravados por utils/audit.py (tabela audit_log no master_data.db).
"""
import json
import aiosqlite
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.helpers import master_con
from app.settings import data_path

from pydantic import BaseModel

router = APIRouter(prefix="/bots", tags=["Audit"])

class AuditEvent(BaseModel):
    event_type: str
    system_key: str
    action_key: str
    actor_discord_id: Optional[int] = None
    actor_name: Optional[str] = None
    target_discord_id: Optional[int] = None
    target_game_id: Optional[int] = None
    target_name: Optional[str] = None
    details: Any = None
    status: str = "success"
    message: Optional[str] = None
    guild_id: Optional[int] = None
    severity: int = 0

@router.get("/{app_id}/audit/bot")
async def get_bot_audit(
    app_id: str,
    limit: int = Query(50, le=500, ge=1),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = None,
    system_key: Optional[str] = None,
    action_key: Optional[str] = None,
    actor_id: Optional[str] = None,
    target_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[int] = None,
    source: Optional[str] = None,
    _ = Depends(require_scope("audit:read"))
):
    """
    Retorna logs de auditoria do bot (master_data.db).
    Suporta filtros por sistema, aÃ§Ã£o, ator, alvo, etc.
    """
    try:
        where, params = [], []
        
        # Filtro obrigatÃ³rio por bot_id (app_id)
        if app_id.isdigit():
            where.append("bot_id = ?")
            params.append(int(app_id))

        if event_type:
            where.append("event_type = ?"); params.append(event_type)
        if system_key:
            where.append("system_key = ?"); params.append(system_key)
        if action_key:
            where.append("action_key = ?"); params.append(action_key)
        if actor_id:
            where.append("actor_discord_id = ?"); params.append(actor_id)
        if target_id:
            # Busca tanto por discord_id quanto por game_id no alvo
            where.append("(target_discord_id = ? OR target_game_id = ?)")
            params.extend([target_id, target_id])
        if status:
            where.append("status = ?"); params.append(status)
        if severity is not None:
            where.append("severity = ?"); params.append(severity)
        if source:
            where.append("source = ?"); params.append(source)

        clause = ("WHERE " + " AND ".join(where)) if where else ""
        
        con = master_con()
        # Query principal
        query = f"SELECT * FROM audit_log {clause} ORDER BY id DESC LIMIT ? OFFSET ?"
        rows = con.execute(query, params + [limit, offset]).fetchall()
        
        # Total para paginaÃ§Ã£o
        total = con.execute(f"SELECT COUNT(1) FROM audit_log {clause}", params).fetchone()[0]
        con.close()
        
        entries = []
        for r in rows:
            # Mapeamento para o que o frontend espera (AuditLogModule.tsx)
            entry = {
                "id": r["id"],
                "data_hora": r["created_at"],
                "sistema": r["system_key"],
                "acao": r["action_key"],
                "quem_fez": {
                    "discord_id": str(r["actor_discord_id"]) if r["actor_discord_id"] else "â€”",
                    "nome": r["actor_name"] or "Sistema",
                    "login": None 
                },
                "alvo": {
                    "discord_id": str(r["target_discord_id"]) if r["target_discord_id"] else "â€”",
                    "game_id": r["target_game_id"],
                    "nome": r["target_name"] or "â€”",
                    "login": None
                } if (r["target_discord_id"] or r["target_game_id"] or r["target_name"]) else None,
                "detalhe": r["message"] or "â€”",
                "status": r["status"],
                "severidade": r["severity"],
                "fonte": r["source"]
            }
            
            # Adiciona detalhes extras se houver JSON
            if r["details_json"]:
                try:
                    entry["detalhes_raw"] = json.loads(r["details_json"])
                except:
                    entry["detalhes_raw"] = r["details_json"]
                    
            entries.append(entry)
        
        res, status_code = ok({"total": total, "logs": entries})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{app_id}/audit/")
async def get_audit_log_simple(
    app_id: str,
    limit: int = Query(50),
    offset: int = Query(0)
):
    """
    Endpoint simples que reflete a tabela audit_log conforme requisitos específicos.
    """
    # Regra 3: Paginação (obrigatória)
    # Se limit não for informado -> usar 50 (já via Query)
    # Se limit for maior que 100 -> usar 100
    if limit > 100:
        limit = 100
    elif limit < 1:
        limit = 50
    
    # Se offset não for informado -> usar 0 (já via Query)
    if offset < 0:
        offset = 0

    db_path = data_path("master_data.db")
    
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Regras 1, 2, 4 e 10: Query parametrizada, filtro bot_id, ordenação created_at DESC
            # SQL esperado: SELECT * FROM audit_log WHERE bot_id = :app_id ORDER BY created_at DESC LIMIT :limit OFFSET :offset
            async with db.execute(
                "SELECT * FROM audit_log WHERE bot_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (app_id, limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()

        result_data = []
        for row in rows:
            item = dict(row)
            
            # Regra 5: Renomeação de campos (OBRIGATÓRIO)
            item["feito_em"] = item.pop("created_at")
            item["nome_sistema"] = item.pop("system_key")
            item["autor"] = item.pop("actor_discord_id")
            item["alvo"] = item.pop("target_discord_id")
            
            # Regra 6: Campo details_json (Parse JSON ou string original)
            details = item.get("details_json")
            if details:
                try:
                    if isinstance(details, str):
                        item["details_json"] = json.loads(details)
                except (json.JSONDecodeError, TypeError, ValueError):
                    # Se falhar -> retornar como string original
                    pass
            
            result_data.append(item)

        # Regra 7 e 8: Estrutura de resposta (OBRIGATÓRIO)
        # Se não houver registros -> retorna data: []
        return {
            "ok": True,
            "data": result_data
        }
    except Exception as e:
        # Em caso de erro crítico no banco de dados
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/{app_id}/audit/bot")
async def create_bot_audit(
    app_id: str,
    event: AuditEvent,
    _ = Depends(require_scope("audit:write"))
):
    """
    Registra um novo evento de auditoria para o bot.
    """
    try:
        from app.core.audit import audit_log
        audit_log(
            app_id=app_id,
            action=event.action_key,
            details=event.details or event.message,
            event_type=event.event_type,
            status=event.status
        )
        res, status_code = ok({"message": "Log registrado com sucesso"})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

