"""
routes_status.py â€” status pÃºblico e resumo do sistema (FastAPI version).
"""
import os, sqlite3
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err

router = APIRouter(tags=["Status"])
_REFERENCE_DB = "data/reference_data.db"
_EMBED_DB     = "data/embed_data.db"
_MASTER_DB    = "data/master_data.db"

_REQUIRED_SINGLE = {
    "configuracoes_organizacao": ["sigla","nome"],
    "configuracoes_servidor":    ["guild_id"],
}
_REQUIRED_COUNTS = {"cargos_gerais": 1, "chats_gerais": 1}

def _count(db, table, where=""):
    try:
        con = sqlite3.connect(db)
        q = f"SELECT COUNT(1) FROM {table}" + (f" WHERE {where}" if where else "")
        n = con.execute(q).fetchone()[0]; con.close()
        return int(n or 0)
    except Exception: return -1

def _check_setup():
    issues, complete = [], True
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        for table, cols in _REQUIRED_SINGLE.items():
            try:
                row = con.execute(f"SELECT {','.join(cols)} FROM {table} LIMIT 1").fetchone()
                for i, col in enumerate(cols):
                    val = row[i] if row else None
                    if not val or str(val).strip() == "":
                        issues.append(f"{table}.{col} nÃ£o configurado"); complete = False
            except Exception as e:
                issues.append(f"Erro ao ler {table}: {e}"); complete = False
        for table, mn in _REQUIRED_COUNTS.items():
            try:
                n = con.execute(f"SELECT COUNT(1) FROM {table}").fetchone()[0]
                if n < mn: issues.append(f"{table}: {n}/{mn}"); complete = False
            except Exception as e:
                issues.append(str(e)); complete = False
        con.close()
    except Exception as e:
        issues.append(str(e)); complete = False
    return {"complete": complete, "issues": issues}

@router.get("/status/setup")
async def setup_status(_ = Depends(require_scope("references:read"))):
    result = _check_setup()
    res, status = ok(result, "Setup completo" if result["complete"] else "Setup incompleto")
    return res

@router.get("/status/summary")
async def system_summary(_ = Depends(require_scope("references:read"))):
    data = {
        "referencias": {
            "cargos_gerais":    _count(_REFERENCE_DB, "cargos_gerais"),
            "chats_gerais":     _count(_REFERENCE_DB, "chats_gerais"),
            "calls":            _count(_REFERENCE_DB, "calls"),
            "categorias_gerais":_count(_REFERENCE_DB, "categorias_gerais"),
            "logs":             _count(_REFERENCE_DB, "logs"),
            "hierarquia_niveis":_count(_REFERENCE_DB, "hierarquia"),
            "users_autorizados":_count(_REFERENCE_DB, "users"),
        },
        "embeds": {
            "templates_ativos": _count(_EMBED_DB, "embeds", "is_active=1"),
        },
        "dados_operacionais": {
            "membros_registrados": _count(_MASTER_DB, "players"),
            "advertencias_ativas": _count(_MASTER_DB, "player_warnings"),
            "ausencias_ativas":    _count(_MASTER_DB, "player_absences"),
            "tickets_total":       _count(_MASTER_DB, "tickets"),
            "tickets_abertos":     _count(_MASTER_DB, "tickets", "closed_by_id IS NULL"),
        },
        "setup": _check_setup(),
    }
    res, status = ok(data)
    return res

