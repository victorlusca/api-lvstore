from typing import List, Optional, Dict, Any
from app.services.sqlite_engine import SQLiteService

sqlite_service = SQLiteService(db_filename="master_data.db", remote_path="data")

class TranscriptRepository:
    async def get_transcripts(self, app_id: str, page: int, limit: int) -> List[Dict[str, Any]]:
        offset = (page - 1) * limit
        query = "SELECT transcript_name, transcript_filename FROM tickets LIMIT ? OFFSET ?"
        return await sqlite_service.execute_query(app_id, query, (limit, offset))

    async def get_transcript_by_name(self, app_id: str, name: str) -> Optional[Dict[str, Any]]:
        query = "SELECT transcript_name, transcript_filename FROM tickets WHERE transcript_name = ?"
        rows = await sqlite_service.execute_query(app_id, query, (name,))
        return rows[0] if rows else None

transcript_repository = TranscriptRepository()
