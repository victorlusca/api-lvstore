"""
responses.py â€” helpers de resposta padronizada.
Auditoria agora em api/audit.py (write_audit).
MantÃ©m ok()/err() para retrocompatibilidade.
"""
from typing import Any, Optional
from fastapi.responses import JSONResponse

def json_safe_data(obj: Any) -> Any:
    """
    Recursivamente converte inteiros que excedem o limite de precisÃ£o do JavaScript
    (Number.MAX_SAFE_INTEGER) em strings para evitar problemas no frontend.
    """
    if isinstance(obj, int):
        # JavaScript's Number.MAX_SAFE_INTEGER is 9007199254740991
        if obj > 9007199254740991 or obj < -9007199254740991:
            return str(obj)
    elif isinstance(obj, list):
        return [json_safe_data(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: json_safe_data(v) for k, v in obj.items()}
    return obj

class SafeJSONResponse(JSONResponse):
    """
    Custom JSONResponse que garante que IDs grandes nÃ£o percam precisÃ£o no frontend.
    """
    def render(self, content: Any) -> bytes:
        return super().render(json_safe_data(content))

def ok(data: Any = None, message: str = "ok", status: int = 200):
    body = {"ok": True, "message": message}
    if data is not None:
        body["data"] = data
    return body, status

def err(message: str, status: int = 400, details: Any = None):
    # Nunca expÃµe stack trace ou info interna em produÃ§Ã£o
    body = {"ok": False, "error": message}
    if details is not None:
        body["details"] = details
    return body, status

# Legado â€” usado por routes_references/embeds antigos
def audit(status_code: int, note: str = "") -> None:
    from app.audit import write_audit
    write_audit(status=status_code, message=note)

