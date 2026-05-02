"""
routes_players.py â€” CRUD de jogadores (FastAPI version).
"""
import sqlite3
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.audit import write_audit
from app.helpers import master_con

router = APIRouter(tags=["Players"])

_MASTER = "data/master_data.db"

@router.get("/players")
async def list_players(_ = Depends(require_scope("references:read"))):
    try:
        con = master_con()
        rows = con.execute(
            "SELECT id, playerName, playerLogin, playerID, discordUserID FROM players ORDER BY id ASC"
        ).fetchall()
        con.close()
        data = [{"id": r["id"], "nome": r["playerName"], "login": r["playerLogin"],
                 "game_id": str(r["playerID"]) if r["playerID"] else None, 
                 "discord_id": str(r["discordUserID"]) if r["discordUserID"] else None} for r in rows]
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/players/{pid}")
async def get_player(pid: int, _ = Depends(require_scope("references:read"))):
    try:
        con = master_con()
        p = con.execute(
            "SELECT id,playerName,playerLogin,playerID,discordUserID FROM players WHERE id=?", (pid,)
        ).fetchone()
        if not p:
            con.close()
            raise HTTPException(status_code=404, detail="Jogador nÃ£o encontrado")
        discord_id = p["discordUserID"]
        h_row = con.execute(
            "SELECT total_hours FROM player_total_hours WHERE user_id=?", (discord_id,)
        ).fetchone()
        pt_row = con.execute(
            "SELECT total_points FROM player_points WHERE discord_id=?", (discord_id,)
        ).fetchone()
        con.close()
        data = {
            "id": p["id"], "nome": p["playerName"], "login": p["playerLogin"],
            "game_id": str(p["playerID"]) if p["playerID"] else None,
            "discord_id": str(discord_id) if discord_id else None,
            "horas_totais": h_row["total_hours"] if h_row else "0",
            "pontos": pt_row["total_points"] if pt_row else 0,
        }
        res, status = ok(data)
        return res
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/players")
async def create_player(request: Request, _ = Depends(require_scope("references:write"))):
    body = await request.json() if await request.body() else {}
    nome  = str(body.get("nome", "")).strip()
    login = str(body.get("login", "")).strip()
    game_id      = body.get("game_id")
    discord_id   = body.get("discord_id")
    if not nome or not login:
        raise HTTPException(status_code=400, detail="Campos obrigatÃ³rios: nome, login")
    try:
        con = sqlite3.connect(_MASTER)
        con.execute(
            "INSERT INTO players (playerName, playerLogin, playerID, discordUserID) VALUES (?,?,?,?)",
            (nome, login, game_id, discord_id),
        )
        con.commit()
        new_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.close()
        write_audit(status=201, resource_type="players", resource_key=str(new_id),
                    new_value={"nome": nome, "login": login}, message="Jogador criado")
        res, status = ok({"id": new_id}, "Jogador criado", 201)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/players/{pid}")
async def update_player(pid: int, request: Request, _ = Depends(require_scope("references:write"))):
    body = await request.json() if await request.body() else {}
    try:
        con = sqlite3.connect(_MASTER)
        exists = con.execute("SELECT 1 FROM players WHERE id=?", (pid,)).fetchone()
        if not exists:
            con.close()
            raise HTTPException(status_code=404, detail="Jogador nÃ£o encontrado")
        
        updates, params = [], []
        mapping = {"nome": "playerName", "login": "playerLogin", "game_id": "playerID", "discord_id": "discordUserID"}
        for k, v in mapping.items():
            if k in body:
                updates.append(f"{v} = ?")
                params.append(body[k])
        
        if updates:
            params.append(pid)
            con.execute(f"UPDATE players SET {', '.join(updates)} WHERE id=?", params)
            con.commit()
        
        con.close()
        write_audit(status=200, resource_type="players", resource_key=str(pid), message="Jogador atualizado")
        res, status = ok(None, "Jogador atualizado")
        return res
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/players/{pid}")
async def delete_player(pid: int, _ = Depends(require_scope("references:write"))):
    try:
        con = sqlite3.connect(_MASTER)
        n = con.execute("DELETE FROM players WHERE id=?", (pid,)).rowcount
        con.commit()
        con.close()
        if n == 0:
            raise HTTPException(status_code=404, detail="Jogador nÃ£o encontrado")
        write_audit(status=200, resource_type="players", resource_key=str(pid), message="Jogador removido")
        res, status = ok(None, "Jogador removido")
        return res
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

