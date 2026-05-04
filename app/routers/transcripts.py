import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.services.square_blob import blob_service
from app.services.sqlite_engine import sqlite_service
from app.core.security import get_api_key
import logging
import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots/{app_id}/transcripts", tags=["Transcripts"])

def get_blob_name_from_hash(transcript_hash: str) -> str:
    """
    Mapeia o hash puro do banco para o nome real do blob na Square Cloud.
    Ex: 4ef40e59... -> transcripts/4ef40e59...-ex30.html
    """
    # Limpa qualquer resquício de sufixo ou extensão para garantir o hash puro
    clean_hash = transcript_hash.split("/")[-1].replace(".html", "").replace("-ex30", "")
    return f"transcripts/{clean_hash}-ex30.html"

async def fetch_blob_content_by_url(url: str, pure_hash: str) -> Optional[Dict[str, Any]]:
    """
    Busca conteúdo de um blob a partir de sua URL pública e retorna com o hash puro.
    """
    try:
        content = await blob_service.get_object_content(url)
        if content:
            return {
                "transcript_name": pure_hash, # Retornamos apenas o HASH puro (sem -ex30)
                "content": content,
                "url": url
            }
    except Exception as e:
        logger.error(f"Erro ao buscar conteúdo do blob {pure_hash}: {str(e)}")
    return None

@router.get("", dependencies=[Depends(get_api_key)])
async def list_transcripts(
    app_id: str, 
    limit: int = Query(20, ge=1, le=100),
    include_content: bool = Query(True)
):
    """
    Lista os transcripts usando o hash puro do Banco.
    """
    try:
        # 1. Buscar hashes do Banco de Dados
        query = "SELECT transcript_name FROM tickets WHERE transcript_name IS NOT NULL ORDER BY id DESC LIMIT ?"
        db_tickets = await sqlite_service.execute_query(app_id, query, (limit,))
        
        # 2. Listar Blobs para obter as URLs reais
        blobs = await blob_service.list_objects(prefix="transcripts")
        
        # Criar um mapeamento de hash puro -> url do blob
        blob_map = {}
        for b in blobs:
            name = b.get("name", "")
            if "-ex30.html" in name:
                # Extrair o hash puro do nome do blob
                # Ex: transcripts/4ef40e59...-ex30.html -> 4ef40e59...
                match = re.search(r"transcripts/(.+)-ex30\.html", name)
                if match:
                    pure_hash = match.group(1)
                    blob_map[pure_hash] = b.get("url")

        # 3. Cruzar dados do Banco com o Blob usando o hash puro
        final_list = []
        for ticket in db_tickets:
            t_hash = ticket["transcript_name"].replace("-ex30", "") # Garante hash puro
            if t_hash in blob_map:
                final_list.append({
                    "hash": t_hash,
                    "url": blob_map[t_hash]
                })

        # Fallback para o Blob se o banco estiver vazio
        if not final_list:
            for b_hash, b_url in list(blob_map.items())[:limit]:
                final_list.append({"hash": b_hash, "url": b_url})

        # 4. Buscar conteúdos em paralelo
        data = []
        if include_content and final_list:
            tasks = [fetch_blob_content_by_url(item["url"], item["hash"]) for item in final_list]
            results = await asyncio.gather(*tasks)
            data = [r for r in results if r is not None]
        else:
            for item in final_list:
                data.append({
                    "transcript_name": item["hash"],
                    "content": None,
                    "url": item["url"]
                })

        return {"status": "ok", "data": data}
    except Exception as e:
        logger.error(f"Erro ao listar transcripts: {str(e)}")
        return {"status": "ok", "data": []}

@router.get("/{transcript_hash}", dependencies=[Depends(get_api_key)])
async def get_transcript(app_id: str, transcript_hash: str):
    """
    Obtém um único transcript pelo seu HASH PURO.
    """
    # 1. Mapear hash puro para o nome real do blob (transcripts/{hash}-ex30.html)
    blob_name = get_blob_name_from_hash(transcript_hash)
    
    # 2. Buscar a URL no Blob Storage
    blobs = await blob_service.list_objects(prefix=blob_name)
    target = next((b for b in blobs if b["name"] == blob_name), None)
    
    if not target:
        # Tenta uma busca mais flexível se o mapeamento fixo falhar
        clean_hash = transcript_hash.replace(".html", "").replace("-ex30", "")
        blobs = await blob_service.list_objects(prefix=f"transcripts/{clean_hash}")
        target = next((b for b in blobs if clean_hash in b["name"]), None)

    if not target or not target.get("url"):
        raise HTTPException(status_code=404, detail=f"Transcript {transcript_hash} não encontrado")

    # 3. Baixar conteúdo
    content = await blob_service.get_object_content(target["url"])
    if not content:
        raise HTTPException(status_code=404, detail="Não foi possível carregar o conteúdo do HTML")

    return {
        "status": "ok",
        "data": [
            {
                "transcript_name": transcript_hash.replace("-ex30", ""), # Retorna hash puro
                "content": content,
                "url": target["url"]
            }
        ]
    }

@router.delete("/{transcript_hash}", dependencies=[Depends(get_api_key)])
async def delete_transcript(app_id: str, transcript_hash: str):
    """
    Deleta o transcript pelo HASH PURO.
    """
    blob_name = get_blob_name_from_hash(transcript_hash)
    clean_hash = transcript_hash.replace("-ex30", "")
    
    # 1. Deletar do Blob
    blob_deleted = await blob_service.delete_object(blob_name)
    
    # 2. Deletar do Banco
    query = "DELETE FROM tickets WHERE transcript_name = ? OR transcript_name = ?"
    try:
        # Tenta deletar tanto o hash puro quanto com o sufixo (por segurança)
        await sqlite_service.execute_update(app_id, query, (clean_hash, f"{clean_hash}-ex30"))
        db_deleted = True
    except Exception:
        db_deleted = False

    return {
        "status": "ok",
        "message": "Exclusão concluída",
        "details": {"blob": blob_deleted, "database": db_deleted}
    }
