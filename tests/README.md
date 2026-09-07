# Suite de testes da API

## Rodar

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Não precisa de credencial, de rede nem do banco de produção. A Square Cloud é
substituída por `FakeSquareCloud` (em `conftest.py`), que lê e escreve um
diretório temporário; os bancos de teste são construídos do zero a cada teste a
partir do DDL real do bot, guardado em `fixtures/schema_*.sql`.

## Atualizar o schema quando o bot mudar

```bash
python tests/fixtures/gerar_fixtures.py ../APP/data
```

Isso reextrai o DDL para os `.sql`. Nenhum dado real é copiado — as linhas de
teste são sintéticas e ficam em `conftest.py`.

## O que cada arquivo cobre

| Arquivo | Cobre |
|---|---|
| `test_auth.py` | escopos, token inválido, master key desligável, e as regressões de segurança já corrigidas (chave embutida no código, brute-force por `X-Forwarded-For`, comparação não constante) |
| `test_leitura.py` | os 16 endpoints de leitura, o contrato do `/players`, 404 para app inexistente, e a garantia de que o cache de snapshot não seja removido |
| `test_audit.py` | caminho feliz e a **assinatura de cada modo de falha** do `/audit` — use como tabela de diagnóstico ao ler um 500 de produção |
| `test_integridade.py` | mojibake nos fontes, IDs grandes serializados como string, detector de snowflake arredondado |

## Testes marcados `xfail`

Dois testes descrevem o comportamento **correto** de defeitos ainda não
corrigidos. Eles falham hoje, de propósito, e estão marcados `strict=True`:
quando o defeito for corrigido, o teste passa e o `strict` acusa — aí é só
remover a marcação.

- `test_escrita_da_api_nao_pode_apagar_escrita_do_bot` — a API baixa o `.db`
  inteiro, edita e sobrescreve; escritas que o bot fizer nessa janela são
  apagadas. Só some com banco transacional.
- `test_seguranca_sem_guild_id_deveria_dar_erro_de_configuracao` — bot sem
  `guild_id` configurado devolve 500 em vez de dizer que não está configurado.
