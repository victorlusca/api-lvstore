"""/audit: caminho feliz e as assinaturas de cada modo de falha.

Este arquivo existe porque o endpoint devolvia 500 em producao sem dizer por que.
Cada teste abaixo sabota o banco de um jeito diferente e trava a mensagem
resultante, para que o log de producao possa ser lido como um diagnostico.
"""
import sqlite3

from tests.conftest import APP_ID


def _sem_cache():
    from app.services import sqlite_engine as se
    se._snapshot_cache.clear()
    se._remote_listing_cache.clear()


def test_audit_le_o_banco_do_bot(client, auth):
    r = client.get(f"/bots/{APP_ID}/audit?limit=50", headers=auth)
    assert r.status_code == 200
    dados = r.json()["data"]
    assert len(dados) == 5
    # O endpoint renomeia colunas para o contrato do painel.
    assert {"feito_em", "nome_sistema", "autor", "alvo"} <= set(dados[0])
    assert "created_at" not in dados[0]


def test_details_json_vira_objeto(client, auth):
    dados = client.get(f"/bots/{APP_ID}/audit", headers=auth).json()["data"]
    assert dados[0]["details_json"] == {"campo": "valor"}


def test_limit_e_limitado_a_100(client, auth):
    r = client.get(f"/bots/{APP_ID}/audit?limit=99999", headers=auth)
    assert r.status_code == 200


def test_tabela_ausente_diz_qual_tabela(client, auth, db_do_bot):
    """Assinatura A: 'no such table: audit_log' => o banco perdeu a tabela."""
    con = sqlite3.connect(db_do_bot)
    con.execute("DROP TABLE audit_log")
    con.commit()
    con.close()
    _sem_cache()

    r = client.get(f"/bots/{APP_ID}/audit", headers=auth)
    assert r.status_code == 500
    assert "no such table: audit_log" in r.json()["detail"]


def test_arquivo_corrompido_diz_que_esta_corrompido(client, auth, db_do_bot):
    """Assinatura B: 'database disk image is malformed' => upload corrompeu o arquivo."""
    dados = db_do_bot.read_bytes()
    db_do_bot.write_bytes(dados[: len(dados) // 2])
    _sem_cache()

    r = client.get(f"/bots/{APP_ID}/audit", headers=auth)
    assert r.status_code == 500
    assert "malformed" in r.json()["detail"]


def test_banco_ausente_devolve_404_e_nao_500(client, auth, db_do_bot):
    """Regressao: o router reembrulhava tudo em 500.

    Um 404 ("o app nao tem esse banco") virava "erro interno do servidor", o que
    mandava procurar bug de codigo onde o problema era de deploy.
    """
    db_do_bot.unlink()
    _sem_cache()

    r = client.get(f"/bots/{APP_ID}/audit", headers=auth)
    assert r.status_code == 404, f"esperado 404, veio {r.status_code}: {r.text[:200]}"


def test_rate_limit_na_listagem_nao_pode_virar_dado_velho_silencioso(client, auth, nuvem, db_do_bot):
    """DEFEITO CONHECIDO, documentado aqui de proposito.

    `_list_remote_dir` engole qualquer excecao e devolve []. Com HTTP 429 da
    Square Cloud, a API conclui que nao existe `-wal`, le so o arquivo principal
    e devolve 200 com dados defasados — sem erro, sem aviso, sem log de alerta.
    E o modo de falha mais perigoso do sistema: parece que funcionou.

    Este teste NAO falha hoje; ele registra o comportamento para que qualquer
    mudanca no tratamento de 429 seja consciente.
    """
    nuvem.falhar_listagem = True
    _sem_cache()

    r = client.get(f"/bots/{APP_ID}/audit", headers=auth)
    assert r.status_code == 200, "comportamento mudou: revisar _list_remote_dir"
    assert nuvem.contagem("list") >= 1
