from fastapi import APIRouter, Depends, HTTPException
from app.core.security import get_api_key
from app.services.sqlite_engine import embed_service
from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/embeds", tags=["Embeds"])

@router.get("", dependencies=[Depends(get_api_key)])
async def get_all_embeds(app_id: str):
    audit_log(app_id, "GET_EMBEDS", "Fetching all active embeds")
    query = "SELECT * FROM embeds WHERE is_active=1"
    data = await embed_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.get("/{system_key}", dependencies=[Depends(get_api_key)])
async def get_system_embeds(app_id: str, system_key: str):
    audit_log(app_id, "GET_SYSTEM_EMBEDS", f"Fetching embeds for system: {system_key}")
    query = "SELECT * FROM embeds WHERE system_key = ? AND is_active = 1"
    data = await embed_service.execute_query(app_id, query, (system_key,))
    return {"ok": True, "data": data}
