"""
routes_references.py â€” CRUD de referÃªncias com escopos, validaÃ§Ã£o e auditoria forte (FastAPI version).
"""
import sqlite3, os, sys
from fastapi import APIRouter, Request, HTTPException, Depends, Path
from typing import Optional, List, Dict, Any
from app.auth import require_scope
from app.responses import ok, err
from app.audit import write_audit
from app.validators import validate_reference, PROTECTED_FIELDS

router = APIRouter(tags=["References"])
_REFERENCE_DB = "data/reference_data.db"

_KV_TABLES = {"users","cargos_gerais","chats_gerais","calls","categorias_gerais","logs"}
_SINGLE_TABLES = {
    "configuracoes_organizacao": ["sigla","nome","tag","tag_change","tipo","mudar_tag"],
    "configuracoes_servidor":    ["guild_id","store_id","pontos_origem_server","pontos_origem_canal"],
    "configuracoes_plano":       ["premium","cliente","vencimento","pix_copia_e_cola"],
    "configuracoes_e_numeros":   ["acertos_minimos_edital","meta_diaria_rotas","delay_rotas","margem_horas_upamento"],
}
_HIERARCHY_TABLE = "hierarquia"
ALL_TABLES = _KV_TABLES | set(_SINGLE_TABLES) | {_HIERARCHY_TABLE}

def _con(): return sqlite3.connect(_REFERENCE_DB)

def _read_kv(t):
    con = _con()
    try:
        rows = con.execute(f"SELECT key_name,value FROM {t}").fetchall()
        return {str(r[0]): r[1] for r in rows}
    finally: con.close()

def _read_single(t, cols):
    con = _con()
    try:
        row = con.execute(f"SELECT {','.join(cols)} FROM {t} ORDER BY id LIMIT 1").fetchone()
        return {cols[i]: row[i] for i in range(len(cols))} if row else {c: None for c in cols}
    finally: con.close()

def _read_hierarchy():
    con = _con()
    try:
        rows = con.execute("SELECT hierarchy_index,cargo_id,nome,sigla,horas FROM hierarquia ORDER BY hierarchy_index").fetchall()
        return [{"hierarchy_index":r[0],"cargo_id":r[1],"nome":r[2],"sigla":r[3],"horas":r[4]} for r in rows]
    finally: con.close()

def _write_kv(t, key, val):
    con = _con()
    try:
        con.execute(f"INSERT INTO {t}(key_name,value)VALUES(?,?) ON CONFLICT(key_name) DO UPDATE SET value=excluded.value", (key, val))
        con.commit()
    finally: con.close()

def _write_single(t, col, val):
    con = _con()
    try:
        con.execute(f"INSERT OR IGNORE INTO {t}(id) VALUES(1)")
        con.execute(f"UPDATE {t} SET {col}=? WHERE id=1", (val,))
        con.commit()
    finally: con.close()

@router.get("/references")
async def get_all_references(_ = Depends(require_scope("references:read"))):
    data = {}
    for t in _KV_TABLES: data[t] = _read_kv(t)
    for t, cols in _SINGLE_TABLES.items(): data[t] = _read_single(t, cols)
    data["hierarquia"] = _read_hierarchy()
    res, status = ok(data)
    return res

@router.get("/references/{table}")
async def get_table_references(table: str, _ = Depends(require_scope("references:read"))):
    if table not in ALL_TABLES:
        raise HTTPException(status_code=404, detail=f"Tabela '{table}' inexistente")
    if table in _KV_TABLES: data = _read_kv(table)
    elif table in _SINGLE_TABLES: data = _read_single(table, _SINGLE_TABLES[table])
    else: data = _read_hierarchy()
    res, status = ok(data)
    return res

@router.get("/references/{table}/{key}")
async def get_reference_key(table: str, key: str, _ = Depends(require_scope("references:read"))):
    if table not in (_KV_TABLES | set(_SINGLE_TABLES)):
        raise HTTPException(status_code=404, detail="OperaÃ§Ã£o suportada apenas para tabelas KV ou Single")
    if table in _KV_TABLES:
        val = _read_kv(table).get(key)
    else:
        if key not in _SINGLE_TABLES[table]:
            raise HTTPException(status_code=404, detail=f"Campo '{key}' inexistente na tabela '{table}'")
        val = _read_single(table, _SINGLE_TABLES[table]).get(key)
    res, status = ok(val)
    return res

@router.put("/references/{table}/{key}")
async def update_reference(table: str, key: str, request: Request, _ = Depends(require_scope("references:write"))):
    if table not in (_KV_TABLES | set(_SINGLE_TABLES)):
        raise HTTPException(status_code=404, detail="EdiÃ§Ã£o direta suportada apenas para tabelas KV ou Single")
    
    body = await request.json()
    new_val = body.get("value")
    if new_val is None:
        raise HTTPException(status_code=400, detail="Campo 'value' obrigatÃ³rio no body")
    
    # ValidaÃ§Ãµes extras (pode levantar exceÃ§Ã£o)
    validate_reference(table, key, new_val)
    
    # Auditoria (valor antigo)
    old_v = None
    try:
        if table in _KV_TABLES: old_v = _read_kv(table).get(key)
        else: old_v = _read_single(table, _SINGLE_TABLES[table]).get(key)
    except: pass

    if table in _KV_TABLES: _write_kv(table, key, new_val)
    else: _write_single(table, key, new_val)

    write_audit(status=200, resource_type=f"ref:{table}", resource_key=key, 
                old_value=old_v, new_value=new_val, message=f"ReferÃªncia {table}/{key} atualizada")
    
    res, status = ok(new_val, "ReferÃªncia atualizada")
    return res

@router.post("/reload/references")
async def reload_references(_ = Depends(require_scope("reload:run"))):
    # No FastAPI, o reload de referÃªncias pode ser apenas um sinal de sucesso se nÃ£o houver cache em memÃ³ria global
    write_audit(status=200, resource_type="system", resource_key="reload", message="Reload de referÃªncias solicitado")
    res, status = ok(None, "ReferÃªncias recarregadas")
    return res

