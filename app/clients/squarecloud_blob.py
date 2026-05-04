import httpx
import asyncio
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class SquareCloudBlobClient:
    def __init__(self):
        self.base_url = "https://public-blob.squarecloud.dev"
        self.app_id = settings.SQUARE_CLOUD_APP_ID
        self.token = settings.SQUARE_CLOUD_API_TOKEN
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        self.max_retries = 3

    def get_blob_url(self, transcript_filename: str) -> str:
        return f"{self.base_url}/{self.app_id}/transcripts/{transcript_filename}-ex30.html"

    async def fetch_transcript_html(self, transcript_filename: str) -> str:
        url = self.get_blob_url(transcript_filename)
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
