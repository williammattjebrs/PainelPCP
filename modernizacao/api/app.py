from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import os
import sqlite3
import time

import pandas as pd
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parents[1]
DB_PATH = Path(os.getenv("PCP_DB_PATH", APP_DIR / "runtime" / "indicadores_teste.db"))
if not DB_PATH.is_absolute():
    DB_PATH = (Path.cwd() / DB_PATH).resolve()
PRODUCTION_DB = (ROOT / "data" / "indicadores.db").resolve()
TOKEN_TTL_SECONDS = 8 * 60 * 60
PERMISSIONS = {
    "view_matrix": "Ver Painel Diário de Indicadores",
    "view_dashboard": "Ver Dashboard Executivo",
    "view_daily": "Ver Visão Dia a Dia",
    "view_monthly": "Ver Visão Mensal",
    "import_data": "Importar Dados",
    "edit_data": "Editar Dados Diários",
    "configure_indicators": "Configurar Indicadores",
    "configure_targets": "Configurar Metas",
    "configure_calculations": "Configurar Cálculos",
    "manage_centers": "Gerir CDs",
    "manage_users": "Gerir Usuários",
    "view_audit": "Ver Auditoria",
    "export_reports": "Exportar Relatórios",
}
REQUIRED_TABLES = {
    "users", "user_permissions", "user_centers", "centers", "values_indicators",
    "work_calendar", "audit_changes", "imports", "indicator_config", "target_versions",
    "monthly_objectives", "config_audit",
}

app = FastAPI(title="Painel PCP API — Preview", version="0.1.0")
origins = [x.strip() for x in os.getenv("PCP_CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def _db() -> sqlite3.Connection:
    if DB_PATH.resolve() == PRODUCTION_DB:
        raise HTTPException(503, "A API de preview não pode abrir o banco operacional.")
    if not DB_PATH.is_file():
        raise HTTPException(503, "Banco de teste ausente. Rode scripts/copy_test_db.py.")
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def transaction():
    conn = _db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(503, f"Configure {name} em arquivo local não versionado.")
    return value


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _password_hash(password: str) -> str:
    salt = os.urandom(16)
    iterations = 600_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256$" + str(iterations) + "$" + base64.urlsafe_b64encode(salt).decode().rstrip("=") + "$" + base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _verify_password(stored: str, password: str) -> tuple[bool, bool]:
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt_text, digest_text = stored.split("$", 3)
            salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
            expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
            return hmac.compare_digest(expected, actual), False
        except Exception:
            return False, False
    legacy_salt = _secret("PCP_PASSWORD_SALT")
    legacy = hashlib.sha256(f"{legacy_salt}:{password}".encode()).hexdigest()
    return hmac.compare_digest(stored, legacy), True


def _token(username: str) -> str:
    payload = json.dumps({"sub": username, "exp": int(time.time()) + TOKEN_TTL_SECONDS}, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(_secret("PCP_AUTH_SECRET").encode(), encoded.encode(), hashlib.sha256).digest()
    return encoded + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


def _decode_token(token: str) -> str:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(_secret("PCP_AUTH_SECRET").encode(), encoded.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, actual):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        return str(payload["sub"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Sessão inválida ou expirada.")


def _user(username: str) -> dict[str, Any]:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT username, full_name, role, active FROM users WHERE username=?",
            (username,),
        ).fetchone()
        if not row or not row["active"]:
            raise HTTPException(401, "Usuário inativo ou inexistente.")
        permissions = [r[0] for r in conn.execute(
            "SELECT permission FROM user_permissions WHERE username=? AND enabled=1", (username,)
        ).fetchall()]
        centers = [r[0] for r in conn.execute(
            "SELECT cd FROM user_centers WHERE username=? AND enabled=1 ORDER BY cd", (username,)
        ).fetchall()]
        if not centers:
            centers = [r[0] for r in conn.execute("SELECT code FROM centers WHERE active=1 ORDER BY code").fetchall()]
        return {**dict(row), "permissions": permissions, "centers": centers}
    finally:
        conn.close()


def current_user(authorization: str | None = None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Autenticação necessária.")
    return _user(_decode_token(authorization[7:].strip()))


def authenticated(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    return current_user(authorization)


def require(permission: str):
    def check(user: dict[str, Any] = Depends(authenticated)) -> dict[str, Any]:
        if user["role"] != "admin" and permission not in user["permissions"]:
            raise HTTPException(403, "Sem permissão para esta operação.")
        return user
    return check



def require_any(*permissions: str):
    def check(user: dict[str, Any] = Depends(authenticated)) -> dict[str, Any]:
        if user["role"] != "admin" and not any(p in user["permissions"] for p in permissions):
            raise HTTPException(403, "Sem permissão para esta operação.")
        return user
    return check


def _scope_center(user: dict[str, Any], cd: str | None) -> None:
    if cd and user["role"] != "admin" and cd not in user["centers"]:
        raise HTTPException(403, "CD fora do escopo deste usuário.")


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _verify_database() -> dict[str, Any]:
    if DB_PATH.resolve() == PRODUCTION_DB:
        return {"ok": False, "reason": "production_path"}
    if not DB_PATH.is_file():
        return {"ok": False, "reason": "test_database_missing", "path": str(DB_PATH)}
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        tables = _tables(conn)
        absent = sorted(REQUIRED_TABLES - tables)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if absent or integrity != "ok":
            return {"ok": False, "reason": "invalid_database", "missing_tables": absent, "integrity": integrity}
        return {"ok": True, "integrity": integrity, "table_count": len(tables)}
    finally:
        conn.close()


@app.on_event("startup")
def startup_check() -> None:
    health = _verify_database()
    if not health["ok"]:
        raise RuntimeError(f"Banco de preview inválido ou ausente: {health}")


class LoginInput(BaseModel):
    username: str
    password: str


class CorrectionInput(BaseModel):
    value: float | None
    reason: str = Field(min_length=1, max_length=1000)


class TargetInput(BaseModel):
    cd: str
    grupo: str
    indicador: str
    valor_meta: float
    direcao_meta: str = "maior_melhor"
    data_inicio: date
    tolerancia_amarela: float = 0.05
    motivo: str = Field(min_length=1, max_length=1000)


class UserInput(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12)
    role: str = "operador"
    active: bool = True
    centers: list[str] = Field(default_factory=list)


class IndicatorPatch(BaseModel):
    updates: dict[str, Any]
    reason: str = Field(min_length=1, max_length=1000)


def _iso(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


@app.get("/api/health")
def health():
    result = _verify_database()
    if not result["ok"]:
        raise HTTPException(503, result)
    return {"status": "ok", "mode": "local-preview", "database": result}


@app.post("/api/auth/login")
def login(body: LoginInput):
    conn = _db()
    try:
        row = conn.execute(
            "SELECT username, password_hash FROM users WHERE username=? AND active=1",
            (body.username.strip().lower(),),
        ).fetchone()
        if not row:
            raise HTTPException(401, "Usuário ou senha inválidos.")
        valid, legacy = _verify_password(str(row["password_hash"]), body.password)
        if not valid:
            raise HTTPException(401, "Usuário ou senha inválidos.")
        if legacy:
            conn.execute("UPDATE users SET password_hash=? WHERE username=?", (_password_hash(body.password), row["username"]))
            conn.commit()
    finally:
        conn.close()
    return {"access_token": _token(row["username"]), "token_type": "bearer", "user": _user(row["username"])}


@app.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(authenticated)):
    return user


@app.get("/api/centers")
def centers(user: dict[str, Any] = Depends(authenticated)):
    conn = _db()
    try:
        rows = conn.execute("SELECT code, name, active, is_default FROM centers ORDER BY code").fetchall()
        return [dict(r) for r in rows if user["role"] == "admin" or r["code"] in user["centers"]]
    finally:
        conn.close()


@app.post("/api/centers")
def save_center(body: dict[str, Any], user: dict[str, Any] = Depends(require("manage_centers"))):
    code, name = str(body.get("code", "")).strip().upper(), str(body.get("name", "")).strip()
    if not code or not name:
        raise HTTPException(422, "Código e nome do CD são obrigatórios.")
    with transaction() as conn:
        conn.execute(
            "INSERT INTO centers(code,name,active,created_at,created_by) VALUES(?,?,1,?,?) "
            "ON CONFLICT(code) DO UPDATE SET name=excluded.name, active=1",
            (code, name, _now(), user["username"]),
        )
    return {"code": code, "name": name}


@app.get("/api/indicators")
def indicators(cd: str | None = None, active_only: bool = True, user: dict[str, Any] = Depends(require_any("view_matrix", "view_dashboard", "view_daily", "view_monthly", "configure_indicators"))):
    _scope_center(user, cd)
    conn = _db()
    try:
        where, args = [], []
        if cd:
            where.append("cd=?"); args.append(cd)
        if active_only:
            where.append("ativo=1")
        sql = "SELECT * FROM indicator_config"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY cd, grupo_ordem, grupo, indicador_ordem, indicador"
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


@app.get("/api/values")
def values(
    cd: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(default=5000, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
    user: dict[str, Any] = Depends(require_any("view_matrix", "view_dashboard", "view_daily", "view_monthly")),
):
    _scope_center(user, cd)
    conn = _db()
    try:
        where, args = [], []
        if cd:
            where.append("cd=?"); args.append(cd)
        elif user["role"] != "admin" and user["centers"]:
            where.append("cd IN (" + ",".join("?" for _ in user["centers"]) + ")")
            args.extend(user["centers"])
        if start:
            where.append("data>=?"); args.append(start)
        if end:
            where.append("data<=?"); args.append(end)
        sql = "SELECT * FROM values_indicators"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY data DESC, cd, grupo, indicador LIMIT ? OFFSET ?"
        args.extend([limit, offset])
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


@app.get("/api/dashboard/summary")
def dashboard_summary(cd: str | None = None, day: str | None = None, user: dict[str, Any] = Depends(require("view_dashboard"))):
    day = day or date.today().isoformat()
    _scope_center(user, cd)
    conn = _db()
    try:
        where = ["data=?"]; args: list[Any] = [day]
        if cd:
            where.append("cd=?"); args.append(cd)
        elif user["role"] != "admin" and user["centers"]:
            where.append("cd IN (" + ",".join("?" for _ in user["centers"]) + ")")
            args.extend(user["centers"])
        rows = conn.execute(
            "SELECT cd, grupo, indicador, codigo_indicador, valor, source, updated_at "
            "FROM values_indicators WHERE " + " AND ".join(where) + " ORDER BY cd, grupo, indicador",
            args,
        ).fetchall()
        return {"day": day, "rows": [dict(r) for r in rows], "row_count": len(rows)}
    finally:
        conn.close()


@app.get("/api/audit")
def audit(limit: int = Query(1000, ge=1, le=10000), user: dict[str, Any] = Depends(require("view_audit"))):
    conn = _db()
    try:
        return {
            "data": [dict(r) for r in conn.execute("SELECT * FROM audit_changes ORDER BY changed_at DESC LIMIT ?", (limit,))],
            "configuration": [dict(r) for r in conn.execute("SELECT * FROM config_audit ORDER BY changed_at DESC LIMIT ?", (limit,))],
            "imports": [dict(r) for r in conn.execute("SELECT * FROM imports ORDER BY imported_at DESC LIMIT ?", (limit,))],
        }
    finally:
        conn.close()


@app.put("/api/values/{row_id}")
def correct_value(row_id: int, body: CorrectionInput, user: dict[str, Any] = Depends(require("edit_data"))):
    with transaction() as conn:
        old = conn.execute("SELECT * FROM values_indicators WHERE id=?", (row_id,)).fetchone()
        if not old:
            raise HTTPException(404, "Registro não encontrado.")
        _scope_center(user, old["cd"])
        now = _now()
        conn.execute(
            "UPDATE values_indicators SET valor=?, updated_by=?, updated_at=? WHERE id=?",
            (body.value, user["username"], now, row_id),
        )
        conn.execute(
            "INSERT INTO audit_changes(data,cd,grupo,indicador,valor_anterior,valor_novo,motivo,changed_by,changed_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (old["data"], old["cd"], old["grupo"], old["indicador"], old["valor"], body.value, body.reason, user["username"], now),
        )
    return {"id": row_id, "value": body.value, "audited": True}


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip().replace("R$", "").replace("%", "").strip()
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _normalize_import_rows(raw_rows: list[dict[str, Any]], conn: sqlite3.Connection, user: dict[str, Any]):
    config = conn.execute(
        "SELECT cd, grupo, indicador, codigo_indicador, tipo_campo, ativo FROM indicator_config"
    ).fetchall()
    by_code = {(r["cd"], str(r["codigo_indicador"] or "").upper()): dict(r) for r in config}
    by_name = {(r["cd"], r["grupo"], r["indicador"]): dict(r) for r in config}
    accepted, rejected = [], []
    for row in raw_rows:
        row = {str(k).strip().lower(): v for k, v in row.items()}
        raw_date = str(row.get("data") or row.get("date") or "").strip()
        try:
            parsed_date = (datetime.strptime(raw_date[:10], "%d/%m/%Y").date() if "/" in raw_date else datetime.fromisoformat(raw_date[:10]).date()).isoformat()
        except ValueError:
            rejected.append({"row": row, "reason": "Data inválida"}); continue
        cd = str(row.get("cd") or "").strip().upper()
        code = str(row.get("codigo_indicador") or row.get("codigo") or "").strip().upper()
        group = str(row.get("grupo") or "").strip()
        indicator = str(row.get("indicador") or "").strip()
        cfg = by_code.get((cd, code)) if code else None
        if not cfg:
            cfg = by_name.get((cd, group, indicator))
        if not cfg:
            rejected.append({"row": row, "reason": "Indicador/CD não cadastrado"}); continue
        if user["role"] != "admin" and cd not in user["centers"]:
            rejected.append({"row": row, "reason": "CD fora do escopo do usuário"}); continue
        if not cfg["ativo"] or cfg["tipo_campo"] != "dado_diario":
            rejected.append({"row": row, "reason": "Indicador inativo ou não classificado como dado diário"}); continue
        raw_value = row.get("valor", row.get("value"))
        val = _parse_number(raw_value)
        if raw_value not in (None, "") and val is None:
            rejected.append({"row": row, "reason": "Valor inválido"}); continue
        accepted.append({
            "data": parsed_date, "cd": cd, "grupo": cfg["grupo"], "indicador": cfg["indicador"],
            "codigo_indicador": cfg["codigo_indicador"], "valor": val,
        })
    # Impede que um mesmo indicador/data apareça duas vezes na mesma carga.
    seen: dict[tuple[str, str, str], int] = {}
    duplicate_indexes: set[int] = set()
    for index, item in enumerate(accepted):
        identity = (item["data"], item["cd"], str(item["codigo_indicador"] or item["grupo"] + "|" + item["indicador"]))
        if identity in seen:
            duplicate_indexes.add(seen[identity])
            duplicate_indexes.add(index)
            rejected.append({"row": item, "reason": "Chave de data/CD/indicador duplicada no arquivo"})
        else:
            seen[identity] = index
    accepted = [item for index, item in enumerate(accepted) if index not in duplicate_indexes]
    return accepted, rejected


@app.post("/api/imports/preview")
async def import_preview(file: UploadFile = File(...), user: dict[str, Any] = Depends(require("import_data"))):
    raw = await file.read()
    filename = (file.filename or "").lower()
    if filename.endswith(".xlsx"):
        frame = pd.read_excel(io.BytesIO(raw), dtype=object)
        raw_rows = frame.where(pd.notna(frame), None).to_dict("records")
    else:
        text = raw.decode("utf-8-sig")
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t,")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        raw_rows = list(reader)
    conn = _db()
    try:
        accepted, rejected = _normalize_import_rows(raw_rows, conn, user)
    finally:
        conn.close()
    preview_id = hashlib.sha256(raw + user["username"].encode()).hexdigest()
    return {
        "preview_id": preview_id,
        "filename": file.filename or "upload.csv",
        "rows_received": len(raw_rows),
        "rows_accepted": len(accepted),
        "rows_rejected": len(rejected),
        "accepted_sample": accepted[:100],
        "rejected_sample": rejected[:100],
        "accepted_rows": accepted,
    }


class ImportCommit(BaseModel):
    filename: str
    reason: str = Field(min_length=1, max_length=1000)
    rows: list[dict[str, Any]]


@app.post("/api/imports")
def commit_import(body: ImportCommit, user: dict[str, Any] = Depends(require("import_data"))):
    batch_id = hashlib.sha256((user["username"] + _now() + body.filename).encode()).hexdigest()[:32]
    inserted = updated = 0
    now = _now()
    with transaction() as conn:
        valid, rejected = _normalize_import_rows(body.rows, conn, user)
        if rejected or len(valid) != len(body.rows):
            raise HTTPException(422, {"message": "A prévia contém linhas inválidas ou não permitidas.", "rejected": rejected[:100]})
        columns = {r[1] for r in conn.execute("PRAGMA table_info(values_indicators)")}
        has_code = "codigo_indicador" in columns
        for row in valid:
            if row["codigo_indicador"] and has_code:
                old = conn.execute(
                    "SELECT id,valor FROM values_indicators WHERE data=? AND cd=? AND codigo_indicador=? ORDER BY id DESC LIMIT 1",
                    (row["data"], row["cd"], row["codigo_indicador"]),
                ).fetchone()
            else:
                old = None
            if old is None:
                old = conn.execute(
                    "SELECT id,valor FROM values_indicators WHERE data=? AND cd=? AND grupo=? AND indicador=? ORDER BY id DESC LIMIT 1",
                    (row["data"], row["cd"], row["grupo"], row["indicador"]),
                ).fetchone()
            if old is None:
                if has_code:
                    conn.execute(
                        "INSERT INTO values_indicators(data,cd,grupo,indicador,valor,source,batch_id,created_by,created_at,codigo_indicador) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (row["data"],row["cd"],row["grupo"],row["indicador"],row["valor"],body.filename,batch_id,user["username"],now,row["codigo_indicador"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO values_indicators(data,cd,grupo,indicador,valor,source,batch_id,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                        (row["data"],row["cd"],row["grupo"],row["indicador"],row["valor"],body.filename,batch_id,user["username"],now),
                    )
                inserted += 1
            elif old["valor"] != row["valor"]:
                conn.execute(
                    "UPDATE values_indicators SET valor=?,source=?,batch_id=?,updated_by=?,updated_at=? WHERE id=?",
                    (row["valor"],body.filename,batch_id,user["username"],now,old["id"]),
                )
                conn.execute(
                    "INSERT INTO audit_changes(data,cd,grupo,indicador,valor_anterior,valor_novo,motivo,changed_by,changed_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (row["data"],row["cd"],row["grupo"],row["indicador"],old["valor"],row["valor"],body.reason,user["username"],now),
                )
                updated += 1
        conn.execute(
            "INSERT INTO imports(batch_id,filename,cd,rows_received,rows_inserted,rows_updated,imported_by,imported_at,motivo) VALUES(?,?,?,?,?,?,?,?,?)",
            (batch_id,body.filename,"MULTI",len(valid),inserted,updated,user["username"],now,body.reason),
        )
    return {"batch_id": batch_id, "inserted": inserted, "updated": updated, "preserved_history": True}


@app.get("/api/targets")
def targets(cd: str | None = None, user: dict[str, Any] = Depends(require("view_dashboard"))):
    _scope_center(user, cd)
    conn = _db()
    try:
        sql = "SELECT * FROM target_versions"
        args: list[Any] = []
        if cd:
            sql += " WHERE cd=?"; args.append(cd)
        elif user["role"] != "admin" and user["centers"]:
            sql += " WHERE cd IN (" + ",".join("?" for _ in user["centers"]) + ")"; args.extend(user["centers"])
        sql += " ORDER BY cd,grupo,indicador,data_inicio DESC"
        return [dict(r) for r in conn.execute(sql,args)]
    finally:
        conn.close()


@app.post("/api/targets")
def create_target(body: TargetInput, user: dict[str, Any] = Depends(require("configure_targets"))):
    _scope_center(user, body.cd)
    if body.direcao_meta not in {"maior_melhor", "menor_melhor", "igual"}:
        raise HTTPException(422, "Direção de meta inválida.")
    now = _now()
    end_prev = (body.data_inicio - timedelta(days=1)).isoformat()
    with transaction() as conn:
        conn.execute(
            "UPDATE target_versions SET data_fim=?,ativo=0 WHERE cd=? AND grupo=? AND indicador=? AND ativo=1 AND (data_fim IS NULL OR data_fim>=?)",
            (end_prev,body.cd,body.grupo,body.indicador,body.data_inicio.isoformat()),
        )
        conn.execute(
            "INSERT INTO target_versions(cd,grupo,indicador,valor_meta,direcao_meta,data_inicio,data_fim,ativo,exibir_dashboard,exibir_painel_matricial,exibir_meta_como_linha,usar_sinaleira,tolerancia_amarela,motivo,created_by,created_at) VALUES(?,?,?,?,?,?,NULL,1,0,1,0,1,?,?,?,?)",
            (body.cd,body.grupo,body.indicador,body.valor_meta,body.direcao_meta,body.data_inicio.isoformat(),body.tolerancia_amarela,body.motivo,user["username"],now),
        )
        conn.execute(
            "INSERT INTO config_audit(entidade,cd,grupo,indicador,campo,valor_anterior,valor_novo,motivo,changed_by,changed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("target_versions",body.cd,body.grupo,body.indicador,"nova_meta_versionada","",f"{body.valor_meta} desde {body.data_inicio}",body.motivo,user["username"],now),
        )
    return {"saved": True, "effective_from": body.data_inicio.isoformat()}


@app.patch("/api/indicators/{indicator_id}")
def patch_indicator(indicator_id: int, body: IndicatorPatch, user: dict[str, Any] = Depends(require("configure_indicators"))):
    allowed = {
        "grupo", "indicador", "codigo_indicador", "grupo_ordem", "indicador_ordem", "nivel", "tipo_campo",
        "formato", "direcao_meta", "exibir_painel_matricial", "exibir_dashboard", "exibir_dashboard_dia",
        "exibir_dashboard_mes", "exibir_referencia_card", "exibir_meta_como_linha", "exibir_total_mes",
        "exibir_atingimento_mes", "usar_sinaleira", "tolerancia_amarela", "formula", "meta_ref_grupo",
        "meta_ref_indicador", "ativo",
    }
    updates = {k: v for k, v in body.updates.items() if k in allowed}
    if not updates:
        raise HTTPException(422, "Nenhum campo de configuração permitido.")
    with transaction() as conn:
        old = conn.execute("SELECT * FROM indicator_config WHERE id=?", (indicator_id,)).fetchone()
        if not old:
            raise HTTPException(404, "Indicador não encontrado.")
        _scope_center(user, old["cd"])
        unknown = set(body.updates) - allowed
        if unknown:
            raise HTTPException(422, {"message": "Campos não permitidos.", "fields": sorted(unknown)})
        set_clause = ",".join(f'"{key}"=?' for key in updates)
        conn.execute(f"UPDATE indicator_config SET {set_clause},updated_by=?,updated_at=? WHERE id=?", (*updates.values(),user["username"],_now(),indicator_id))
        for key, value in updates.items():
            if str(old[key]) != str(value):
                conn.execute(
                    "INSERT INTO config_audit(entidade,cd,grupo,indicador,campo,valor_anterior,valor_novo,motivo,changed_by,changed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("indicator_config",old["cd"],old["grupo"],old["indicador"],key,str(old[key]),str(value),body.reason,user["username"],_now()),
                )
    return {"saved": True, "audited_fields": list(updates)}


@app.get("/api/users")
def users(user: dict[str, Any] = Depends(require("manage_users"))):
    conn = _db()
    try:
        return [dict(r) for r in conn.execute("SELECT username,full_name,role,active,created_at FROM users ORDER BY username")]
    finally:
        conn.close()


@app.post("/api/users")
def save_user(body: UserInput, user: dict[str, Any] = Depends(require("manage_users"))):
    username = body.username.strip().lower()
    now = _now()
    with transaction() as conn:
        conn.execute(
            "INSERT INTO users(username,full_name,password_hash,role,active,created_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(username) DO UPDATE SET full_name=excluded.full_name,password_hash=excluded.password_hash,role=excluded.role,active=excluded.active",
            (username,body.full_name.strip(),_password_hash(body.password),body.role,int(body.active),now),
        )
        for permission in PERMISSIONS:
            enabled = int(body.role == "admin" or permission.startswith("view_"))
            conn.execute(
                "INSERT OR IGNORE INTO user_permissions(username,permission,enabled,updated_by,updated_at) VALUES(?,?,?,?,?)",
                (username,permission,enabled,user["username"],now),
            )
        center_codes = [r[0] for r in conn.execute("SELECT code FROM centers")]
        for code in center_codes:
            conn.execute(
                "INSERT INTO user_centers(username,cd,enabled) VALUES(?,?,?) ON CONFLICT(username,cd) DO UPDATE SET enabled=excluded.enabled",
                (username,code,int(code in body.centers)),
            )
    return {"username": username, "saved": True}


@app.get("/api/calendar")
def calendar(cd: str, start: str, end: str, user: dict[str, Any] = Depends(require("view_daily"))):
    _scope_center(user, cd)
    conn = _db()
    try:
        rows = conn.execute("SELECT * FROM work_calendar WHERE cd=? AND data BETWEEN ? AND ? ORDER BY data", (cd,start,end))
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.put("/api/calendar/{cd}/{day}")
def set_calendar(cd: str, day: str, body: dict[str, Any], user: dict[str, Any] = Depends(require("edit_data"))):
    _scope_center(user, cd)
    now = _now()
    with transaction() as conn:
        conn.execute(
            "INSERT INTO work_calendar(cd,data,trabalhado,observacao,updated_by,updated_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(cd,data) DO UPDATE SET trabalhado=excluded.trabalhado,observacao=excluded.observacao,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
            (cd,day,int(bool(body.get("trabalhado", True))),str(body.get("observacao") or ""),user["username"],now),
        )
    return {"saved": True}


@app.get("/api/exports/values.csv")
def export_values(cd: str | None = None, start: str | None = None, end: str | None = None, user: dict[str, Any] = Depends(require("export_reports"))):
    _scope_center(user, cd)
    conn = _db()
    try:
        where, args = [], []
        if cd:
            where.append("cd=?"); args.append(cd)
        elif user["role"] != "admin" and user["centers"]:
            where.append("cd IN (" + ",".join("?" for _ in user["centers"]) + ")"); args.extend(user["centers"])
        if start:
            where.append("data>=?"); args.append(start)
        if end:
            where.append("data<=?"); args.append(end)
        sql = "SELECT * FROM values_indicators" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY data,cd,grupo,indicador"
        rows = conn.execute(sql,args).fetchall()
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        if rows:
            writer.writerow(rows[0].keys())
            writer.writerows([tuple(r) for r in rows])
    finally:
        conn.close()
    return StreamingResponse(iter([output.getvalue().encode("utf-8-sig")]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=valores_pcp.csv"})


@app.get("/api/overview/features")
def feature_catalog(user: dict[str, Any] = Depends(authenticated)):
    return [
        {"id":"dashboard","label":"Dashboard Executivo","permission":"view_dashboard"},
        {"id":"matrix","label":"Painel Diário / Matricial","permission":"view_matrix"},
        {"id":"daily","label":"Visão Dia a Dia","permission":"view_daily"},
        {"id":"monthly","label":"Visão Mensal","permission":"view_monthly"},
        {"id":"imports","label":"Importação de Dados","permission":"import_data"},
        {"id":"edit","label":"Preencher / Corrigir Dados","permission":"edit_data"},
        {"id":"calendar","label":"Calendário de Trabalho","permission":"edit_data"},
        {"id":"indicators","label":"Indicadores e Cálculos","permission":"configure_indicators"},
        {"id":"targets","label":"Metas","permission":"configure_targets"},
        {"id":"centers","label":"Centros de Distribuição","permission":"manage_centers"},
        {"id":"users","label":"Usuários e Permissões","permission":"manage_users"},
        {"id":"audit","label":"Auditoria","permission":"view_audit"},
        {"id":"exports","label":"Exportações","permission":"export_reports"},
    ]


# Routes kept separate from the core API for readable administration modules.
import admin_routes  # noqa: E402,F401
