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

# ─── Horas acumuladas ─────────────────────────────────────────────────────────
# O bot é o dono do formato: grava `player_total_hours.total_hours` como "HH:MM"
# (APP/utils/time_utils.py). A API gravava horas decimais ("150.0"), que o bot
# lia como ZERO — o membro aparecia com 150h no site e nenhuma na hierarquia.
# Estas duas funções espelham exatamente as do bot; qualquer divergência aqui
# recria o bug.
def minutos_de_horas(valor: Any) -> int:
    """Converte o valor gravado em minutos.

    "12:30" → 750 · "150.0" → 9000 · "150" → 9000 (sem ":" o valor é em horas).
    """
    if valor is None or isinstance(valor, bool):
        return 0
    texto = str(valor).strip()
    if not texto:
        return 0
    if ":" in texto:
        try:
            partes = texto.split(":")
            return max(0, int(partes[0]) * 60 + (int(partes[1]) if len(partes) > 1 else 0))
        except (TypeError, ValueError):
            return 0
    try:
        return max(0, int(round(float(texto) * 60)))
    except (TypeError, ValueError):
        return 0


def horas_hhmm(minutos: Any) -> str:
    """Formato canônico gravado no banco do bot: "HH:MM"."""
    try:
        total = max(0, int(minutos))
    except (TypeError, ValueError):
        total = 0
    return f"{total // 60:02}:{total % 60:02}"


def com_horas_normalizadas(linhas: list, campo: str = "horas_totais") -> list:
    """Acrescenta `<campo>_minutos` (int) e normaliza `<campo>` para "HH:MM".

    O site passa a ter um número inteiro para ordenar/formatar, em vez de tentar
    `Number("12:30")` — que dava `NaN` e quebrava a ordenação do ranking.
    """
    for linha in linhas:
        minutos = minutos_de_horas(linha.get(campo))
        linha[f"{campo}_minutos"] = minutos
        linha[campo] = horas_hhmm(minutos)
    return linhas


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

