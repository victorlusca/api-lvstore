"""
routers/security.py – Segurança do bot (configuração, whitelist, infrações).
"""
import logging
import traceback
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from pydantic import BaseModel

from app.auth import require_scope
from app.responses import ok
from app.security.security_guard import (
    list_action_configs,
    list_system_states,
    upsert_action_config,
    set_system_state,
    list_recent_infractions,
    VALID_PUNISHMENTS,
    _to_system_name,
)
from app.security.security_whitelist import (
    list_global_users,
    list_global_roles,
    list_action_users,
    list_action_roles,
    add_user,
    remove_user,
    add_role,
    remove_role,
    add_global_user,
    remove_global_user,
    add_global_role,
    remove_global_role,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bots", tags=["Security"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    action_key: Optional[str] = None
    system_name: Optional[str] = None
    infraction_limit: int
    punishment_type: str
    is_enabled: int = 1

class SystemUpdate(BaseModel):
    system_name: str
    enabled: int

class WhitelistUpdate(BaseModel):
    action_key: Optional[str] = None
    user_id: Optional[int] = None
    role_id: Optional[int] = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _http_500(e: Exception, context: str) -> HTTPException:
    """Loga a traceback completa e retorna HTTPException 500 com detalhe legível."""
    detail = str(e)
    logger.error(f"[SecurityRouter] {context}: {detail}\n{traceback.format_exc()}")
    return HTTPException(status_code=500, detail=f"{context}: {detail}")


# ─── Configs (limites + punição + enabled) ───────────────────────────────────

@router.get("/{app_id}/security/configs")
async def get_security_configs(
    app_id: str,
    _ = Depends(require_scope("references:read"))
):
    try:
        data = await list_action_configs(app_id)
        res, status = ok(data)
        return res
    except Exception as e:
        raise _http_500(e, "get_security_configs")

@router.post("/{app_id}/security/configs")
async def update_security_config(
    app_id: str,
    config: ConfigUpdate,
    _ = Depends(require_scope("references:write"))
):
    try:
        key = config.action_key or config.system_name
        if not key:
            raise HTTPException(status_code=400, detail="É necessário fornecer 'action_key' ou 'system_name'")

        sys_name = _to_system_name(key)
        if not sys_name:
            raise HTTPException(
                status_code=400,
                detail=f"Chave de ação/sistema inválida: '{key}'. Use valores como 'anti_ban', 'anti_kick', etc."
            )

        if config.punishment_type.strip().lower() not in VALID_PUNISHMENTS:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de punição inválido: '{config.punishment_type}'. Opções válidas: {sorted(VALID_PUNISHMENTS)}"
            )

        await upsert_action_config(
            app_id,
            action_key=key,
            infraction_limit=config.infraction_limit,
            punishment_type=config.punishment_type,
            is_enabled=config.is_enabled,
        )
        res, status = ok({"message": "Configuração atualizada com sucesso"})
        return res

    except HTTPException:
        raise
    except Exception as e:
        raise _http_500(e, f"update_security_config(key={config.action_key or config.system_name!r})")


# ─── Systems (ligado/desligado) ───────────────────────────────────────────────

@router.get("/{app_id}/security/systems")
async def get_security_systems(
    app_id: str,
    _ = Depends(require_scope("references:read"))
):
    try:
        data = await list_system_states(app_id)
        res, status = ok(data)
        return res
    except Exception as e:
        raise _http_500(e, "get_security_systems")

@router.post("/{app_id}/security/systems")
async def update_security_system(
    app_id: str,
    system: SystemUpdate,
    _ = Depends(require_scope("references:write"))
):
    try:
        sys_name = _to_system_name(system.system_name)
        if not sys_name:
            raise HTTPException(
                status_code=400,
                detail=f"Sistema inválido: '{system.system_name}'"
            )
        await set_system_state(app_id, sys_name, system.enabled)
        res, status = ok({"message": "Sistema atualizado com sucesso"})
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise _http_500(e, f"update_security_system(system={system.system_name!r})")


# ─── Whitelist Global ─────────────────────────────────────────────────────────

@router.get("/{app_id}/security/whitelist/global/users")
async def get_global_whitelist_users(app_id: str, _ = Depends(require_scope("references:read"))):
    try:
        res, status = ok(await list_global_users(app_id))
        return res
    except Exception as e:
        raise _http_500(e, "get_global_whitelist_users")

@router.post("/{app_id}/security/whitelist/global/users")
async def add_global_whitelist_user_endpoint(app_id: str, data: WhitelistUpdate, _ = Depends(require_scope("references:write"))):
    try:
        if not data.user_id:
            raise HTTPException(status_code=400, detail="user_id é obrigatório")
        await add_global_user(app_id, data.user_id)
        res, status = ok({"message": "Usuário adicionado à whitelist global"})
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise _http_500(e, "add_global_whitelist_user")

@router.get("/{app_id}/security/whitelist/global/roles")
async def get_global_whitelist_roles(app_id: str, _ = Depends(require_scope("references:read"))):
    try:
        res, status = ok(await list_global_roles(app_id))
        return res
    except Exception as e:
        raise _http_500(e, "get_global_whitelist_roles")

@router.post("/{app_id}/security/whitelist/global/roles")
async def add_global_whitelist_role_endpoint(app_id: str, data: WhitelistUpdate, _ = Depends(require_scope("references:write"))):
    try:
        if not data.role_id:
            raise HTTPException(status_code=400, detail="role_id é obrigatório")
        await add_global_role(app_id, data.role_id)
        res, status = ok({"message": "Cargo adicionado à whitelist global"})
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise _http_500(e, "add_global_whitelist_role")

@router.delete("/{app_id}/security/whitelist/global/users")
async def del_global_whitelist_user_endpoint(app_id: str, user_id: int, _ = Depends(require_scope("references:write"))):
    try:
        await remove_global_user(app_id, user_id)
        res, status = ok({"message": "Usuário removido da whitelist global"})
        return res
    except Exception as e:
        raise _http_500(e, "del_global_whitelist_user")

@router.delete("/{app_id}/security/whitelist/global/roles")
async def del_global_whitelist_role_endpoint(app_id: str, role_id: int, _ = Depends(require_scope("references:write"))):
    try:
        await remove_global_role(app_id, role_id)
        res, status = ok({"message": "Cargo removido da whitelist global"})
        return res
    except Exception as e:
        raise _http_500(e, "del_global_whitelist_role")


# ─── Whitelist por Ação ───────────────────────────────────────────────────────

@router.get("/{app_id}/security/whitelist/users")
async def get_action_whitelist_users(app_id: str, action_key: str, _ = Depends(require_scope("references:read"))):
    try:
        res, status = ok(await list_action_users(app_id, action_key))
        return res
    except Exception as e:
        raise _http_500(e, "get_action_whitelist_users")

@router.post("/{app_id}/security/whitelist/users")
async def add_action_whitelist_user_endpoint(app_id: str, data: WhitelistUpdate, _ = Depends(require_scope("references:write"))):
    try:
        if not data.action_key or not data.user_id:
            raise HTTPException(status_code=400, detail="action_key e user_id são obrigatórios")
        await add_user(app_id, data.action_key, data.user_id)
        res, status = ok({"message": "Usuário adicionado à whitelist"})
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise _http_500(e, "add_action_whitelist_user")

@router.get("/{app_id}/security/whitelist/roles")
async def get_action_whitelist_roles(app_id: str, action_key: str, _ = Depends(require_scope("references:read"))):
    try:
        res, status = ok(await list_action_roles(app_id, action_key))
        return res
    except Exception as e:
        raise _http_500(e, "get_action_whitelist_roles")

@router.post("/{app_id}/security/whitelist/roles")
async def add_action_whitelist_role_endpoint(app_id: str, data: WhitelistUpdate, _ = Depends(require_scope("references:write"))):
    try:
        if not data.action_key or not data.role_id:
            raise HTTPException(status_code=400, detail="action_key e role_id são obrigatórios")
        await add_role(app_id, data.action_key, data.role_id)
        res, status = ok({"message": "Cargo adicionado à whitelist"})
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise _http_500(e, "add_action_whitelist_role")

@router.delete("/{app_id}/security/whitelist/users")
async def del_action_whitelist_user_endpoint(app_id: str, action_key: str, user_id: int, _ = Depends(require_scope("references:write"))):
    try:
        await remove_user(app_id, action_key, user_id)
        res, status = ok({"message": "Usuário removido da whitelist"})
        return res
    except Exception as e:
        raise _http_500(e, "del_action_whitelist_user")

@router.delete("/{app_id}/security/whitelist/roles")
async def del_action_whitelist_role_endpoint(app_id: str, action_key: str, role_id: int, _ = Depends(require_scope("references:write"))):
    try:
        await remove_role(app_id, action_key, role_id)
        res, status = ok({"message": "Cargo removido da whitelist"})
        return res
    except Exception as e:
        raise _http_500(e, "del_action_whitelist_role")


# ─── Infrações ────────────────────────────────────────────────────────────────

@router.get("/{app_id}/security/infractions")
async def get_security_infractions(
    app_id: str,
    action_key: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    _ = Depends(require_scope("references:read"))
):
    try:
        data = await list_recent_infractions(
            app_id,
            action_key=action_key,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        res, status = ok(data)
        return res
    except Exception as e:
        raise _http_500(e, "get_security_infractions")
