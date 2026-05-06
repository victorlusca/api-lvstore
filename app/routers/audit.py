"""
routes_audit.py â€” Auditoria do bot (logs de aÃ§Ãµes in-game e discord) (FastAPI version).
Este arquivo expÃµe os logs gravados por utils/audit.py (tabela audit_log no master_data.db).
"""
import json
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.helpers import master_con

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

@router.get("/{app_id}/audit")
async def get_audit_log(
    app_id: str,
    limit: int = Query(50),
    offset: int = Query(0),
    _ = Depends(require_scope("audit:read"))
):
    """
    Retorna logs de auditoria brutos da tabela audit_log.
    Fiel ao banco de dados, com renomeação de campos obrigatória.
    """
    # Validação de paginação
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 50
    if offset < 0:
        offset = 0

    try:
        con = master_con()
        
        # Query SQL parametrizada conforme solicitado
        query = """
            SELECT * 
            FROM audit_log 
            WHERE bot_id = :app_id 
            ORDER BY created_at DESC 
            LIMIT :limit OFFSET :offset
        """
        params = {
            "app_id": app_id,
            "limit": limit,
            "offset": offset
        }
        
        rows = con.execute(query, params).fetchall()
        con.close()
        
        data = []
        for row in rows:
            # Converte row para dicionário para manipulação
            item = dict(row)
            
            # Renomeação de campos (OBRIGATÓRIO)
            item["feito_em"] = item.pop("created_at")
            item["nome_sistema"] = item.pop("system_key")
            item["autor"] = item.pop("actor_discord_id")
            item["alvo"] = item.pop("target_discord_id")
            
            # Parse do campo details_json
            details_raw = item.get("details_json")
            if details_raw:
                try:
                    item["details_json"] = json.loads(details_raw)
                except (json.JSONDecodeError, TypeError):
                    # Se falhar, mantém como string original
                    item["details_json"] = details_raw
            
            data.append(item)
            
        return {
            "ok": True,
            "data": data
        }
    except Exception as e:
        # Em caso de erro crítico, retornamos erro 500 para não quebrar a API silenciosamente
        raise HTTPException(status_code=500, detail=str(e))

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

