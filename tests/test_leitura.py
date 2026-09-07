"""Endpoints de leitura: respondem, e respondem lendo o banco do bot."""
import pytest

from tests.conftest import APP_ID

ROTAS = [
    "/players",
    "/ranking/points",
    "/ranking/total",
    "/ranking/active",
    "/ranking/inactive",
    "/ranking/supervisors",
    "/management/hierarchy",
    "/management/warnings",
    "/management/absences",
    "/management/routes/daily",
    "/management/routes/total",
    "/management/supervisors/ranking",
    "/edital/normal",
    "/edital/superior",
    "/audit",
    "/security/configs",
]


@pytest.mark.parametrize("rota", ROTAS)
def test_endpoint_responde_200(client, auth, rota):
    r = client.get(f"/bots/{APP_ID}{rota}", headers=auth)
    assert r.status_code == 200, f"{rota} -> {r.status_code}: {r.text[:200]}"


def test_health_nao_exige_token(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "online"


def test_players_traz_os_dados_do_banco_do_bot(client, auth):
    r = client.get(f"/bots/{APP_ID}/players", headers=auth)
    dados = r.json()["data"]
    nomes = {p["nome"] for p in dados}
    assert nomes == {"jogador_um", "jogador_dois"}


def test_app_inexistente_devolve_404_e_nao_500(client, auth):
    r = client.get("/bots/app_que_nao_existe/players", headers=auth)
    assert r.status_code == 404, f"esperado 404, veio {r.status_code}: {r.text[:200]}"


def test_cache_evita_baixar_o_banco_a_cada_consulta(client, auth, nuvem):
    """O cache de snapshot existe para o painel nao derrubar a API.

    Sem ele, cada consulta baixava o .db inteiro de novo — o que causava
    httpx.ReadTimeout em serie e HTTP 500 nas abas. Este teste trava esse
    comportamento: N consultas nao podem virar N downloads.
    """
    for rota in ROTAS:
        client.get(f"/bots/{APP_ID}{rota}", headers=auth)
    downloads = nuvem.contagem("read")
    assert downloads < len(ROTAS), (
        f"{len(ROTAS)} consultas geraram {downloads} downloads — o cache foi desativado"
    )


@pytest.mark.xfail(
    reason="DEFEITO CONHECIDO: bot sem guild_id configurado devolve 500 em vez de "
           "um erro de configuracao. Quebra a aba de seguranca para todo bot recem-criado.",
    strict=True,
)
def test_seguranca_sem_guild_id_deveria_dar_erro_de_configuracao(client, auth, nuvem):
    """Um bot ainda nao instalado nao e um erro interno do servidor.

    `_get_guild_id` levanta RuntimeError quando `configuracoes_servidor` esta
    vazia, e o router converte isso em HTTP 500. O correto seria um status que
    diga ao painel "este bot ainda nao foi configurado" (409 ou 424), com
    mensagem propria — 500 faz o painel mostrar falha generica e manda o time
    procurar bug onde nao ha.
    """
    import sqlite3
    ref = nuvem.raiz / APP_ID / "data" / "reference_data.db"
    con = sqlite3.connect(ref)
    con.execute("DELETE FROM configuracoes_servidor")
    con.commit()
    con.close()

    from app.services import sqlite_engine as se
    se._snapshot_cache.clear()

    r = client.get(f"/bots/{APP_ID}/security/configs", headers=auth)
    assert r.status_code != 500, f"veio 500: {r.text[:200]}"
