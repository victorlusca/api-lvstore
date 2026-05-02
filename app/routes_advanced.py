"""
routes_advanced.py â€” Hierarquia, Audit do Bot, SeguranÃ§a, Superiores e InformaÃ§Ãµes do Bot.

GET    /hierarchy                          â†’ cargos da hierarquia
POST   /hierarchy                          â†’ criar nÃ­vel
PUT    /hierarchy/<id>                     â†’ editar nÃ­vel
DELETE /hierarchy/<id>                     â†’ deletar nÃ­vel

GET    /audit/bot                          â†’ audit_log do bot (master_data.db)

GET    /security                           â†’ configuraÃ§Ãµes de seguranÃ§a
GET    /security/<action_key>             â†’ whitelist de um tipo especÃ­fico
POST   /security/<action_key>/users       â†’ adicionar usuÃ¡rio Ã  whitelist
DELETE /security/<action_key>/users/<uid> â†’ remover usuÃ¡rio
POST   /security/<action_key>/roles       â†’ adicionar cargo Ã  whitelist
DELETE /security/<action_key>/roles/<rid> â†’ remover cargo

GET    /superiores/ranking                 â†’ ranking de superiores
POST   /superiores/<discord_id>/resetar    â†’ zerar mÃ©tricas de um superior
DELETE /superiores/<discord_id>            â†’ remover registro do superior

GET    /botinfo                            â†’ informaÃ§Ãµes do bot (mensalidade, vencimento, etc.)
"""
import sqlite3
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.audit import write_audit
from app.helpers import master_con, ref_con, resolve_player

router = APIRouter(tags=["Advanced"])

_MASTER = "data/master_data.db"
_REF    = "data/reference_data.db"

_SECURITY_ACTIONS = {
    "anti_ban", "anti_kick", "anti_role_delete", "anti_channel_delete",
    "anti_webhook_create", "anti_member_prune", "anti_bot_add",
}

# â”€â”€ HIERARQUIA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/hierarchy")
async def get_hierarchy(_ = Depends(require_scope("references:read"))):
    try:
        con = ref_con()
        rows = con.execute(
            "SELECT id, hierarchy_index, cargo_id, nome, sigla, horas, is_superior "
            "FROM hierarquia ORDER BY hierarchy_index ASC"
        ).fetchall()
        con.close()
        data = [{
            "id": r["id"],
            "index": r["hierarchy_index"],
            "cargo_id": r["cargo_id"],
            "nome": r["nome"],
            "sigla": r["sigla"],
            "horas": r["horas"],
            "is_superior": bool(r["is_superior"]),
            "tipo": "superior" if r["is_superior"] else ("merito" if r["horas"] is None else "horas"),
        } for r in rows]
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/hierarchy")
async def create_hierarchy(request: Request, _ = Depends(require_scope("references:write"))):
    body = await request.json() if await request.body() else {}
    nome  = str(body.get("nome", "")).strip()
    sigla = str(body.get("sigla", "")).strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Campo obrigatÃ³rio: nome")
    cargo_id = body.get("cargo_id")
    horas    = body.get("horas")
    idx      = body.get("index", 0)
    is_superior = 1 if body.get("is_superior") else 0
    try:
        con = sqlite3.connect(_REF)
        con.execute(
            "INSERT INTO hierarquia (hierarchy_index, cargo_id, nome, sigla, horas, is_superior) VALUES (?,?,?,?,?,?)",
            (idx, cargo_id, nome, sigla, horas, is_superior),
        )
        con.commit()
        new_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.close()
        write_audit(status=201, resource_type="hierarquia", resource_key=str(new_id),
                    new_value={"nome": nome, "sigla": sigla, "horas": horas, "is_superior": is_superior},
                    message="NÃ­vel hierÃ¡rquico criado")
        res, status = ok({"id": new_id}, "NÃ­vel criado", 201)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/hierarchy/{hid}")
async def update_hierarchy(hid: int, request: Request, _ = Depends(require_scope("references:write"))):
    body = await request.json() if await request.body() else {}
    try:
        con = ref_con()
        exists = con.execute("SELECT 1 FROM hierarquia WHERE id=?", (hid,)).fetchone()
        if not exists:
            con.close()
            raise HTTPException(status_code=404, detail="NÃ­vel nÃ£o encontrado")
        
        updates = []
        params = []
        for k in ["hierarchy_index", "cargo_id", "nome", "sigla", "horas", "is_superior"]:
            if k in body:
                updates.append(f"{k} = ?")
                params.append(body[k])
        
        if not updates:
            con.close()
            res, status = ok(None, "Nada a atualizar")
            return res
            
        params.append(hid)
        con.execute(f"UPDATE hierarquia SET {', '.join(updates)} WHERE id=?", params)
        con.commit()
        con.close()
        
        write_audit(status=200, resource_type="hierarquia", resource_key=str(hid),
                    new_value=body, message="NÃ­vel hierÃ¡rquico atualizado")
        res, status = ok(None, "NÃ­vel atualizado")
        return res
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/hierarchy/{hid}")
async def delete_hierarchy(hid: int, _ = Depends(require_scope("references:write"))):
    try:
        con = ref_con()
        n = con.execute("DELETE FROM hierarquia WHERE id=?", (hid,)).rowcount
        con.commit()
        con.close()
        if n == 0:
            raise HTTPException(status_code=404, detail="NÃ­vel nÃ£o encontrado")
        
        write_audit(status=200, resource_type="hierarquia", resource_key=str(hid), message="NÃ­vel hierÃ¡rquico removido")
        res, status = ok(None, "NÃ­vel removido")
        return res
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

# â”€â”€ AUDIT LOG DO BOT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/audit/bot")
async def get_bot_audit(
    limit: int = Query(50, le=500, ge=1),
    offset: int = Query(0, ge=0),
    system: Optional[str] = None,
    action: Optional[str] = None,
    _ = Depends(require_scope("audit:read"))
):
    try:
        where, params = [], []
        if system:
            where.append("system_key = ?"); params.append(system)
        if action:
            where.append("action_key = ?"); params.append(action)

        w_clause = ("WHERE " + " AND ".join(where)) if where else ""
        con = master_con()
        rows = con.execute(
            f"""
            SELECT id, created_at, event_type, system_key, action_key,
                   actor_discord_id, actor_name,
                   target_discord_id, target_game_id, target_name,
                   details_json, status, message, severity, source
            FROM audit_log {w_clause}
            ORDER BY id DESC LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        total = con.execute(f"SELECT COUNT(1) FROM audit_log {w_clause}", params).fetchone()[0]
        con.close()

        data = []
        for r in rows:
            actor  = resolve_player(r["actor_discord_id"])
            target = resolve_player(r["target_discord_id"])
            data.append({
                "id": r["id"],
                "data_hora": r["created_at"],
                "sistema": r["system_key"],
                "acao": r["action_key"],
                "ator": {
                    "discord_id": r["actor_discord_id"],
                    "nome": r["actor_name"] or actor["nome"],
                    "login": actor["login"]
                },
                "alvo": {
                    "discord_id": r["target_discord_id"],
                    "game_id": r["target_game_id"],
                    "nome": r["target_name"] or target["nome"],
                    "login": target["login"]
                },
                "status": r["status"],
                "mensagem": r["message"],
                "severidade": r["severity"],
                "origem": r["source"]
            })
        
        res, status = ok({"total": total, "logs": data})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# â”€â”€ INFORMAÃ‡Ã•ES DO BOT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/botinfo")
async def get_botinfo(_ = Depends(require_scope("references:read"))):
    try:
        con = ref_con()
        plano = con.execute(
            "SELECT premium, cliente, vencimento, paid_until_ts FROM configuracoes_plano LIMIT 1"
        ).fetchone()
        con.close()

        mensalidade_valor = None
        cliente = None
        premium = False
        vencimento_ts = None

        con2 = master_con()
        bot_row = con2.execute("SELECT nome, premium, mensalidade_valor, mensalidade_vencimento, cliente FROM bots LIMIT 1").fetchone()
        con2.close()

        if plano:
            premium = bool(plano["premium"])
            cliente = plano["cliente"]
            vencimento_ts = plano["paid_until_ts"] or plano["vencimento"]

        if bot_row:
            if not cliente: cliente = bot_row["cliente"]
            if not mensalidade_valor: mensalidade_valor = bot_row["mensalidade_valor"]
            if not vencimento_ts: vencimento_ts = bot_row["mensalidade_vencimento"]
            if not premium: premium = bool(bot_row["premium"])

        res, status = ok({
            "premium": premium,
            "cliente": cliente,
            "mensalidade": mensalidade_valor,
            "vencimento": vencimento_ts
        })
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

