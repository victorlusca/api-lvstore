"""
routes_warnings.py â€” AdvertÃªncias e AusÃªncias (FastAPI version).
"""
import sqlite3
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.audit import write_audit
from app.helpers import master_con, resolve_player

router = APIRouter(tags=["Warnings"])

_MASTER = "data/master_data.db"
_DATE_FMTS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"]

def _parse_dt(s):
    if not s: return None
    if isinstance(s, (int, float)):
        try: return datetime.utcfromtimestamp(int(s))
        except: return None
    for fmt in _DATE_FMTS:
        try: return datetime.strptime(str(s), fmt)
        except ValueError: continue
    return None

def _fmt_dt(s):
    d = _parse_dt(s)
    return d.strftime("%d/%m/%Y %H:%M") if d else str(s or "â€”")

def _find_aplicado_por(game_user_id, warn_id):
    try:
        con = master_con()
        row = con.execute(
            """
            SELECT actor_discord_id, actor_name FROM audit_log
            WHERE system_key='AdvertÃªncia' AND action_key LIKE '%aplicar%'
              AND (target_game_id=? OR message_id=?)
            ORDER BY id DESC LIMIT 1
            """,
            (game_user_id, warn_id),
        ).fetchone()
        con.close()
        if row and row["actor_discord_id"]:
            p = resolve_player(row["actor_discord_id"])
            return {"discord_id": row["actor_discord_id"], "nome": p["nome"] or row["actor_name"], "login": p["login"]}
        if row and row["actor_name"]:
            return {"discord_id": None, "nome": row["actor_name"], "login": row["actor_name"]}
    except: pass
    return None

@router.get("/warnings")
async def list_warnings(_ = Depends(require_scope("references:read"))):
    try:
        con = master_con()
        rows = con.execute(
            "SELECT id, user_id_save, game_user_id, adv_tipo, motivo, expires_at, message_id "
            "FROM player_warnings ORDER BY id DESC"
        ).fetchall()
        con.close()
        data = []
        for r in rows:
            p = resolve_player(r["user_id_save"])
            aplicado = _find_aplicado_por(r["game_user_id"], r["id"])
            data.append({
                "id": r["id"],
                "jogador": {"discord_id": r["user_id_save"], "nome": p["nome"], "login": p["login"]},
                "game_id": r["game_user_id"],
                "tipo": r["adv_tipo"],
                "motivo": r["motivo"],
                "vencimento": _fmt_dt(r["expires_at"]),
                "vencimento_raw": str(r["expires_at"]) if r["expires_at"] else None,
                "aplicado_por": aplicado,
            })
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/warnings/{wid}")
async def delete_warning(wid: int, _ = Depends(require_scope("references:write"))):
    try:
        con = master_con()
        n = con.execute("DELETE FROM player_warnings WHERE id=?", (wid,)).rowcount
        con.commit(); con.close()
        if n == 0: raise HTTPException(status_code=404, detail="AdvertÃªncia nÃ£o encontrada")
        write_audit(status=200, resource_type="advertencia", resource_key=str(wid), message="AdvertÃªncia removida")
        res, status = ok(None, "AdvertÃªncia removida")
        return res
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/absences")
async def list_absences(_ = Depends(require_scope("references:read"))):
    try:
        con = master_con()
        rows = con.execute(
            "SELECT id, user_id, reason, start_date, end_date FROM player_absences ORDER BY id DESC"
        ).fetchall()
        con.close()
        data = []
        for r in rows:
            p = resolve_player(r["user_id"])
            data.append({
                "id": r["id"],
                "jogador": {"discord_id": r["user_id"], "nome": p["nome"], "login": p["login"]},
                "motivo": r["reason"],
                "inicio": _fmt_dt(r["start_date"]),
                "fim": _fmt_dt(r["end_date"]),
            })
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

