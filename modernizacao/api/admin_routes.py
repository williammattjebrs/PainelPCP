from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from app import PERMISSIONS, _db, _now, _scope_center, app, authenticated, require, require_any, transaction


class PermissionUpdate(BaseModel):
    permissions: dict[str, bool]
    centers: dict[str, bool] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=1000)


class MonthlyObjectiveInput(BaseModel):
    cd: str
    grupo: str
    indicador: str
    codigo_indicador: str | None = None
    mes_ref: str
    valor_objetivo: float
    direcao_meta: str = "maior_melhor"
    tolerancia_amarela: float = 0.05
    motivo: str = Field(min_length=1, max_length=1000)


class ViewInput(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    contexto: str = "global"
    cd: str = "TODOS"
    descricao: str = ""
    items: list[dict[str, Any]]


@app.get("/api/users/{username}/permissions")
def get_user_permissions(username: str, user: dict[str, Any] = Depends(require("manage_users"))):
    conn = _db()
    try:
        exists = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
        if not exists:
            raise HTTPException(404, "Usuário não encontrado.")
        permissions = {r["permission"]: bool(r["enabled"]) for r in conn.execute(
            "SELECT permission,enabled FROM user_permissions WHERE username=?", (username,)
        )}
        centers = {r["cd"]: bool(r["enabled"]) for r in conn.execute(
            "SELECT cd,enabled FROM user_centers WHERE username=?", (username,)
        )}
        return {"username": username, "permissions": permissions, "centers": centers}
    finally:
        conn.close()


@app.put("/api/users/{username}/permissions")
def update_user_permissions(
    username: str,
    body: PermissionUpdate,
    user: dict[str, Any] = Depends(require("manage_users")),
):
    unknown = set(body.permissions) - set(PERMISSIONS)
    if unknown:
        raise HTTPException(422, {"message": "Permissões desconhecidas.", "values": sorted(unknown)})
    now = _now()
    with transaction() as conn:
        exists = conn.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
        if not exists:
            raise HTTPException(404, "Usuário não encontrado.")
        valid_centers = {r[0] for r in conn.execute("SELECT code FROM centers")}
        unknown_centers = set(body.centers) - valid_centers
        if unknown_centers:
            raise HTTPException(422, {"message": "CDs desconhecidos.", "values": sorted(unknown_centers)})
        for permission, enabled in body.permissions.items():
            old = conn.execute("SELECT enabled FROM user_permissions WHERE username=? AND permission=?", (username,permission)).fetchone()
            old_value = int(old["enabled"]) if old else 0
            new_value = int(enabled)
            conn.execute(
                "INSERT INTO user_permissions(username,permission,enabled,updated_by,updated_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(username,permission) DO UPDATE SET enabled=excluded.enabled,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                (username,permission,new_value,user["username"],now),
            )
            if old_value != new_value:
                conn.execute(
                    "INSERT INTO config_audit(entidade,campo,valor_anterior,valor_novo,motivo,changed_by,changed_at) VALUES(?,?,?,?,?,?,?)",
                    ("user_permission",username+":"+permission,str(old_value),str(new_value),body.reason,user["username"],now),
                )
        for cd, enabled in body.centers.items():
            old = conn.execute("SELECT enabled FROM user_centers WHERE username=? AND cd=?", (username,cd)).fetchone()
            old_value = int(old["enabled"]) if old else 0
            new_value = int(enabled)
            conn.execute(
                "INSERT INTO user_centers(username,cd,enabled) VALUES(?,?,?) "
                "ON CONFLICT(username,cd) DO UPDATE SET enabled=excluded.enabled",
                (username,cd,new_value),
            )
            if old_value != new_value:
                conn.execute(
                    "INSERT INTO config_audit(entidade,campo,valor_anterior,valor_novo,motivo,changed_by,changed_at) VALUES(?,?,?,?,?,?,?)",
                    ("user_center",username+":"+cd,str(old_value),str(new_value),body.reason,user["username"],now),
                )
    return {"saved": True, "audited": True}


@app.get("/api/monthly-objectives")
def list_monthly_objectives(cd: str | None = None, mes_ref: str | None = None, user: dict[str, Any] = Depends(require_any("view_monthly", "configure_targets"))):
    _scope_center(user, cd)
    conn = _db()
    try:
        clauses, args = [], []
        if cd:
            clauses.append("cd=?"); args.append(cd)
        elif user["role"] != "admin" and user["centers"]:
            clauses.append("cd IN (" + ",".join("?" for _ in user["centers"]) + ")"); args.extend(user["centers"])
        if mes_ref:
            clauses.append("mes_ref=?"); args.append(mes_ref)
        sql = "SELECT * FROM monthly_objectives" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY mes_ref DESC,cd,grupo,indicador"
        return [dict(r) for r in conn.execute(sql,args)]
    finally:
        conn.close()


@app.post("/api/monthly-objectives")
def save_monthly_objective(body: MonthlyObjectiveInput, user: dict[str, Any] = Depends(require("configure_targets"))):
    _scope_center(user, body.cd)
    now = _now()
    with transaction() as conn:
        old = conn.execute(
            "SELECT * FROM monthly_objectives WHERE cd=? AND grupo=? AND indicador=? AND mes_ref=?",
            (body.cd,body.grupo,body.indicador,body.mes_ref),
        ).fetchone()
        conn.execute(
            "INSERT INTO monthly_objectives(cd,grupo,indicador,codigo_indicador,mes_ref,valor_objetivo,direcao_meta,tolerancia_amarela,active,motivo,created_by,created_at,updated_by,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,1,?,?,?,?,?) ON CONFLICT(cd,grupo,indicador,mes_ref) DO UPDATE SET "
            "codigo_indicador=excluded.codigo_indicador,valor_objetivo=excluded.valor_objetivo,direcao_meta=excluded.direcao_meta,"
            "tolerancia_amarela=excluded.tolerancia_amarela,active=1,motivo=excluded.motivo,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
            (body.cd,body.grupo,body.indicador,body.codigo_indicador,body.mes_ref,body.valor_objetivo,body.direcao_meta,
             body.tolerancia_amarela,body.motivo,user["username"],now,user["username"],now),
        )
        conn.execute(
            "INSERT INTO config_audit(entidade,cd,grupo,indicador,campo,valor_anterior,valor_novo,motivo,changed_by,changed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("monthly_objectives",body.cd,body.grupo,body.indicador,body.mes_ref,
             str(old["valor_objetivo"]) if old else "",str(body.valor_objetivo),body.motivo,user["username"],now),
        )
    return {"saved": True, "mes_ref": body.mes_ref, "audited": True}


@app.get("/api/visualization-views")
def list_views(contexto: str = "global", cd: str = "TODOS", user: dict[str, Any] = Depends(authenticated)):
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT * FROM visualization_views WHERE active=1 AND contexto IN ('global',?) AND cd IN (?, 'TODOS') ORDER BY nome",
            (contexto,cd),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/visualization-views/{view_id}")
def get_view(view_id: int, user: dict[str, Any] = Depends(authenticated)):
    conn = _db()
    try:
        view = conn.execute("SELECT * FROM visualization_views WHERE id=? AND active=1",(view_id,)).fetchone()
        if not view:
            raise HTTPException(404,"Visão não encontrada.")
        items = conn.execute("SELECT * FROM visualization_view_items WHERE view_id=? ORDER BY sort_order",(view_id,)).fetchall()
        return {"view":dict(view),"items":[dict(r) for r in items]}
    finally:
        conn.close()


@app.post("/api/visualization-views")
def save_view(body: ViewInput, user: dict[str, Any] = Depends(require("configure_indicators"))):
    if body.contexto not in {"global","matricial","dashboard","mensal"}:
        raise HTTPException(422,"Contexto de visão inválido.")
    _scope_center(user, body.cd if body.cd != "TODOS" else None)
    if not body.items:
        raise HTTPException(422,"Selecione ao menos um indicador.")
    now = _now()
    with transaction() as conn:
        conn.execute(
            "INSERT INTO visualization_views(nome,contexto,cd,descricao,active,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,1,?,?,?,?) "
            "ON CONFLICT(nome,contexto,cd) DO UPDATE SET descricao=excluded.descricao,active=1,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
            (body.nome,body.contexto,body.cd,body.descricao,user["username"],now,user["username"],now),
        )
        row = conn.execute("SELECT id FROM visualization_views WHERE nome=? AND contexto=? AND cd=?",(body.nome,body.contexto,body.cd)).fetchone()
        view_id = int(row["id"])
        conn.execute("DELETE FROM visualization_view_items WHERE view_id=?",(view_id,))
        for order,item in enumerate(body.items,1):
            conn.execute(
                "INSERT INTO visualization_view_items(view_id,cd,grupo,indicador,codigo_indicador,sort_order) VALUES(?,?,?,?,?,?)",
                (view_id,str(item.get("cd") or body.cd),str(item["grupo"]),str(item["indicador"]),item.get("codigo_indicador"),order),
            )
        conn.execute(
            "INSERT INTO config_audit(entidade,cd,campo,valor_novo,motivo,changed_by,changed_at) VALUES(?,?,?,?,?,?,?)",
            ("visualization_view",body.cd,body.contexto,body.nome,body.descricao or "Configuração de visão",user["username"],now),
        )
    return {"id":view_id,"saved":True}


@app.delete("/api/visualization-views/{view_id}")
def deactivate_view(view_id: int, user: dict[str, Any] = Depends(require("configure_indicators"))):
    with transaction() as conn:
        view = conn.execute("SELECT * FROM visualization_views WHERE id=?",(view_id,)).fetchone()
        if not view:
            raise HTTPException(404,"Visão não encontrada.")
        conn.execute("UPDATE visualization_views SET active=0,updated_by=?,updated_at=? WHERE id=?",(user["username"],_now(),view_id))
        conn.execute(
            "INSERT INTO config_audit(entidade,cd,campo,valor_anterior,valor_novo,motivo,changed_by,changed_at) VALUES(?,?,?,?,?,?,?,?)",
            ("visualization_view",view["cd"],view["contexto"],"1","0","Inativação de visão",user["username"],_now()),
        )
    return {"deactivated":True}
