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

## Publicacao (dominio)

Objetivo final:

- Host: `api.lvstore.site`
- Base API: `https://api.lvstore.site/v3/`

Exemplo com `uvicorn`:

```bash
uvicorn app.app:app --host 0.0.0.0 --port 8000
```
