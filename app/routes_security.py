"""
routes_security.py â€” SeguranÃ§a do bot (configuraÃ§Ã£o, whitelist, infraÃ§Ãµes) (FastAPI version).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from app.auth import require_scope
from app.responses import ok
from app.security.security_guard import (
    list_action_configs,
    list_system_states,
)
from app.security.security_whitelist import (
    list_action_whitelist,
)

router = APIRouter(tags=["Security"])

@router.get("/security/configs")
async def get_security_configs(
    guild_id: int = Query(..., ge=1),
    _ = Depends(require_scope("references:read"))
):
    try:
        data = list_action_configs(guild_id)
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
        if not action_key:
            res, status = ok({})
            return res
        users, roles = list_action_whitelist(action_key)
        data = {"action_key": action_key, "users": users, "roles": roles}
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

