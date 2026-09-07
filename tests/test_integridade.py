"""Integridade de dados e regressoes de codificacao/serializacao."""
import asyncio
import os
import sqlite3
from pathlib import Path

import pytest

from tests.conftest import APP_ID

API_ROOT = Path(__file__).resolve().parent.parent
LIMITE_JS = 2 ** 53  # maior inteiro que o JavaScript representa sem perder digitos


# ─── Codificacao ─────────────────────────────────────────────────────────────

MARCAS_MOJIBAKE = ("Ã¡", "Ã£", "Ã§", "Ãµ", "Ã©", "Ãª", "Ã­", "Ã³", "Ãº", "â€", "﻿")


def test_nenhum_fonte_com_utf8_duplo_codificado():
    """Regressao: textos como 'Token invÃ¡lido' iam para a resposta HTTP.

    Nao era so comentario: mensagens de erro de auth e de validacao apareciam
    corrompidas no painel.
    """
    problemas = []
    for raiz, dirs, arquivos in os.walk(API_ROOT / "app"):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for nome in arquivos:
            if not nome.endswith(".py"):
                continue
            caminho = Path(raiz) / nome
            texto = caminho.read_text(encoding="utf-8")
            achados = sum(texto.count(m) for m in MARCAS_MOJIBAKE)
            if achados:
                problemas.append(f"{caminho.relative_to(API_ROOT)}: {achados}")
    assert not problemas, "mojibake reintroduzido em:\n  " + "\n  ".join(problemas)


# ─── Snowflakes ──────────────────────────────────────────────────────────────

def test_ids_grandes_saem_como_string_no_json():
    """IDs do Discord passam de 2^53. Se sairem como numero, o JavaScript
    arredonda e o ID gravado deixa de casar com o real — foi assim que a
    whitelist de seguranca parou de reconhecer usuarios."""
    from app.responses import json_safe_data
    grande = 807317692318089246
    saida = json_safe_data({"discord_id": grande, "pequeno": 42})
    assert saida["discord_id"] == str(grande)
    assert saida["pequeno"] == 42


def test_endpoint_players_nao_devolve_id_como_numero(client, auth):
    dados = client.get(f"/bots/{APP_ID}/players", headers=auth).json()["data"]
    for p in dados:
        valor = p["discord_id"]
        assert isinstance(valor, str), f"discord_id saiu como {type(valor).__name__}"
        assert int(valor) > LIMITE_JS


def test_detector_de_id_arredondado(db_do_bot):
    """Ferramenta de diagnostico: encontra IDs que perderam digitos.

    Um snowflake que passou por JSON como numero volta arredondado. Compara-se
    o que o bot gravou direto (audit_log) com o que veio pelo painel (players).
    """
    con = sqlite3.connect(db_do_bot)
    con.execute(
        "INSERT INTO players (playerName, playerLogin, playerID, discordUserID)"
        " VALUES (?,?,?,?)", ("corrompido", "c", 999, 807317692318089200))
    con.execute(
        "INSERT INTO audit_log (event_type, system_key, action_key, actor_discord_id, status)"
        " VALUES (?,?,?,?,?)", ("t", "s", "a", 807317692318089246, "success"))
    con.commit()

    reais = {r[0] for r in con.execute(
        "SELECT DISTINCT actor_discord_id FROM audit_log WHERE actor_discord_id IS NOT NULL")}
    suspeitos = []
    for (pid,) in con.execute("SELECT discordUserID FROM players WHERE discordUserID IS NOT NULL"):
        if pid <= LIMITE_JS:
            continue
        proximos = [r for r in reais if r != pid and abs(r - pid) < 10_000]
        if proximos:
            suspeitos.append((pid, proximos))
    con.close()

    assert suspeitos, "o detector deixou de encontrar o ID arredondado plantado"
    corrompido, [real] = suspeitos[0]
    assert corrompido == 807317692318089200 and real == 807317692318089246


# ─── Corrida de escrita (defeito arquitetural conhecido) ─────────────────────

@pytest.mark.xfail(
    reason="DEFEITO ARQUITETURAL CONHECIDO (CRITICO-3): a API baixa o .db inteiro, "
           "edita e sobrescreve. Escritas que o bot fizer nessa janela sao apagadas. "
           "So some com banco transacional — nao ha correcao pontual.",
    strict=True,
)
async def test_escrita_da_api_nao_pode_apagar_escrita_do_bot(nuvem, db_do_bot):
    from app.services import sqlite_engine as se

    leitura_original = nuvem.read_file
    escrita_original = nuvem.update_file_content

    async def leitura_lenta(app_id, path):
        await asyncio.sleep(0.4)          # latencia de download
        return await leitura_original(app_id, path)

    async def escrita_lenta(app_id, path, content):
        await asyncio.sleep(0.4)          # latencia de upload
        return await escrita_original(app_id, path, content)

    nuvem.read_file = leitura_lenta
    nuvem.update_file_content = escrita_lenta

    def grava_como_o_bot(i):
        con = sqlite3.connect(db_do_bot, timeout=15)
        con.execute("PRAGMA journal_mode=DELETE")
        con.execute(
            "INSERT INTO audit_log (event_type, system_key, action_key, status, message)"
            " VALUES (?,?,?,?,?)", ("registro", "bot", "ESCRITA_DO_BOT", "success", f"#{i}"))
        con.commit()
        con.close()

    tarefa = asyncio.create_task(se.sqlite_service.execute_update(
        APP_ID,
        "INSERT INTO audit_log (event_type, system_key, action_key, status) VALUES (?,?,?,?)",
        ("painel", "admin", "ESCRITA_DA_API", "success")))

    await asyncio.sleep(0.5)
    for i in range(5):
        grava_como_o_bot(i)
        await asyncio.sleep(0.05)
    await tarefa

    con = sqlite3.connect(db_do_bot)
    sobreviveram = con.execute(
        "SELECT COUNT(*) FROM audit_log WHERE action_key='ESCRITA_DO_BOT'").fetchone()[0]
    con.close()

    assert sobreviveram == 5, f"a API apagou {5 - sobreviveram} de 5 escritas do bot"
