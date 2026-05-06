import sqlite3
import os
import tempfile
import logging
from typing import List, Dict, Any, Optional
from app.services.square_cloud import square_cloud_service
from fastapi import HTTPException
from app.responses import json_safe_data

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
            if not content or len(content) < 100: # Arquivo SQLite mínimo tem 100 bytes
                logger.error(f"Arquivo lido da Square Cloud parece inválido ou vazio para {app_id}: {full_remote_path}")
                return []
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
                return [json_safe_data(dict(row)) for row in rows]
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
            try:
                cursor.execute(query, params)
                conn.commit()
                conn.close()
            except sqlite3.OperationalError as e:
                conn.close()
                logger.error(f"SQLite Operational Error during update: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro na execução do SQL (Update): {str(e)}"
                )
            except Exception as e:
                if conn:
                    conn.close()
                logger.error(f"General SQLite Error during update: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro inesperado no banco de dados: {str(e)}"
                )
            
            # 4. Ler arquivo atualizado
            with open(tmp_path, "rb") as f:
                updated_content = f.read()
            
            # 5. Sincronizar de volta para Square Cloud
            # Revertendo para o método original que usava PUT + Buffer (lista de ints)
            # pois o POST pode estar falhando se o arquivo já existir ou se o formato multipart for diferente
            try:
                buffer_data = list(updated_content)
                await square_cloud_service.update_file_content(app_id, full_remote_path, buffer_data)
            except Exception as e:
                logger.error(f"Error uploading to Square Cloud: {str(e)}")
                # Se falhar o PUT, tentamos o POST como fallback
                await square_cloud_service.upload_file(
                    app_id=app_id, 
                    path=self.remote_path, 
                    file_content=updated_content, 
                    filename=self.db_filename
                )
            
            return True
        finally:
            # Limpar arquivo temporário
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

sqlite_service = SQLiteService(db_filename="master_data.db")
reference_service = SQLiteService(db_filename="reference_data.db")
embed_service = SQLiteService(db_filename="embed_data.db")
