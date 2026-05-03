import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
import io
from datetime import datetime

from app.core.security import get_api_key
from app.services.square_cloud import square_cloud_service

router = APIRouter(prefix="/bots", tags=["Bots"])
logger = logging.getLogger("audit")

def audit_log(app_id: str, action: str, details: str):
    timestamp = datetime.now().isoformat()
    logger.info(f"[{timestamp}] Bot: {app_id} | Action: {action} | Details: {details}")
    print(f"AUDIT: [{timestamp}] Bot: {app_id} | Action: {action} | Details: {details}")

@router.get("/{app_id}/files", dependencies=[Depends(get_api_key)])
async def list_files(app_id: str, path: str = Query("/", description="Caminho da pasta")):
    audit_log(app_id, "LIST_FILES", f"Path: {path}")
    files = await square_cloud_service.list_files(app_id, path)
    return {"ok": True, "files": files}

@router.get("/{app_id}/files/db", dependencies=[Depends(get_api_key)])
async def list_db_files(app_id: str):
    audit_log(app_id, "LIST_DB_FILES", "Searching for .db files in /data")
    # Usually databases are in /data
    all_files = await square_cloud_service.list_files(app_id, "/data")
    db_files = [f for f in all_files if f.get("name", "").endswith(".db")]
    return {"ok": True, "files": db_files}

@router.get("/{app_id}/files/{filename}", dependencies=[Depends(get_api_key)])
async def download_file(app_id: str, filename: str, path: str = Query("/data", description="Caminho da pasta")):
    full_path = f"{path.rstrip('/')}/{filename}"
    audit_log(app_id, "DOWNLOAD_FILE", f"File: {full_path}")
    
    content = await square_cloud_service.read_file(app_id, full_path)
    
    if not content:
        raise HTTPException(status_code=404, detail="File not found or empty")
        
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

class FileUpdate(BaseModel):
    content: str
    path: Optional[str] = None

@router.put("/{app_id}/files/{filename}", dependencies=[Depends(get_api_key)])
async def update_file(app_id: str, filename: str, update: FileUpdate, path: str = Query("/data", description="Caminho da pasta")):
    # Se o path não for enviado no JSON, usa o da query
    target_path = update.path or f"{path.rstrip('/')}/{filename}"
    audit_log(app_id, "UPDATE_FILE", f"File: {target_path}")
    
    await square_cloud_service.update_file_content(app_id, target_path, update.content)
    
    return {"ok": True, "message": f"File {filename} updated successfully"}

@router.post("/{app_id}/files", dependencies=[Depends(get_api_key)])
async def upload_new_file(app_id: str, file: UploadFile = File(...), path: str = Query("/data", description="Caminho da pasta")):
    filename = file.filename
    audit_log(app_id, "UPLOAD_FILE", f"File: {path}/{filename}")
    
    content = await file.read()
    await square_cloud_service.upload_file(app_id, path, content, filename)
    
    return {"ok": True, "message": f"File {filename} uploaded successfully"}
