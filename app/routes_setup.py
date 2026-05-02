"""
routes_setup.py â€” geraÃ§Ã£o e gestÃ£o de tokens com escopos (FastAPI version).
"""
import os
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from typing import Optional
from app.auth import require_scope, generate_token, revoke_token, list_tokens, _load_token_hash, ALL_SCOPES, validate_token
from app.responses import ok, err
from app.audit import write_audit

router = APIRouter(tags=["Setup"])
_SETUP_KEY = os.environ.get("API_SETUP_KEY", "")

def _check_setup_key(x_setup_key: Optional[str] = Header(None)):
    if _SETUP_KEY and x_setup_key != _SETUP_KEY:
        return False
    return True

@router.post("/setup/token")
async def create_token(request: Request, x_setup_key: Optional[str] = Header(None)):
    """
    Bootstrap: gera token na primeira vez (sem auth).
    RotaÃ§Ã£o: requer X-Setup-Key se API_SETUP_KEY estiver definida, ou escopo setup:write.
    """
    has_existing = _load_token_hash() is not None

    if has_existing:
        # Requer ou X-Setup-Key ou token com setup:write
        setup_key_ok = _SETUP_KEY and x_setup_key == _SETUP_KEY
        if not setup_key_ok:
            # Tenta validar token via Authorization header se existir
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise HTTPException(status_code=403, detail="Token jÃ¡ existe. ForneÃ§a X-Setup-Key ou token com escopo setup:write.")
            
            try:
                # ImportaÃ§Ã£o local para evitar circular dependÃªncia se houver
                from app.auth import validate_token
                from fastapi.security import HTTPAuthorizationCredentials
                # SimulaÃ§Ã£o manual de validaÃ§Ã£o de token para este caso especial
                scheme, credentials = auth_header.split()
                info = await validate_token(request, HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials))
                if "admin:*" not in info["scopes"] and "setup:write" not in info["scopes"]:
                    raise HTTPException(status_code=403, detail="Escopo 'setup:write' necessÃ¡rio para rotacionar token")
            except Exception as e:
                if isinstance(e, HTTPException): raise e
                raise HTTPException(status_code=403, detail="Token invÃ¡lido ou insuficiente")

    body = await request.json() if await request.body() else {}
    label = str(body.get("label", "default"))[:64]
    scopes = str(body.get("scopes", "admin:*"))

    # Valida escopos
    given = {s.strip() for s in scopes.split(",")}
    if not given.issubset(ALL_SCOPES):
        raise HTTPException(status_code=400, detail=f"Escopos invÃ¡lidos: {given - ALL_SCOPES}")

    try:
        token = generate_token(label=label, scopes=scopes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    write_audit(status=201, resource_type="api_token", resource_key=label,
                message=f"Token gerado com escopos: {scopes}")
    
    res, status = ok({"token": token, "label": label, "scopes": list(given)},
                    "Token gerado. Guarde em local seguro â€” nÃ£o serÃ¡ exibido novamente.", 201)
    return res

@router.delete("/setup/token/{label}")
async def delete_token(label: str, _ = Depends(require_scope("setup:write"))):
    n = revoke_token(label)
    if n == 0:
        raise HTTPException(status_code=404, detail=f"Nenhum token ativo com label '{label}'")
    
    write_audit(status=200, resource_type="api_token", resource_key=label,
                message=f"Token '{label}' revogado")
    
    res, status = ok({"label": label, "revoked": n}, f"{n} token(s) revogado(s)")
    return res

@router.get("/setup/tokens")
async def list_active_tokens(_ = Depends(require_scope("setup:write"))):
    res, status = ok(list_tokens())
    return res

