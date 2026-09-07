"""Extrai o SCHEMA dos bancos do bot para os .sql usados nos testes.

Nao copia dado real: so o DDL. As linhas sinteticas ficam em conftest.py.
Rode de novo quando o schema do bot mudar:

    python tests/fixtures/gerar_fixtures.py <caminho-do-APP/data>
"""
import sqlite3
import sys
from pathlib import Path

AQUI = Path(__file__).parent

# IDs sinteticos, mas com a mesma ordem de grandeza de um snowflake real
# (acima de 2^53) — e isso que exercita a serializacao segura de inteiros.
USER_A = 900000000000000001
USER_B = 900000000000000002
GUILD = 800000000000000001


def extrair_schema(origem: Path, nome_sql: str):
    """Grava o DDL do banco do bot como .sql — texto, versionavel e diffavel.

    Os .db de teste NAO vao para o Git: sao construidos a partir deste .sql no
    momento do teste (ver conftest.py::construir_fixture).
    """
    src = sqlite3.connect(f"file:{origem}?mode=ro", uri=True)
    ddl = [r[0] for r in src.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")]
    src.close()
    destino = AQUI / nome_sql
    destino.write_text(";\n".join(ddl) + ";\n", encoding="utf-8")
    print(f"  {nome_sql}: {len(ddl)} objetos de schema")


def povoar_reference(con):
    # A aba de seguranca do painel resolve o guild_id por aqui. Sem esta linha,
    # o bot conta como "nao instalado" — ver test_seguranca_sem_guild_id.
    con.execute("INSERT INTO configuracoes_servidor (id, guild_id) VALUES (1, ?)",
                (str(GUILD),))


def povoar_master(con):
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


if __name__ == "__main__":
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "../APP/data")
    print(f"extraindo schema de {base}")
    extrair_schema(base / "master_data.db", "schema_master.sql")
    extrair_schema(base / "reference_data.db", "schema_reference.sql")
    print("pronto — nenhum dado real foi copiado.")
