"""
auth.py — autenticação por token com escopos, proteção brute-force e multi-token (FastAPI version).

Escopos:
  references:read   references:write
  embeds:read       embeds:write
  reload:run        audit:read
  setup:write       backup:run
  admin:*           (superset de todos)
"""
import os, sqlite3, secrets, hashlib, time, logging
from typing import Optional, List, Dict, Any
from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

_REFERENCE_DB = "data/reference_data.db"

ALL_SCOPES = {
    "references:read", "references:write",
    "embeds:read",     "embeds:write",
    "reload:run",      "audit:read",
    "setup:write",     "backup:run",
    "tasks:read",      "tasks:write",
    "bots:manage",
    "admin:*",
}

_BF_MAX  = int(os.environ.get("API_BF_MAX_FAILURES", "10"))
_BF_WIN  = int(os.environ.get("API_BF_WINDOW_SECS",  "300"))
_bf: dict = {}

security = HTTPBearer()

if not settings.API_KEY:
    logging.getLogger(__name__).critical(
        "API_KEY nao esta definida no ambiente. A master key esta DESLIGADA e "
        "somente tokens da tabela api_tokens serao aceitos. Defina API_KEY nas "
        "variaveis de ambiente da hospedagem para reativar o acesso administrativo."
    )

# ─── Schema ──────────────────────────────────────────────────────────────────
def _ensure_token_table() -> None:
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        con.executescript("""
            CREATE TABLE IF NOT EXISTS api_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                token_hash TEXT    NOT NULL UNIQUE,
                label      TEXT    NOT NULL DEFAULT 'default',
                scopes     TEXT    NOT NULL DEFAULT 'admin:*',
                is_active  INTEGER NOT NULL DEFAULT 1,
                created_at TEXT    DEFAULT (datetime('now')),
                last_used  TEXT,
                last_ip    TEXT
            );
        """)
        con.commit(); con.close()
    except Exception:
        pass

_ensure_token_table()

# ─── Brute-force ─────────────────────────────────────────────────────────────
def _get_ip(request: Request) -> str:
    """IP usado como chave do contador de brute-force.

    NAO usa X-Forwarded-For: esse header e escrito pelo cliente. Chavear o
    contador por ele permitia zerar o bloqueio a cada tentativa, bastando variar
    o header — a protecao existia mas nao protegia nada. O IP da conexao e o
    unico valor que o atacante nao controla. Se um dia houver um proxy reverso
    confiavel na frente, ele deve ser lido a partir de uma lista de proxies
    conhecidos, nunca do header cru.
    """
    return request.client.host if request.client else "unknown"

def _check_bf(ip: str):
    now = time.time()
    if ip not in _bf: return
    fails, first_fail = _bf[ip]
    if now - first_fail > _BF_WIN:
        del _bf[ip]; return
    if fails >= _BF_MAX:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Tente novamente mais tarde.")

def _log_fail(ip: str):
    now = time.time()
    if ip not in _bf: _bf[ip] = [1, now]
    else:
        _bf[ip][0] += 1
        if now - _bf[ip][1] > _BF_WIN: _bf[ip] = [1, now]

# ─── Token Validation ────────────────────────────────────────────────────────
def _load_token_hash() -> Optional[str]:
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        row = con.execute("SELECT token_hash FROM api_tokens WHERE is_active=1 LIMIT 1").fetchone()
        con.close()
        return row[0] if row else None
    except Exception:
        return None

async def validate_token(request: Request, auth: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    ip = _get_ip(request)
    _check_bf(ip)
    
    token = auth.credentials
    
    # 1. Master API_KEY vinda do ambiente.
    #    - Vazia => master key DESLIGADA. Nunca casa com token nenhum.
    #    - compare_digest em vez de "==": o "==" de strings sai no primeiro byte
    #      diferente, o que vaza o prefixo correto por tempo de resposta.
    master = settings.API_KEY or ""
    if master and secrets.compare_digest(token, master):
        return {"label": "master_key", "scopes": ALL_SCOPES}

    # 2. Verificar no banco de dados de tokens dinâmicos
    h = hashlib.sha256(token.encode()).hexdigest()
    
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        row = con.execute(
            "SELECT label, scopes FROM api_tokens WHERE token_hash=? AND is_active=1",
            (h,)
        ).fetchone()
        
        if not row:
            con.close()
            _log_fail(ip)
            raise HTTPException(status_code=401, detail="Token inválido ou expirado")
        
        # Update last used
        con.execute(
            "UPDATE api_tokens SET last_used=datetime('now'), last_ip=? WHERE token_hash=?",
            (ip, h)
        )
        con.commit()
        con.close()
        
        return {"label": row[0], "scopes": set(row[1].split(","))}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Erro interno de autenticação")

def require_scope(scope: str):
    async def _dependency(info: Dict[str, Any] = Depends(validate_token)):
        scopes = info["scopes"]
        if "admin:*" in scopes:
            return info
        if scope not in scopes:
            raise HTTPException(status_code=403, detail=f"Escopo '{scope}' necessário")
        return info
    return _dependency

# ─── Token CRUD (reused from original) ───────────────────────────────────────
def generate_token(label: str = "default", scopes: Optional[str] = None) -> str:
    _ensure_token_table()
    if scopes is None:
        scopes = "admin:*"
    given = {s.strip() for s in scopes.split(",")}
    invalid = given - ALL_SCOPES
    if invalid:
        raise ValueError(f"Escopos inválidos: {invalid}")
    token = secrets.token_hex(32)
    h = hashlib.sha256(token.encode()).hexdigest()
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        con.execute("UPDATE api_tokens SET is_active=0 WHERE label=?", (label,))
        con.execute("INSERT INTO api_tokens (token_hash,label,scopes) VALUES (?,?,?)", (h, label, scopes))
        con.commit(); con.close()
    except Exception:
        pass
    return token

def revoke_token(label: str) -> int:
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        n = con.execute("UPDATE api_tokens SET is_active=0 WHERE label=?", (label,)).rowcount
        con.commit(); con.close()
        return n
    except Exception:
        return 0

def list_tokens() -> list:
    try:
        con = sqlite3.connect(_REFERENCE_DB)
        rows = con.execute(
            "SELECT id,label,scopes,created_at,last_used,last_ip FROM api_tokens WHERE is_active=1 ORDER BY id"
        ).fetchall()
        con.close()
        return [{"id":r[0],"label":r[1],"scopes":r[2].split(","),
                 "created_at":r[3],"last_used":r[4],"last_ip":r[5]} for r in rows]
    except Exception:
        return []

