from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.auth import require_scope
from app.services.sqlite_engine import sqlite_service, reference_service
from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/system", tags=["System"])

class KVUpdate(BaseModel):
    key_name: str
    value: str

# --- EDITAL E TRANSCRIPTS ---

@router.get("/transcripts", dependencies=[Depends(require_scope("admin:*"))])
async def get_transcripts(app_id: str):
    audit_log(app_id, "GET_TRANSCRIPTS", "Fetching ticket transcripts")
    query = """
    SELECT 
        id, 
        channel_id, 
        opened_by_id, 
        attended_by_id,
        closed_by_id,
        ticket_type, 
        transcript_filename,
        transcript_url, 
        stars,
        opened_at_ts,
        attended_at_ts,
        closed_at_ts
    FROM tickets 
    WHERE transcript_url IS NOT NULL 
    ORDER BY id DESC
    """
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.post("/transcripts", dependencies=[Depends(require_scope("admin:*"))])
async def sync_transcripts(app_id: str):
    audit_log(app_id, "SYNC_TRANSCRIPTS", "Transcript sync requested")
    # Este endpoint pode ser usado para forçar uma atualização ou processamento
    return {"ok": True, "message": "Sincronização de transcripts iniciada"}

# --- CONFIGURAÇÕES (REFERENCE_DATA.DB) ---

@router.get("/settings/{table}", dependencies=[Depends(require_scope("admin:*"))])
async def get_reference_settings(app_id: str, table: str):
    allowed_tables = {
        "cargos_gerais", "categorias_gerais", "chats_gerais",
        "configuracoes_e_numeros", "configuracoes_organizacao",
        "configuracoes_plano", "configuracoes_servidor",
        "logs", "calls", "bot_configuration"
    }
    if table not in allowed_tables:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")
    
    audit_log(app_id, "GET_SETTINGS", f"Fetching settings from {table}")
    query = f"SELECT * FROM {table}"
    data = await reference_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.put("/settings/{table}/kv", dependencies=[Depends(require_scope("admin:*"))])
async def update_kv_settings(app_id: str, table: str, update: KVUpdate):
    # `calls` e `logs` têm o mesmo formato (id, key_name, value) das demais —
    # só nunca tinham sido liberadas para escrita, então o painel não conseguia
    # salvar as abas "Canais de Voz" e "Logs". Adição pura: nada muda para as
    # tabelas que já eram aceitas.
    kv_tables = {"cargos_gerais", "categorias_gerais", "chats_gerais", "calls", "logs"}
    if table not in kv_tables:
        raise HTTPException(status_code=400, detail="Esta tabela não é do tipo Chave-Valor")
    
    audit_log(app_id, "UPDATE_SETTINGS_KV", f"Updating {table}: {update.key_name}")
    query = f"UPDATE {table} SET value = ? WHERE key_name = ?"
    await reference_service.execute_update(app_id, query, (update.value, update.key_name))
    return {"ok": True, "message": "Configuração atualizada"}

@router.put("/settings/{table}/row", dependencies=[Depends(require_scope("admin:*"))])
async def update_row_settings(app_id: str, table: str, data: Dict[str, Any]):
    row_tables = {
        "configuracoes_e_numeros", "configuracoes_organizacao",
        "configuracoes_plano", "configuracoes_servidor",
        "bot_configuration"
    }
    if table not in row_tables:
        raise HTTPException(status_code=400, detail="Esta tabela não é do tipo Linha Única")
    
    audit_log(app_id, "UPDATE_SETTINGS_ROW", f"Updating settings row in {table}")
    
    # Construir query dinamicamente para os campos enviados
    fields = []
    params = []
    for k, v in data.items():
        if k != "id": # Não atualizamos o ID
            fields.append(f"{k} = ?")
            params.append(v)
    
    if not fields:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    
    query = f"UPDATE {table} SET {', '.join(fields)} WHERE id = 1"
    await reference_service.execute_update(app_id, query, tuple(params))
    return {"ok": True, "message": "Configurações atualizadas"}

# --- SEGURANÇA ---

@router.get("/security/whitelist", dependencies=[Depends(require_scope("admin:*"))])
async def get_security_whitelist(app_id: str):
    audit_log(app_id, "GET_SECURITY_WHITELIST", "Fetching security whitelist")
    query = "SELECT * FROM security_whitelist_users"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.get("/security/punishments", dependencies=[Depends(require_scope("admin:*"))])
async def get_security_punishments(app_id: str):
    audit_log(app_id, "GET_SECURITY_PUNISHMENTS", "Fetching security punishments")
    query = "SELECT * FROM security_punishments ORDER BY id DESC"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.get("/security/infractions", dependencies=[Depends(require_scope("admin:*"))])
async def get_security_infractions(app_id: str):
    audit_log(app_id, "GET_SECURITY_INFRACTIONS", "Fetching security infractions")
    query = "SELECT * FROM security_infractions ORDER BY id DESC"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

# --- CONFIGURAÇÕES E EMBEDS ---

@router.get("/settings/systems", dependencies=[Depends(require_scope("admin:*"))])
async def get_system_settings(app_id: str):
    audit_log(app_id, "GET_SYSTEM_SETTINGS", "Fetching system toggle settings")
    query = "SELECT * FROM security_systems"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.get("/settings/bot", dependencies=[Depends(require_scope("admin:*"))])
async def get_bot_settings(app_id: str):
    audit_log(app_id, "GET_BOT_SETTINGS", "Fetching bot specific settings")
    query = "SELECT * FROM bots"
    data = await sqlite_service.execute_query(app_id, query)
    return {"ok": True, "data": data}
