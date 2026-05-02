"""
rate_limit.py â€” rate limiting por IP com janela deslizante em memÃ³ria.

ConfigurÃ¡vel por grupo de rotas via decorator ou diretamente.
"""
import time, os
from functools import wraps
from flask import request, jsonify

_STORE: dict = {}   # ip -> [timestamps]

# Limites padrÃ£o (podem ser sobrepostos por env)
_DEFAULTS = {
    "global":     (int(os.environ.get("API_RL_GLOBAL",  "200")), 60),   # 200/min
    "write":      (int(os.environ.get("API_RL_WRITE",    "30")), 60),   # 30 escritas/min
    "setup":      (int(os.environ.get("API_RL_SETUP",     "5")), 60),   # 5 setup ops/min
    "backup":     (int(os.environ.get("API_RL_BACKUP",    "3")), 60),   # 3 backups/min
}

def _client_ip() -> str:
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr or "unknown")

def _check(bucket: str, max_req: int, window: int) -> bool:
    """True = permitido, False = bloqueado."""
    ip = _client_ip()
    key = f"{ip}:{bucket}"
    now = time.time()
    hits = [t for t in _STORE.get(key, []) if now - t < window]
    _STORE[key] = hits
    if len(hits) >= max_req:
        return False
    _STORE[key].append(now)
    return True

def rate_limit(bucket: str = "global"):
    """Decorator de rate limiting para uma rota Flask."""
    max_req, window = _DEFAULTS.get(bucket, _DEFAULTS["global"])
    def decorator(f):
        @wraps(f)
        def d(*a, **kw):
            if not _check(bucket, max_req, window):
                return jsonify({"ok": False, "error": "Rate limit excedido. Tente em breve."}), 429
            return f(*a, **kw)
        return d
    return decorator

def get_stats() -> dict:
    """Retorna contagem de IPs ativos por bucket (para observabilidade)."""
    now = time.time()
    buckets = {}
    for key, hits in _STORE.items():
        active = [t for t in hits if now - t < 60]
        bucket = key.split(":", 1)[1] if ":" in key else "?"
        buckets.setdefault(bucket, set()).add(key.split(":")[0])
    return {b: len(ips) for b, ips in buckets.items()}

