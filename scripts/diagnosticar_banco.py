#!/usr/bin/env python3
"""Diagnostico somente-leitura de um banco do bot.

Existe para responder, sem adivinhacao, a pergunta que hoje custa horas:
"por que o /audit devolveu 500 em producao?". Baixe o `master_data.db` do app
pelo painel da Square Cloud e rode:

    python scripts/diagnosticar_banco.py caminho/para/master_data.db

Nao escreve nada, nao conecta em lugar nenhum, nao precisa de credencial.
O reparo de IDs arredondados NAO e feito aqui: quem repara e o bot, em
`APP/commands/instalacao.py::repair_rounded_snowflakes`, que roda no on_ready e
tem acesso aos IDs reais do Discord. Este script apenas aponta o problema.
"""
from __future__ import annotations

import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

JS_MAX_SAFE_INTEGER = 9007199254740991
TABELAS_DE_HISTORICO = {"audit_log", "api_audit_log", "admin_audit_log", "logs"}

OK, ALERTA, ERRO = "  [ok]   ", "  [!]    ", "  [ERRO] "


def _js_rounded_id(real_id: int) -> int:
    """Mesma regra de `instalacao.py::_js_rounded_id`: String(Number(x)) do JS."""
    return int(Decimal(repr(float(real_id))))


def _colunas_de_id(con, tabela: str) -> list[str]:
    return [c[1] for c in con.execute(f'PRAGMA table_info("{tabela}")') if "id" in c[1].lower()]


def diagnosticar(caminho: Path) -> int:
    if not caminho.is_file():
        print(f"{ERRO}arquivo nao encontrado: {caminho}")
        return 2

    print(f"\nBanco: {caminho}  ({caminho.stat().st_size / 1024:.0f} KB)")
    for sufixo in ("-wal", "-shm"):
        vizinho = caminho.with_name(caminho.name + sufixo)
        if vizinho.exists():
            print(f"{ALERTA}existe {vizinho.name} ({vizinho.stat().st_size} bytes). "
                  "A API so recupera os commits do journal se baixar este arquivo junto.")

    problemas = 0
    try:
        con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    except sqlite3.Error as e:
        print(f"{ERRO}nao foi possivel abrir: {e}")
        return 2

    # ── 1. Integridade ───────────────────────────────────────────────────────
    print("\n1. Integridade")
    try:
        resultado = [r[0] for r in con.execute("PRAGMA integrity_check")]
        if resultado == ["ok"]:
            print(f"{OK}integrity_check: ok")
        else:
            problemas += 1
            print(f"{ERRO}integrity_check falhou:")
            for linha in resultado[:10]:
                print(f"           {linha}")
            print("           => causa provavel do 'database disk image is malformed'.")
    except sqlite3.DatabaseError as e:
        problemas += 1
        print(f"{ERRO}{e}  => arquivo corrompido ou truncado (upload interrompido?)")
        return 1

    modo = con.execute("PRAGMA journal_mode").fetchone()[0]
    if modo.lower() == "wal":
        problemas += 1
        print(f"{ALERTA}journal_mode = wal. O bot deve usar DELETE: em WAL, commits ficam "
              "no arquivo -wal e a API pode servir dados defasados sem erro nenhum.")
    else:
        print(f"{OK}journal_mode: {modo}")

    # ── 2. Tabelas que o painel consulta ─────────────────────────────────────
    print("\n2. Tabelas exigidas pelo painel")
    existentes = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for tabela in ("players", "audit_log", "player_points", "player_total_hours",
                   "security_limits", "security_whitelist_global_users"):
        if tabela in existentes:
            n = con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
            print(f"{OK}{tabela}: {n} linhas")
        else:
            problemas += 1
            print(f"{ERRO}{tabela}: AUSENTE  => causa do 'no such table: {tabela}'")

    # ── 3. IDs do Discord arredondados ───────────────────────────────────────
    print("\n3. IDs do Discord com perda de precisao")
    reais: set[int] = set()
    for tabela in TABELAS_DE_HISTORICO & existentes:
        for coluna in _colunas_de_id(con, tabela):
            try:
                reais.update(
                    r[0] for r in con.execute(
                        f'SELECT DISTINCT "{coluna}" FROM "{tabela}" '
                        f'WHERE typeof("{coluna}")=\'integer\' AND "{coluna}" > ?',
                        (JS_MAX_SAFE_INTEGER,)))
            except sqlite3.Error:
                continue

    arredondados = {_js_rounded_id(r): r for r in reais if _js_rounded_id(r) != r}
    suspeitos = []
    for tabela in sorted(existentes - TABELAS_DE_HISTORICO):
        if tabela.startswith("sqlite_"):
            continue
        for coluna in _colunas_de_id(con, tabela):
            try:
                valores = [r[0] for r in con.execute(
                    f'SELECT DISTINCT "{coluna}" FROM "{tabela}" '
                    f'WHERE typeof("{coluna}")=\'integer\' AND "{coluna}" > ?',
                    (JS_MAX_SAFE_INTEGER,))]
            except sqlite3.Error:
                continue
            for v in valores:
                if v in arredondados:
                    suspeitos.append((tabela, coluna, v, arredondados[v]))

    if not suspeitos:
        print(f"{OK}nenhum ID arredondado detectavel "
              f"({len(reais)} IDs de referencia vindos das tabelas de historico)")
    else:
        problemas += 1
        print(f"{ERRO}{len(suspeitos)} valor(es) arredondado(s):")
        for tabela, coluna, ruim, real in suspeitos:
            print(f"           {tabela}.{coluna}: {ruim}  deveria ser  {real}")
        print("           => joins e whitelist deixam de casar com o ID real.")
        print("           => reinicie o bot: repair_rounded_snowflakes() corrige no on_ready,")
        print("              desde que o usuario esteja visivel em algum servidor do bot.")

    con.close()
    print(f"\n{'Nenhum problema encontrado.' if not problemas else f'{problemas} problema(s) encontrado(s).'}\n")
    return 1 if problemas else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(max(diagnosticar(Path(a)) for a in sys.argv[1:]))
