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
                conn.close()
                logger.error(f"SQLite Operational Error: {str(e)}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Erro na execução do SQL: {str(e)}"
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
            
            # 4. Ler arquivo atualizado e converter para lista de bytes (Buffer format da Square Cloud)
            with open(tmp_path, "rb") as f:
                updated_content = f.read()
            
            # A Square Cloud V2 aceita o envio de conteúdo via PUT JSON se formatado corretamente.
            # No entanto, para arquivos .db (binários), o mais seguro é converter para uma lista de bytes
            # se estivermos usando o endpoint /files com PUT.
            # De acordo com sua referência: PUT /files com {"path": "...", "content": "..."}
            
            # Convertendo bytes para uma lista de inteiros (Buffer) para compatibilidade total
            buffer_data = list(updated_content)
            
            # 5. Sincronizar de volta para Square Cloud usando PUT
            # Nota: O serviço square_cloud_service.update_file_content foi atualizado para lidar com isso
            await square_cloud_service.update_file_content(app_id, full_remote_path, buffer_data)
            
            return True
        finally:
            # Limpar arquivo temporário
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

sqlite_service = SQLiteService()
