import aiosqlite
import os
from typing import List, Optional, Dict, Any

class TranscriptRepository:
    def __init__(self, db_path: str = "data/master_data.db"):
        self.db_path = db_path

    async def get_transcripts(self, page: int, limit: int) -> List[Dict[str, Any]]:
        offset = (page - 1) * limit
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT transcript_name, transcript_filename FROM tickets LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_transcript_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT transcript_name, transcript_filename FROM tickets WHERE transcript_name = ?",
                (name,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

transcript_repository = TranscriptRepository()
