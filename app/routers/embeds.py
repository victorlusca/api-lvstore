from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.auth import require_scope
from app.services.sqlite_engine import embed_service
from app.core.audit import audit_log
from datetime import datetime

router = APIRouter(prefix="/bots/{app_id}/embeds", tags=["Embeds"])

class EmbedUpdate(BaseModel):
    system_key: str
    embed_key: str
    content: Optional[str] = None
    title: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    timestamp: Optional[str] = None
    color: Optional[int] = None
    footer_json: Optional[str] = None
    image_json: Optional[str] = None
    thumbnail_json: Optional[str] = None
    video_json: Optional[str] = None
    provider_json: Optional[str] = None
    author_json: Optional[str] = None
    fields_json: Optional[str] = None
    raw_json: Optional[str] = None
    is_active: Optional[int] = 1

@router.get("", dependencies=[Depends(require_scope("admin:*"))])
async def get_all_embeds(app_id: str):
    audit_log(app_id, "GET_EMBEDS", "Fetching all custom embeds configuration")
    query = "SELECT id, system_key, embed_key, content, title, type, description, url, timestamp, color FROM embeds ORDER BY system_key ASC, embed_key ASC"
    data = await embed_service.execute_query(app_id, query)
    return {"ok": True, "data": data}

@router.put("", dependencies=[Depends(require_scope("admin:*"))])
async def update_embed(app_id: str, update: EmbedUpdate):
    audit_log(app_id, "UPDATE_EMBED", f"Updating embed: {update.system_key}:{update.embed_key}")
    
    query = """
    INSERT INTO embeds (system_key, embed_key, content, title, type, description, url, timestamp, color)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(system_key, embed_key) DO UPDATE SET
        content = excluded.content,
        title = excluded.title,
        type = excluded.type,
        description = excluded.description,
        url = excluded.url,
        timestamp = excluded.timestamp,
        color = excluded.color
    """
    
    await embed_service.execute_update(app_id, query, (
        update.system_key,
        update.embed_key,
        update.content,
        update.title,
        update.type,
        update.description,
        update.url,
        update.timestamp,
        update.color
    ))
    
    return {"ok": True, "message": "Embed atualizada com sucesso"}

@router.delete("/{system_key}/{embed_key}", dependencies=[Depends(require_scope("admin:*"))])
async def delete_embed(app_id: str, system_key: str, embed_key: str):
    audit_log(app_id, "DELETE_EMBED", f"Deleting embed: {system_key}:{embed_key}")
    query = "DELETE FROM embeds WHERE system_key = ? AND embed_key = ?"
    await embed_service.execute_update(app_id, query, (system_key, embed_key))
    return {"ok": True, "message": "Embed removida com sucesso"}
