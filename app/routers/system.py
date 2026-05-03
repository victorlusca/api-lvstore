from fastapi import APIRouter, Depends
from app.core.security import get_api_key
from app.services.sqlite_engine import sqlite_service
from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/system", tags=["System"])

# --- EDITAL E TRANSCRIPTS ---

@router.get("/transcripts", dependencies=[Depends(get_api_key)])
async def get_transcripts(app_id: str):
    audit_log(app_id, "GET_TRANSCRIPTS", "Fetching ticket transcripts")
    query = """
    SELECT 
        id, 
        channel_id, 
        opened_by_id, 
        ticket_type, 
        transcript_url, 
        opened_at_ts as data_abertura 
    FROM tickets 
    WHERE transcript_url IS NOT NULL 
    ORDER BY id DESC
    """
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

# --- SEGURANÇA ---

@router.get("/security/whitelist", dependencies=[Depends(get_api_key)])
async def get_security_whitelist(app_id: str):
    audit_log(app_id, "GET_SECURITY_WHITELIST", "Fetching security whitelist")
    query = "SELECT * FROM security_whitelist_users"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.get("/security/punishments", dependencies=[Depends(get_api_key)])
async def get_security_punishments(app_id: str):
    audit_log(app_id, "GET_SECURITY_PUNISHMENTS", "Fetching security punishments")
    query = "SELECT * FROM security_punishments ORDER BY id DESC"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.get("/security/infractions", dependencies=[Depends(get_api_key)])
async def get_security_infractions(app_id: str):
    audit_log(app_id, "GET_SECURITY_INFRACTIONS", "Fetching security infractions")
    query = "SELECT * FROM security_infractions ORDER BY id DESC"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

# --- CONFIGURAÇÕES E EMBEDS ---

@router.get("/settings/systems", dependencies=[Depends(get_api_key)])
async def get_system_settings(app_id: str):
    audit_log(app_id, "GET_SYSTEM_SETTINGS", "Fetching system toggle settings")
    query = "SELECT * FROM security_systems"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.get("/settings/bot", dependencies=[Depends(get_api_key)])
async def get_bot_settings(app_id: str):
    audit_log(app_id, "GET_BOT_SETTINGS", "Fetching bot specific settings")
    query = "SELECT * FROM bots"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}
