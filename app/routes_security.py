"""
routes_security.py â€” SeguranÃ§a do bot (configuraÃ§Ã£o, whitelist, infraÃ§Ãµes) (FastAPI version).
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.audit import write_audit
from app.responses import err, ok
from utils.security_guard import (
    ACTION_KEYS,
    list_action_configs,
    list_recent_infractions,
    list_system_states,
    set_system_state,
    upsert_action_config,
)
from utils.security_whitelist import (
    add_role as wl_add_role,
    add_user as wl_add_user,
    list_action_whitelist,
    remove_role as wl_remove_role,
    remove_user as wl_remove_user,
)

router = APIRouter(tags=["Security"])

@router.get("/security/configs")
async def get_security_configs(_ = Depends(require_scope("references:read"))):
    try:
        data = list_action_configs()
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/security/systems")
async def get_security_systems(_ = Depends(require_scope("references:read"))):
    try:
        data = list_system_states()
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/security/whitelist")
async def get_security_whitelist(action_key: Optional[str] = None, _ = Depends(require_scope("references:read"))):
    try:
        data = list_action_whitelist(action_key) if action_key else {}
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

