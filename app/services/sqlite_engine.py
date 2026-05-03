import sqlite3
import os
import tempfile
import logging
from typing import List, Dict, Any, Optional
from app.services.square_cloud import square_cloud_service
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class SQLiteService:
    def __init__(self, db_filename: str = "master_data.db", remote_path: str = "data"):
        self.db_filename = db_filename
        self.remote_path = remote_path

    def _get_connection(self, db_path: str):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def execute_query(self, app_id: str, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        # Garante que o caminho seja 'data/master_data.db' sem barras duplicadas ou iniciais
        full_remote_path = f"{self.remote_path.strip('/')}/{self.db_filename.strip('/')}"
        
        # 1. Baixar o arquivo .db
        try:
            content = await square_cloud_service.read_file(app_id, full_remote_path)
        except HTTPException as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Database {full_remote_path} not found in {app_id}")
            raise e

        # 2. Salvar temporariamente
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # 3. Executar Query
            conn = self._get_connection(tmp_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
                return [dict(row) for row in rows]
            except sqlite3.OperationalError as e:
                # Se der erro, vamos listar tabelas e colunas das tabelas principais para debug
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row['name'] for row in cursor.fetchall()]
                
                schema_info = {}
                for t in ['players', 'player_total_hours', 'player_points']:
                    if t in tables:
                        cursor.execute(f"PRAGMA table_info({t});")
                        schema_info[t] = [row['name'] for row in cursor.fetchall()]
                
                conn.close()
                logger.error(f"SQLite Error: {str(e)}. Schema: {schema_info}")
                raise HTTPException(
                    status_code=500, 
                    detail={
                        "error": str(e),
                        "found_tables": tables,
                        "schema_debug": schema_info,
                        "db_size": f"{len(content)} bytes"
                    }
                )
        finally:
            # Limpar arquivo temporário
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def execute_update(self, app_id: str, query: str, params: tuple = ()):
        # Garante que o caminho seja 'data/master_data.db' sem barras duplicadas ou iniciais
        full_remote_path = f"{self.remote_path.strip('/')}/{self.db_filename.strip('/')}"
        
        # 1. Baixar o arquivo .db
        try:
            content = await square_cloud_service.read_file(app_id, full_remote_path)
        except HTTPException as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Database {full_remote_path} not found in {app_id}")
            raise e

        # 2. Salvar temporariamente
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # 3. Executar Update
            conn = self._get_connection(tmp_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            conn.close()
            
            # 4. Ler arquivo atualizado
            with open(tmp_path, "rb") as f:
                updated_content = f.read()
            
            # 5. Upload de volta para Square Cloud
            await square_cloud_service.upload_file(app_id, self.remote_path, updated_content, self.db_filename)
            
            return True
        finally:
            # Limpar arquivo temporário
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

sqlite_service = SQLiteService()
