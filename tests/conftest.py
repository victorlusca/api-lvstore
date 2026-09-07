"""Infraestrutura da suite.

A API nao tem banco proprio: ela baixa o `.db` do bot pela Square Cloud. Para
testar sem credenciais e sem rede, `FakeSquareCloud` implementa a mesma
interface do `SquareCloudService` lendo e escrevendo um diretorio temporario.
Cada teste recebe uma copia limpa dos bancos de referencia em `tests/fixtures/`.
"""
import os
import sqlite3
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

APP_ID = "app_de_teste"
MASTER_KEY = "chave-mestra-de-teste"

os.environ.setdefault("API_KEY", MASTER_KEY)
os.environ.setdefault("API_DEBUG", "0")
os.environ.setdefault("SQUARECLOUD_API_TOKEN", "token-falso")

FIXTURES = Path(__file__).parent / "fixtures"

# IDs sinteticos acima de 2^53 — e isso que exercita a serializacao segura de
# inteiros grandes (um snowflake real tem essa ordem de grandeza).
USER_A = 900000000000000001
USER_B = 900000000000000002
GUILD = 800000000000000001


def construir_fixture(destino: Path, schema_sql: Path, povoar=None) -> None:
    """Cria um banco de teste a partir do DDL real do bot.

    O schema vem de `fixtures/schema_*.sql`, extraido do banco do bot por
    `fixtures/gerar_fixtures.py`. Os .db nao sao versionados: nascem aqui, a
    cada teste, sempre limpos.
    """
    con = sqlite3.connect(destino)
    con.execute("PRAGMA journal_mode=DELETE")
    con.executescript(schema_sql.read_text(encoding="utf-8"))
    if povoar:
        povoar(con)
    con.commit()
    con.close()


def _povoar_master(con):
    con.execute("INSERT INTO players (playerName, playerLogin, playerID, discordUserID)"
                " VALUES (?,?,?,?)", ("jogador_um", "um", 101, USER_A))
    con.execute("INSERT INTO players (playerName, playerLogin, playerID, discordUserID)"
                " VALUES (?,?,?,?)", ("jogador_dois", "dois", 102, USER_B))
    con.execute("INSERT INTO player_total_hours (user_id, total_hours) VALUES (?,?)",
                (USER_A, "12:30"))
    con.execute("INSERT INTO player_points (discord_id, game_id, total_points)"
                " VALUES (?,?,?)", (USER_A, 101, 42))
    for i in range(5):
        con.execute(
            "INSERT INTO audit_log (event_type, system_key, action_key, actor_discord_id,"
            " target_discord_id, guild_id, status, message, details_json)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            ("teste", "sistema", f"acao_{i}", USER_A, USER_B, GUILD, "success",
             f"evento sintetico {i}", '{"campo": "valor"}'))
    con.execute("INSERT INTO security_whitelist_global_users (user_id) VALUES (?)", (USER_A,))


def _povoar_reference(con):
    # A aba de seguranca resolve o guild_id por aqui. Sem esta linha o bot conta
    # como "nao instalado" — ver test_seguranca_sem_guild_id.
    con.execute("INSERT INTO configuracoes_servidor (id, guild_id) VALUES (1, ?)", (str(GUILD),))


class FakeSquareCloud:
    """Substituto local do SquareCloudService. Sem rede, sem credenciais."""

    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.chamadas: list[tuple] = []
        self.falhar_listagem = False   # simula HTTP 429 na listagem

    def _abs(self, app_id: str, path: str) -> Path:
        return self.raiz / app_id / path.strip("/")

    async def list_files(self, app_id: str, path: str = ""):
        from fastapi import HTTPException
        self.chamadas.append(("list", app_id, path))
        if self.falhar_listagem:
            raise HTTPException(status_code=429, detail="Square Cloud Rate Limit exceeded")
        d = self._abs(app_id, path)
        if not d.is_dir():
            raise HTTPException(status_code=404, detail="APP_NOT_FOUND")
        return [
            {"name": f.name, "type": "file", "size": f.stat().st_size,
             "lastModified": int(f.stat().st_mtime * 1000)}
            for f in d.iterdir() if f.is_file()
        ]

    async def read_file(self, app_id: str, path: str) -> bytes:
        from fastapi import HTTPException
        self.chamadas.append(("read", app_id, path))
        p = self._abs(app_id, path)
        if not p.is_file():
            raise HTTPException(status_code=404, detail=f"not found: {path}")
        return p.read_bytes()

    async def update_file_content(self, app_id: str, path: str, content):
        self.chamadas.append(("write", app_id, path))
        p = self._abs(app_id, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(bytes(content) if isinstance(content, list) else content)
        return {"status": "success"}

    async def upload_file(self, app_id: str, path: str, file_content: bytes, filename: str):
        return await self.update_file_content(app_id, f"{path}/{filename}", list(file_content))

    async def delete_file(self, app_id: str, path: str):
        p = self._abs(app_id, path)
        if p.is_file():
            p.unlink()
        return {"status": "success"}

    def contagem(self, tipo: str) -> int:
        return sum(1 for c in self.chamadas if c[0] == tipo)


@pytest.fixture
def nuvem(tmp_path, monkeypatch):
    """Square Cloud falsa, ja populada com os bancos de fixture."""
    destino = tmp_path / "apps" / APP_ID / "data"
    destino.mkdir(parents=True)
    construir_fixture(destino / "master_data.db",
                      FIXTURES / "schema_master.sql", _povoar_master)
    construir_fixture(destino / "reference_data.db",
                      FIXTURES / "schema_reference.sql", _povoar_reference)

    fake = FakeSquareCloud(tmp_path / "apps")

    # O servico e importado por nome em varios modulos; e preciso reapontar
    # todos, nao so o modulo de origem.
    from app.services import square_cloud as mod_sc
    from app.services import sqlite_engine as mod_se
    monkeypatch.setattr(mod_sc, "square_cloud_service", fake)
    monkeypatch.setattr(mod_se, "square_cloud_service", fake)
    for nome in ("app.routers.bots", "app.routers.system", "app.routers.transcripts"):
        modulo = sys.modules.get(nome)
        if modulo is not None and hasattr(modulo, "square_cloud_service"):
            monkeypatch.setattr(modulo, "square_cloud_service", fake)

    # Caches sao globais de modulo: sem limpar, um teste contamina o seguinte.
    mod_se._snapshot_cache.clear()
    mod_se._remote_listing_cache.clear()
    mod_se._snapshot_locks.clear()
    yield fake
    mod_se._snapshot_cache.clear()
    mod_se._remote_listing_cache.clear()
    mod_se._snapshot_locks.clear()


@pytest.fixture
def client(nuvem):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {MASTER_KEY}"}


@pytest.fixture
def db_do_bot(nuvem):
    """Caminho do master_data.db dentro da nuvem falsa, para inspecao direta."""
    return nuvem.raiz / APP_ID / "data" / "master_data.db"
