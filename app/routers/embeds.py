from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.core.security import get_api_key
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

@router.post("", dependencies=[Depends(get_api_key)])
async def create_or_update_embed(app_id: str, embed: EmbedUpdate):
    audit_log(app_id, "UPSERT_EMBED", f"Saving embed: {embed.system_key}/{embed.embed_key}")
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    query = """
    INSERT INTO embeds (
        system_key, embed_key, content, title, type, description, url, 
        timestamp, color, footer_json, image_json, thumbnail_json, 
        video_json, provider_json, author_json, fields_json, raw_json, 
        is_active, created_at, updated_at
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    )
    ON CONFLICT(system_key, embed_key) DO UPDATE SET
        content = excluded.content,
        title = excluded.title,
        type = excluded.type,
        description = excluded.description,
        url = excluded.url,
        timestamp = excluded.timestamp,
        color = excluded.color,
        footer_json = excluded.footer_json,
        image_json = excluded.image_json,
        thumbnail_json = excluded.thumbnail_json,
        video_json = excluded.video_json,
        provider_json = excluded.provider_json,
        author_json = excluded.author_json,
        fields_json = excluded.fields_json,
        raw_json = excluded.raw_json,
        is_active = excluded.is_active,
        updated_at = excluded.updated_at
    """
    
    params = (
        embed.system_key, embed.embed_key, embed.content, embed.title, embed.type,
        embed.description, embed.url, embed.timestamp, embed.color, 
        embed.footer_json, embed.image_json, embed.thumbnail_json, 
        embed.video_json, embed.provider_json, embed.author_json, 
        embed.fields_json, embed.raw_json, embed.is_active, now, now
    )
    
    await embed_service.execute_update(app_id, query, params)
    return {"ok": True, "message": "Embed salva com sucesso"}
