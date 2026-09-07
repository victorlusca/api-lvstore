"""Autenticacao e protecao de escopo."""
import importlib

import pytest

from tests.conftest import APP_ID, MASTER_KEY

ROTA = f"/bots/{APP_ID}/players"


def test_sem_token_recusa(client):
    assert client.get(ROTA).status_code in (401, 403)


def test_token_invalido_recusa(client):
    r = client.get(ROTA, headers={"Authorization": "Bearer token-que-nao-existe"})
    assert r.status_code == 401


def test_master_key_concede_acesso(client, auth):
    assert client.get(ROTA, headers=auth).status_code == 200


def test_master_key_vazia_desliga_o_acesso_mestre(client, monkeypatch):
    """Regressao: API_KEY sem valor nao pode virar 'aceita qualquer coisa'.

    Antes existia um default fixo no config.py, versionado no repositorio: quem
    lesse o codigo tinha admin:* na producao. Removido o default, uma API_KEY
    vazia precisa DESLIGAR a master key, nunca liberar acesso.
    """
    from app.core import config
    monkeypatch.setattr(config.settings, "API_KEY", "")
    for tentativa in ("", "qualquer-coisa", MASTER_KEY):
        r = client.get(ROTA, headers={"Authorization": f"Bearer {tentativa}"})
        assert r.status_code in (401, 403), f"token {tentativa!r} passou com API_KEY vazia"


def test_config_nao_tem_chave_embutida():
    """Regressao: nenhuma chave literal pode voltar para o codigo-fonte."""
    from pathlib import Path
    fonte = (Path(__file__).parent.parent / "app" / "core" / "config.py").read_text(encoding="utf-8")
    import re
    linha = [l for l in fonte.splitlines() if "API_KEY" in l and "Field(" in l]
    assert linha, "campo API_KEY sumiu do config.py"
    assert re.search(r'Field\(\s*""', linha[0]), f"API_KEY voltou a ter default embutido: {linha[0].strip()}"


def test_brute_force_nao_usa_header_do_cliente():
    """Regressao: o contador nao pode ser chaveado por X-Forwarded-For.

    Esse header e escrito pelo cliente; chavear por ele permitia zerar o
    bloqueio a cada tentativa, bastando variar o valor.
    """
    from pathlib import Path
    fonte = (Path(__file__).parent.parent / "app" / "auth.py").read_text(encoding="utf-8")
    inicio = fonte.index("def _get_ip")
    corpo = fonte[inicio:fonte.index("def _check_bf")]
    assert "X-Forwarded-For" not in corpo.split('"""')[-1], \
        "_get_ip voltou a confiar em X-Forwarded-For"


def test_comparacao_de_token_e_constante():
    """Regressao: '==' vaza o prefixo correto por tempo de resposta."""
    from pathlib import Path
    fonte = (Path(__file__).parent.parent / "app" / "auth.py").read_text(encoding="utf-8")
    assert "secrets.compare_digest" in fonte, "comparacao da master key voltou a usar =="
