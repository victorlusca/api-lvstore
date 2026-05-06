"""
routes_audit.py â€” Auditoria do bot (logs de aÃ§Ãµes in-game e discord) (FastAPI version).
Este arquivo expÃµe os logs gravados por utils/audit.py (tabela audit_log no master_data.db).
"""
import json
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.services.sqlite_engine import sqlite_service

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
        # A API deve ser um ESPELHO do banco. Listar tudo sem filtros adicionais além de paginação.
        query = """
            SELECT * 
            FROM audit_log 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """
        # Usando o sqlite_service que busca o banco na Square Cloud
        rows = await sqlite_service.execute_query(
            app_id, 
            query, 
            (limit, offset)
        )
        
        data = []
        for row in rows:
            item = dict(row)
            
            # Mapeamento obrigatório de campos
            item["feito_em"] = item.pop("created_at")
            item["nome_sistema"] = item.pop("system_key")
            item["autor"] = item.pop("actor_discord_id")
            item["alvo"] = item.pop("target_discord_id")
            
            # Campo details_json: parse se válido, senão string original
            details_raw = item.get("details_json")
            if details_raw:
                try:
                    item["details_json"] = json.loads(details_raw)
                except Exception:
                    # Se falhar o parse, mantém a string original sem quebrar a API
                    pass
            
            data.append(item)
            
        return {
            "ok": True,
            "data": data
        }
    except Exception as e:
        # Em caso de erro crítico, retornamos erro 500 para não quebrar a API silenciosamente
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{app_id}/audit/write")
async def create_bot_audit(
    app_id: str,
    event: AuditEvent,
    _ = Depends(require_scope("audit:write"))
):
    """
    Registra um novo evento de auditoria no banco remoto do bot (Square Cloud).
    """
    try:
        query = """
            INSERT INTO audit_log (
                event_type, system_key, action_key, 
                actor_discord_id, actor_name, 
                target_discord_id, target_game_id, target_name, 
                details_json, status, message, 
                bot_id, source, severity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        details_json = json.dumps(event.details) if event.details else None
        
        params = (
            event.event_type,
            event.system_key,
            event.action_key,
            event.actor_discord_id,
            event.actor_name,
            event.target_discord_id,
            event.target_game_id,
            event.target_name,
            details_json,
            event.status,
            event.message,
            int(app_id) if app_id.isdigit() else None,
            "api",
            event.severity
        )
        
        await sqlite_service.execute_update(app_id, query, params)
        
        res, status_code = ok({"message": "Log registrado no banco remoto com sucesso"})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

