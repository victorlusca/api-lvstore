"""
responses.py â€” helpers de resposta padronizada.
Auditoria agora em api/audit.py (write_audit).
MantÃ©m ok()/err() para retrocompatibilidade.
"""
from typing import Any, Optional

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

