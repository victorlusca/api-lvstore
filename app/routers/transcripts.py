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
            # Extrair o nome limpo do transcript (sem prefixo e sem .html)
            # Ex: transcripts/4ef40e59...html -> 4ef40e59...
            clean_name = name.split("/")[-1].replace(".html", "")
            return {
                "transcript_name": clean_name,
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
        
        # Filtra apenas HTMLs e limita
        html_blobs = [b for b in blobs if b.get("name", "").endswith(".html")]
        # Pega os mais recentes (assumindo que o Blob retorna em ordem ou que queremos os últimos da lista)
        html_blobs = html_blobs[-limit:]
        
        data = []
        if include_content and html_blobs:
            # Busca o conteúdo em paralelo para todos os blobs
            tasks = [fetch_blob_content(app_id, b) for b in html_blobs]
            results = await asyncio.gather(*tasks)
            data = [r for r in results if r is not None]
        else:
            for b in html_blobs:
                clean_name = b["name"].split("/")[-1].replace(".html", "")
                data.append({
                    "transcript_name": clean_name,
                    "content": None,
                    "url": b.get("url")
                })
        
        return {"status": "ok", "data": data}
    except Exception as e:
        logger.error(f"Erro ao listar transcripts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{transcript_id}", dependencies=[Depends(get_api_key)])
async def get_transcript(app_id: str, transcript_id: str):
    """
    Obtém o conteúdo de um transcript específico pelo ID (nome).
    Busca primeiro no Blob e complementa com dados do banco se necessário.
    """
    # 1. Tentar encontrar no Blob (precisamos da URL pública)
    # Como não temos um GET direto por nome no Blob que retorne a URL, 
    # listamos e filtramos (ou montamos a URL se o padrão for fixo)
    
    blobs = await blob_service.list_objects(prefix=f"transcripts/{transcript_id}")
    target_blob = next((b for b in blobs if transcript_id in b.get("name", "")), None)
    
    if not target_blob:
        # Tenta listar tudo e filtrar (fallback se o prefixo não funcionar como esperado)
        blobs = await blob_service.list_objects(prefix="transcripts")
        target_blob = next((b for b in blobs if transcript_id in b.get("name", "")), None)

    if not target_blob:
        raise HTTPException(status_code=404, detail="Transcript não encontrado no Blob Storage")

    content = await blob_service.get_object_content(target_blob["url"])
    
    if content is None:
        raise HTTPException(status_code=404, detail="Não foi possível ler o conteúdo do transcript")

    return {
        "status": "ok",
        "data": [
            {
                "transcript_name": transcript_id,
                "content": content,
                "url": target_blob["url"]
            }
        ]
    }

@router.delete("/{transcript_id}", dependencies=[Depends(get_api_key)])
async def delete_transcript(app_id: str, transcript_id: str):
    """
    Exclui um transcript do Blob e do banco de dados local.
    """
    # 1. Identificar o objeto no Blob para deletar
    # Precisamos do nome completo do objeto (ex: transcripts/id.html)
    blobs = await blob_service.list_objects(prefix="transcripts")
    target_blob = next((b for b in blobs if transcript_id in b.get("name", "")), None)
    
    blob_deleted = False
    if target_blob:
        blob_deleted = await blob_service.delete_object(target_blob["name"])
    else:
        logger.warning(f"Transcript {transcript_id} não encontrado no Blob para exclusão")

    # 2. Excluir do Banco de Dados local (master_data.db)
    # O usuário informou que o nome pode estar em transcript_filename, transcript_name ou na URL
    query = """
    DELETE FROM tickets 
    WHERE transcript_name = ? 
       OR transcript_filename LIKE ? 
       OR transcript_url LIKE ?
    """
    pattern = f"%{transcript_id}%"
    
    try:
        await sqlite_service.execute_update(app_id, query, (transcript_id, pattern, pattern))
        db_deleted = True
    except Exception as e:
        logger.error(f"Erro ao deletar do banco de dados: {str(e)}")
        db_deleted = False

    if not blob_deleted and not db_deleted:
        raise HTTPException(status_code=404, detail="Não foi possível excluir o transcript de nenhuma fonte")

    return {
        "status": "ok",
        "message": "Transcript excluído com sucesso",
        "details": {
            "blob": "Excluído" if blob_deleted else "Não encontrado/Erro",
            "database": "Excluído" if db_deleted else "Erro"
        }
    }
