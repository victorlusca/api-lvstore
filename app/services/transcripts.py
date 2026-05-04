from typing import List, Dict, Any
from app.repositories.transcripts import transcript_repository
from app.clients.squarecloud_blob import squarecloud_blob_client
from app.core.exceptions import TranscriptNotFound, BlobExpired, ExternalRequestFailed
import httpx

class TranscriptService:
    async def list_transcripts(self, app_id: str, page: int, limit: int) -> Dict[str, Any]:
        records = await transcript_repository.get_transcripts(app_id, page, limit)
        
        data = []
        for rec in records:
            data.append({
                "name": rec["transcript_name"],
                "blob_url": squarecloud_blob_client.get_blob_url(app_id, rec["transcript_filename"])
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
