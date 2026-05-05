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

async def _fetch_audit_logs(
    bot_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None,
    system_key: Optional[str] = None,
    action_key: Optional[str] = None,
    actor_id: Optional[str] = None,
    target_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[int] = None,
    source: Optional[str] = None
):
    try:
        where, params = [], []
        
        if bot_id and bot_id.isdigit():
            where.append("bot_id = ?")
            params.append(int(bot_id))

        if event_type:
            where.append("event_type = ?"); params.append(event_type)
        if system_key:
            where.append("system_key = ?"); params.append(system_key)
        if action_key:
            where.append("action_key = ?"); params.append(action_key)
        if actor_id:
            where.append("actor_discord_id = ?"); params.append(actor_id)
        if target_id:
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
        query = f"SELECT * FROM audit_log {clause} ORDER BY id DESC LIMIT ? OFFSET ?"
        rows = con.execute(query, params + [limit, offset]).fetchall()
        
        total = con.execute(f"SELECT COUNT(1) FROM audit_log {clause}", params).fetchone()[0]
        con.close()
        
        entries = []
        for r in rows:
            entry = {
                "id": r["id"],
                "bot_id": r["bot_id"],
                "data_hora": r["created_at"],
                "sistema": r["system_key"],
                "acao": r["action_key"],
                "quem_fez": {
                    "discord_id": str(r["actor_discord_id"]) if r["actor_discord_id"] else "â€”",
                    "nome": r["actor_name"] or "Sistema",
                },
                "alvo": {
                    "discord_id": str(r["target_discord_id"]) if r["target_discord_id"] else "â€”",
                    "game_id": r["target_game_id"],
                    "nome": r["target_name"] or "â€”",
                } if (r["target_discord_id"] or r["target_game_id"] or r["target_name"]) else None,
                "detalhe": r["message"] or "â€”",
                "status": r["status"],
                "severidade": r["severity"],
                "fonte": r["source"]
            }
            if r["details_json"]:
                try: entry["detalhes_raw"] = json.loads(r["details_json"])
                except: entry["detalhes_raw"] = r["details_json"]
            entries.append(entry)
        
        return ok({"total": total, "logs": entries})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit/all")
async def get_all_audit(
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
    Retorna todos os logs de auditoria do banco de dados (sem filtro de bot_id por padrão).
    """
    res, status_code = await _fetch_audit_logs(
        limit=limit, offset=offset, event_type=event_type,
        system_key=system_key, action_key=action_key, actor_id=actor_id,
        target_id=target_id, status=status, severity=severity, source=source
    )
    return res

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
    Retorna logs de auditoria de um bot específico.
    """
    res, status_code = await _fetch_audit_logs(
        bot_id=app_id, limit=limit, offset=offset, event_type=event_type,
        system_key=system_key, action_key=action_key, actor_id=actor_id,
        target_id=target_id, status=status, severity=severity, source=source
    )
    return res

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

