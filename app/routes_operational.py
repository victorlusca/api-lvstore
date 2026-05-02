"""
routes_operational.py â€” Rotas e Transcripts (FastAPI version).
"""
import sqlite3
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.audit import write_audit
from app.helpers import master_con, resolve_player

router = APIRouter(tags=["Operational"])
_MASTER = "data/master_data.db"

# â”€â”€ ROTAS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/routes/ranking")
async def ranking_rotas(_ = Depends(require_scope("references:read"))):
    try:
        con = master_con()
        rows = con.execute(
            """
            SELECT tr.user_id,
                   COALESCE(tr.total_routes, 0) AS total_routes,
                   COALESCE(dr.routes, 0)       AS daily_routes
            FROM total_routes tr
            LEFT JOIN daily_routes dr ON dr.user_id = tr.user_id
            ORDER BY tr.total_routes DESC
            """
        ).fetchall()
        con.close()
        data = []
        for i, r in enumerate(rows, 1):
            p = resolve_player(r["user_id"])
            data.append({
                "posicao": i,
                "discord_id": r["user_id"],
                "nome": p["nome"],
                "login": p["login"],
                "total_rotas": r["total_routes"],
                "rotas_hoje": r["daily_routes"],
            })
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# â”€â”€ TICKETS / TRANSCRIPTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _fmt_ts(ts):
    if not ts: return "â€”"
    try:
        if isinstance(ts, (int, float)):
            return datetime.utcfromtimestamp(int(ts)).strftime("%d/%m/%Y %H:%M")
        return str(ts)
    except: return str(ts)

@router.get("/tickets")
async def list_tickets(
    limit: int = Query(100, le=500, ge=1),
    offset: int = Query(0, ge=0),
    _ = Depends(require_scope("references:read"))
):
    try:
        con = master_con()
        rows = con.execute(
            """
            SELECT id, channel_id, opened_by_id, attended_by_id, closed_by_id,
                   opened_at_ts, attended_at_ts, closed_at_ts,
                   ticket_type, transcript_filename, transcript_url,
                   stars, log_message_id
            FROM tickets
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        total = con.execute("SELECT COUNT(1) FROM tickets").fetchone()[0]
        con.close()

        data = []
        for r in rows:
            aberto_por  = resolve_player(r["opened_by_id"])
            atendido_por = resolve_player(r["attended_by_id"])
            data.append({
                "id": r["id"],
                "channel_id": r["channel_id"],
                "aberto_por": aberto_por,
                "atendido_por": atendido_por,
                "aberto_em": _fmt_ts(r["opened_at_ts"]),
                "atendido_em": _fmt_ts(r["attended_at_ts"]),
                "fechado_em": _fmt_ts(r["closed_at_ts"]),
                "tipo": r["ticket_type"] or "Geral",
                "transcript": r["transcript_url"],
                "estrelas": r["stars"]
            })
        res, status = ok({"total": total, "tickets": data})
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

