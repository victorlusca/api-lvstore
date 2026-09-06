import asyncio
import sqlite3
import os
import shutil
import tempfile
import time
import logging
from typing import List, Dict, Any, Optional
from app.services.square_cloud import square_cloud_service
from fastapi import HTTPException
from app.responses import json_safe_data

logger = logging.getLogger(__name__)

# Listagem de `data/` por app_id, com TTL curto. O painel dispara várias leituras
# em paralelo (uma por tabela de configuração) e todas precisam saber se existe
# um `-wal` ao lado do banco; sem o cache isso dobraria as chamadas à Square
# Cloud, que já tem limite de taxa (HTTP 429).
_REMOTE_LISTING_TTL_S = 15
_remote_listing_cache: Dict[str, Any] = {}

# Cache dos BYTES do banco baixado.
#
# Abrir uma aba do painel dispara dezenas de consultas; sem cache, cada uma
# baixava os ~400 KB do master_data.db de novo (a Square Cloud devolve o binário
# como array JSON de inteiros, ~1,5 MB por download). O resultado eram
# `httpx.ReadTimeout` em série e HTTP 500 nas abas — e o /api/me do site batendo
# em 524 porque dependia dessas leituras.
#
# TTL curto: o painel é leitura de painel administrativo, não tempo real; e toda
# escrita invalida a entrada na hora, então salvar continua refletindo na hora.
_SNAPSHOT_TTL_S = 15
_snapshot_cache: Dict[str, Dict[str, Any]] = {}
# Uma trava por banco: as consultas chegam em paralelo, então só o TTL não
# bastaria — sem single-flight, 20 requisições simultâneas iniciariam 20
# downloads antes de o primeiro popular o cache.
_snapshot_locks: Dict[str, asyncio.Lock] = {}


def _prune_snapshots(agora: float) -> None:
    for k in [k for k, v in _snapshot_cache.items() if agora - v["at"] > _SNAPSHOT_TTL_S]:
        _snapshot_cache.pop(k, None)


class SQLiteService:
    def __init__(self, db_filename: str = "master_data.db", remote_path: str = "data"):
        self.db_filename = db_filename
        self.remote_path = remote_path

    @property
    def full_remote_path(self) -> str:
        # Garante 'data/master_data.db' sem barras duplicadas ou iniciais
        return f"{self.remote_path.strip('/')}/{self.db_filename.strip('/')}"

    def _get_connection(self, db_path: str):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def _list_remote_dir(self, app_id: str) -> List[Dict[str, Any]]:
        key = f"{app_id}:{self.remote_path}"
        hit = _remote_listing_cache.get(key)
        if hit and time.time() - hit["at"] < _REMOTE_LISTING_TTL_S:
            return hit["files"]
        try:
            files = await square_cloud_service.list_files(app_id, self.remote_path)
        except Exception:
            # Falha na listagem não pode derrubar a leitura do banco: sem ela
            # apenas seguimos sem o `-wal` (comportamento anterior).
            return []
        _remote_listing_cache[key] = {"at": time.time(), "files": files}
        return files

    async def _remote_wal_size(self, app_id: str) -> int:
        """Tamanho do `<banco>.db-wal` remoto (0 quando não existe)."""
        wal_name = f"{self.db_filename}-wal"
        for f in await self._list_remote_dir(app_id):
            if f.get("name") == wal_name:
                try:
                    return int(f.get("size") or 0)
                except (TypeError, ValueError):
                    return 0
        return 0

    def _cache_key(self, app_id: str) -> str:
        return f"{app_id}:{self.full_remote_path}"

    async def _remote_bytes(self, app_id: str, force: bool = False) -> tuple:
        """Bytes do banco (e do `-wal`, se houver), com cache + single-flight.

        `force=True` ignora o cache: usado na escrita, que precisa partir do
        estado mais recente possível para não sobrescrever o que o bot gravou
        nesse meio-tempo. A leitura pode usar cache; a escrita, não.

        Retorna (db_bytes, wal_bytes|None). Levanta 404 quando o banco não existe.
        """
        key = self._cache_key(app_id)
        if not force:
            hit = _snapshot_cache.get(key)
            if hit and time.time() - hit["at"] < _SNAPSHOT_TTL_S:
                return hit["db"], hit["wal"]

        lock = _snapshot_locks.setdefault(key, asyncio.Lock())
        async with lock:
            # Quem esperou na fila aproveita o download de quem chegou primeiro.
            if not force:
                hit = _snapshot_cache.get(key)
                if hit and time.time() - hit["at"] < _SNAPSHOT_TTL_S:
                    return hit["db"], hit["wal"]

            try:
                db = await square_cloud_service.read_file(app_id, self.full_remote_path)
            except HTTPException as e:
                if e.status_code == 404:
                    raise HTTPException(status_code=404, detail=f"Database {self.full_remote_path} not found in {app_id}")
                raise e

            wal = None
            if db and len(db) >= 100 and await self._remote_wal_size(app_id) > 0:
                try:
                    baixado = await square_cloud_service.read_file(app_id, f"{self.full_remote_path}-wal")
                    if baixado:
                        wal = baixado
                        logger.warning(
                            f"{app_id}: {self.db_filename} está em modo WAL; o journal foi baixado junto. "
                            "Atualize/reinicie o bot para que ele passe a usar arquivo único."
                        )
                except Exception as e:
                    logger.error(f"Falha ao baixar o WAL de {app_id}/{self.full_remote_path}: {e}")

            _prune_snapshots(time.time())
            _snapshot_cache[key] = {"at": time.time(), "db": db, "wal": wal}
            return db, wal

    async def _download_snapshot(self, app_id: str, force: bool = False) -> tuple:
        """Materializa o banco num diretório temporário para consulta local.

        O arquivo é gravado com o **nome real** e o WAL ao lado com o sufixo que
        o SQLite espera — só assim o engine recupera os commits que ainda estão
        no journal. Um banco em WAL cujo `-wal` não é baixado devolve dados
        defasados: era por isso que um registro feito no bot não aparecia no site.

        Retorna (tmp_dir, db_path, tinha_wal).
        """
        content, wal = await self._remote_bytes(app_id, force=force)

        if not content or len(content) < 100:  # Arquivo SQLite mínimo tem 100 bytes
            logger.error(f"Arquivo lido da Square Cloud parece inválido ou vazio para {app_id}: {self.full_remote_path}")
            return None, None, False

        tmp_dir = tempfile.mkdtemp(prefix="botdb_")
        db_path = os.path.join(tmp_dir, self.db_filename)
        with open(db_path, "wb") as f:
            f.write(content)

        tinha_wal = False
        if wal:
            with open(f"{db_path}-wal", "wb") as f:
                f.write(wal)
            tinha_wal = True

        return tmp_dir, db_path, tinha_wal

    @staticmethod
    def _cleanup(tmp_dir: Optional[str]) -> None:
        if tmp_dir and os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)

    async def execute_query(self, app_id: str, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        tmp_dir, db_path, _ = await self._download_snapshot(app_id)
        if not db_path:
            return []

        try:
            conn = self._get_connection(db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [json_safe_data(dict(row)) for row in rows]
            except sqlite3.DatabaseError as e:
                logger.error(f"SQLite Error ({app_id} / {self.db_filename}): {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro na execução do SQL: {str(e)}"
                )
            finally:
                conn.close()
        finally:
            self._cleanup(tmp_dir)

    async def execute_update(self, app_id: str, query: str, params: tuple = ()):
        tmp_dir, db_path, tinha_wal = await self._download_snapshot(app_id, force=True)
        if not db_path:
            raise HTTPException(status_code=404, detail=f"Database {self.full_remote_path} not found in {app_id}")

        try:
            conn = self._get_connection(db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                # Consolida o journal no arquivo principal: é o arquivo principal,
                # sozinho, que sobe de volta para a Square Cloud.
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                # Nunca publicar uma imagem corrompida por cima do banco do bot.
                # Foi assim que os índices de audit_log foram destruídos em
                # produção; a partir daqui a escrita é abortada em vez de
                # propagar o estrago.
                problemas = [r[0] for r in conn.execute("PRAGMA quick_check")]
                if problemas != ["ok"]:
                    logger.error(f"Integridade comprometida em {app_id}/{self.db_filename}, upload abortado: {problemas[:5]}")
                    raise HTTPException(
                        status_code=500,
                        detail="Banco do bot está inconsistente; a alteração não foi gravada para não agravar o problema.",
                    )
            except HTTPException:
                raise
            except sqlite3.DatabaseError as e:
                logger.error(f"SQLite Error during update ({app_id} / {self.db_filename}): {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro na execução do SQL (Update): {str(e)}"
                )
            except Exception as e:
                logger.error(f"General SQLite Error during update: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro inesperado no banco de dados: {str(e)}"
                )
            finally:
                conn.close()

            # 4. Ler arquivo atualizado
            with open(db_path, "rb") as f:
                updated_content = f.read()

            # 5. Sincronizar de volta para Square Cloud
            # PUT + Buffer (lista de ints); POST multipart como fallback.
            try:
                buffer_data = list(updated_content)
                await square_cloud_service.update_file_content(app_id, self.full_remote_path, buffer_data)
            except Exception as e:
                logger.error(f"Error uploading to Square Cloud: {str(e)}")
                # Se falhar o PUT, tentamos o POST como fallback
                await square_cloud_service.upload_file(
                    app_id=app_id,
                    path=self.remote_path,
                    file_content=updated_content,
                    filename=self.db_filename
                )

            # O conteúdo do WAL remoto já entrou no arquivo principal acima.
            # Deixá-lo intacto faria o bot reaplicar frames antigos sobre páginas
            # que acabaram de mudar — a origem exata da corrupção. Zerar é
            # seguro: um `-wal` de 0 byte é lido como "sem frames".
            if tinha_wal:
                try:
                    await square_cloud_service.update_file_content(app_id, f"{self.full_remote_path}-wal", [])
                    logger.warning(f"{app_id}: WAL remoto de {self.db_filename} consolidado e zerado.")
                except Exception as e:
                    logger.error(f"Falha ao zerar o WAL remoto de {app_id}/{self.db_filename}: {e}")

            # O cache passa a refletir exatamente o que acabou de subir: a
            # próxima leitura já enxerga a alteração, sem baixar de novo.
            _snapshot_cache[self._cache_key(app_id)] = {
                "at": time.time(), "db": updated_content, "wal": None,
            }
            _remote_listing_cache.pop(f"{app_id}:{self.remote_path}", None)
            return True
        finally:
            self._cleanup(tmp_dir)

sqlite_service = SQLiteService(db_filename="master_data.db")
reference_service = SQLiteService(db_filename="reference_data.db")
embed_service = SQLiteService(db_filename="embed_data.db")
