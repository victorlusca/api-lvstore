"""
routes_embeds.py â€” CRUD de embeds com escopos, validaÃ§Ã£o forte e auditoria (FastAPI version).
"""
import json, sqlite3, os
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.audit import write_audit

router = APIRouter(tags=["Embeds"])
_EMBED_DB = "data/embed_data.db"

@router.get("/embeds")
async def get_all_embeds(_ = Depends(require_scope("embeds:read"))):
    try:
        con = sqlite3.connect(_EMBED_DB)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM embeds WHERE is_active=1").fetchall()
        con.close()
        res, status = ok([dict(r) for r in rows])
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/embeds/{system_key}")
async def get_system_embeds(system_key: str, _ = Depends(require_scope("embeds:read"))):
    try:
        con = sqlite3.connect(_EMBED_DB)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM embeds WHERE system_key=? AND is_active=1", (system_key,)).fetchall()
        con.close()
        res, status = ok([dict(r) for r in rows])
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

