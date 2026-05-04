from typing import List, Dict, Any
from app.repositories.transcripts import transcript_repository
from app.clients.squarecloud_blob import squarecloud_blob_client
from app.core.exceptions import TranscriptNotFound, BlobExpired, ExternalRequestFailed
import httpx

class TranscriptService:
    async def list_transcripts(self, app_id: str, page: int, limit: int) -> Dict[str, Any]:
        # 1. Buscar objetos diretamente da Blob API
        objects = await squarecloud_blob_client.list_objects(prefix="transcripts")
        
        # 2. Paginação manual da lista de objetos
        start = (page - 1) * limit
        end = start + limit
        paginated_objects = objects[start:end]
        
        data = []
        for obj in paginated_objects:
            # A API v1 usa 'id' para o caminho completo do arquivo
            file_key = obj.get("id") or obj.get("key") or obj.get("name")
            if not file_key:
                continue
                
            # Extrair o nome amigável
            # Ex: "app_id/transcripts/nome-ex30.html" -> "nome"
            display_name = file_key.split("/")[-1].replace("-ex30.html", "").replace(".html", "")
            
            data.append({
                "name": display_name,
                "blob_url": squarecloud_blob_client.get_blob_url(app_id, file_key)
            })
            
        return {
            "page": page,
            "limit": limit,
            "data": data
        }

    async def get_transcript_detail(self, app_id: str, name: str) -> Dict[str, Any]:
        record = await transcript_repository.get_transcript_by_name(app_id, name)
        
        if not record:
            raise TranscriptNotFound()
        
        filename = record["transcript_filename"]
        blob_url = squarecloud_blob_client.get_blob_url(app_id, filename)
        
        try:
            content = await squarecloud_blob_client.fetch_transcript_html(app_id, filename)
            
            if content == "BLOB_EXPIRED":
                raise BlobExpired()
                
            return {
                "name": name,
                "blob_url": blob_url,
                "content": content,
                "expired": False
            }
        except httpx.HTTPError:
            raise ExternalRequestFailed()

transcript_service = TranscriptService()
