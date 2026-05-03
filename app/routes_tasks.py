from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Any, Optional

from app.auth import require_scope
from app.responses import ok
from app.task_store import (
    ack_task,
    create_task,
    list_bots,
    list_tasks,
    poll_tasks,
    register_bot,
    revoke_bot,
    validate_bot,
)

router = APIRouter(tags=["Tasks"])
_bot_security = HTTPBearer()


def _client_ip(request: Request) -> str:
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


def _require_bot(bot_id: str, request: Request, auth: HTTPAuthorizationCredentials) -> None:
    if not validate_bot(bot_id=bot_id, token=auth.credentials, ip=_client_ip(request)):
        raise HTTPException(status_code=401, detail="Bot token invalido para este bot_id")


@router.post("/bots/register")
async def create_bot_identity(request: Request, _=Depends(require_scope("bots:manage"))):
    body = await request.json() if await request.body() else {}
    bot_id = str(body.get("bot_id", "")).strip().lower()
    label = str(body.get("label", "")).strip()
    if not bot_id:
        raise HTTPException(status_code=400, detail="Campo 'bot_id' obrigatorio")
    data = register_bot(bot_id=bot_id, label=label)
    res, status = ok(data, "Bot registrado. Guarde o token em local seguro.", 201)
    return res


@router.get("/bots")
async def get_bots(_=Depends(require_scope("bots:manage"))):
    res, status = ok(list_bots())
    return res


@router.delete("/bots/{bot_id}")
async def delete_bot(bot_id: str, _=Depends(require_scope("bots:manage"))):
    n = revoke_bot(bot_id=bot_id.strip().lower())
    if n == 0:
        raise HTTPException(status_code=404, detail="Bot nao encontrado")
    res, status = ok({"bot_id": bot_id, "revoked": n}, "Bot revogado")
    return res


@router.post("/tasks")
async def enqueue_task(request: Request, info=Depends(require_scope("tasks:write"))):
    body = await request.json() if await request.body() else {}
    bot_id = str(body.get("bot_id", "")).strip().lower()
    task_type = str(body.get("task_type", "")).strip()
    payload = body.get("payload", {})
    if not bot_id or not task_type:
        raise HTTPException(status_code=400, detail="Campos obrigatorios: bot_id, task_type")

    data = create_task(
        bot_id=bot_id,
        task_type=task_type,
        payload=payload,
        created_by=str(info.get("label", "api")),
        priority=int(body.get("priority", 100)),
        max_attempts=int(body.get("max_attempts", 3)),
        available_in_secs=int(body.get("available_in_secs", 0)),
        idempotency_key=(str(body.get("idempotency_key", "")).strip() or None),
    )
    res, status = ok(data, "Task criada", 201)
    return res


@router.get("/tasks")
async def admin_list_tasks(
    bot_id: Optional[str] = None,
    status: Optional[str] = Query(None, pattern="^(pending|in_progress|done|failed|cancelled|retry)?$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_scope("tasks:read")),
):
    data = list_tasks(bot_id=bot_id, status=status, limit=limit, offset=offset)
    res, status_code = ok(data)
    return res


@router.get("/tasks/{bot_id}")
async def bot_poll_tasks(
    bot_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    auth: HTTPAuthorizationCredentials = Security(_bot_security),
):
    bot_id = bot_id.strip().lower()
    _require_bot(bot_id, request, auth)
    tasks = poll_tasks(bot_id=bot_id, limit=limit)
    res, status = ok({"bot_id": bot_id, "count": len(tasks), "tasks": tasks})
    return res


@router.post("/tasks/{bot_id}/ack/{task_id}")
async def bot_ack_task(
    bot_id: str,
    task_id: int,
    request: Request,
    auth: HTTPAuthorizationCredentials = Security(_bot_security),
):
    bot_id = bot_id.strip().lower()
    _require_bot(bot_id, request, auth)

    body = await request.json() if await request.body() else {}
    status = str(body.get("status", "")).strip().lower()
    if status not in {"done", "failed", "retry"}:
        raise HTTPException(status_code=400, detail="status deve ser done, failed ou retry")

    ok_ack = ack_task(
        bot_id=bot_id,
        task_id=task_id,
        status=status,
        result=body.get("result"),
        error=body.get("error"),
        retry_in_secs=int(body.get("retry_in_secs", 30)),
    )
    if not ok_ack:
        raise HTTPException(status_code=404, detail="Task nao encontrada ou estado invalido")

    res, status_code = ok({"task_id": task_id, "status": status}, "Task atualizada")
    return res
