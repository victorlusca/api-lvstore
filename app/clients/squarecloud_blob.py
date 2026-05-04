import httpx
import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class SquareCloudBlobClient:
    def __init__(self):
        self.base_url = "https://public-blob.squarecloud.dev"
        self.api_url = "https://blob.squarecloud.app/v1"
        self.token = settings.SQUARE_CLOUD_API_TOKEN
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        self.max_retries = 3

    def get_blob_url(self, app_id: str, transcript_filename: str) -> str:
        # Se o filename já contém o app_id (formato do 'id' da API v1)
        if app_id in transcript_filename:
            return f"{self.base_url}/{transcript_filename}"
            
        # Fallback para o formato antigo
        if transcript_filename.endswith(".html"):
            return f"{self.base_url}/{app_id}/{transcript_filename}"
        return f"{self.base_url}/{app_id}/transcripts/{transcript_filename}-ex30.html"

    async def list_objects(self, prefix: str = "transcripts") -> List[Dict[str, Any]]:
        url = f"{self.api_url}/objects?prefix={prefix}"
        headers = {"Authorization": self.token}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    
                    # A API retorna no formato {"status": "success", "response": {"objects": [...]}}
                    if isinstance(data, dict):
                        inner_response = data.get("response", {})
                        if isinstance(inner_response, dict):
                            return inner_response.get("objects", [])
                    return []
                except Exception as exc:
                    if attempt == self.max_retries - 1:
                        logger.error(f"Failed to list objects from Square Cloud: {exc}")
                        return []
                    await asyncio.sleep(1)
        return []

    async def fetch_transcript_html(self, app_id: str, transcript_filename: str) -> str:
        url = self.get_blob_url(app_id, transcript_filename)
        headers = {"Authorization": f"Bearer {self.token}"}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 404:
                        logger.warning(f"Blob not found (expired?): {url}")
                        return "BLOB_EXPIRED"
                    
                    response.raise_for_status()
                    return response.text
                
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    logger.error(f"Attempt {attempt + 1} failed for {url}: {exc}")
                    if attempt == self.max_retries - 1:
                        raise exc
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
            
            raise httpx.RequestError("Max retries reached")

squarecloud_blob_client = SquareCloudBlobClient()
