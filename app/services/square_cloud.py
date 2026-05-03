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

    def _normalize_path(self, path: str) -> str:
        # Square Cloud V2 usually expects paths without leading slash for some operations
        # and 'path' instead of '/path'
        path = path.strip()
        if path.startswith("/"):
            path = path[1:]
        return path

    async def list_files(self, app_id: str, path: str = "") -> List[Dict[str, Any]]:
        endpoint = f"/apps/{app_id}/files"
        params = {"path": self._normalize_path(path)}
        data = await self._request("GET", endpoint, params=params)
        return data.get("response", [])

    async def read_file(self, app_id: str, path: str) -> bytes:
        # Square Cloud V2: GET /files/content returns the file content
        endpoint = f"/apps/{app_id}/files/content"
        params = {"path": self._normalize_path(path)}
        data = await self._request("GET", endpoint, params=params)
        
        # The API returns the content directly in the response field or via a URL
        response_data = data.get("response", {})
        
        if isinstance(response_data, dict):
            # If it's a direct content (for text files)
            if "content" in response_data:
                content = response_data["content"]
                if isinstance(content, str):
                    return content.encode("utf-8")
                return content

            # If it's a download URL (common for .db files)
            download_url = response_data.get("url")
            if download_url:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(download_url)
                    resp.raise_for_status()
                    return resp.content
        
        # If response_data is not a dict, it might be the content itself if the API behaves differently
        if isinstance(response_data, str):
            return response_data.encode("utf-8")
            
        return b""

    async def update_file_content(self, app_id: str, path: str, content: str):
        # Square Cloud V2: PUT /apps/{app_id}/files with JSON payload
        endpoint = f"/apps/{app_id}/files"
        payload = {
            "path": self._normalize_path(path),
            "content": content
        }
        return await self._request("PUT", endpoint, json=payload)

    async def upload_file(self, app_id: str, path: str, file_content: bytes, filename: str):
        # Fallback for binary files if PUT + JSON doesn't support them
        # Square Cloud V2: POST /apps/{app_id}/files
        endpoint = f"/apps/{app_id}/files"
        files = {"file": (filename, file_content)}
        data = {"path": self._normalize_path(path)} 
        return await self._request("POST", endpoint, files=files, data=data)

    async def delete_file(self, app_id: str, path: str):
        # Square Cloud V2: DELETE /apps/{app_id}/files?path=...
        endpoint = f"/apps/{app_id}/files"
        params = {"path": self._normalize_path(path)}
        return await self._request("DELETE", endpoint, params=params)

square_cloud_service = SquareCloudService()
