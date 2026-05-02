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

router = APIRouter(tags=["Audit"])

@router.get("/audit/bot")
async def get_bot_audit(
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
        
        res, status = ok({"total": total, "logs": entries})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

