"""
routes_edital.py â€” Perguntas de Edital Normal e Superior (FastAPI version).
"""
import sqlite3
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.audit import write_audit

router = APIRouter(tags=["Edital"])
_REF = "data/reference_data.db"

def _connect(*, row_factory: bool = False) -> sqlite3.Connection:
    con = sqlite3.connect(_REF)
    con.execute("PRAGMA foreign_keys = ON")
    if row_factory:
        con.row_factory = sqlite3.Row
    return con

# â”€â”€ EDITAL NORMAL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/edital/normal")
async def get_edital_normal(_ = Depends(require_scope("references:read"))):
    try:
        con = _connect(row_factory=True)
        perguntas = con.execute(
            "SELECT id, question_text FROM recruitment_questions ORDER BY id ASC"
        ).fetchall()
        opcoes = con.execute(
            "SELECT id, question_id, option_text, is_correct FROM recruitment_question_options ORDER BY question_id ASC, id ASC"
        ).fetchall()
        con.close()

        opts_map: dict = {}
        for o in opcoes:
            opts_map.setdefault(o["question_id"], []).append({
                "id": o["id"], "texto": o["option_text"], "correta": bool(o["is_correct"])
            })

        data = [{
            "id": q["id"],
            "pergunta": q["question_text"],
            "alternativas": opts_map.get(q["id"], []),
        } for q in perguntas]
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/edital/normal/perguntas")
async def criar_pergunta_normal(request: Request, _ = Depends(require_scope("references:write"))):
    body = await request.json() if await request.body() else {}
    texto = str(body.get("pergunta", "")).strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Campo 'pergunta' obrigatÃ³rio")
    try:
        con = _connect()
        con.execute("INSERT INTO recruitment_questions (question_text) VALUES (?)", (texto,))
        con.commit()
        new_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.close()
        write_audit(status=201, resource_type="edital:pergunta", resource_key=str(new_id), message=f"Pergunta normal criada: {texto}")
        res, status = ok({"id": new_id}, "Pergunta criada", 201)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/edital/normal/perguntas/{qid}")
async def deletar_pergunta_normal(qid: int, _ = Depends(require_scope("references:write"))):
    try:
        con = _connect()
        n = con.execute("DELETE FROM recruitment_questions WHERE id=?", (qid,)).rowcount
        con.commit(); con.close()
        if n == 0:
            raise HTTPException(status_code=404, detail="Pergunta nÃ£o encontrada")
        write_audit(status=200, resource_type="edital:pergunta", resource_key=str(qid), message="Pergunta normal removida")
        res, status = ok(None, "Pergunta removida")
        return res
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

# â”€â”€ EDITAL SUPERIOR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/edital/superior")
async def get_edital_superior(_ = Depends(require_scope("references:read"))):
    try:
        con = _connect(row_factory=True)
        perguntas = con.execute(
            "SELECT id, question_text FROM superior_application_questions ORDER BY id ASC"
        ).fetchall()
        con.close()
        data = [{"id": q["id"], "pergunta": q["question_text"]} for q in perguntas]
        res, status = ok(data)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/edital/superior/perguntas")
async def criar_pergunta_superior(request: Request, _ = Depends(require_scope("references:write"))):
    body = await request.json() if await request.body() else {}
    texto = str(body.get("pergunta", "")).strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Campo 'pergunta' obrigatÃ³rio")
    try:
        con = _connect()
        con.execute("INSERT INTO superior_application_questions (question_text) VALUES (?)", (texto,))
        con.commit()
        new_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.close()
        write_audit(status=201, resource_type="edital:superior", resource_key=str(new_id), message=f"Pergunta superior criada: {texto}")
        res, status = ok({"id": new_id}, "Pergunta criada", 201)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

