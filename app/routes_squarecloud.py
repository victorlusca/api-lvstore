"""
Integra arquivo remoto da SquareCloud para listar, ler, salvar e remover arquivos.
"""
import json
import os
from typing import Any, Dict, Optional
from urllib import error, parse, request

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.auth import require_scope
from app.responses import ok

router = APIRouter(tags=["SquareCloud"])


def _squarecloud_config() -> tuple[str, str]:
    app_id = os.environ.get("SQUARECLOUD_APP_ID", "").strip()
    token = os.environ.get("SQUARECLOUD_API_TOKEN", "").strip()
    if not app_id:
        raise HTTPException(status_code=500, detail="Variavel SQUARECLOUD_APP_ID nao configurada")
    if not token:
        raise HTTPException(status_code=500, detail="Variavel SQUARECLOUD_API_TOKEN nao configurada")
    return app_id, token


def _request_squarecloud(
    method: str,
    *,
    path: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    app_id, token = _squarecloud_config()
    base_url = f"https://api.squarecloud.app/v2/apps/{app_id}/files"
    if path:
        qs = parse.urlencode({"path": path})
        base_url = f"{base_url}?{qs}"

    body = None
    headers = {
        "Authorization": token,
        "Accept": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(base_url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8") if resp else ""
            return json.loads(raw) if raw else {"status": "success"}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        detail: Any = raw or f"SquareCloud HTTP {exc.code}"
        try:
            parsed = json.loads(raw)
            detail = parsed.get("response") or parsed
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=detail) from exc
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao conectar com SquareCloud: {exc.reason}") from exc


@router.get("/squarecloud/files")
async def list_squarecloud_files(
    path: str = Query("/", description="Caminho remoto para listar, ex: / ou data"),
    _=Depends(require_scope("references:read")),
):
    data = _request_squarecloud("GET", path=path)
    res, _status = ok(data)
    return res


@router.get("/squarecloud/files/read")
async def read_squarecloud_file(
    path: str = Query(..., description="Arquivo remoto para leitura, ex: data/config.json"),
    _=Depends(require_scope("references:read")),
):
    data = _request_squarecloud("GET", path=path)
    res, _status = ok(data)
    return res


@router.put("/squarecloud/files")
async def upsert_squarecloud_file(
    body: Dict[str, Any] = Body(..., description='{"path":"data/file.txt","content":"..."}'),
    _=Depends(require_scope("references:write")),
):
    remote_path = str(body.get("path", "")).strip()
    content = body.get("content")
    if not remote_path:
        raise HTTPException(status_code=400, detail="Campo 'path' e obrigatorio")
    if content is None:
        raise HTTPException(status_code=400, detail="Campo 'content' e obrigatorio")

    data = _request_squarecloud("PUT", payload={"path": remote_path, "content": str(content)})
    res, _status = ok(data, "Arquivo remoto salvo")
    return res


@router.delete("/squarecloud/files")
async def delete_squarecloud_file(
    path: str = Query(..., description="Arquivo remoto para remover"),
    _=Depends(require_scope("references:write")),
):
    data = _request_squarecloud("DELETE", path=path)
    res, _status = ok(data, "Arquivo remoto removido")
    return res
