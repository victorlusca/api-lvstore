import httpx
import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class SquareCloudBlobService:
    BASE_URL = "https://blob.squarecloud.app/v1"

    def __init__(self):
        self.headers = {
            "Authorization": settings.SQUARE_CLOUD_API_TOKEN
        }

    async def list_objects(self, prefix: str = "transcripts") -> List[Dict[str, Any]]:
        """
        Lista objetos no Square Cloud Blob com um prefixo.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                url = f"{self.BASE_URL}/objects"
                params = {"prefix": prefix}
                response = await client.get(url, headers=self.headers, params=params)
                
                if response.status_code == 429:
                    raise HTTPException(status_code=429, detail="Square Cloud Blob Rate Limit exceeded")
                
                response.raise_for_status()
                data = response.json()
                
                # A API retorna { "status": "success", "data": { "objects": [...] } }
                if data.get("status") == "success":
                    return data.get("data", {}).get("objects", [])
                return []
            except Exception as e:
                logger.error(f"Erro ao listar objetos no Blob: {str(e)}")
                return []

    async def get_object_content(self, public_url: str) -> Optional[str]:
        """
        Baixa o conteúdo de um objeto a partir de sua URL pública.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(public_url)
                response.raise_for_status()
                return response.text
            except Exception as e:
                logger.error(f"Erro ao baixar conteúdo do Blob URL {public_url}: {str(e)}")
                return None

    async def delete_object(self, object_name: str) -> bool:
        """
        Exclui um objeto do Square Cloud Blob.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                url = f"{self.BASE_URL}/objects"
                payload = {"object": object_name}
                response = await client.request("DELETE", url, headers=self.headers, json=payload)
                
                if response.status_code == 429:
                    raise HTTPException(status_code=429, detail="Square Cloud Blob Rate Limit exceeded")
                
                response.raise_for_status()
                data = response.json()
                return data.get("status") == "success"
            except Exception as e:
                logger.error(f"Erro ao excluir objeto {object_name} do Blob: {str(e)}")
                return False

blob_service = SquareCloudBlobService()
