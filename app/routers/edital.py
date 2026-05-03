from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
from app.core.security import get_api_key
from app.services.sqlite_engine import reference_service
from app.core.audit import audit_log

router = APIRouter(prefix="/bots/{app_id}/edital", tags=["Edital"])

class OptionCreate(BaseModel):
    texto: str
    correta: bool = False

class QuestionCreate(BaseModel):
    pergunta: str
    options: Optional[List[OptionCreate]] = None

class OptionUpdate(BaseModel):
    id: Optional[int] = None
    texto: str
    correta: bool

class QuestionUpdate(BaseModel):
    pergunta: str
    options: Optional[List[OptionUpdate]] = None

# --- EDITAL NORMAL ---

@router.get("/normal", dependencies=[Depends(get_api_key)])
async def get_edital_normal(app_id: str):
    audit_log(app_id, "GET_EDITAL_NORMAL", "Fetching recruitment questions and options")
    
    perguntas_query = "SELECT id, question_text FROM recruitment_questions ORDER BY id ASC"
    opcoes_query = "SELECT id, question_id, option_text, is_correct FROM recruitment_question_options ORDER BY question_id ASC, id ASC"
    
    perguntas = await reference_service.execute_query(app_id, perguntas_query)
    opcoes = await reference_service.execute_query(app_id, opcoes_query)
    
    opts_map = {}
    for o in opcoes:
        qid = o["question_id"]
        if qid not in opts_map:
            opts_map[qid] = []
        opts_map[qid].append({
            "id": o["id"],
            "texto": o["option_text"],
            "correta": bool(o["is_correct"])
        })
        
    data = []
    for q in perguntas:
        data.append({
            "id": q["id"],
            "pergunta": q["question_text"],
            "alternativas": opts_map.get(q["id"], [])
        })
        
    return {"ok": True, "data": data}

@router.post("/normal/perguntas", dependencies=[Depends(get_api_key)])
async def create_edital_normal_question(app_id: str, question: QuestionCreate):
    audit_log(app_id, "CREATE_EDITAL_NORMAL", f"New question: {question.pergunta[:50]}...")
    
    # 1. Inserir a pergunta
    query_q = "INSERT INTO recruitment_questions (question_text) VALUES (?)"
    await reference_service.execute_update(app_id, query_q, (question.pergunta,))
    
    # Pegar o ID da pergunta recém criada
    res = await reference_service.execute_query(app_id, "SELECT id FROM recruitment_questions WHERE question_text = ? ORDER BY id DESC LIMIT 1", (question.pergunta,))
    if not res:
        raise HTTPException(status_code=500, detail="Erro ao recuperar ID da pergunta criada")
    
    question_id = res[0]["id"]
    
    # 2. Inserir alternativas se houver
    if question.options:
        for opt in question.options:
            query_o = "INSERT INTO recruitment_question_options (question_id, option_text, is_correct) VALUES (?, ?, ?)"
            await reference_service.execute_update(app_id, query_o, (question_id, opt.texto, 1 if opt.correta else 0))
            
    return {"ok": True, "message": "Pergunta e alternativas criadas com sucesso", "id": question_id}

@router.put("/normal/perguntas/{qid}", dependencies=[Depends(get_api_key)])
async def update_edital_normal_question(app_id: str, qid: int, question: QuestionUpdate):
    audit_log(app_id, "UPDATE_EDITAL_NORMAL", f"Updating question ID: {qid}")
    
    # 1. Atualizar texto da pergunta
    await reference_service.execute_update(app_id, "UPDATE recruitment_questions SET question_text = ? WHERE id = ?", (question.pergunta, qid))
    
    # 2. Atualizar alternativas
    if question.options is not None:
        await reference_service.execute_update(app_id, "DELETE FROM recruitment_question_options WHERE question_id = ?", (qid,))
        for opt in question.options:
            query_o = "INSERT INTO recruitment_question_options (question_id, option_text, is_correct) VALUES (?, ?, ?)"
            await reference_service.execute_update(app_id, query_o, (qid, opt.texto, 1 if opt.correta else 0))
            
    return {"ok": True, "message": "Pergunta atualizada com sucesso"}

@router.delete("/normal/perguntas/{qid}", dependencies=[Depends(get_api_key)])
async def delete_edital_normal_question(app_id: str, qid: int):
    audit_log(app_id, "DELETE_EDITAL_NORMAL", f"Deleting question ID: {qid}")
    # O DELETE CASCADE deve cuidar das opções se o banco estiver configurado, mas garantimos manualmente também
    await reference_service.execute_update(app_id, "DELETE FROM recruitment_question_options WHERE question_id = ?", (qid,))
    await reference_service.execute_update(app_id, "DELETE FROM recruitment_questions WHERE id = ?", (qid,))
    return {"ok": True, "message": "Pergunta removida com sucesso"}

# --- EDITAL SUPERIOR ---

@router.get("/superior", dependencies=[Depends(get_api_key)])
async def get_edital_superior(app_id: str):
    audit_log(app_id, "GET_EDITAL_SUPERIOR", "Fetching superior application questions")
    query = "SELECT id, question_text FROM superior_application_questions ORDER BY id ASC"
    data = await reference_service.execute_query(app_id, query)
    return {"ok": True, "data": [{"id": d["id"], "pergunta": d["question_text"]} for d in data]}

@router.post("/superior/perguntas", dependencies=[Depends(get_api_key)])
async def create_edital_superior_question(app_id: str, question: QuestionCreate):
    audit_log(app_id, "CREATE_EDITAL_SUPERIOR", f"New superior question: {question.pergunta[:50]}...")
    query = "INSERT INTO superior_application_questions (question_text) VALUES (?)"
    await reference_service.execute_update(app_id, query, (question.pergunta,))
    return {"ok": True, "message": "Pergunta de edital superior criada"}

@router.put("/superior/perguntas/{qid}", dependencies=[Depends(get_api_key)])
async def update_edital_superior_question(app_id: str, qid: int, question: QuestionCreate):
    audit_log(app_id, "UPDATE_EDITAL_SUPERIOR", f"Updating superior question ID: {qid}")
    query = "UPDATE superior_application_questions SET question_text = ? WHERE id = ?"
    await reference_service.execute_update(app_id, query, (question.pergunta, qid))
    return {"ok": True, "message": "Pergunta de edital superior atualizada"}

@router.delete("/superior/perguntas/{qid}", dependencies=[Depends(get_api_key)])
async def delete_edital_superior_question(app_id: str, qid: int):
    audit_log(app_id, "DELETE_EDITAL_SUPERIOR", f"Deleting superior question ID: {qid}")
    query = "DELETE FROM superior_application_questions WHERE id = ?"
    await reference_service.execute_update(app_id, query, (qid,))
    return {"ok": True, "message": "Pergunta de edital superior removida"}
