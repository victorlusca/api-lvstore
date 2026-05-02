"""
validators.py â€” validaÃ§Ã£o forte e governanÃ§a de integridade de dados.

Regras por tabela/campo:
  - tipo esperado (int, bool, str)
  - tamanho mÃ¡ximo
  - campos protegidos (leitura apenas via bot)
  - campos que aceitam vazio
"""
import re
from typing import Any, Optional, Tuple

# â”€â”€â”€ Campos protegidos (nÃ£o editÃ¡veis via API) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PROTECTED_FIELDS = {
    # Nunca sobrescrever via API (risco de romper o bot)
    "configuracoes_plano": {"premium", "cliente", "vencimento", "pix_copia_e_cola"}, # managed pela LV Store
    "configuracoes_servidor": {"pontos_origem_server",  # managed pelo sistema de pontos
                               "pontos_origem_canal"},
}

# â”€â”€â”€ Tipos e limites por tabela/coluna â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Formato: {table: {column: {"type": str|int|bool|snowflake, "max_len": int, "required": bool}}}
_FIELD_RULES: dict = {
    # KV tables â€” valor sempre Ã© string no banco
    "users":           {"*": {"type": "snowflake", "max_len": 20}},
    "cargos_gerais":   {"*": {"type": "snowflake", "max_len": 20}},
    "chats_gerais":    {"*": {"type": "snowflake", "max_len": 20}},
    "calls":           {"*": {"type": "snowflake", "max_len": 20}},
    "categorias_gerais":{"*": {"type": "snowflake", "max_len": 20}},
    "logs":            {"*": {"type": "snowflake", "max_len": 20}},
    # Single-row
    "configuracoes_organizacao": {
        "sigla":       {"type": "str", "max_len": 20},
        "nome":        {"type": "str", "max_len": 100},
        "tag":         {"type": "str", "max_len": 10},
        "tag_change":  {"type": "str", "max_len": 10},
        "tipo":        {"type": "str", "max_len": 50},
        "mudar_tag":   {"type": "bool"},
    },
    "configuracoes_servidor": {
        "guild_id":    {"type": "snowflake", "max_len": 20},
        "store_id":    {"type": "snowflake", "max_len": 20},
        "pontos_origem_server": {"type": "snowflake", "max_len": 20},
        "pontos_origem_canal":  {"type": "snowflake", "max_len": 20},
    },
    "configuracoes_plano": {
        "premium":          {"type": "bool"},
        "cliente":          {"type": "snowflake", "max_len": 20},
        "vencimento":       {"type": "int", "min": 1, "max": 31},
        "pix_copia_e_cola": {"type": "str", "max_len": 500},
    },
    "configuracoes_e_numeros": {
        "acertos_minimos_edital": {"type": "int", "min": 0, "max": 100},
        "meta_diaria_rotas":      {"type": "int", "min": 1, "max": 999},
        "delay_rotas":            {"type": "int", "min": 0, "max": 86400},
        "margem_horas_upamento":  {"type": "int", "min": 0, "max": 9999},
    },
}

_SNOWFLAKE_RE = re.compile(r"^\d{15,20}$")


def _rule(table: str, column: str) -> dict:
    t = _FIELD_RULES.get(table, {})
    return t.get(column, t.get("*", {"type": "str", "max_len": 500}))


def validate_reference(table: str, column: str, value: Any) -> Tuple[bool, Optional[str]]:
    """
    Valida um valor para table/column.
    Retorna (True, None) se vÃ¡lido, (False, motivo) se invÃ¡lido.
    """
    # ProteÃ§Ã£o de campo
    protected = PROTECTED_FIELDS.get(table, set())
    if column in protected:
        return False, f"Campo '{column}' em '{table}' Ã© gerenciado internamente e nÃ£o pode ser alterado via API."

    rule = _rule(table, column)
    t    = rule.get("type", "str")
    s    = str(value).strip()

    if t == "snowflake":
        if not _SNOWFLAKE_RE.match(s):
            return False, f"'{column}' deve ser um ID Discord vÃ¡lido (15-20 dÃ­gitos). Recebido: '{s}'"
        max_len = rule.get("max_len", 20)
        if len(s) > max_len:
            return False, f"'{column}' excede {max_len} caracteres."

    elif t == "int":
        try:
            n = int(s)
        except ValueError:
            return False, f"'{column}' deve ser um inteiro. Recebido: '{s}'"
        mn = rule.get("min")
        mx = rule.get("max")
        if mn is not None and n < mn:
            return False, f"'{column}' deve ser >= {mn}. Recebido: {n}"
        if mx is not None and n > mx:
            return False, f"'{column}' deve ser <= {mx}. Recebido: {n}"

    elif t == "bool":
        if s.lower() not in {"0","1","true","false","sim","nÃ£o","yes","no","nao"}:
            return False, f"'{column}' deve ser booleano (0/1/true/false). Recebido: '{s}'"

    else:  # str
        max_len = rule.get("max_len", 500)
        if len(s) > max_len:
            return False, f"'{column}' excede {max_len} caracteres."

    return True, None


def validate_embed_payload(body: dict) -> Tuple[bool, Optional[str]]:
    """ValidaÃ§Ã£o extra de payload de embed alÃ©m da checagem de campos."""
    if "color" in body:
        try:
            c = int(str(body["color"]), 0)
            if c < 0 or c > 0xFFFFFF:
                return False, "color deve estar entre 0x000000 e 0xFFFFFF"
        except Exception:
            return False, "color deve ser inteiro (hex ou decimal)"

    if "title" in body and len(str(body["title"])) > 256:
        return False, "title nÃ£o pode exceder 256 caracteres (limite Discord)"
    if "description" in body and len(str(body["description"])) > 4096:
        return False, "description nÃ£o pode exceder 4096 caracteres (limite Discord)"
    if "url" in body:
        u = str(body["url"])
        if u and not (u.startswith("http://") or u.startswith("https://")):
            return False, "url deve comeÃ§ar com http:// ou https://"

    # Valida fields_json se vier como lista
    if "fields_json" in body and isinstance(body["fields_json"], list):
        if len(body["fields_json"]) > 25:
            return False, "MÃ¡ximo de 25 fields por embed (limite Discord)"
        for i, f in enumerate(body["fields_json"]):
            if not isinstance(f, dict):
                return False, f"Field {i} deve ser um objeto"
            if "name" not in f or "value" not in f:
                return False, f"Field {i} deve ter 'name' e 'value'"
            if len(str(f.get("name",""))) > 256:
                return False, f"Field {i}: name excede 256 chars"
            if len(str(f.get("value",""))) > 1024:
                return False, f"Field {i}: value excede 1024 chars"

    return True, None


def sanitize_str(s: str, max_len: int = 500) -> str:
    """Remove caracteres nulos e trunca."""
    return s.replace("\x00", "").strip()[:max_len]

