"""
routes_admin.py â€” administraÃ§Ã£o, backup/export, auditoria e observabilidade (FastAPI version).
"""
import os, json, shutil, sqlite3
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.auth import require_scope, list_tokens
from app.responses import ok, err
from app.audit import write_audit, read_audit, audit_stats

router = APIRouter(tags=["Admin"])

_REFERENCE_DB = "data/reference_data.db"
_EMBED_DB     = "data/embed_data.db"
_MASTER_DB    = "data/master_data.db"
_BACKUP_DIR   = "data/backups"

# â”€â”€â”€ Auditoria â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/admin/audit")
async def get_audit(
    limit: int = Query(50, le=500, ge=1),
    offset: int = Query(0, ge=0),
    resource_type: Optional[str] = None,
    actor: Optional[str] = None,
    status: Optional[int] = None,
    _ = Depends(require_scope("audit:read"))
):
    entries = read_audit(
        limit=limit, offset=offset,
        resource_type=resource_type,
        actor=actor,
        status=status,
    )
    res, status_code = ok({"entries": entries, "limit": limit, "offset": offset, "count": len(entries)})
    return res

# â”€â”€â”€ MÃ©tricas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/admin/metrics")
async def get_metrics(_ = Depends(require_scope("audit:read"))):
    def _count(db, table, where=""):
        try:
            con = sqlite3.connect(db)
            q = f"SELECT COUNT(1) FROM {table}" + (f" WHERE {where}" if where else "")
            n = con.execute(q).fetchone()[0]
            con.close()
            return int(n or 0)
        except Exception:
            return -1

    data = {
        "auditoria": audit_stats(),
        "tokens_ativos": len(list_tokens()),
        "referencias": {
            "cargos_gerais":    _count(_REFERENCE_DB, "cargos_gerais"),
            "chats_gerais":     _count(_REFERENCE_DB, "chats_gerais"),
            "categorias_gerais":_count(_REFERENCE_DB, "categorias_gerais"),
            "hierarquia_niveis":_count(_REFERENCE_DB, "hierarquia"),
        },
        "embeds": {
            "templates_ativos": _count(_EMBED_DB, "embeds", "is_active=1"),
            "sistemas":         _distinct_embed_systems(),
        },
        "operacional": {
            "membros":      _count(_MASTER_DB, "players"),
            "advertencias": _count(_MASTER_DB, "player_warnings"),
            "tickets":      _count(_MASTER_DB, "tickets"),
            "tickets_open": _count(_MASTER_DB, "tickets", "closed_by_id IS NULL"),
        },
    }
    res, status = ok(data)
    return res

def _distinct_embed_systems():
    try:
        con = sqlite3.connect(_EMBED_DB)
        rows = con.execute("SELECT DISTINCT system_key FROM embeds WHERE is_active=1 ORDER BY system_key").fetchall()
        con.close()
        return [r[0] for r in rows]
    except Exception:
        return []

# â”€â”€â”€ Export â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/admin/export/references")
async def export_references(_ = Depends(require_scope("backup:run"))):
    # ImplementaÃ§Ã£o simplificada de exportaÃ§Ã£o
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        con.row_factory = sqlite3.Row
        tables = ["users", "configuracoes_organizacao", "configuracoes_servidor", "configuracoes_plano", "cargos_gerais", "chats_gerais", "calls", "categorias_gerais", "logs", "configuracoes_e_numeros", "hierarquia"]
        data = {}
        for t in tables:
            try:
                rows = con.execute(f"SELECT * FROM {t}").fetchall()
                data[t] = [dict(r) for r in rows]
            except: pass
        con.close()
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

