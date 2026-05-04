from fastapi import APIRouter, Query, Depends
from app.schemas.transcripts import TranscriptListResponse, TranscriptDetailResponse
from app.services.transcripts import transcript_service

router = APIRouter(prefix="/transcripts", tags=["transcripts"])

@router.get("", response_model=TranscriptListResponse)
async def list_transcripts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Listagem de transcripts paginada (sem conteúdo HTML).
    """
    return await transcript_service.list_transcripts(page, limit)

@router.get("/{name}", response_model=TranscriptDetailResponse)
async def get_transcript(name: str):
    """
    Busca transcript detalhado com conteúdo HTML completo.
    """
    return await transcript_service.get_transcript_detail(name)
