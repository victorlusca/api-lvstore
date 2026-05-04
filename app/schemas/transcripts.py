from pydantic import BaseModel
from typing import List, Optional

class TranscriptListItem(BaseModel):
    name: str
    blob_url: str

class TranscriptListResponse(BaseModel):
    page: int
    limit: int
    data: List[TranscriptListItem]

class TranscriptDetailResponse(BaseModel):
    name: str
    blob_url: str
    content: str
    expired: bool

class ErrorResponse(BaseModel):
    error: bool = True
    code: str
    message: str
