"""
routes_security.py â€” SeguranÃ§a do bot (configuraÃ§Ã£o, whitelist, infraÃ§Ãµes) (FastAPI version).
"""
"""
routes_security.py â€” SeguranÃ§a do bot (configuraÃ§Ã£o, whitelist, infraÃ§Ãµes) (FastAPI version).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.auth import require_scope
from app.responses import ok
from app.security.security_guard import (
    list_action_configs,
    list_system_states,
    upsert_action_config,
    set_system_state,
    list_recent_infractions,
)
from app.security.security_whitelist import (
    list_action_whitelist,
    list_global_whitelist,
    add_user,
    remove_user,
    add_role,
    remove_role,
    add_global_user,
    remove_global_user,
    add_global_role,
    remove_global_role,
)

router = APIRouter(prefix="/bots", tags=["Security"])

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

@router.get("/{app_id}/security/configs")
async def get_security_configs(
    app_id: str,
    _ = Depends(require_scope("references:read"))
):
    try:
        data = list_action_configs()
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{app_id}/security/configs")
async def update_security_config(
    app_id: str,
    config: ConfigUpdate,
    _ = Depends(require_scope("references:write"))
):
    try:
        # Tenta usar action_key ou system_name
        key = config.action_key or config.system_name
        if not key:
            raise HTTPException(status_code=400, detail="É necessário fornecer 'action_key' ou 'system_name'")

        # Validação extra para ajudar o usuário
        from app.security.security_guard import VALID_PUNISHMENTS, _to_system_name
        
        sys_name = _to_system_name(key)
        if not sys_name:
            raise HTTPException(
                status_code=400, 
                detail=f"Chave de ação ou sistema inválida: {key}. Use chaves como 'anti_ban', 'anti_kick', etc."
            )
            
        if config.punishment_type not in VALID_PUNISHMENTS:
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de punição inválido: {config.punishment_type}. Opções: {list(VALID_PUNISHMENTS)}"
            )

        success = upsert_action_config(
            action_key=key,
            infraction_limit=config.infraction_limit,
            punishment_type=config.punishment_type,
            is_enabled=config.is_enabled
        )
        if success:
            res, status = ok({"message": "Configuração atualizada com sucesso"})
            return res
        
        raise Exception("Falha interna ao salvar no banco de dados")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{app_id}/security/systems")
async def get_security_systems(app_id: str, _ = Depends(require_scope("references:read"))):
    try:
        data = list_system_states()
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{app_id}/security/systems")
async def update_security_system(
    app_id: str,
    system: SystemUpdate,
    _ = Depends(require_scope("references:write"))
):
    try:
        from app.security.security_guard import _to_system_name
        sys_name = _to_system_name(system.system_name)
        if not sys_name:
            raise HTTPException(
                status_code=400, 
                detail=f"Sistema inválido: {system.system_name}"
            )

        success = set_system_state(sys_name, system.enabled)
        if success:
            res, status = ok({"message": "Sistema atualizado com sucesso"})
            return res
        raise Exception("Falha ao atualizar estado do sistema no banco")
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{app_id}/security/whitelist")
async def get_security_whitelist(
    app_id: str,
    action_key: Optional[str] = None, 
    _ = Depends(require_scope("references:read"))
):
    try:
        if not action_key:
            from app.security.security_guard import ACTION_KEYS
            return {"error": False, "message": "Forneça um action_key", "available_keys": ACTION_KEYS}
            
        users, roles = list_action_whitelist(action_key)
        data = {"action_key": action_key, "users": users, "roles": roles}
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{app_id}/security/whitelist/global")
async def get_global_security_whitelist(
    app_id: str,
    _ = Depends(require_scope("references:read"))
):
    try:
        users, roles = list_global_whitelist()
        data = {"users": users, "roles": roles}
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{app_id}/security/whitelist/user")
async def add_whitelist_user(app_id: str, data: WhitelistUpdate, _ = Depends(require_scope("references:write"))):
    try:
        if not data.action_key or not data.user_id:
            raise HTTPException(status_code=400, detail="action_key e user_id são obrigatórios")
        add_user(data.action_key, data.user_id)
        res, status = ok({"message": "Usuário adicionado à whitelist"})
        return res
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{app_id}/security/whitelist/user")
async def del_whitelist_user(app_id: str, action_key: str, user_id: int, _ = Depends(require_scope("references:write"))):
    try:
        remove_user(action_key, user_id)
        res, status = ok({"message": "Usuário removido da whitelist"})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{app_id}/security/whitelist/role")
async def add_whitelist_role(app_id: str, data: WhitelistUpdate, _ = Depends(require_scope("references:write"))):
    try:
        if not data.action_key or not data.role_id:
            raise HTTPException(status_code=400, detail="action_key e role_id são obrigatórios")
        add_role(data.action_key, data.role_id)
        res, status = ok({"message": "Cargo adicionado à whitelist"})
        return res
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{app_id}/security/whitelist/role")
async def del_whitelist_role(app_id: str, action_key: str, role_id: int, _ = Depends(require_scope("references:write"))):
    try:
        remove_role(action_key, role_id)
        res, status = ok({"message": "Cargo removido da whitelist"})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{app_id}/security/whitelist/global/user")
async def add_global_whitelist_user(app_id: str, data: WhitelistUpdate, _ = Depends(require_scope("references:write"))):
    try:
        if not data.user_id:
            raise HTTPException(status_code=400, detail="user_id é obrigatório")
        add_global_user(data.user_id)
        res, status = ok({"message": "Usuário adicionado à whitelist global"})
        return res
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{app_id}/security/whitelist/global/user")
async def del_global_whitelist_user(app_id: str, user_id: int, _ = Depends(require_scope("references:write"))):
    try:
        remove_global_user(user_id)
        res, status = ok({"message": "Usuário removido da whitelist global"})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{app_id}/security/whitelist/global/role")
async def add_global_whitelist_role(app_id: str, data: WhitelistUpdate, _ = Depends(require_scope("references:write"))):
    try:
        if not data.role_id:
            raise HTTPException(status_code=400, detail="role_id é obrigatório")
        add_global_role(data.role_id)
        res, status = ok({"message": "Cargo adicionado à whitelist global"})
        return res
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{app_id}/security/whitelist/global/role")
async def del_global_whitelist_role(app_id: str, role_id: int, _ = Depends(require_scope("references:write"))):
    try:
        remove_global_role(role_id)
        res, status = ok({"message": "Cargo removido da whitelist global"})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        data = list_recent_infractions(
            action_key=action_key,
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

