from fastapi import APIRouter, Query, Depends
from app.auth import require_scope
from app.schemas.transcripts import TranscriptListResponse, TranscriptDetailResponse
from app.services.transcripts import transcript_service

router = APIRouter(prefix="/bots", tags=["transcripts"])

@router.get("/{app_id}/transcripts", response_model=TranscriptListResponse, dependencies=[Depends(require_scope("admin:*"))])
async def list_transcripts(
    app_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Listagem de transcripts paginada (sem conteúdo HTML).
    """
    return await transcript_service.list_transcripts(app_id, page, limit)

@router.get("/{app_id}/transcripts/{name}", response_model=TranscriptDetailResponse, dependencies=[Depends(require_scope("admin:*"))])
async def get_transcript(app_id: str, name: str):
    """
    Busca transcript detalhado com conteúdo HTML completo.
    """
    return await transcript_service.get_transcript_detail(app_id, name)
