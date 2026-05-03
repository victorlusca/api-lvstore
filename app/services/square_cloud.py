import httpx
import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class SquareCloudService:
    BASE_URL = "https://api.squarecloud.app/v2"

    def __init__(self):
        self.headers = {
            "Authorization": settings.SQUARE_CLOUD_API_TOKEN
        }

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                url = f"{self.BASE_URL}{endpoint}"
                response = await client.request(method, url, headers=self.headers, **kwargs)
                
                if response.status_code == 429:
                    raise HTTPException(status_code=429, detail="Square Cloud Rate Limit exceeded")
                
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "error":
                    raise HTTPException(status_code=400, detail=data.get("message", "Square Cloud API Error"))
                
                return data
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred: {e.response.text}")
                raise HTTPException(status_code=e.response.status_code, detail=f"Square Cloud API error: {e.response.text}")
            except Exception as e:
                logger.error(f"An error occurred: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Internal error connecting to Square Cloud: {str(e)}")

    async def list_files(self, app_id: str, path: str = "/") -> List[Dict[str, Any]]:
        endpoint = f"/apps/{app_id}/files/list"
        params = {"path": path}
        data = await self._request("GET", endpoint, params=params)
        return data.get("response", [])

    async def read_file(self, app_id: str, path: str) -> bytes:
        endpoint = f"/apps/{app_id}/files/read"
        params = {"path": path}
        data = await self._request("GET", endpoint, params=params)
        
        response_data = data.get("response", {})
        
        # If it's a direct content
        if "content" in response_data:
            content = response_data["content"]
            if isinstance(content, str):
                return content.encode("utf-8")
            return content

        # If it's a download URL
        download_url = response_data.get("url")
        if download_url:
            async with httpx.AsyncClient() as client:
                resp = await client.get(download_url)
                resp.raise_for_status()
                return resp.content
        
        return b""

    async def upload_file(self, app_id: str, path: str, file_content: bytes, filename: str):
        # Square Cloud Upload uses multipart/form-data
        endpoint = f"/apps/{app_id}/files/upload"
        files = {"file": (filename, file_content)}
        # The path is usually passed in the body or as a parameter
        # According to some docs, it's a POST with 'file' and optional 'path'
        data = {"path": path} 
        return await self._request("POST", endpoint, files=files, data=data)

    async def delete_file(self, app_id: str, path: str):
        endpoint = f"/apps/{app_id}/files/delete"
        params = {"path": path}
        return await self._request("DELETE", endpoint, params=params)

square_cloud_service = SquareCloudService()
