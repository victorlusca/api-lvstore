# API LV Store (Standalone)

API unica em FastAPI para publicar em `api.lvstore.site` com base path `\/v3`.

## Executar local

```bash
cd api.lvstore.site
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Health:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/v3/health`

## Variaveis principais

- `API_BASE_PATH=/v3`
- `API_DATA_DIR=` caminho do diretorio `data` (se vazio, tenta `../data`)
- `API_CORS_ORIGINS=https://lvstore.site,https://www.lvstore.site`
- `SQUARECLOUD_APP_ID=` id do app na SquareCloud (ex.: `cf3d02a3525c470590d00df4be4e539d`)
- `SQUARECLOUD_API_TOKEN=` token da API da SquareCloud

### Arquivos via SquareCloud (definitivo)

- A API suporta multiplos bots/apps via `app_id` nas rotas `/v3/squarecloud/files*`.
- Se `app_id` nao for enviado, usa `SQUARECLOUD_APP_ID` como fallback.
- Fluxo de arquivos remotos usa somente SquareCloud (sem gravar `api_token.txt` local).

## Publicacao (dominio)

Objetivo final:

- Host: `api.lvstore.site`
- Base API: `https://api.lvstore.site/v3/`

Exemplo com `uvicorn`:

```bash
uvicorn app.app:app --host 0.0.0.0 --port 8000
```

## Task System (bots)

Fluxo recomendado:

- site/painel cria task: `POST /v3/tasks` (token API com escopo `tasks:write`)
- bot faz polling: `GET /v3/tasks/{bot_id}` (token do bot)
- bot confirma resultado: `POST /v3/tasks/{bot_id}/ack/{task_id}` (token do bot)

Criar identidade de bot:

- `POST /v3/bots/register` com body `{ "bot_id": "azp", "label": "Bot AZP" }`
- resposta retorna o token do bot (mostrar uma vez)

## Checagem de autonomia

Antes de publicar, rode:

```bash
python scripts/check_standalone_imports.py
```

Esse script falha se algum arquivo em `app/` importar modulos externos do bot (ex.: `utils.*`, `commands.*`, `api.*`).
