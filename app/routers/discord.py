"""
discord.py — cargos e canais do servidor do bot, lidos da API do Discord.

Existe para o painel poder oferecer um **seletor** em vez de um campo de ID solto:
o cliente escolhe "CEO" e o que vai para o banco é o snowflake certo. Sem isso, a
única forma de configurar era colar o ID na mão, e um dígito errado só aparecia
quando o sistema falhava em produção.

O token do bot nunca sai daqui: é lido do `reference_data.db` do próprio bot
(`bot_configuration.bot_token`), usado para chamar o Discord e descartado. A
resposta só tem id, nome, cor e posição.
"""
import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_scope
from app.core.audit import audit_log
from app.services.sqlite_engine import reference_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots/{app_id}/discord", tags=["Discord"])

DISCORD_API = "https://discord.com/api/v10"

# Cargos e canais mudam pouco e o painel pede a lista em várias telas
# (configurações, hierarquia, segurança). Sem cache, cada tela viraria uma
# chamada ao Discord — que tem limite de taxa por bot.
_TTL_S = 60
_cache: Dict[str, Dict[str, Any]] = {}


async def _credenciais(app_id: str) -> tuple:
    """(guild_id, token) do bot, lidos do `reference_data.db` dele."""
    servidor = await reference_service.execute_query(
        app_id, "SELECT guild_id FROM configuracoes_servidor WHERE id = 1 LIMIT 1"
    )
    guild_id = str(servidor[0].get("guild_id")) if servidor else ""

    config = await reference_service.execute_query(
        app_id, "SELECT bot_token FROM bot_configuration WHERE id = 1 LIMIT 1"
    )
    token = str(config[0].get("bot_token") or "") if config else ""

    if not guild_id or guild_id in ("0", "None"):
        raise HTTPException(status_code=409, detail="Servidor não configurado no bot (guild_id vazio).")
    if not token:
        raise HTTPException(status_code=409, detail="Token do bot não configurado.")
    return guild_id, token


async def _buscar(app_id: str, recurso: str) -> List[Dict[str, Any]]:
    chave = f"{app_id}:{recurso}"
    guardado = _cache.get(chave)
    if guardado and time.time() - guardado["at"] < _TTL_S:
        return guardado["dados"]

    guild_id, token = await _credenciais(app_id)
    async with httpx.AsyncClient(timeout=20.0) as client:
        resposta = await client.get(
            f"{DISCORD_API}/guilds/{guild_id}/{recurso}",
            headers={"Authorization": f"Bot {token}"},
        )
    if resposta.status_code == 401:
        raise HTTPException(status_code=409, detail="Token do bot inválido ou expirado.")
    if resposta.status_code == 403:
        raise HTTPException(status_code=409, detail="O bot não tem permissão para ler este servidor.")
    if resposta.status_code == 404:
        raise HTTPException(status_code=409, detail="O bot não está no servidor configurado.")
    if resposta.status_code == 429:
        raise HTTPException(status_code=429, detail="Limite de requisições do Discord atingido.")
    if resposta.status_code >= 400:
        logger.error(f"Discord {recurso} {resposta.status_code}: {resposta.text[:200]}")
        raise HTTPException(status_code=502, detail="O Discord não respondeu corretamente.")

    dados = resposta.json()
    if not isinstance(dados, list):
        raise HTTPException(status_code=502, detail="Resposta inesperada do Discord.")
    _cache[chave] = {"at": time.time(), "dados": dados}
    return dados


@router.get("/roles", dependencies=[Depends(require_scope("admin:*"))])
async def listar_cargos(app_id: str):
    """Cargos do servidor, do mais alto para o mais baixo.

    `@everyone` fica de fora: nunca é uma escolha válida de configuração. Cargos
    gerenciados por integração (bots, boosters) vêm marcados para o painel poder
    sinalizá-los — o Discord não deixa atribuí-los manualmente.
    """
    audit_log(app_id, "GET_DISCORD_ROLES", "Fetching guild roles")
    cargos = await _buscar(app_id, "roles")
    saida = [
        {
            # str: snowflake acima de MAX_SAFE_INTEGER perde dígitos como número.
            "id": str(c.get("id")),
            "name": c.get("name") or "",
            "color": int(c.get("color") or 0),
            "position": int(c.get("position") or 0),
            "managed": bool(c.get("managed")),
        }
        for c in cargos
        if str(c.get("id")) != str(c.get("name")) and c.get("name") != "@everyone"
    ]
    saida.sort(key=lambda c: c["position"], reverse=True)
    return {"ok": True, "data": saida}


# Tipos de canal do Discord que interessam ao painel.
CANAL_TEXTO = 0
CANAL_VOZ = 2
CATEGORIA = 4
CANAL_ANUNCIO = 5
CANAL_FORUM = 15


@router.get("/channels", dependencies=[Depends(require_scope("admin:*"))])
async def listar_canais(app_id: str):
    """Canais do servidor, com a categoria de cada um.

    O painel usa `tipo` para filtrar: campos de log/chat só oferecem canais de
    texto, os de call só oferecem voz, e os de categoria só oferecem categorias.
    """
    audit_log(app_id, "GET_DISCORD_CHANNELS", "Fetching guild channels")
    canais = await _buscar(app_id, "channels")

    categorias = {
        str(c.get("id")): (c.get("name") or "")
        for c in canais
        if int(c.get("type", -1)) == CATEGORIA
    }

    def rotulo(bruto: int) -> Optional[str]:
        return {
            CANAL_TEXTO: "texto",
            CANAL_ANUNCIO: "texto",
            CANAL_FORUM: "texto",
            CANAL_VOZ: "voz",
            CATEGORIA: "categoria",
        }.get(bruto)

    saida = []
    for c in canais:
        tipo = rotulo(int(c.get("type", -1)))
        if not tipo:
            continue
        pai = str(c.get("parent_id")) if c.get("parent_id") else None
        saida.append({
            "id": str(c.get("id")),
            "name": c.get("name") or "",
            "tipo": tipo,
            "position": int(c.get("position") or 0),
            "categoria": categorias.get(pai) if pai else None,
        })
    saida.sort(key=lambda c: (c.get("categoria") or "", c["position"]))
    return {"ok": True, "data": saida}
