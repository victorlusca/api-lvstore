import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.services.square_blob import blob_service
from app.services.sqlite_engine import sqlite_service
from app.core.security import get_api_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots/{app_id}/transcripts", tags=["Transcripts"])

async def fetch_blob_content(app_id: str, blob_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Auxiliar para buscar o conteúdo de um objeto do Blob.
    """
    url = blob_info.get("url")
    name = blob_info.get("name", "")
    
    if not url:
        return None
        
    try:
        content = await blob_service.get_object_content(url)
        if content:
            # Mantemos o nome original do blob como ID para garantir o link correto
            # Se o nome for 'transcripts/file.html', o ID será 'transcripts/file.html'
            return {
                "transcript_name": name,
                "content": content,
                "url": url
            }
    except Exception as e:
        logger.error(f"Erro ao buscar conteúdo do blob {name}: {str(e)}")
        
    return None

@router.get("", dependencies=[Depends(get_api_key)])
async def list_transcripts(
    app_id: str, 
    limit: int = Query(20, ge=1, le=50),
    include_content: bool = Query(True, description="Se deve incluir o conteúdo HTML de cada transcript")
):
    """
    Lista os transcripts do Square Cloud Blob e opcionalmente seu conteúdo.
    """
    try:
        # 1. Lista objetos do Blob com prefixo transcripts
        blobs = await blob_service.list_objects(prefix="transcripts")
        
        # Filtra apenas HTMLs
        html_blobs = [b for b in blobs if b.get("name", "").endswith(".html")]
        
        # Inverte para pegar os mais recentes primeiro e limita
        html_blobs.reverse()
        html_blobs = html_blobs[:limit]
        
        data = []
        if include_content and html_blobs:
            # Busca o conteúdo em paralelo para todos os blobs
            tasks = [fetch_blob_content(app_id, b) for b in html_blobs]
            results = await asyncio.gather(*tasks)
            data = [r for r in results if r is not None]
        else:
            for b in html_blobs:
                data.append({
                    "transcript_name": b["name"],
                    "content": None,
                    "url": b.get("url")
                })
        
        return {"status": "ok", "data": data}
    except Exception as e:
        logger.error(f"Erro ao listar transcripts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{transcript_path:path}", dependencies=[Depends(get_api_key)])
async def get_transcript(app_id: str, transcript_path: str):
    """
    Obtém o conteúdo de um transcript específico pelo caminho completo (ex: transcripts/id.html).
    """
    # 1. Tentar encontrar no Blob
    # Se o usuário passou apenas o ID, tentamos prefixar com transcripts/ e sufixar com .html
    search_path = transcript_path
    if not search_path.startswith("transcripts/"):
        search_path = f"transcripts/{search_path}"
    if not search_path.endswith(".html"):
        search_path = f"{search_path}.html"

    blobs = await blob_service.list_objects(prefix=search_path)
    target_blob = next((b for b in blobs if b.get("name") == search_path), None)
    
    if not target_blob:
        # Fallback: listar tudo e procurar (mais lento, mas seguro se o prefixo falhar)
        blobs = await blob_service.list_objects(prefix="transcripts")
        target_blob = next((b for b in blobs if b.get("name") == search_path), None)

    if not target_blob:
        raise HTTPException(status_code=404, detail=f"Transcript '{search_path}' não encontrado no Blob Storage")

    content = await blob_service.get_object_content(target_blob["url"])
    
    if content is None:
        raise HTTPException(status_code=404, detail="Não foi possível ler o conteúdo do transcript")

    return {
        "status": "ok",
        "data": [
            {
                "transcript_name": target_blob["name"],
                "content": content,
                "url": target_blob["url"]
            }
        ]
    }

@router.delete("/{transcript_path:path}", dependencies=[Depends(get_api_key)])
async def delete_transcript(app_id: str, transcript_path: str):
    """
    Exclui um transcript do Blob e do banco de dados local.
    """
    search_path = transcript_path
    if not search_path.startswith("transcripts/"):
        search_path = f"transcripts/{search_path}"
    if not search_path.endswith(".html"):
        search_path = f"{search_path}.html"

    # 1. Deletar do Blob
    blob_deleted = await blob_service.delete_object(search_path)

    # 2. Excluir do Banco de Dados local (master_data.db)
    # Pegamos o ID limpo para o banco de dados
    clean_id = search_path.split("/")[-1].replace(".html", "")
    
    query = """
    DELETE FROM tickets 
    WHERE transcript_name = ? 
       OR transcript_filename = ? 
       OR transcript_url LIKE ?
    """
    pattern = f"%{clean_id}%"
    
    try:
        await sqlite_service.execute_update(app_id, query, (clean_id, search_path, pattern))
        db_deleted = True
    except Exception as e:
        logger.error(f"Erro ao deletar do banco de dados: {str(e)}")
        db_deleted = False

    return {
        "status": "ok",
        "message": "Processo de exclusão finalizado",
        "details": {
            "blob": "Excluído" if blob_deleted else "Não encontrado ou erro",
            "database": "Excluído" if db_deleted else "Erro ou não encontrado"
        }
    }
