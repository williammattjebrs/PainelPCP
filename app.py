from __future__ import annotations

import base64
import hashlib
import html
import io
import os
import re
import sqlite3
import uuid
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Any

import pandas as pd
import plotly.express as px
import streamlit as st

APP_TITLE = "Painel de Indicadores Intralogística"
APP_BUILD_FIX = "baseline_login_meta_export_buttons_visible_2026_05_11"
GLOBAL_DASHBOARD_USERNAME = "__TODOS_USUARIOS__"
DB_PATH = os.getenv("PCP_DB_PATH", "data/indicadores.db")
LOGO_PATH = Path("assets/br_supply_logo.png")
MODELOS = Path("modelos")
CATALOG_CSV = MODELOS / "catalogo_layout_indicadores.csv"
CLASSIFICACAO_XLSX = MODELOS / "classificacao_usuario_metas_dados_calculos.xlsx"
DADOS_DIARIOS_CSV = MODELOS / "modelo_dados_diarios_ajustado_2025-06-02_ate_2026-05-05.csv"
METAS_AJUSTADAS_CSV = MODELOS / "modelo_metas_config_ajustado.csv"
CALCULADOS_CSV = MODELOS / "indicadores_calculados_ajustado.csv"

BR_ORANGE = "#F68620"
BR_DARK = "#333333"
BR_LIGHT = "#FFF4EA"
BR_BORDER = "rgba(246, 134, 32, 0.26)"

REQUIRED_LONG_COLUMNS = {"data", "cd", "grupo", "indicador", "valor"}
REQUIRED_CODE_COLUMNS = {"data", "cd", "codigo_indicador", "valor"}
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
PAGE_PERMISSIONS = {
    "Painel Diário de Indicadores": "view_matrix",
    "Dashboard Executivo": "view_dashboard",
    "Preencher Dados": "edit_data",
    "Calendário de Trabalho": "edit_data",
    "Visão Dia a Dia": "view_daily",
    "Visão Mensal": "view_monthly",
    "Indicadores": "configure_indicators",
    "Metas": "configure_targets",
    "Usuários e Permissões": "manage_users",
    "Centros de Distribuição": "manage_centers",
    "Auditoria": "view_audit",
}
TIPOS_CAMPO = ["dado_diario", "meta", "calculo", "parametro"]
FORMATOS = ["numero", "percentual", "moeda"]
DIRECOES = ["maior_melhor", "menor_melhor", "igual"]

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = f"""
<style>
.main .block-container {{padding-top: 1.0rem; padding-bottom: 2rem;}}
.stApp {{font-family: "Inter", "Segoe UI", Roboto, Arial, sans-serif;}}
html, body, [class*="css"] {{font-family: "Inter", "Segoe UI", Roboto, Arial, sans-serif;}}
.app-banner {{border:1px solid {BR_BORDER}; border-radius:18px; padding:20px 140px 20px 140px; background:linear-gradient(90deg, rgba(246,134,32,.08), rgba(255,255,255,.96)); margin-bottom:1rem; position:relative; min-height:84px; display:flex; align-items:center; justify-content:center; text-align:center;}}
.app-title {{font-size:2.05rem; line-height:1.12; font-weight:900; color:{BR_DARK}; margin:0; text-align:center;}}
.app-sub {{font-size:.95rem; color:#6b7280; margin-top:6px; text-align:center;}}
.app-logo-topright {{position:absolute; top:14px; right:18px; max-height:44px; max-width:132px; object-fit:contain;}}
.kpi-card {{border:1px solid {BR_BORDER}; border-radius:18px; padding:16px; background:linear-gradient(180deg, #fff, {BR_LIGHT}); box-shadow:0 10px 26px rgba(51,51,51,.07); min-height:130px;}}
.kpi-label {{font-size:.74rem; color:#777; text-transform:uppercase; letter-spacing:.04em; font-weight:700;}}
.kpi-value {{font-size:1.75rem; color:{BR_DARK}; font-weight:850; margin-top:6px;}}
.kpi-sub {{font-size:.80rem; color:#6b7280; margin-top:7px; min-height:1.1rem;}}
.dashboard-grid {{display:grid; grid-template-columns:repeat(auto-fit, minmax(250px, 1fr)); gap:16px; align-items:stretch; margin:.85rem 0 1.25rem 0;}}
.dashboard-card {{border:1px solid {BR_BORDER}; border-radius:18px; padding:17px 18px; background:linear-gradient(180deg, #fff, {BR_LIGHT}); box-shadow:0 10px 26px rgba(51,51,51,.065); min-height:154px; height:100%; display:flex; flex-direction:column; justify-content:space-between;}}
.dashboard-card-label {{font-size:.78rem; line-height:1.35; color:#737373; text-transform:uppercase; letter-spacing:.055em; font-weight:850; min-height:2.15rem;}}
.dashboard-card-value {{font-size:1.85rem; line-height:1.08; color:{BR_DARK}; font-weight:900; margin:.55rem 0 .35rem 0; font-variant-numeric:tabular-nums;}}
.dashboard-card-sub {{font-size:.84rem; color:#6b7280; min-height:1.25rem;}}
.dashboard-card-status {{display:inline-flex; align-items:center; gap:.45rem;}}
.dashboard-card-emoji {{font-size:1.95rem; line-height:1; vertical-align:middle;}}
.dashboard-card-native {{position:relative; overflow:visible;}}
.dashboard-card-info {{display:inline-flex; align-items:center; justify-content:center; width:17px; height:17px; border-radius:50%; background:#fff3e7; color:#F68620; border:1px solid rgba(246,134,32,.38); font-size:.68rem; font-weight:900; margin-left:7px; vertical-align:middle;}}
.dashboard-card-native[data-tooltip]:hover::after, .dashboard-card-native[data-tooltip]:focus::after {{content:attr(data-tooltip); white-space:pre-line; position:absolute; z-index:9999; left:18px; top:34px; max-width:420px; min-width:260px; padding:12px 14px; border-radius:13px; border:1px solid rgba(51,51,51,.14); background:#ffffff; color:#333333; box-shadow:0 16px 38px rgba(17,24,39,.18); font-size:.82rem; line-height:1.35; text-transform:none; letter-spacing:0;}}
.dashboard-save-box {{border:1px dashed {BR_BORDER}; border-radius:14px; padding:12px 14px; background:#fffaf6; margin-top:.75rem;}}
.exec-panel {{border:1px solid {BR_BORDER}; background:#fff; border-radius:18px; padding:15px 18px; margin:.4rem 0 1rem 0;}}
.mgmt-summary-card {{border:1px solid rgba(246,134,32,.22); background:#fff; border-radius:18px; padding:15px 18px; margin:.45rem 0 1rem 0; box-shadow:0 8px 22px rgba(51,51,51,.045);}}
.mgmt-summary-ok {{border-color:rgba(34,197,94,.55); background:linear-gradient(180deg, rgba(34,197,94,.17), rgba(34,197,94,.08));}}
.mgmt-summary-warn {{border-color:rgba(245,179,1,.60); background:linear-gradient(180deg, rgba(245,179,1,.20), rgba(245,179,1,.09));}}
.mgmt-summary-bad {{border-color:rgba(225,29,72,.55); background:linear-gradient(180deg, rgba(225,29,72,.17), rgba(225,29,72,.08));}}
.mgmt-summary-none {{border-color:{BR_BORDER}; background:linear-gradient(180deg, #fff, {BR_LIGHT});}}
.mgmt-summary-title {{display:flex; align-items:center; gap:.55rem; font-size:.92rem; font-weight:850; color:{BR_DARK};}}
.mgmt-summary-text {{font-size:.90rem; color:#374151; margin-top:6px; line-height:1.45;}}
.mgmt-summary-meta {{font-size:.78rem; color:#6b7280; margin-top:7px;}}
.tiny-pill {{display:inline-block; padding:4px 9px; border-radius:999px; background:{BR_LIGHT}; color:{BR_DARK}; border:1px solid {BR_BORDER}; font-size:.78rem; font-weight:700; margin-right:6px;}}
div[data-testid="stSidebar"] {{border-right:1px solid {BR_BORDER};}}
.matrix-cell {{border:1px solid rgba(51,51,51,.10); min-height:38px; padding:9px 10px; background:#fffaf6; font-size:.90rem; display:flex; align-items:center;}}
.matrix-head {{background:#f8f9fb; color:#6b7280; font-size:.86rem; font-weight:780;}}
.matrix-indicator {{font-weight:500; color:#111827;}}
.matrix-value {{justify-content:flex-end; text-align:right; font-variant-numeric: tabular-nums;}}
.matrix-gear-note {{font-size:.78rem; color:#6b7280; margin:.25rem 0 .6rem 0;}}
.matrix-scroll-wrap {{width:100%; overflow-x:auto; border:1px solid rgba(51,51,51,.12); border-radius:10px; background:#fff; margin-bottom:12px;}}
table.matrix-table {{border-collapse:collapse; min-width:980px; width:max-content; font-size:.88rem;}}
table.matrix-table th, table.matrix-table td {{border:1px solid rgba(51,51,51,.10); padding:8px 10px; white-space:nowrap; background:#fffaf6;}}
table.matrix-table th {{background:#f8f9fb; color:#6b7280; font-weight:750; position:sticky; top:0; z-index:1;}}
table.matrix-table th.matrix-ind-col, table.matrix-table td.matrix-ind-col {{min-width:360px; max-width:520px; white-space:normal; text-align:left; background:#fff7ef;}}
table.matrix-table th.matrix-ind-col {{background:#f8f9fb;}}
table.matrix-table td.matrix-num {{text-align:right; font-variant-numeric:tabular-nums; min-width:88px;}}
table.matrix-table th.matrix-flag-col, table.matrix-table td.matrix-flag-col {{min-width:44px; text-align:center; background:#f8f9fb;}}
.matrix-hidden-html td {{opacity:.52; background:#f3f4f6 !important;}}
.config-box {{border:1px solid rgba(246,134,32,.22); border-radius:14px; padding:14px 16px; background:#fffaf6; margin:.6rem 0 1rem 0;}}
.config-muted {{font-size:.82rem; color:#6b7280;}}
.config-alert {{border-left:4px solid #F68620; padding:8px 11px; background:#fff4ea; border-radius:8px; margin:.35rem 0 .75rem 0; font-size:.84rem; color:#333;}}
.matrix-hidden-row .matrix-cell {{opacity:.50; background:#f3f4f6;}}
.matrix-flag-help {{font-size:.76rem; color:#6b7280; margin:.15rem 0 .35rem 0;}}
.matrix-admin-strip {{border:1px solid rgba(246,134,32,.22); border-radius:12px; background:#fffaf6; padding:10px 12px; margin:.35rem 0 .75rem 0;}}

div[data-testid="stCheckbox"] label {{min-height: 1.1rem;}}
div[data-testid="stCheckbox"] p {{font-size: .84rem;}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------- helpers gerais -----------------------------

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def hash_password(password: str) -> str:
    salt = os.getenv("PCP_PASSWORD_SALT", "trocar-este-salt-no-deploy")
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def logo_base64() -> str:
    if not LOGO_PATH.exists():
        return ""
    return base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")


def render_header(title: str, subtitle: str = "", cd: Optional[str] = None) -> None:
    title_txt = f"{title} - {cd}" if cd else title
    logo_html = ""
    if LOGO_PATH.exists():
        logo_html = f'<img class="app-logo-topright" src="data:image/png;base64,{logo_base64()}" />'
    sub_html = f'<div class="app-sub">{html.escape(str(subtitle))}</div>' if str(subtitle or "").strip() else ""
    st.markdown(
        f"""
        <div class="app-banner">
          {logo_html}
          <div>
            <p class="app-title">{html.escape(str(title_txt))}</p>
            {sub_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_panel(title: str, subtitle: str, pills: Optional[list[str]] = None) -> None:
    pills_html = "".join([f'<span class="tiny-pill">{p}</span>' for p in (pills or [])])
    st.markdown(
        f"""
        <div class="exec-panel">
          <div style="font-size:1.02rem;font-weight:850;color:{BR_DARK};">{title}</div>
          <div style="font-size:.86rem;color:#6b7280;margin-top:4px;">{subtitle}</div>
          <div style="margin-top:8px;">{pills_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_value(value: Any, formato: str = "numero", indicador: str = "") -> str:
    """
    Formata valores para exibição respeitando prioritariamente o campo `formato`.

    Regra importante:
    - Se o cadastro estiver como `numero`, o sistema exibe número.
    - Se estiver como `moeda`, exibe R$.
    - Se estiver como `percentual`, exibe %.

    O nome do indicador não deve forçar moeda. Exemplo: "Avaria de Item"
    pode ser quantidade e deve aparecer como número quando formato = numero.
    """
    if value is None or pd.isna(value):
        return ""
    try:
        v = float(value)
    except Exception:
        return str(value)

    formato_norm = str(formato or "numero").strip().lower()
    ind = str(indicador or "").lower()

    # Somente usa inferência pelo nome se o formato estiver ausente/indefinido.
    if formato_norm in {"", "nan", "none", "null"}:
        if "%" in ind or "performance" in ind or "atingimento" in ind:
            formato_norm = "percentual"
        elif "faturamento" in ind or "receita" in ind or "valor" in ind:
            formato_norm = "moeda"
        else:
            formato_norm = "numero"

    if formato_norm == "percentual":
        if abs(v) > 1.5:
            v = v / 100
        return f"{v:.2%}".replace(".", ",")

    if formato_norm == "moeda":
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # formato = numero
    if abs(v) >= 1000:
        return f"{v:,.0f}".replace(",", ".")
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v))}"
    return f"{v:.2f}".replace(".", ",")


def parse_number(x: Any) -> Optional[float]:
    if x is None or pd.isna(x):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return None
    s = s.replace("R$", "").replace("%", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
        if "%" in str(x) and abs(v) > 1.5:
            return v / 100
        return v
    except Exception:
        return None


def br_date_label(d: Any) -> str:
    dt = pd.to_datetime(d).date()
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return f"{dt.day:02d}/{meses[dt.month-1]}"


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip())

# ----------------------------- schema e seed -----------------------------

def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'operador',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_permissions (
            username TEXT NOT NULL,
            permission TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            updated_by TEXT,
            updated_at TEXT,
            UNIQUE(username, permission)
        );
        CREATE TABLE IF NOT EXISTS user_centers (
            username TEXT NOT NULL,
            cd TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            UNIQUE(username, cd)
        );
        CREATE TABLE IF NOT EXISTS centers (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            created_by TEXT
        );
        CREATE TABLE IF NOT EXISTS values_indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            cd TEXT NOT NULL,
            grupo TEXT NOT NULL,
            indicador TEXT NOT NULL,
            valor REAL,
            source TEXT NOT NULL,
            batch_id TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT,
            UNIQUE(data, cd, grupo, indicador)
        );
        CREATE TABLE IF NOT EXISTS work_calendar (
            cd TEXT NOT NULL,
            data TEXT NOT NULL,
            trabalhado INTEGER NOT NULL DEFAULT 1,
            observacao TEXT,
            updated_by TEXT,
            updated_at TEXT,
            UNIQUE(cd, data)
        );
        CREATE TABLE IF NOT EXISTS audit_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            cd TEXT NOT NULL,
            grupo TEXT NOT NULL,
            indicador TEXT NOT NULL,
            valor_anterior REAL,
            valor_novo REAL,
            motivo TEXT NOT NULL,
            changed_by TEXT NOT NULL,
            changed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            cd TEXT NOT NULL,
            rows_received INTEGER NOT NULL,
            rows_inserted INTEGER NOT NULL,
            rows_updated INTEGER NOT NULL,
            imported_by TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            motivo TEXT
        );
        CREATE TABLE IF NOT EXISTS indicator_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cd TEXT NOT NULL,
            grupo TEXT NOT NULL,
            indicador TEXT NOT NULL,
            codigo_indicador TEXT,
            grupo_ordem INTEGER DEFAULT 999,
            indicador_ordem INTEGER DEFAULT 999,
            nivel INTEGER DEFAULT 0,
            tipo_campo TEXT NOT NULL DEFAULT 'dado_diario',
            formato TEXT NOT NULL DEFAULT 'numero',
            direcao_meta TEXT NOT NULL DEFAULT 'maior_melhor',
            exibir_painel_matricial INTEGER NOT NULL DEFAULT 1,
            exibir_dashboard INTEGER NOT NULL DEFAULT 0,
            exibir_dashboard_dia INTEGER NOT NULL DEFAULT 1,
            exibir_dashboard_mes INTEGER NOT NULL DEFAULT 1,
            exibir_referencia_card INTEGER NOT NULL DEFAULT 1,
            card_ref_grupo TEXT,
            card_ref_indicador TEXT,
            exibir_meta_como_linha INTEGER NOT NULL DEFAULT 0,
            exibir_total_mes INTEGER NOT NULL DEFAULT 0,
            exibir_atingimento_mes INTEGER NOT NULL DEFAULT 0,
            exibir_objetivo_mes_dashboard INTEGER NOT NULL DEFAULT 0,
            total_mes_ref_grupo TEXT,
            total_mes_ref_indicador TEXT,
            usar_sinaleira INTEGER NOT NULL DEFAULT 0,
            tolerancia_amarela REAL NOT NULL DEFAULT 0.05,
            formula TEXT,
            meta_ref_grupo TEXT,
            meta_ref_indicador TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            updated_by TEXT,
            updated_at TEXT,
            UNIQUE(cd, grupo, indicador)
        );
        CREATE TABLE IF NOT EXISTS target_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cd TEXT NOT NULL,
            grupo TEXT NOT NULL,
            indicador TEXT NOT NULL,
            valor_meta REAL NOT NULL,
            direcao_meta TEXT NOT NULL DEFAULT 'maior_melhor',
            data_inicio TEXT NOT NULL,
            data_fim TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            exibir_dashboard INTEGER NOT NULL DEFAULT 0,
            exibir_painel_matricial INTEGER NOT NULL DEFAULT 1,
            exibir_meta_como_linha INTEGER NOT NULL DEFAULT 0,
            usar_sinaleira INTEGER NOT NULL DEFAULT 1,
            tolerancia_amarela REAL NOT NULL DEFAULT 0.05,
            motivo TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS monthly_objectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cd TEXT NOT NULL,
            grupo TEXT NOT NULL,
            indicador TEXT NOT NULL,
            codigo_indicador TEXT,
            mes_ref TEXT NOT NULL,
            valor_objetivo REAL NOT NULL,
            direcao_meta TEXT NOT NULL DEFAULT 'maior_melhor',
            tolerancia_amarela REAL NOT NULL DEFAULT 0.05,
            active INTEGER NOT NULL DEFAULT 1,
            motivo TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT,
            UNIQUE(cd, grupo, indicador, mes_ref)
        );
        CREATE TABLE IF NOT EXISTS config_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entidade TEXT NOT NULL,
            cd TEXT,
            grupo TEXT,
            indicador TEXT,
            campo TEXT,
            valor_anterior TEXT,
            valor_novo TEXT,
            motivo TEXT NOT NULL,
            changed_by TEXT NOT NULL,
            changed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_card_config (
            username TEXT NOT NULL,
            cd TEXT NOT NULL,
            grupo TEXT NOT NULL,
            indicador TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT,
            UNIQUE(username, cd, grupo, indicador)
        );
        CREATE TABLE IF NOT EXISTS dashboard_card_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            cd TEXT NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            UNIQUE(username, cd, nome)
        );
        CREATE TABLE IF NOT EXISTS dashboard_card_view_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            view_id INTEGER NOT NULL,
            cd TEXT NOT NULL,
            grupo TEXT NOT NULL,
            indicador TEXT NOT NULL,
            codigo_indicador TEXT,
            sort_order INTEGER NOT NULL DEFAULT 999,
            FOREIGN KEY(view_id) REFERENCES dashboard_card_views(id) ON DELETE CASCADE,
            UNIQUE(view_id, cd, grupo, indicador)
        );
        
        CREATE TABLE IF NOT EXISTS visualization_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            contexto TEXT NOT NULL DEFAULT 'global',
            cd TEXT NOT NULL DEFAULT 'TODOS',
            descricao TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT,
            UNIQUE(nome, contexto, cd)
        );
        CREATE TABLE IF NOT EXISTS visualization_view_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            view_id INTEGER NOT NULL,
            cd TEXT NOT NULL,
            grupo TEXT NOT NULL,
            indicador TEXT NOT NULL,
            codigo_indicador TEXT,
            sort_order INTEGER NOT NULL DEFAULT 999,
            FOREIGN KEY(view_id) REFERENCES visualization_views(id) ON DELETE CASCADE,
            UNIQUE(view_id, cd, grupo, indicador)
        );
        """
    )
    # Migração leve para bancos criados em versões anteriores.
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(indicator_config)").fetchall()}
    if "meta_ref_grupo" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN meta_ref_grupo TEXT")
    if "meta_ref_indicador" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN meta_ref_indicador TEXT")
    if "codigo_indicador" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN codigo_indicador TEXT")
    if "dashboard_titulo" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN dashboard_titulo TEXT")
    if "exibir_dashboard_dia" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN exibir_dashboard_dia INTEGER NOT NULL DEFAULT 1")
    if "exibir_dashboard_mes" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN exibir_dashboard_mes INTEGER NOT NULL DEFAULT 1")
    if "exibir_referencia_card" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN exibir_referencia_card INTEGER NOT NULL DEFAULT 1")
    if "card_ref_grupo" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN card_ref_grupo TEXT")
    if "card_ref_indicador" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN card_ref_indicador TEXT")
    if "exibir_total_mes" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN exibir_total_mes INTEGER NOT NULL DEFAULT 0")
    if "exibir_atingimento_mes" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN exibir_atingimento_mes INTEGER NOT NULL DEFAULT 0")
    if "exibir_objetivo_mes_dashboard" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN exibir_objetivo_mes_dashboard INTEGER NOT NULL DEFAULT 0")
    if "total_mes_ref_grupo" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN total_mes_ref_grupo TEXT")
    if "total_mes_ref_indicador" not in existing_cols:
        conn.execute("ALTER TABLE indicator_config ADD COLUMN total_mes_ref_indicador TEXT")

    value_cols = {r[1] for r in conn.execute("PRAGMA table_info(values_indicators)").fetchall()}
    if "codigo_indicador" not in value_cols:
        conn.execute("ALTER TABLE values_indicators ADD COLUMN codigo_indicador TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_values_codigo ON values_indicators(data, cd, codigo_indicador)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_values_cd_data ON values_indicators(cd, data)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_values_cd_grupo_indicador_data ON values_indicators(cd, grupo, indicador, data)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_targets_cd_datas ON target_versions(cd, data_inicio, data_fim)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dashboard_views_lookup ON dashboard_card_views(username, cd, active, is_default)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dashboard_view_items_view ON dashboard_card_view_items(view_id, sort_order)")

    # Migração para permitir uploads com valor em branco.
    # Versões anteriores criaram values_indicators.valor e audit_changes.valor_novo como NOT NULL.
    def _recreate_table_if_notnull(table_name: str, nullable_columns: set[str]) -> None:
        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        if not cols:
            return
        must_recreate = any(c[1] in nullable_columns and int(c[3]) == 1 for c in cols)
        if not must_recreate:
            return
        sql_row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
        if not sql_row or not sql_row[0]:
            return
        create_sql = sql_row[0]
        new_table = f"{table_name}_new"
        create_new = create_sql.replace(f"CREATE TABLE {table_name}", f"CREATE TABLE {new_table}").replace(f"CREATE TABLE IF NOT EXISTS {table_name}", f"CREATE TABLE {new_table}")
        for col in nullable_columns:
            create_new = create_new.replace(f"{col} REAL NOT NULL", f"{col} REAL")
            create_new = create_new.replace(f"{col} TEXT NOT NULL", f"{col} TEXT")
        conn.execute(create_new)
        col_names = [c[1] for c in cols]
        joined = ", ".join(col_names)
        conn.execute(f"INSERT INTO {new_table} ({joined}) SELECT {joined} FROM {table_name}")
        conn.execute(f"DROP TABLE {table_name}")
        conn.execute(f"ALTER TABLE {new_table} RENAME TO {table_name}")

    _recreate_table_if_notnull("values_indicators", {"valor"})
    _recreate_table_if_notnull("audit_changes", {"valor_novo"})

    now = now_iso()
    cur.executemany(
        "INSERT OR IGNORE INTO users(username, full_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            ("admin", "Administrador", hash_password("admin123"), "admin", now),
            ("operador", "Operador PCP", hash_password("op123"), "operador", now),
        ],
    )
    cur.executemany(
        "INSERT OR IGNORE INTO centers(code, name, created_at, created_by) VALUES (?, ?, ?, ?)",
        [("SBC", "São Bernardo do Campo", now, "seed"), ("RS", "Rio Grande do Sul", now, "seed")],
    )
    conn.commit()
    conn.close()
    seed_permissions()
    seed_indicator_config()
    ensure_indicator_codes()
    ensure_default_visualization_views()


def seed_permissions() -> None:
    conn = get_conn()
    cur = conn.cursor()
    users = pd.read_sql_query("SELECT username, role FROM users", conn)
    centers = [r[0] for r in conn.execute("SELECT code FROM centers WHERE active = 1").fetchall()]
    for _, u in users.iterrows():
        for perm in PERMISSIONS:
            default = 1 if u["role"] == "admin" else int(perm in {"view_matrix", "view_dashboard", "view_daily", "view_monthly", "import_data", "edit_data"})
            cur.execute(
                "INSERT OR IGNORE INTO user_permissions(username, permission, enabled, updated_by, updated_at) VALUES (?, ?, ?, 'seed', ?)",
                (u["username"], perm, default, now_iso()),
            )
        for cd in centers:
            cur.execute("INSERT OR IGNORE INTO user_centers(username, cd, enabled) VALUES (?, ?, 1)", (u["username"], cd))
    conn.commit()
    conn.close()


def slugify_code(text: str, max_len: int = 32) -> str:
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    return (text[:max_len] or "IND")


def build_indicator_code(grupo_ordem: int, indicador_ordem: int, indicador: str) -> str:
    return f"G{int(grupo_ordem or 999):03d}_I{int(indicador_ordem or 999):03d}_{slugify_code(indicador, 18)}"


def ensure_unique_indicator_code(conn: sqlite3.Connection, cd: str, proposed: str, ignore_id: Optional[int] = None) -> str:
    base = slugify_code(proposed, 52)
    candidate = base
    n = 2
    while True:
        if ignore_id is None:
            row = conn.execute("SELECT id FROM indicator_config WHERE cd=? AND codigo_indicador=? LIMIT 1", (cd, candidate)).fetchone()
        else:
            row = conn.execute("SELECT id FROM indicator_config WHERE cd=? AND codigo_indicador=? AND id<>? LIMIT 1", (cd, candidate, ignore_id)).fetchone()
        if row is None:
            return candidate
        candidate = f"{base}_{n}"
        n += 1


def ensure_indicator_codes() -> None:
    conn = get_conn()
    rows = conn.execute("SELECT id, cd, indicador, grupo_ordem, indicador_ordem, codigo_indicador FROM indicator_config ORDER BY cd, grupo_ordem, indicador_ordem, id").fetchall()
    for r in rows:
        current = str(r["codigo_indicador"] or "").strip()
        if current:
            continue
        proposed = build_indicator_code(int(r["grupo_ordem"] or 999), int(r["indicador_ordem"] or 999), str(r["indicador"] or "IND"))
        code = ensure_unique_indicator_code(conn, str(r["cd"]), proposed, int(r["id"]))
        conn.execute("UPDATE indicator_config SET codigo_indicador=?, updated_at=COALESCE(updated_at, ?), updated_by=COALESCE(updated_by, 'system') WHERE id=?", (code, now_iso(), int(r["id"])))
    conn.commit()
    conn.close()

def classify_from_observation(obs: str, catalog_tipo: str = "dado") -> str:
    o = str(obs or "").lower()
    if "calcul" in o:
        return "calculo"
    if "meta" in o and "não" not in o and "nao" not in o:
        return "meta"
    if "parâmetro" in o or "parametro" in o:
        return "parametro"
    if "dado" in o or "sobe" in o or catalog_tipo == "dado":
        return "dado_diario"
    return "dado_diario"


def seed_indicator_config() -> None:
    conn = get_conn()
    existing = conn.execute("SELECT COUNT(*) FROM indicator_config").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    centers = [r[0] for r in conn.execute("SELECT code FROM centers WHERE active = 1").fetchall()]
    frames: list[pd.DataFrame] = []
    if CLASSIFICACAO_XLSX.exists():
        try:
            raw = pd.read_excel(CLASSIFICACAO_XLSX)
            raw.columns = [c.strip().lower() for c in raw.columns]
            if {"cd", "grupo", "indicador"}.issubset(raw.columns):
                tmp = raw[["cd", "grupo", "indicador", "observacao"]].copy()
                tmp["tipo_campo"] = tmp["observacao"].map(classify_from_observation)
                tmp["formato"] = tmp["indicador"].astype(str).apply(lambda x: "percentual" if ("%" in x or "performance" in x.lower() or "atingimento" in x.lower()) else ("moeda" if any(k in x.lower() for k in ["faturamento", "perda", "avaria", "extravio"]) else "numero"))
                frames.append(tmp)
        except Exception:
            pass
    if CATALOG_CSV.exists():
        cat = pd.read_csv(CATALOG_CSV)
        if {"grupo", "indicador"}.issubset(cat.columns):
            cat_tmp = cat.copy()
            cat_tmp["cd"] = "TODOS"
            if "tipo_linha" in cat_tmp.columns:
                cat_tmp["tipo_campo"] = cat_tmp["tipo_linha"].astype(str).replace({"dado": "dado_diario", "meta_parametro": "meta", "calculado": "calculo"})
            else:
                cat_tmp["tipo_campo"] = "dado_diario"
            if "formato" not in cat_tmp.columns:
                cat_tmp["formato"] = "numero"
            frames.append(cat_tmp)

    if not frames:
        conn.close()
        return

    base = pd.concat(frames, ignore_index=True, sort=False)
    base["grupo"] = base["grupo"].map(normalize_text)
    base["indicador"] = base["indicador"].map(normalize_text)
    base = base.drop_duplicates(subset=["cd", "grupo", "indicador"], keep="first")
    records = []
    seq_by_group = {}
    for _, r in base.iterrows():
        cd_list = centers if str(r.get("cd", "TODOS")).upper() in {"TODOS", "NAN", ""} else [str(r.get("cd")).upper()]
        grupo = r["grupo"]
        indicador = r["indicador"]
        grupo_ordem = int(r["grupo_ordem"]) if "grupo_ordem" in r and not pd.isna(r.get("grupo_ordem")) else int(re.match(r"^(\d+)", grupo).group(1)) if re.match(r"^(\d+)", grupo) else 999
        key = grupo
        seq_by_group[key] = seq_by_group.get(key, 0) + 1
        indicador_ordem = int(r["indicador_ordem"]) if "indicador_ordem" in r and not pd.isna(r.get("indicador_ordem")) else seq_by_group[key]
        nivel = int(r["nivel"]) if "nivel" in r and not pd.isna(r.get("nivel")) else max(0, indicador.count(".") - 1)
        tipo = str(r.get("tipo_campo", "dado_diario"))
        if tipo not in TIPOS_CAMPO:
            tipo = "dado_diario"
        formato = str(r.get("formato", "numero"))
        if formato not in FORMATOS:
            formato = "numero"
        exibir_dash = int(tipo in {"dado_diario", "calculo"} and any(k in indicador.lower() for k in ["performance", "atraso", "ruptura", "ocorrência", "faturamento", "atingimento", "consolidação"]))
        exibir_meta_linha = int(tipo == "meta")
        usar_sinal = int(tipo in {"dado_diario", "calculo", "meta"})
        for cd in cd_list:
            codigo = build_indicator_code(grupo_ordem, indicador_ordem, indicador)
            records.append((cd, grupo, indicador, codigo, grupo_ordem, indicador_ordem, nivel, tipo, formato, "menor_melhor" if any(k in indicador.lower() for k in ["atraso", "ruptura", "perda", "avaria", "ocorrência"]) else "maior_melhor", 1, exibir_dash, exibir_meta_linha, usar_sinal, 0.05, None, None, None, 1, "seed", now_iso()))
    conn.executemany(
        """
        INSERT OR IGNORE INTO indicator_config(cd, grupo, indicador, codigo_indicador, grupo_ordem, indicador_ordem, nivel, tipo_campo, formato, direcao_meta, exibir_painel_matricial, exibir_dashboard, exibir_meta_como_linha, usar_sinaleira, tolerancia_amarela, formula, meta_ref_grupo, meta_ref_indicador, ativo, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )
    conn.commit()
    conn.close()


# ----------------------------- auth/permissões -----------------------------

def authenticate(username: str, password: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT username, full_name, role FROM users WHERE username = ? AND password_hash = ? AND active = 1",
        (username.strip().lower(), hash_password(password)),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def user_permissions(username: str) -> set[str]:
    conn = get_conn()
    rows = conn.execute("SELECT permission FROM user_permissions WHERE username = ? AND enabled = 1", (username,)).fetchall()
    conn.close()
    return {r[0] for r in rows}


def has_perm(perm: str) -> bool:
    u = st.session_state.get("user")
    if not u:
        return False
    if u.get("role") == "admin":
        return True
    return perm in st.session_state.get("permissions", set())


def allowed_centers(username: str) -> list[str]:
    conn = get_conn()
    rows = conn.execute("SELECT cd FROM user_centers WHERE username = ? AND enabled = 1 ORDER BY cd", (username,)).fetchall()
    if not rows:
        rows = conn.execute("SELECT code FROM centers WHERE active = 1 ORDER BY code").fetchall()
    conn.close()
    return [r[0] for r in rows]


def require_login() -> bool:
    if "user" in st.session_state:
        return True

    logo_html = ""
    if LOGO_PATH.exists():
        logo_html = f'<img class="login-logo" src="data:image/png;base64,{logo_base64()}" alt="BR Supply" />'

    st.markdown(
        f"""
        <style>
        section[data-testid="stSidebar"] {{display:none;}}
        div[data-testid="collapsedControl"] {{display:none;}}
        .main .block-container {{max-width: 1120px; padding-top: 5.2rem;}}
        .login-page-title {{
            text-align:center;
            font-size:2.15rem;
            line-height:1.12;
            font-weight:850;
            color:{BR_DARK};
            letter-spacing:-.035em;
            margin:0 0 .35rem 0;
        }}
        .login-page-subtitle {{
            text-align:center;
            font-size:.98rem;
            color:#6b7280;
            margin:0 0 1.35rem 0;
        }}
        .login-card-head {{
            text-align:center;
            padding:.35rem 0 .75rem 0;
        }}
        .login-logo {{
            max-height:54px;
            max-width:170px;
            object-fit:contain;
            margin:0 auto .9rem auto;
            display:block;
        }}
        .login-card-title {{
            color:{BR_DARK};
            font-size:1.22rem;
            font-weight:850;
            margin:0;
            letter-spacing:-.015em;
        }}
        .login-card-sub {{
            color:#6b7280;
            font-size:.86rem;
            margin:.35rem 0 0 0;
        }}
        .login-footnote {{
            text-align:center;
            color:#8a8f98;
            font-size:.76rem;
            margin-top:1rem;
        }}
        div[data-testid="stForm"] {{
            border:0;
            padding:0;
            box-shadow:none;
            background:transparent;
        }}
        div[data-testid="stTextInput"] label {{
            color:#4b5563;
            font-weight:700;
            font-size:.82rem;
        }}
        div[data-testid="stTextInput"] input {{
            border-radius:12px;
            min-height:42px;
        }}
        div[data-testid="stFormSubmitButton"] button {{
            border-radius:12px;
            min-height:43px;
            font-weight:800;
            background:{BR_ORANGE};
            border-color:{BR_ORANGE};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1.25, 0.9, 1.25], gap="large")
    with center:
        st.markdown(
            f"""
            <div class="login-card-head">
                {logo_html}
                <h1 class="login-page-title">{html.escape(APP_TITLE)}</h1>
                <p class="login-page-subtitle">Acesse sua conta para continuar.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown(
                """
                <div class="login-card-head">
                    <p class="login-card-title">Entrar</p>
                    <p class="login-card-sub">Use seu usuário e senha corporativos.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.form("login_form"):
                username = st.text_input("Usuário", placeholder="Digite seu usuário")
                password = st.text_input("Senha", placeholder="Digite sua senha", type="password")
                submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

            if submitted:
                user = authenticate(username, password)
                if user:
                    st.session_state["user"] = user
                    st.session_state["permissions"] = user_permissions(user["username"])
                    st.session_state["allowed_centers"] = allowed_centers(user["username"])
                    st.rerun()
                st.error("Usuário ou senha inválidos.")

        st.markdown('<div class="login-footnote">Painel de Indicadores Intralogística</div>', unsafe_allow_html=True)

    return False

def sidebar_nav() -> str:
    user = st.session_state["user"]
    if LOGO_PATH.exists():
        st.sidebar.image(str(LOGO_PATH), use_container_width=True)
    st.sidebar.markdown("### Painel PCP")
    st.sidebar.caption(f"Usuário: **{user['full_name']}** · {user['role']}")

    # Garante que usuários administradores sempre enxerguem toda a administração,
    # mesmo quando o banco foi criado em uma versão anterior ou a sessão estava aberta
    # antes da atualização do app.py.
    if user.get("role") == "admin":
        pages = list(PAGE_PERMISSIONS.keys())
    else:
        pages = [p for p, perm in PAGE_PERMISSIONS.items() if has_perm(perm)]

    if user.get("role") == "admin" and "Usuários e Permissões" not in pages:
        pages.append("Usuários e Permissões")

    if not pages:
        st.sidebar.error("Usuário sem permissões configuradas.")
        pages = ["Painel Diário de Indicadores"]

    page = st.sidebar.radio("Navegação", pages)
    st.sidebar.divider()

    if user.get("role") == "admin":
        st.sidebar.caption("Administração habilitada: usuários, permissões, indicadores e metas.")

    render_global_indicator_admin_tools()

    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    return page

# ----------------------------- consultas -----------------------------

def list_centers(active_only: bool = True) -> pd.DataFrame:
    conn = get_conn()
    sql = "SELECT code, name, active, created_at, created_by FROM centers"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY code"
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df


def load_indicator_config(cd: Optional[str] = None, active_only: bool = True) -> pd.DataFrame:
    conn = get_conn()
    sql = "SELECT * FROM indicator_config WHERE 1=1"
    params = []
    if cd:
        sql += " AND cd = ?"
        params.append(cd)
    if active_only:
        sql += " AND ativo = 1"
    sql += " ORDER BY cd, grupo_ordem, grupo, indicador_ordem, indicador"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df




def active_center_codes() -> list[str]:
    """Centros ativos usados nas colunas rápidas de visibilidade."""
    try:
        df = list_centers(active_only=True)
        if df.empty:
            return ["SBC", "RS"]
        # Mantém SBC/RS no início, depois demais CDs em ordem alfabética.
        codes = [str(c) for c in df["code"].dropna().tolist()]
        preferred = [c for c in ["SBC", "RS"] if c in codes]
        others = sorted([c for c in codes if c not in preferred])
        return preferred + others
    except Exception:
        return ["SBC", "RS"]



# ----------------------------- visões executivas -----------------------------

def ensure_default_visualization_views() -> None:
    """Cria visões padrão iniciais por CD, sem substituir visões criadas pelo admin."""
    conn = get_conn()
    try:
        existing = conn.execute("SELECT COUNT(*) FROM visualization_views").fetchone()[0]
        if existing > 0:
            return
        cfg = pd.read_sql_query("SELECT * FROM indicator_config WHERE indicador <> '__CABECALHO__' ORDER BY cd, grupo_ordem, indicador_ordem", conn)
        if cfg.empty:
            return
        now = now_iso()
        presets = {
            "Performance": ["performance", "atraso", "prazo", "pendente", "embarque"],
            "Abastecimento e Rupturas": ["abastecimento", "ruptura", "coleta", "ocorrência", "ocorrencia"],
            "Faturamento": ["faturamento", "faturado", "nota fiscal", "consolidado"],
        }
        for cd in sorted(cfg["cd"].dropna().astype(str).unique()):
            cfg_cd = cfg[cfg["cd"].astype(str) == cd].copy()
            for nome, keywords in presets.items():
                mask = cfg_cd.apply(lambda r: any(k in f"{r['grupo']} {r['indicador']}".lower() for k in keywords), axis=1)
                items = cfg_cd[mask].copy()
                if items.empty:
                    continue
                cur = conn.execute(
                    "INSERT OR IGNORE INTO visualization_views(nome, contexto, cd, descricao, active, created_by, created_at, updated_by, updated_at) VALUES (?, 'global', ?, ?, 1, 'seed', ?, 'seed', ?)",
                    (nome, cd, f"Visão padrão: {nome}", now, now),
                )
                row = conn.execute("SELECT id FROM visualization_views WHERE nome=? AND contexto='global' AND cd=?", (nome, cd)).fetchone()
                if not row:
                    continue
                view_id = int(row["id"])
                for i, (_, r) in enumerate(items.iterrows(), start=1):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO visualization_view_items(view_id, cd, grupo, indicador, codigo_indicador, sort_order)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (view_id, cd, str(r["grupo"]), str(r["indicador"]), str(r.get("codigo_indicador") or ""), i),
                    )
        conn.commit()
    finally:
        conn.close()


def load_visualization_views(contexto: str, cd: str) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT * FROM visualization_views
        WHERE active=1 AND contexto IN ('global', ?) AND cd IN (?, 'TODOS')
        ORDER BY CASE WHEN nome='Todos' THEN 0 ELSE 1 END, contexto, nome
        """,
        conn,
        params=(contexto, cd),
    )
    conn.close()
    return df


def load_visualization_view_items(view_id: Optional[int]) -> pd.DataFrame:
    if not view_id:
        return pd.DataFrame()
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM visualization_view_items WHERE view_id=? ORDER BY sort_order, grupo, indicador",
        conn,
        params=(int(view_id),),
    )
    conn.close()
    return df


def apply_visualization_view(cfg: pd.DataFrame, view_id: Optional[int]) -> pd.DataFrame:
    if cfg.empty or not view_id:
        return cfg
    items = load_visualization_view_items(view_id)
    if items.empty:
        return cfg.iloc[0:0].copy()
    codes = {str(c).strip().upper() for c in items.get("codigo_indicador", pd.Series(dtype=str)).dropna().tolist() if str(c).strip()}
    pairs = {(str(r["grupo"]), str(r["indicador"])) for _, r in items.iterrows()}
    mask = pd.Series(False, index=cfg.index)
    if "codigo_indicador" in cfg.columns and codes:
        mask = mask | cfg["codigo_indicador"].fillna("").astype(str).str.upper().isin(codes)
    if pairs:
        mask = mask | cfg.apply(lambda r: (str(r["grupo"]), str(r["indicador"])) in pairs, axis=1)
    return cfg[mask].copy()


def view_selector(contexto: str, cd: str, key: str) -> tuple[str, Optional[int]]:
    views = load_visualization_views(contexto, cd)
    options = ["Todos"]
    label_to_id: dict[str, Optional[int]] = {"Todos": None}
    if not views.empty:
        for _, r in views.iterrows():
            suffix = "" if str(r["contexto"]) == "global" else f" · {str(r['contexto']).capitalize()}"
            label = f"{r['nome']}{suffix}"
            if label in label_to_id:
                label = f"{label} · {r['cd']}"
            options.append(label)
            label_to_id[label] = int(r["id"])
    choice = st.selectbox("Visão de indicadores", options, key=key)
    return choice, label_to_id.get(choice)


def center_button_selector(label: str, centers: list[str], key: str, include_all: bool = False) -> str:
    opts = (["Todos"] if include_all else []) + list(centers)
    if not opts:
        return ""
    if key not in st.session_state or st.session_state.get(key) not in opts:
        st.session_state[key] = opts[0]
    st.caption(label)
    cols = st.columns(len(opts), gap="small")
    for i, c in enumerate(opts):
        selected = st.session_state.get(key) == c
        with cols[i]:
            if st.button(c, key=f"{key}_{c}", type="primary" if selected else "secondary", use_container_width=True):
                st.session_state[key] = c
                st.rerun()
    return str(st.session_state.get(key))


def build_indicator_label_map(cfg: pd.DataFrame) -> tuple[list[str], dict[str, pd.Series]]:
    labels: list[str] = []
    mapping: dict[str, pd.Series] = {}
    if cfg.empty:
        return labels, mapping
    scope = cfg[cfg["indicador"].astype(str).ne("__CABECALHO__")].copy()
    scope = scope.sort_values(["grupo_ordem", "grupo", "indicador_ordem", "indicador"], kind="stable")
    for _, r in scope.iterrows():
        codigo = str(r.get("codigo_indicador") or "SEM_COD")
        label = f"{codigo} · {r['grupo']} · {r['indicador']}"
        labels.append(label)
        mapping[label] = r
    return labels, mapping


def build_group_label_map(cfg: pd.DataFrame) -> tuple[list[str], dict[str, pd.DataFrame]]:
    """Retorna grandes grupos para composição das visões executivas.

    A visão passa a ser configurada por macrogrupo: ao selecionar o grupo
    "1. Performance de Embarque", todos os indicadores abaixo dele entram
    juntos na visão. Isso evita manutenção item a item e mantém a lógica do
    painel matricial.
    """
    labels: list[str] = []
    mapping: dict[str, pd.DataFrame] = {}
    if cfg.empty:
        return labels, mapping
    scope = cfg[cfg["indicador"].astype(str).ne("__CABECALHO__")].copy()
    if scope.empty:
        return labels, mapping
    scope = scope.sort_values(["grupo_ordem", "grupo", "indicador_ordem", "indicador"], kind="stable")
    for grupo, gdf in scope.groupby("grupo", sort=False):
        grupo_ordem = gdf["grupo_ordem"].dropna().iloc[0] if "grupo_ordem" in gdf.columns and not gdf["grupo_ordem"].dropna().empty else ""
        try:
            ordem_txt = str(int(float(grupo_ordem))) if str(grupo_ordem).strip() else ""
        except Exception:
            ordem_txt = str(grupo_ordem).strip()
        prefix = f"{ordem_txt}. " if ordem_txt and not str(grupo).strip().startswith(f"{ordem_txt}.") else ""
        qtd = len(gdf)
        label = f"{prefix}{grupo} · {qtd} item(ns)"
        labels.append(label)
        mapping[label] = gdf.copy()
    return labels, mapping

def save_visualization_view(nome: str, contexto: str, cd: str, labels: list[str], label_map: dict[str, pd.Series], descricao: str, user: str) -> int:
    if not nome.strip():
        raise ValueError("Informe o nome da visão.")
    if not labels:
        raise ValueError("Selecione ao menos um indicador para a visão.")
    contexto = contexto if contexto in {"global", "matricial", "dashboard", "mensal"} else "global"
    now = now_iso()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO visualization_views(nome, contexto, cd, descricao, active, created_by, created_at, updated_by, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(nome, contexto, cd) DO UPDATE SET descricao=excluded.descricao, active=1, updated_by=excluded.updated_by, updated_at=excluded.updated_at
            """,
            (nome.strip(), contexto, cd, descricao.strip(), user, now, user, now),
        )
        view_id = int(conn.execute("SELECT id FROM visualization_views WHERE nome=? AND contexto=? AND cd=?", (nome.strip(), contexto, cd)).fetchone()["id"])
        conn.execute("DELETE FROM visualization_view_items WHERE view_id=?", (view_id,))
        for i, label in enumerate(labels, start=1):
            r = label_map[label]
            conn.execute(
                """
                INSERT INTO visualization_view_items(view_id, cd, grupo, indicador, codigo_indicador, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (view_id, str(r["cd"]), str(r["grupo"]), str(r["indicador"]), str(r.get("codigo_indicador") or ""), i),
            )
        conn.execute(
            "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("visualization_view", cd, None, None, contexto, None, nome.strip(), descricao.strip() or "Configuração de visão", user, now),
        )
        conn.commit()
        return view_id
    finally:
        conn.close()




def save_visualization_view_by_groups(nome: str, contexto: str, cd: str, group_labels: list[str], group_map: dict[str, pd.DataFrame], descricao: str, user: str) -> int:
    if not nome.strip():
        raise ValueError("Informe o nome da visão.")
    if not group_labels:
        raise ValueError("Selecione ao menos um grande grupo para a visão.")
    contexto = contexto if contexto in {"global", "matricial", "dashboard", "mensal"} else "global"
    now = now_iso()

    selected_rows: list[pd.Series] = []
    for label in group_labels:
        gdf = group_map.get(label)
        if gdf is None or gdf.empty:
            continue
        for _, r in gdf.sort_values(["grupo_ordem", "indicador_ordem", "indicador"], kind="stable").iterrows():
            selected_rows.append(r)
    if not selected_rows:
        raise ValueError("Os grupos selecionados não possuem indicadores válidos.")

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO visualization_views(nome, contexto, cd, descricao, active, created_by, created_at, updated_by, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(nome, contexto, cd) DO UPDATE SET descricao=excluded.descricao, active=1, updated_by=excluded.updated_by, updated_at=excluded.updated_at
            """,
            (nome.strip(), contexto, cd, descricao.strip(), user, now, user, now),
        )
        view_id = int(conn.execute("SELECT id FROM visualization_views WHERE nome=? AND contexto=? AND cd=?", (nome.strip(), contexto, cd)).fetchone()["id"])
        conn.execute("DELETE FROM visualization_view_items WHERE view_id=?", (view_id,))
        seen: set[str] = set()
        sort_order = 1
        for r in selected_rows:
            code = str(r.get("codigo_indicador") or "").strip()
            identity = code or f"{r['cd']}|{r['grupo']}|{r['indicador']}"
            if identity in seen:
                continue
            seen.add(identity)
            conn.execute(
                """
                INSERT INTO visualization_view_items(view_id, cd, grupo, indicador, codigo_indicador, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (view_id, str(r["cd"]), str(r["grupo"]), str(r["indicador"]), code, sort_order),
            )
            sort_order += 1
        grupos_txt = "; ".join([g.split(" · ")[0] for g in group_labels])
        conn.execute(
            "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("visualization_view", cd, None, None, contexto, None, nome.strip(), descricao.strip() or f"Configuração de visão por grupos: {grupos_txt}", user, now),
        )
        conn.commit()
        return view_id
    finally:
        conn.close()

def render_visualization_admin(contexto: str, cd: str, cfg_scope: pd.DataFrame, key_prefix: str) -> None:
    if not has_perm("configure_indicators"):
        return
    with st.expander("Configurar visões de indicadores", expanded=False):
        st.caption("Configuração por grande grupo. Ao selecionar um macrogrupo, todos os itens abaixo dele entram juntos na visão.")
        group_labels, group_map = build_group_label_map(cfg_scope)
        if not group_labels:
            st.info("Não há grandes grupos disponíveis para montar visão.")
            return
        c1, c2, c3 = st.columns([1.2, 1, 1.8])
        with c1:
            nome = st.text_input("Nome da visão", placeholder="Ex.: Performance", key=f"{key_prefix}_view_nome")
        with c2:
            escopo = st.selectbox("Escopo", ["global", contexto], format_func=lambda x: "Todas as telas" if x == "global" else "Somente esta tela", key=f"{key_prefix}_view_context")
        with c3:
            descricao = st.text_input("Descrição/motivo", placeholder="Ex.: visão executiva de performance operacional", key=f"{key_prefix}_view_desc")

        selected_groups = st.multiselect("Grandes grupos da visão", group_labels, key=f"{key_prefix}_view_groups")

        preview_rows: list[pd.DataFrame] = []
        for label in selected_groups:
            gdf = group_map.get(label)
            if gdf is not None and not gdf.empty:
                preview_rows.append(gdf[["grupo", "indicador", "codigo_indicador", "tipo_campo", "formato"]].copy())
        if preview_rows:
            preview = pd.concat(preview_rows, ignore_index=True).drop_duplicates(subset=["codigo_indicador", "grupo", "indicador"])
            with st.expander(f"Prévia dos indicadores incluídos ({len(preview)})", expanded=False):
                st.dataframe(preview, use_container_width=True, hide_index=True, height=min(360, 80 + len(preview) * 28))
        else:
            st.caption("Selecione um ou mais grandes grupos para visualizar os itens que serão incluídos.")

        csave, cdel = st.columns([1, 1])
        with csave:
            if st.button("Salvar visão", type="primary", use_container_width=True, key=f"{key_prefix}_save_view"):
                try:
                    save_visualization_view_by_groups(nome, escopo, cd, selected_groups, group_map, descricao, st.session_state["user"]["username"])
                    st.success("Visão salva.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        with cdel:
            views = load_visualization_views(contexto, cd)
            if not views.empty:
                label_to_id = {f"{r['nome']} · {r['contexto']} · {r['cd']}": int(r["id"]) for _, r in views.iterrows()}
                remove_label = st.selectbox("Inativar visão existente", [""] + list(label_to_id.keys()), key=f"{key_prefix}_remove_view")
                if st.button("Inativar visão", use_container_width=True, key=f"{key_prefix}_remove_view_btn") and remove_label:
                    conn = get_conn(); now = now_iso(); user = st.session_state["user"]["username"]
                    conn.execute("UPDATE visualization_views SET active=0, updated_by=?, updated_at=? WHERE id=?", (user, now, label_to_id[remove_label]))
                    conn.execute("INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("visualization_view", cd, None, None, "active", "1", "0", "Inativação de visão", user, now))
                    conn.commit(); conn.close()
                    st.success("Visão inativada.")
                    st.rerun()


def _identity_where_clause(row: pd.Series | dict[str, Any], target_cd: str) -> tuple[str, list[Any]]:
    code = str(row.get("codigo_indicador") or "").strip()
    if code:
        return "cd=? AND codigo_indicador=?", [target_cd, code]
    return "cd=? AND grupo=? AND indicador=?", [target_cd, str(row.get("grupo")), str(row.get("indicador"))]


def find_indicator_by_identity(row: pd.Series | dict[str, Any], target_cd: str) -> Optional[sqlite3.Row]:
    conn = get_conn()
    where, params = _identity_where_clause(row, target_cd)
    found = conn.execute(f"SELECT * FROM indicator_config WHERE {where} ORDER BY id LIMIT 1", params).fetchone()
    conn.close()
    return found


def indicator_visible_for_cd(row: pd.Series | dict[str, Any], target_cd: str) -> bool:
    found = find_indicator_by_identity(row, target_cd)
    if not found:
        return False
    return bool(found["ativo"]) and bool(found["exibir_painel_matricial"])


def build_visibility_lookup(cds: list[str]) -> dict[tuple[str, str, str, str], bool]:
    """Mapa rápido de visibilidade por CD/indicador.

    Evita abrir uma conexão SQLite para cada checkbox/linha da matriz.
    Em painéis com muitos indicadores, isso reduz drasticamente o tempo de abertura
    da engrenagem, pois o Streamlit reroda a página inteira a cada clique.
    """
    if not cds:
        return {}
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT cd, codigo_indicador, grupo, indicador, ativo, exibir_painel_matricial
        FROM indicator_config
        WHERE cd IN (%s)
        """ % ",".join(["?"] * len(cds)),
        tuple(cds),
    ).fetchall()
    conn.close()
    lookup: dict[tuple[str, str, str, str], bool] = {}
    for r in rows:
        visible = bool(r["ativo"]) and bool(r["exibir_painel_matricial"])
        cd = str(r["cd"])
        code = str(r["codigo_indicador"] or "").strip()
        grupo = str(r["grupo"] or "")
        indicador = str(r["indicador"] or "")
        if code:
            lookup[("code", cd, code, "")] = visible
        lookup[("legacy", cd, grupo, indicador)] = visible
    return lookup


def indicator_visible_for_cd_fast(row: pd.Series | dict[str, Any], target_cd: str, visibility_lookup: Optional[dict[tuple[str, str, str, str], bool]] = None) -> bool:
    if visibility_lookup is not None:
        code = str(row.get("codigo_indicador") or "").strip()
        if code and ("code", str(target_cd), code, "") in visibility_lookup:
            return bool(visibility_lookup[("code", str(target_cd), code, "")])
        legacy_key = ("legacy", str(target_cd), str(row.get("grupo") or ""), str(row.get("indicador") or ""))
        if legacy_key in visibility_lookup:
            return bool(visibility_lookup[legacy_key])
        return False
    return indicator_visible_for_cd(row, target_cd)


def target_for_matrix_row_cached(cd: str, row: Any, ref_date: str, target_lookup: dict[tuple[str, str, str], dict]) -> Optional[dict]:
    """Versão sem consulta ao banco de target_for_matrix_row para renderização da matriz."""
    grupo = str(row.get("grupo") or "")
    indicador = str(row.get("indicador") or "")
    ref_grupo = str(row.get("meta_ref_grupo") or "").strip()
    ref_indicador = str(row.get("meta_ref_indicador") or "").strip()
    if ref_grupo and ref_indicador:
        found = target_lookup.get((str(cd), ref_grupo, ref_indicador))
        if found:
            return found
    return target_lookup.get((str(cd), grupo, indicador))

def manual_calc_target_suffix(cd: str, row: Any, ref_date: str, target_lookup: Optional[dict[tuple[str, str, str], dict]] = None) -> str:
    """Retorna sufixo visual para cálculo com meta manual fixa.

    Ex.: Total Atrasos (meta = 40).
    A regra vale apenas quando o cálculo usa sinaleira e NÃO aponta para uma
    linha separada de meta/parâmetro. Se houver referência cadastrada, o nome
    permanece limpo porque a meta já está em outro campo.
    """
    try:
        tipo = str(row.get("tipo_campo") or "")
        if tipo != "calculo" or not bool(row.get("usar_sinaleira")):
            return ""
        ref_grupo = str(row.get("meta_ref_grupo") or "").strip()
        ref_indicador = str(row.get("meta_ref_indicador") or "").strip()
        if ref_grupo or ref_indicador:
            return ""
        if target_lookup is not None:
            target = target_for_matrix_row_cached(cd, row, ref_date, target_lookup)
        else:
            target = target_for_matrix_row(cd, row, ref_date)
        if not target or target.get("valor_meta") is None:
            return ""
        meta_text = format_value(target.get("valor_meta"), row.get("formato") or "numero", row.get("indicador") or "")
        if not meta_text:
            return ""
        return f" (meta = {meta_text})"
    except Exception:
        return ""


def clone_indicator_to_cd(source: pd.Series | dict[str, Any], target_cd: str, user: str, motivo: str) -> int:
    conn = get_conn()
    now = now_iso()
    src = dict(source)
    columns = [
        "cd", "grupo", "indicador", "codigo_indicador", "grupo_ordem", "indicador_ordem", "nivel",
        "tipo_campo", "formato", "direcao_meta", "exibir_painel_matricial", "exibir_dashboard",
        "exibir_dashboard_dia", "exibir_dashboard_mes", "exibir_referencia_card", "card_ref_grupo", "card_ref_indicador",
        "exibir_meta_como_linha", "exibir_total_mes", "exibir_atingimento_mes",
        "exibir_objetivo_mes_dashboard", "total_mes_ref_grupo", "total_mes_ref_indicador",
        "usar_sinaleira", "tolerancia_amarela", "formula", "meta_ref_grupo", "meta_ref_indicador",
        "ativo", "updated_by", "updated_at",
    ]
    values = [
        target_cd,
        src.get("grupo"),
        src.get("indicador"),
        src.get("codigo_indicador"),
        int(src.get("grupo_ordem") or 999),
        int(src.get("indicador_ordem") or 999),
        int(src.get("nivel") or 0),
        src.get("tipo_campo") or "dado_diario",
        src.get("formato") or "numero",
        src.get("direcao_meta") or "maior_melhor",
        1,
        int(src.get("exibir_dashboard") or 0),
        int(src.get("exibir_dashboard_dia") if src.get("exibir_dashboard_dia") is not None else 1),
        int(src.get("exibir_dashboard_mes") if src.get("exibir_dashboard_mes") is not None else 1),
        int(src.get("exibir_referencia_card") if src.get("exibir_referencia_card") is not None else 1),
        src.get("card_ref_grupo"),
        src.get("card_ref_indicador"),
        int(src.get("exibir_meta_como_linha") or 0),
        int(src.get("exibir_total_mes") or 0),
        int(src.get("exibir_atingimento_mes") or 0),
        int(src.get("exibir_objetivo_mes_dashboard") or 0),
        src.get("total_mes_ref_grupo"),
        src.get("total_mes_ref_indicador"),
        int(src.get("usar_sinaleira") or 0),
        float(src.get("tolerancia_amarela") or 0.05),
        src.get("formula"),
        src.get("meta_ref_grupo"),
        src.get("meta_ref_indicador"),
        1,
        user,
        now,
    ]
    placeholders = ", ".join(["?"] * len(columns))
    cur = conn.execute(
        f"INSERT INTO indicator_config({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )
    new_id = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("indicator_config", target_cd, src.get("grupo"), src.get("indicador"), "replicar_para_cd", None, "ativo=1;exibir_painel_matricial=1", motivo, user, now),
    )
    conn.commit()
    conn.close()
    return new_id

def set_indicator_visibility_for_cd(source: pd.Series | dict[str, Any], target_cd: str, enabled: bool, motivo: str, user: str) -> None:
    """Ativa/oculta linha na matriz para um CD específico, auditando a mudança.

    Se a linha ainda não existir no CD alvo e o usuário marcar como ativa, o sistema replica
    a configuração-base da linha atual para o novo CD.
    """
    if not motivo.strip():
        raise ValueError("Informe o motivo para ativar/ocultar linhas.")
    found = find_indicator_by_identity(source, target_cd)
    if not found:
        if enabled:
            clone_indicator_to_cd(source, target_cd, user, motivo)
        return
    old = dict(found)
    new_ativo = int(bool(enabled))
    new_exibir = int(bool(enabled))
    conn = get_conn()
    now = now_iso()
    conn.execute(
        "UPDATE indicator_config SET ativo=?, exibir_painel_matricial=?, updated_by=?, updated_at=? WHERE id=?",
        (new_ativo, new_exibir, user, now, int(old["id"])),
    )
    for campo, old_val, new_val in [
        ("ativo", old.get("ativo"), new_ativo),
        ("exibir_painel_matricial", old.get("exibir_painel_matricial"), new_exibir),
    ]:
        if str(old_val) != str(new_val):
            conn.execute(
                "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("indicator_config", target_cd, old.get("grupo"), old.get("indicador"), campo, str(old_val), str(new_val), motivo, user, now),
            )
    conn.commit()
    conn.close()


def handle_visibility_flag_change(source_row_dict: dict[str, Any], target_cd: str, motivo: str, key: str, previous_value: bool) -> None:
    """Callback do checkbox de visibilidade.

    Importante: o Streamlit não permite alterar st.session_state[key] depois que o widget
    com esse mesmo key já foi instanciado no ciclo atual. Por isso toda reversão de valor
    precisa acontecer em callback, antes da renderização do widget.
    """
    new_value = bool(st.session_state.get(key, previous_value))
    if new_value == bool(previous_value):
        return

    motivo_final = str(motivo or "").strip() or "Alteração rápida de visibilidade no Painel Matricial"

    try:
        set_indicator_visibility_for_cd(
            source_row_dict,
            target_cd,
            bool(new_value),
            motivo_final,
            st.session_state["user"]["username"],
        )
        st.session_state["matrix_quick_visibility_success"] = f"Visibilidade atualizada para {target_cd}."
    except Exception as exc:
        st.session_state["matrix_quick_visibility_warning"] = str(exc)
        st.session_state[key] = bool(previous_value)


def render_visibility_flag(source_row: pd.Series | dict[str, Any], target_cd: str, motivo: str, key_prefix: str, current_value: Optional[bool] = None) -> None:
    current = bool(current_value) if current_value is not None else bool(indicator_visible_for_cd(source_row, target_cd))
    key = f"{key_prefix}_flag_{target_cd}_{source_row.get('id', '')}"

    # Inicializa apenas se ainda não existir. Não sobrescrever sempre, pois isso impediria
    # o checkbox de detectar a alteração do usuário no rerun do Streamlit.
    if key not in st.session_state:
        st.session_state[key] = current

    st.checkbox(
        str(target_cd),
        key=key,
        label_visibility="collapsed",
        on_change=handle_visibility_flag_change,
        args=(dict(source_row), target_cd, motivo, key, current),
    )


def handle_total_month_flag_change(source_row_dict: dict[str, Any], motivo: str, key: str, previous_value: bool) -> None:
    """Callback para habilitar/desabilitar a coluna Total Mês na matriz."""
    new_value = bool(st.session_state.get(key, previous_value))
    if new_value == bool(previous_value):
        return

    motivo_final = str(motivo or "").strip() or "Alteração rápida de exibição do Total Mês no Painel Matricial"
    try:
        rid = int(source_row_dict.get("id"))
        user = st.session_state["user"]["username"]
        now = now_iso()
        conn = get_conn()
        old = conn.execute("SELECT * FROM indicator_config WHERE id=?", (rid,)).fetchone()
        if old is None:
            raise ValueError("Indicador não encontrado para atualizar Total Mês.")
        conn.execute(
            "UPDATE indicator_config SET exibir_total_mes=?, updated_by=?, updated_at=? WHERE id=?",
            (int(new_value), user, now, rid),
        )
        conn.execute(
            "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "indicator_config",
                old["cd"],
                old["grupo"],
                old["indicador"],
                "exibir_total_mes",
                str(int(old["exibir_total_mes"] or 0)),
                str(int(new_value)),
                motivo_final,
                user,
                now,
            ),
        )
        conn.commit()
        conn.close()
        st.session_state["matrix_quick_visibility_success"] = "Exibição do Total Mês atualizada."
    except Exception as exc:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:
            pass
        st.session_state["matrix_quick_visibility_warning"] = str(exc)
        st.session_state[key] = bool(previous_value)


def render_total_month_flag(source_row: pd.Series | dict[str, Any], motivo: str, key_prefix: str) -> None:
    """Checkbox inline para mostrar/ocultar o Total Mês da linha."""
    current = bool(source_row.get("exibir_total_mes", 0))
    key = f"{key_prefix}_total_mes_{source_row.get('id', '')}"
    if key not in st.session_state:
        st.session_state[key] = current
    st.checkbox(
        "Total Mês",
        key=key,
        label_visibility="collapsed",
        on_change=handle_total_month_flag_change,
        args=(dict(source_row), motivo, key, current),
    )

def load_values(cds: Optional[list[str]] = None, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
    conn = get_conn()
    sql = "SELECT * FROM values_indicators WHERE 1=1"
    params: list[Any] = []
    if cds:
        sql += " AND cd IN (%s)" % ",".join(["?"] * len(cds))
        params.extend(cds)
    if start:
        sql += " AND data >= ?"
        params.append(start)
    if end:
        sql += " AND data <= ?"
        params.append(end)
    sql += " ORDER BY data, cd, grupo, indicador"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def current_target(cd: str, grupo: str, indicador: str, ref_date: Optional[str] = None) -> Optional[dict]:
    """Retorna a meta válida para uma data.

    Não filtra apenas ativo=1, porque metas encerradas continuam
    válidas no histórico até a data_fim. Isso preserva a regra:
    meta antiga vale até seu encerramento; meta nova vale a partir
    da nova vigência.
    """
    conn = get_conn()
    d = ref_date or date.today().isoformat()
    row = conn.execute(
        """
        SELECT * FROM target_versions
        WHERE cd = ? AND grupo = ? AND indicador = ?
          AND data_inicio <= ? AND (data_fim IS NULL OR data_fim >= ?)
        ORDER BY data_inicio DESC, ativo DESC, id DESC LIMIT 1
        """,
        (cd, grupo, indicador, d, d),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def target_lookup_for_date(cds: list[str], ref_date: str) -> dict[tuple[str, str, str], dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT * FROM target_versions
        WHERE cd IN (%s) AND data_inicio <= ? AND (data_fim IS NULL OR data_fim >= ?)
        ORDER BY data_inicio DESC, ativo DESC, id DESC
        """ % ",".join(["?"] * len(cds)),
        (*cds, ref_date, ref_date),
    ).fetchall()
    conn.close()
    out: dict[tuple[str, str, str], dict] = {}
    for r in rows:
        key = (r["cd"], r["grupo"], r["indicador"])
        if key not in out:
            out[key] = dict(r)
    return out

def target_lookup_for_dates(cds: list[str], date_iso: list[str]) -> dict[str, dict[tuple[str, str, str], dict]]:
    """Carrega metas de um período em consulta única e devolve mapa por data.

    Evita uma consulta no banco para cada dia do mês durante a renderização do dashboard.
    """
    clean_cds = [str(x) for x in cds if str(x).strip()]
    clean_dates = sorted({str(x) for x in date_iso if str(x).strip()})
    if not clean_cds or not clean_dates:
        return {}
    start_ref = clean_dates[0]
    end_ref = clean_dates[-1]
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT * FROM target_versions
        WHERE cd IN (%s)
          AND data_inicio <= ?
          AND (data_fim IS NULL OR data_fim >= ?)
        ORDER BY data_inicio DESC, ativo DESC, id DESC
        """ % ",".join(["?"] * len(clean_cds)),
        (*clean_cds, end_ref, start_ref),
    ).fetchall()
    conn.close()
    rows_dict = [dict(r) for r in rows]
    out: dict[str, dict[tuple[str, str, str], dict]] = {}
    for ds in clean_dates:
        day_map: dict[tuple[str, str, str], dict] = {}
        for r in rows_dict:
            ini = str(r.get("data_inicio") or "")
            fim = r.get("data_fim")
            if ini <= ds and (fim is None or str(fim) >= ds):
                key = (str(r.get("cd") or ""), str(r.get("grupo") or ""), str(r.get("indicador") or ""))
                if key not in day_map:
                    day_map[key] = r
        out[ds] = day_map
    return out


def last_day_of_month(ref: Optional[date] = None) -> date:
    ref = ref or date.today()
    if ref.month == 12:
        return date(ref.year, 12, 31)
    return date(ref.year, ref.month + 1, 1) - timedelta(days=1)


def target_for_matrix_row(cd: str, row: Any, ref_date: str) -> Optional[dict]:
    """Meta usada para exibição e sinaleira de qualquer linha do painel.

    Regra atual:
    - Linhas do tipo meta/parâmetro recebem valor manual diretamente nelas.
    - Cálculos com sinaleira apontam para uma linha de meta/parâmetro manual.
    - Dados diários podem usar uma meta própria quando existir.

    Ou seja: a meta não precisa mais referenciar o indicador real. Ela é um
    input manual versionado e o cálculo escolhe qual campo de meta usará como
    balizador visual.
    """
    grupo = str(row.get("grupo") or "")
    indicador = str(row.get("indicador") or "")
    ref_grupo = str(row.get("meta_ref_grupo") or "").strip()
    ref_indicador = str(row.get("meta_ref_indicador") or "").strip()

    # Para cálculo com sinaleira, usa diretamente a meta/parâmetro selecionada.
    if ref_grupo and ref_indicador:
        found = current_target(cd, ref_grupo, ref_indicador, ref_date)
        if found:
            return found

    # Para meta/parâmetro, ou dado diário com meta própria, usa a própria linha.
    return current_target(cd, grupo, indicador, ref_date)


def load_target_history() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM target_versions ORDER BY cd, grupo, indicador, data_inicio DESC", conn)
    conn.close()
    return df

# ----------------------------- dados e cálculos -----------------------------

def _parse_code_order(code: str) -> tuple[Optional[int], Optional[int]]:
    """Extrai Gxxx/Ixxx do codigo_indicador, quando existir."""
    m = re.search(r"G(\d+)_I(\d+)", str(code or "").upper())
    if not m:
        return None, None
    try:
        return int(m.group(1)), int(m.group(2))
    except Exception:
        return None, None


def _norm_match_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip().upper()
    return text


def learn_upload_codes_from_file(df: pd.DataFrame) -> int:
    """Sincroniza o codigo_indicador do arquivo com o cadastro do sistema.

    Regra:
    - Se o código já existe para o CD, não faz nada.
    - Se vier grupo/indicador, tenta localizar a linha pelo nome e grava o código.
    - Se não vier nome, tenta localizar por Gxxx/Ixxx no código.
    - Como o arquivo enviado é uma planilha de dados diários, a linha encontrada é
      marcada como dado_diario, ativa e visível na matriz.

    Isso evita rejeição por `__CODIGO_NAO_ENCONTRADO__` quando a planilha final
    foi gerada com códigos novos, mas o banco local ainda tem códigos antigos.
    """
    if df.empty or "codigo_indicador" not in df.columns or "cd" not in df.columns:
        return 0

    cols = ["cd", "codigo_indicador"]
    if "grupo" in df.columns:
        cols.append("grupo")
    if "indicador" in df.columns:
        cols.append("indicador")
    candidates = df[cols].drop_duplicates().copy()
    candidates["cd"] = candidates["cd"].astype(str).str.strip().str.upper()
    candidates["codigo_indicador"] = candidates["codigo_indicador"].astype(str).str.strip().str.upper()
    candidates = candidates[candidates["codigo_indicador"].ne("")]
    if candidates.empty:
        return 0

    conn = get_conn()
    updated = 0
    now = now_iso()
    try:
        for r in candidates.to_dict("records"):
            cd = str(r.get("cd") or "").strip().upper()
            code = str(r.get("codigo_indicador") or "").strip().upper()
            if not cd or not code or code.lower() == "nan":
                continue

            exists = conn.execute(
                "SELECT id FROM indicator_config WHERE cd=? AND UPPER(COALESCE(codigo_indicador,''))=? LIMIT 1",
                (cd, code),
            ).fetchone()
            if exists:
                # Mesmo quando já existe, garante que a linha pode receber carga diária.
                conn.execute(
                    "UPDATE indicator_config SET tipo_campo='dado_diario', ativo=1, exibir_painel_matricial=1, updated_at=?, updated_by='import_sync' WHERE id=?",
                    (now, int(exists["id"])),
                )
                updated += 1
                continue

            target = None
            grupo = r.get("grupo") if "grupo" in r else None
            indicador = r.get("indicador") if "indicador" in r else None
            if grupo is not None and indicador is not None and str(indicador).strip():
                cfg_rows = conn.execute(
                    "SELECT id, grupo, indicador FROM indicator_config WHERE cd=?",
                    (cd,),
                ).fetchall()
                g_norm = _norm_match_text(grupo)
                i_norm = _norm_match_text(indicador)
                for cfg in cfg_rows:
                    if _norm_match_text(cfg["grupo"]) == g_norm and _norm_match_text(cfg["indicador"]) == i_norm:
                        target = int(cfg["id"])
                        break

            if target is None:
                g_ord, i_ord = _parse_code_order(code)
                if g_ord is not None and i_ord is not None:
                    row = conn.execute(
                        "SELECT id FROM indicator_config WHERE cd=? AND CAST(grupo_ordem AS INTEGER)=? AND CAST(indicador_ordem AS INTEGER)=? ORDER BY id LIMIT 1",
                        (cd, g_ord, i_ord),
                    ).fetchone()
                    if row:
                        target = int(row["id"])

            if target is not None:
                conn.execute(
                    """
                    UPDATE indicator_config
                       SET codigo_indicador=?, tipo_campo='dado_diario', ativo=1,
                           exibir_painel_matricial=1, updated_at=?, updated_by='import_sync'
                     WHERE id=?
                    """,
                    (code, now, target),
                )
                updated += 1
        conn.commit()
        return updated
    finally:
        conn.close()


def read_csv_auto(uploaded) -> pd.DataFrame:
    """Lê CSV detectando separador comum no Brasil (; ou ,)."""
    content = uploaded.getvalue()
    attempts = [
        {"sep": ";"},
        {"sep": ","},
        {"sep": None, "engine": "python"},
    ]
    best = None
    for kwargs in attempts:
        try:
            df = pd.read_csv(io.BytesIO(content), **kwargs)
            # Prefere o parse que resultou em mais colunas úteis.
            if best is None or len(df.columns) > len(best.columns):
                best = df
            cols_joined = "|".join([str(c).lower() for c in df.columns])
            if any(k in cols_joined for k in ["codigo_indicador", "grupo", "indicador"]):
                return df
        except Exception:
            continue
    if best is None:
        raise ValueError("Não foi possível ler o CSV. Verifique o separador e o encoding.")
    return best


def normalize_long_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza arquivos no formato longo.

    Aceita:
    1) data, cd, grupo, indicador, valor
    2) data, cd, codigo_indicador, valor
    3) data, cd, codigo_indicador, grupo, indicador, valor

    O modelo 3 é o mais seguro para a primeira carga após revisão, porque permite
    sincronizar o código do arquivo com o cadastro local do sistema.
    """
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    aliases = {
        "data": "data", "date": "data", "dia": "data",
        "cd": "cd", "centro": "cd", "centro_distribuicao": "cd", "centro de distribuição": "cd",
        "grupo": "grupo", "bloco": "grupo", "cabecalho": "grupo", "cabeçalho": "grupo",
        "indicador": "indicador", "campo": "indicador", "nome_indicador": "indicador",
        "codigo": "codigo_indicador", "código": "codigo_indicador", "cod_indicador": "codigo_indicador", "codigo_indicador": "codigo_indicador", "código_indicador": "codigo_indicador",
        "valor": "valor", "value": "valor", "dado": "valor",
    }
    out = out.rename(columns={c: aliases.get(c, c) for c in out.columns})
    has_code_model = REQUIRED_CODE_COLUMNS.issubset(set(out.columns))
    has_name_model = REQUIRED_LONG_COLUMNS.issubset(set(out.columns))
    if not has_code_model and not has_name_model:
        raise ValueError("Colunas obrigatórias ausentes. Use data, cd, valor e codigo_indicador; ou data, cd, grupo, indicador, valor.")

    wanted = ["data", "cd"]
    if "codigo_indicador" in out.columns:
        wanted.append("codigo_indicador")
    if "grupo" in out.columns:
        wanted.append("grupo")
    if "indicador" in out.columns:
        wanted.append("indicador")
    wanted.append("valor")
    out = out[wanted].copy()
    out["data"] = pd.to_datetime(out["data"], errors="coerce").dt.date.astype(str)
    out["cd"] = out["cd"].astype(str).str.strip().str.upper()
    if "codigo_indicador" in out.columns:
        out["codigo_indicador"] = out["codigo_indicador"].astype(str).str.strip().str.upper()
    if "grupo" in out.columns:
        out["grupo"] = out["grupo"].map(normalize_text)
    if "indicador" in out.columns:
        out["indicador"] = out["indicador"].map(normalize_text)
    out["valor"] = out["valor"].map(parse_number)
    out = out.dropna(subset=["data", "cd"])
    out = out[out["data"].ne("NaT")]

    # Aprende/sincroniza códigos antes de tentar resolver pelo cadastro.
    if "codigo_indicador" in out.columns:
        learn_upload_codes_from_file(out)

    if "codigo_indicador" in out.columns and ("grupo" not in out.columns or "indicador" not in out.columns):
        cfg = load_indicator_config(active_only=False)[["cd", "codigo_indicador", "grupo", "indicador"]].copy()
        cfg["codigo_indicador"] = cfg["codigo_indicador"].astype(str).str.upper()
        out = out.merge(cfg, on=["cd", "codigo_indicador"], how="left")
    elif "codigo_indicador" in out.columns and {"grupo", "indicador"}.issubset(out.columns):
        # Se veio código e também nome, o código prevalece quando encontrar cadastro.
        cfg = load_indicator_config(active_only=False)[["cd", "codigo_indicador", "grupo", "indicador"]].copy()
        cfg["codigo_indicador"] = cfg["codigo_indicador"].astype(str).str.upper()
        out = out.merge(cfg, on=["cd", "codigo_indicador"], how="left", suffixes=("_arquivo", ""))
        out["grupo"] = out["grupo"].fillna(out.get("grupo_arquivo"))
        out["indicador"] = out["indicador"].fillna(out.get("indicador_arquivo"))
        for c in ["grupo_arquivo", "indicador_arquivo"]:
            if c in out.columns:
                out = out.drop(columns=[c])

    if "codigo_indicador" in out.columns:
        missing_code_mask = out["grupo"].isna() | out["indicador"].isna()
        out.loc[missing_code_mask, "grupo"] = "__CODIGO_NAO_ENCONTRADO__"
        out.loc[missing_code_mask, "indicador"] = out.loc[missing_code_mask, "codigo_indicador"].astype(str)
    out = out.dropna(subset=["grupo", "indicador"])
    cols = ["data", "cd"]
    if "codigo_indicador" in out.columns:
        cols.append("codigo_indicador")
    cols += ["grupo", "indicador", "valor"]
    return out[cols].copy()


def normalize_wide_df(df: pd.DataFrame, default_cd: Optional[str] = None) -> pd.DataFrame:
    raw = df.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    lower = {c.lower(): c for c in raw.columns}
    has_nome = "grupo" in lower and "indicador" in lower
    has_codigo = any(k in lower for k in ["codigo_indicador", "código_indicador", "codigo", "código", "cod_indicador"])
    if not has_nome and not has_codigo:
        raise ValueError("Modelo matricial precisa das colunas grupo/indicador ou codigo_indicador.")
    grupo_col = lower.get("grupo")
    indicador_col = lower.get("indicador")
    codigo_col = lower.get("codigo_indicador") or lower.get("código_indicador") or lower.get("codigo") or lower.get("código") or lower.get("cod_indicador")
    cd_col = lower.get("cd")
    if not cd_col and not default_cd:
        raise ValueError("Modelo matricial sem coluna cd exige CD padrão informado na tela.")
    id_cols = ([grupo_col] if grupo_col else []) + ([indicador_col] if indicador_col else []) + ([codigo_col] if codigo_col else []) + ([cd_col] if cd_col else [])
    date_cols = []
    for c in raw.columns:
        if c in id_cols:
            continue
        try:
            pd.to_datetime(c, errors="raise")
            date_cols.append(c)
        except Exception:
            pass
    if not date_cols:
        raise ValueError("Nenhuma coluna de data identificada no modelo matricial.")
    long = raw.melt(id_vars=id_cols, value_vars=date_cols, var_name="data", value_name="valor")
    rename_map = {}
    if grupo_col:
        rename_map[grupo_col] = "grupo"
    if indicador_col:
        rename_map[indicador_col] = "indicador"
    if codigo_col:
        rename_map[codigo_col] = "codigo_indicador"
    long = long.rename(columns=rename_map)
    if cd_col:
        long = long.rename(columns={cd_col: "cd"})
    else:
        long["cd"] = default_cd
    return normalize_long_df(long)


def parse_uploaded_file(uploaded, default_cd: Optional[str]) -> pd.DataFrame:
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        df = read_csv_auto(uploaded)
        cols = {str(c).strip().lower() for c in df.columns}
        if REQUIRED_LONG_COLUMNS.issubset(cols) or REQUIRED_CODE_COLUMNS.issubset(cols):
            return normalize_long_df(df)
        return normalize_wide_df(df, default_cd)
    xl = pd.ExcelFile(uploaded)
    errors = []
    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet)
            cols = {str(c).strip().lower() for c in df.columns}
            if REQUIRED_LONG_COLUMNS.issubset(cols) or REQUIRED_CODE_COLUMNS.issubset(cols):
                return normalize_long_df(df)
            if {"grupo", "indicador"}.issubset(cols) or {"codigo_indicador"}.issubset(cols) or {"codigo"}.issubset(cols):
                return normalize_wide_df(df, default_cd)
        except Exception as exc:
            errors.append(f"{sheet}: {exc}")
    raise ValueError("Nenhuma aba válida encontrada. " + " | ".join(errors[:3]))


def filter_import_by_config(df: pd.DataFrame, user: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cds = allowed_centers(user)
    cfg = load_indicator_config(active_only=False).copy()

    base_cols = ["data", "cd"]
    if "codigo_indicador" in df.columns:
        base_cols.append("codigo_indicador")
    base_cols += ["grupo", "indicador", "valor"]

    if "codigo_indicador" in df.columns:
        cfg_code = cfg[["cd", "codigo_indicador", "grupo", "indicador", "tipo_campo", "ativo"]].copy()
        cfg_code["codigo_indicador"] = cfg_code["codigo_indicador"].astype(str).str.upper()
        merged = df.merge(
            cfg_code.rename(columns={"grupo": "grupo_cfg", "indicador": "indicador_cfg"}),
            on=["cd", "codigo_indicador"],
            how="left",
        )
        merged["grupo"] = merged["grupo_cfg"].fillna(merged["grupo"])
        merged["indicador"] = merged["indicador_cfg"].fillna(merged["indicador"])
    else:
        cfg_name = cfg[["cd", "grupo", "indicador", "tipo_campo", "ativo"]].copy()
        merged = df.merge(cfg_name, on=["cd", "grupo", "indicador"], how="left")

    merged["motivo_rejeicao"] = ""
    merged.loc[~merged["cd"].isin(cds), "motivo_rejeicao"] = "CD sem permissão para o usuário"
    merged.loc[merged["tipo_campo"].isna(), "motivo_rejeicao"] = "Código/indicador não encontrado no cadastro"
    merged.loc[(merged["motivo_rejeicao"].eq("")) & (merged["ativo"].fillna(0).astype(int).ne(1)), "motivo_rejeicao"] = "Indicador inativo"
    merged.loc[(merged["motivo_rejeicao"].eq("")) & (merged["tipo_campo"].ne("dado_diario")), "motivo_rejeicao"] = "Indicador não classificado como dado_diario"

    ok = merged["motivo_rejeicao"].eq("")
    accepted_cols = [c for c in base_cols if c in merged.columns]
    accepted = merged[ok][accepted_cols].copy()
    # upsert_values não precisa do código, mas mantemos no preview; ele ignora colunas extras.
    rejected_cols = accepted_cols + ["tipo_campo", "ativo", "motivo_rejeicao"]
    rejected = merged[~ok][[c for c in rejected_cols if c in merged.columns]].copy()
    return accepted, rejected


def upsert_values(df: pd.DataFrame, user: str, source: str, batch_id: str, motivo: str) -> tuple[int, int]:
    """Insere/atualiza valores usando codigo_indicador como chave preferencial.

    O dado é sempre gravado com o grupo/indicador vigente na configuração.
    Isso evita divergência entre a tela de preenchimento e a matriz quando nomes
    ou ordem forem ajustados pelo admin.
    """
    conn = get_conn()
    value_cols = {r[1] for r in conn.execute("PRAGMA table_info(values_indicators)").fetchall()}
    has_code_col = "codigo_indicador" in value_cols
    inserted = updated = 0
    now = now_iso()

    for r in df.to_dict("records"):
        new_value = None if pd.isna(r.get("valor")) else float(r.get("valor"))
        cd = str(r.get("cd") or "").strip().upper()
        codigo = str(r.get("codigo_indicador") or "").strip()
        grupo = str(r.get("grupo") or "").strip()
        indicador = str(r.get("indicador") or "").strip()

        # Revalida a configuração vigente pelo código. O código é a chave operacional.
        if codigo:
            cfg = conn.execute(
                "SELECT grupo, indicador FROM indicator_config WHERE cd=? AND codigo_indicador=? ORDER BY ativo DESC, id DESC LIMIT 1",
                (cd, codigo),
            ).fetchone()
            if cfg:
                grupo = str(cfg["grupo"])
                indicador = str(cfg["indicador"])

        old = None
        if has_code_col and codigo:
            old = conn.execute(
                "SELECT id, valor FROM values_indicators WHERE data=? AND cd=? AND codigo_indicador=? ORDER BY id DESC LIMIT 1",
                (r["data"], cd, codigo),
            ).fetchone()
        if old is None:
            old = conn.execute(
                "SELECT id, valor FROM values_indicators WHERE data=? AND cd=? AND grupo=? AND indicador=? ORDER BY id DESC LIMIT 1",
                (r["data"], cd, grupo, indicador),
            ).fetchone()

        if old is None:
            if has_code_col:
                conn.execute(
                    "INSERT INTO values_indicators(data, cd, grupo, indicador, valor, source, batch_id, created_by, created_at, codigo_indicador) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (r["data"], cd, grupo, indicador, new_value, source, batch_id, user, now, codigo or None),
                )
            else:
                conn.execute(
                    "INSERT INTO values_indicators(data, cd, grupo, indicador, valor, source, batch_id, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (r["data"], cd, grupo, indicador, new_value, source, batch_id, user, now),
                )
            inserted += 1
        else:
            old_value = None if old["valor"] is None else float(old["valor"])
            changed = (old_value is None and new_value is not None) or (old_value is not None and new_value is None) or (old_value is not None and new_value is not None and abs(old_value - new_value) > 1e-9)
            if changed:
                if has_code_col:
                    conn.execute(
                        "UPDATE values_indicators SET valor=?, grupo=?, indicador=?, codigo_indicador=?, source=?, batch_id=?, updated_by=?, updated_at=? WHERE id=?",
                        (new_value, grupo, indicador, codigo or None, source, batch_id, user, now, old["id"]),
                    )
                else:
                    conn.execute(
                        "UPDATE values_indicators SET valor=?, grupo=?, indicador=?, source=?, batch_id=?, updated_by=?, updated_at=? WHERE id=?",
                        (new_value, grupo, indicador, source, batch_id, user, now, old["id"]),
                    )
                conn.execute(
                    "INSERT INTO audit_changes(data, cd, grupo, indicador, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (r["data"], cd, grupo, indicador, old_value, new_value, motivo, user, now),
                )
                updated += 1
            elif has_code_col and codigo:
                # Mantém o vínculo do código atualizado mesmo quando o valor não mudou.
                conn.execute("UPDATE values_indicators SET grupo=?, indicador=?, codigo_indicador=? WHERE id=?", (grupo, indicador, codigo, old["id"]))

    conn.execute(
        "INSERT OR IGNORE INTO imports(batch_id, filename, cd, rows_received, rows_inserted, rows_updated, imported_by, imported_at, motivo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (batch_id, source, "MULTI", len(df), inserted, updated, user, now, motivo),
    )
    conn.commit()
    conn.close()
    return inserted, updated

def _formula_key(value: Any) -> str:
    """Normaliza chaves de fórmula para evitar divergência por espaço, caixa ou acento."""
    s = "" if value is None else str(value)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.upper().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _formula_code_key(value: Any) -> str:
    """Normaliza códigos técnicos de indicadores usados entre colchetes."""
    s = _formula_key(value)
    s = re.sub(r"[^A-Z0-9]+", "_", s).strip("_")
    return s


def safe_eval_formula(formula: str, values: dict[str, float]) -> Optional[float]:
    """Avalia fórmula de indicador.

    Regras:
    - Campos devem estar entre colchetes: [CODIGO_INDICADOR].
    - Códigos são comparados de forma tolerante a caixa, espaços e caracteres especiais.
    - Campo sem valor no dia é tratado como 0. Isso permite somatórios de vários itens
      mesmo quando algum componente ainda não teve movimentação/preenchimento.
    - Divisão por zero ou fórmula inválida retorna vazio.
    """
    if not formula:
        return None

    raw_formula = str(formula)
    if not raw_formula.strip() or raw_formula.strip().lower() == "nan":
        return None

    value_exact: dict[str, float] = {}
    value_norm: dict[str, float] = {}
    value_code: dict[str, float] = {}

    for name, val in values.items():
        if val is None or pd.isna(val):
            continue
        try:
            fval = float(val)
        except Exception:
            continue
        skey = str(name).strip()
        value_exact[skey] = fval
        value_norm[_formula_key(skey)] = fval
        value_code[_formula_code_key(skey)] = fval

    def replace_token(match: re.Match) -> str:
        token = str(match.group(1) or "").strip()
        if token in value_exact:
            return str(float(value_exact[token]))

        norm = _formula_key(token)
        if norm in value_norm:
            return str(float(value_norm[norm]))

        code = _formula_code_key(token)
        if code in value_code:
            return str(float(value_code[code]))

        # Compatibilidade: alguns códigos antigos terminavam com "_" e outros não.
        code_no_underscore = code.rstrip("_")
        for k, v in value_code.items():
            if k.rstrip("_") == code_no_underscore:
                return str(float(v))

        # Campo não preenchido no dia: tratar como zero para somatórios.
        return "0"

    expr = re.sub(r"\[([^\]]+)\]", replace_token, raw_formula)
    expr = expr.replace(",", ".").replace("×", "*").replace("÷", "/")

    if not re.fullmatch(r"[0-9\.\+\-\*\/\(\)\s]+", expr):
        return None

    try:
        result = float(eval(expr, {"__builtins__": {}}, {}))
        if pd.isna(result) or result in (float("inf"), float("-inf")):
            return None
        return result
    except Exception:
        return None


def compute_calculated_values(df_values: pd.DataFrame, configs: pd.DataFrame, cd: str, ref_date: str) -> dict[tuple[str, str], float]:
    vals = df_values[(df_values["cd"].astype(str) == str(cd)) & (df_values["data"] == ref_date)].copy()

    cfg_cd = configs[configs["cd"].astype(str) == str(cd)].copy()
    cfg_lookup = cfg_cd.set_index(["grupo", "indicador"], drop=False) if not cfg_cd.empty else pd.DataFrame()

    by_ind: dict[str, float] = {}

    def add_value_keys(grupo: str, indicador: str, valor: float) -> None:
        by_ind[str(indicador)] = float(valor)
        by_ind[f"{grupo} · {indicador}"] = float(valor)
        if not cfg_cd.empty and (grupo, indicador) in cfg_lookup.index:
            cfgrow = cfg_lookup.loc[(grupo, indicador)]
            if isinstance(cfgrow, pd.DataFrame):
                cfgrow = cfgrow.iloc[0]
            codigo = cfgrow.get("codigo_indicador")
            if codigo is not None and not pd.isna(codigo) and str(codigo).strip():
                by_ind[str(codigo).strip()] = float(valor)
            try:
                by_ind[f"ID_{int(cfgrow['id'])}"] = float(valor)
            except Exception:
                pass

    for _, r in vals.iterrows():
        if r["valor"] is not None and not pd.isna(r["valor"]):
            add_value_keys(str(r["grupo"]), str(r["indicador"]), float(r["valor"]))

    # Inclui metas e parâmetros manuais como componentes válidos de fórmula.
    # Antes, o cálculo só enxergava valores vindos de values_indicators; então fórmulas
    # como [Abastecimento Realizado] / [Abastecimento Projetado] ficavam vazias
    # quando o projetado era uma meta/parâmetro exibido pela target_versions.
    try:
        target_lookup = target_lookup_for_date([cd], ref_date)
    except Exception:
        target_lookup = {}
    for _, r in cfg_cd[cfg_cd["tipo_campo"].isin(["meta", "parametro"])].iterrows():
        target = target_for_matrix_row_cached(cd, r, ref_date, target_lookup)
        if target and target.get("valor_meta") is not None and not pd.isna(target.get("valor_meta")):
            try:
                add_value_keys(str(r["grupo"]), str(r["indicador"]), float(target["valor_meta"]))
            except Exception:
                pass

    out: dict[tuple[str, str], float] = {}
    calc_cfg = cfg_cd[(cfg_cd["tipo_campo"] == "calculo") & cfg_cd["formula"].notna()].copy()
    calc_cfg = calc_cfg.sort_values(["grupo_ordem", "indicador_ordem", "grupo", "indicador"], kind="stable")

    # Duas passagens simples permitem cálculo dependente de outro cálculo já resolvido.
    for _ in range(2):
        changed = False
        for _, r in calc_cfg.iterrows():
            formula = "" if pd.isna(r.get("formula")) else str(r.get("formula") or "")
            res = safe_eval_formula(formula, by_ind)
            if res is not None:
                key = (str(r["grupo"]), str(r["indicador"]))
                if key not in out or abs(out[key] - float(res)) > 1e-12:
                    out[key] = float(res)
                    add_value_keys(str(r["grupo"]), str(r["indicador"]), float(res))
                    changed = True
        if not changed:
            break
    return out


def _cfg_text(cfg: Optional[pd.Series]) -> str:
    if cfg is None:
        return ""
    parts = []
    for field in ["grupo", "indicador", "codigo_indicador", "formula"]:
        try:
            parts.append(str(cfg.get(field) or ""))
        except Exception:
            pass
    return _formula_key(" ".join(parts)).lower()


def _effective_direction(direcao: str, value: float, meta: float, cfg: Optional[pd.Series] = None) -> str:
    """Resolve a direção de comparação da sinaleira.

    Em cálculos percentuais de atingimento, como `Faturamento Realizado /
    Faturamento Necessário`, valores acima de 100% devem ficar verdes. Na
    prática alguns indicadores ficaram com direção `igual` ou `menor_melhor`
    durante ajustes de configuração. Esta camada evita falso vermelho quando o
    próprio nome/fórmula indica atingimento positivo. Indicadores negativos
    como atraso, ruptura e perda continuam usando menor_melhor quando aplicável.
    """
    direcao = str(direcao or "maior_melhor")
    if cfg is None:
        return direcao

    tipo = str(cfg.get("tipo_campo") or "")
    formato = str(cfg.get("formato") or "")
    text = _cfg_text(cfg)

    negative_terms = [
        "atraso", "ruptura", "perda", "avaria", "ocorrencia", "ocorrência",
        "erro", "pendente", "fora", "devolucao", "devolução", "rejeicao",
        "rejeição", "corte", "falta", "cancelamento",
    ]
    positive_terms = [
        "performance", "faturamento", "atingimento", "realizado", "receita",
        "produtividade", "prazo", "on time", "otd", "sla", "meta", "nivel",
        "nível", "conversao", "conversão",
    ]
    has_negative = any(term in text for term in negative_terms)
    has_positive = any(term in text for term in positive_terms)

    # Para cálculo percentual, respeite a direção configurada pelo admin.
    # A regra anterior tratava qualquer fórmula com divisão como `maior_melhor`,
    # o que invertia indicadores como `% Coletas em Pulmão`, onde menor é melhor.
    # Só aplicamos inferência automática quando a direção veio como `igual` e o
    # texto do indicador/fórmula sinaliza claramente atingimento positivo.
    if tipo == "calculo" and formato == "percentual" and not has_negative:
        if direcao == "igual" and has_positive:
            return "maior_melhor"

    # Caso específico: somente direções ambíguas (`igual`) podem ser ajustadas
    # automaticamente. Direções explícitas como `menor_melhor` devem prevalecer.
    if tipo == "calculo" and has_positive and not has_negative and value >= meta and direcao == "igual":
        return "maior_melhor"

    return direcao


def status_for_value(value: Optional[float], target: Optional[dict], cfg: Optional[pd.Series] = None) -> tuple[str, str]:
    if value is None or target is None:
        return "", "Sem meta"

    v = float(value)
    meta = float(target["valor_meta"])

    cfg_tipo = ""
    cfg_formato = ""
    cfg_direcao = None
    cfg_tol = None
    if cfg is not None:
        try:
            cfg_tipo = str(cfg.get("tipo_campo") or "")
            cfg_formato = str(cfg.get("formato") or "")
            cfg_direcao = cfg.get("direcao_meta")
            cfg_tol = cfg.get("tolerancia_amarela")
        except Exception:
            pass

    # Para linhas calculadas, a direção operacional da própria linha deve prevalecer
    # sobre a direção salva na meta manual. Isso evita falso vermelho quando a meta
    # foi gravada antes com direção `igual`, mas o cálculo está como `maior_melhor`.
    if cfg_tipo == "calculo":
        direcao_original = cfg_direcao or target.get("direcao_meta") or "maior_melhor"
    else:
        direcao_original = target.get("direcao_meta") or cfg_direcao or "maior_melhor"

    tol = float(target.get("tolerancia_amarela") or cfg_tol or 0.05)

    # Normalização de escala para percentuais.
    # No cadastro manual, é comum o usuário informar 99 ou 100 para representar
    # 99%/100%. Internamente, o painel calcula percentuais como 0,99 ou 1,00.
    # Portanto, para indicadores percentuais, metas acima de 2 são interpretadas
    # como percentuais digitados em escala humana e convertidas para base decimal.
    if cfg_formato == "percentual":
        if abs(meta) > 2:
            meta = meta / 100.0
        # Proteção adicional caso algum cálculo/manual venha em escala 100.
        if abs(v) > 2 and abs(meta) <= 2:
            v = v / 100.0

    direcao = _effective_direction(str(direcao_original), v, meta, cfg)

    if direcao == "maior_melhor":
        if v >= meta:
            return "🟢", "Dentro"
        if v >= meta * (1 - tol):
            return "🟡", "Atenção"
        return "🔴", "Fora"
    if direcao == "menor_melhor":
        if v <= meta:
            return "🟢", "Dentro"
        if v <= meta * (1 + tol):
            return "🟡", "Atenção"
        return "🔴", "Fora"
    if abs(v - meta) <= abs(meta) * tol:
        return "🟢", "Dentro"
    return "🔴", "Fora"

# ----------------------------- gravação config/metas -----------------------------

def audit_config(entidade: str, cd: str, grupo: str, indicador: str, campo: str, old: Any, new: Any, motivo: str, user: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (entidade, cd, grupo, indicador, campo, str(old), str(new), motivo, user, now_iso()),
    )
    conn.commit()
    conn.close()


def save_indicator_config(record_id: int, updates: dict[str, Any], motivo: str, user: str) -> None:
    conn = get_conn()
    old = dict(conn.execute("SELECT * FROM indicator_config WHERE id=?", (record_id,)).fetchone())
    set_clause = ", ".join([f"{k}=?" for k in updates])
    params = list(updates.values()) + [user, now_iso(), record_id]
    conn.execute(f"UPDATE indicator_config SET {set_clause}, updated_by=?, updated_at=? WHERE id=?", params)
    conn.commit()
    conn.close()
    for k, new in updates.items():
        if str(old.get(k)) != str(new):
            audit_config("indicator_config", old["cd"], old["grupo"], old["indicador"], k, old.get(k), new, motivo, user)


def create_target_version(cd: str, grupo: str, indicador: str, meta: float, direcao: str, data_inicio: str, vis_dash: bool, vis_mat: bool, vis_linha: bool, sinal: bool, tol: float, motivo: str, user: str) -> None:
    conn = get_conn()
    start = pd.to_datetime(data_inicio).date()
    end_prev = (start - timedelta(days=1)).isoformat()
    conn.execute(
        "UPDATE target_versions SET data_fim=?, ativo=0 WHERE cd=? AND grupo=? AND indicador=? AND ativo=1 AND (data_fim IS NULL OR data_fim >= ?)",
        (end_prev, cd, grupo, indicador, data_inicio),
    )
    conn.execute(
        """
        INSERT INTO target_versions(cd, grupo, indicador, valor_meta, direcao_meta, data_inicio, data_fim, ativo, exibir_dashboard, exibir_painel_matricial, exibir_meta_como_linha, usar_sinaleira, tolerancia_amarela, motivo, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, NULL, 1, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (cd, grupo, indicador, float(meta), direcao, data_inicio, int(vis_dash), int(vis_mat), int(vis_linha), int(sinal), float(tol), motivo, user, now_iso()),
    )
    conn.commit()
    conn.close()
    audit_config("target_versions", cd, grupo, indicador, "nova_meta_versionada", "", f"{meta} desde {data_inicio}", motivo, user)


# ----------------------------- matriz executiva -----------------------------

def matrix_cell(content: str, cls: str = "") -> None:
    st.markdown(f"<div class='matrix-cell {cls}'>{content}</div>", unsafe_allow_html=True)


def render_matrix_header(date_labels: list[str], summary_labels: list[str] | str, show_config: bool, admin_centers: Optional[list[str]] = None, show_total_flag: bool = False) -> None:
    admin_centers = admin_centers or []
    if isinstance(summary_labels, str):
        summary_labels = [summary_labels]
    summary_labels = list(summary_labels or [])
    widths = ([0.40] * len(admin_centers)) + ([0.55] if show_total_flag else []) + ([0.34] if show_config else []) + [3.85] + [1.15] * len(date_labels) + [1.15] * len(summary_labels)
    cols = st.columns(widths, gap="small")
    idx = 0
    for center in admin_centers:
        with cols[idx]:
            matrix_cell(html.escape(center), "matrix-head")
        idx += 1
    if show_total_flag:
        with cols[idx]:
            matrix_cell("Total", "matrix-head")
        idx += 1
    if show_config:
        with cols[idx]:
            matrix_cell("⚙️", "matrix-head")
        idx += 1
    with cols[idx]:
        matrix_cell("Indicador", "matrix-head")
    idx += 1
    for label in date_labels:
        with cols[idx]:
            matrix_cell(html.escape(label), "matrix-head")
        idx += 1
    for label in summary_labels:
        with cols[idx]:
            matrix_cell(html.escape(str(label)), "matrix-head")
        idx += 1

def _matrix_has_unsaved_config() -> bool:
    return bool(st.session_state.get("matrix_config_dirty")) and bool(st.session_state.get("matrix_config_record_id"))


def request_matrix_config(record_id: int) -> None:
    """Controla abertura/fechamento da configuração inline da matriz.

    Regras:
    - clicar na engrenagem da linha aberta fecha a seção;
    - clicar em outra linha fecha a anterior e abre a nova;
    - se a seção atual tiver alterações não salvas, bloqueia a troca e avisa.
    """
    record_id = int(record_id)
    current = st.session_state.get("matrix_config_record_id")
    dirty = _matrix_has_unsaved_config()

    # Toggle: clicar novamente na mesma engrenagem fecha.
    if current == record_id:
        st.session_state.pop("matrix_config_record_id", None)
        st.session_state["matrix_config_dirty"] = False
        st.session_state.pop("matrix_config_dirty_record_id", None)
        st.session_state.pop("matrix_config_warning", None)
        st.session_state.pop("matrix_config_pending_record_id", None)
        return

    # Troca bloqueada se a seção atual foi alterada e ainda não foi salva.
    if current is not None and dirty:
        st.session_state["matrix_config_warning"] = (
            "Existe uma configuração aberta com alterações não salvas. "
            "Salve a configuração atual antes de abrir outro indicador."
        )
        st.session_state["matrix_config_pending_record_id"] = record_id
        return

    st.session_state["matrix_config_record_id"] = record_id
    st.session_state["matrix_config_dirty"] = False
    st.session_state.pop("matrix_config_dirty_record_id", None)
    st.session_state.pop("matrix_config_warning", None)
    st.session_state.pop("matrix_config_pending_record_id", None)


def render_matrix_unsaved_warning() -> None:
    msg = st.session_state.get("matrix_config_warning")
    if not msg:
        return
    st.warning(msg)
    pending = st.session_state.get("matrix_config_pending_record_id")
    if pending is not None:
        c1, c2 = st.columns([1, 1])
        with c1:
            st.caption("A troca foi bloqueada para evitar perda de configuração.")
        with c2:
            if st.button("Descartar alteração e abrir novo", key="matrix_discard_and_open", use_container_width=True):
                st.session_state["matrix_config_record_id"] = int(pending)
                st.session_state["matrix_config_dirty"] = False
                st.session_state.pop("matrix_config_dirty_record_id", None)
                st.session_state.pop("matrix_config_warning", None)
                st.session_state.pop("matrix_config_pending_record_id", None)
                st.rerun()


def render_matrix_row(
    row_id: int,
    indicador_html: str,
    values: list[str],
    summary_values: list[str] | str,
    show_config: bool,
    tooltip: str,
    source_row: Optional[pd.Series | dict[str, Any]] = None,
    admin_centers: Optional[list[str]] = None,
    motivo_visibilidade: str = "",
    hidden_row: bool = False,
    visibility_lookup: Optional[dict[tuple[str, str, str, str], bool]] = None,
    show_total_flag: bool = False,
) -> None:
    admin_centers = admin_centers or []
    if isinstance(summary_values, str):
        summary_values = [summary_values]
    summary_values = list(summary_values or [])
    widths = ([0.40] * len(admin_centers)) + ([0.55] if show_total_flag else []) + ([0.34] if show_config else []) + [3.85] + [1.15] * len(values) + [1.15] * len(summary_values)
    row_class = "matrix-hidden-row" if hidden_row else ""
    if row_class:
        st.markdown(f"<div class='{row_class}'>", unsafe_allow_html=True)
    cols = st.columns(widths, gap="small")
    idx = 0
    if source_row is not None:
        for center in admin_centers:
            with cols[idx]:
                current_flag = indicator_visible_for_cd_fast(source_row, center, visibility_lookup)
                render_visibility_flag(source_row, center, motivo_visibilidade, key_prefix="matrix_inline", current_value=current_flag)
            idx += 1
    else:
        for _ in admin_centers:
            with cols[idx]:
                matrix_cell("", "matrix-value")
            idx += 1
    if show_total_flag:
        with cols[idx]:
            if source_row is not None:
                render_total_month_flag(source_row, motivo_visibilidade, key_prefix="matrix_inline")
            else:
                matrix_cell("", "matrix-value")
        idx += 1
    if show_config:
        with cols[idx]:
            opened = st.session_state.get("matrix_config_record_id") == int(row_id)
            btn_label = "✕" if opened else "⚙️"
            if st.button(btn_label, key=f"matrix_cfg_{row_id}", use_container_width=True):
                request_matrix_config(int(row_id))
                st.rerun()
        idx += 1
    with cols[idx]:
        matrix_cell(indicador_html, "matrix-indicator")
    idx += 1
    for value in values:
        with cols[idx]:
            matrix_cell(html.escape(value or ""), "matrix-value")
        idx += 1
    for value in summary_values:
        with cols[idx]:
            matrix_cell(html.escape(value or ""), "matrix-value")
        idx += 1
    if row_class:
        st.markdown("</div>", unsafe_allow_html=True)

def render_matrix_scroll_table(date_labels: list[str], summary_labels: list[str] | str, rows: list[dict[str, Any]], admin_centers: Optional[list[str]] = None, show_total_flag: bool = False) -> None:
    """Tabela matricial com rolagem horizontal para períodos longos.

    Para admins, a tabela exibe as colunas de status dos CDs no início. A edição
    interativa dessas flags fica no editor compacto logo acima da tabela, dentro
    da própria página/bloco.
    """
    admin_centers = admin_centers or []
    if isinstance(summary_labels, str):
        summary_labels = [summary_labels]
    summary_labels = list(summary_labels or [])
    flag_header = "".join([f"<th class='matrix-flag-col'>{html.escape(c)}</th>" for c in admin_centers])
    if show_total_flag:
        flag_header += "<th class='matrix-flag-col'>Total</th>"
    header_cells = "".join([f"<th>{html.escape(str(lbl))}</th>" for lbl in date_labels])
    summary_header = "".join([f"<th>{html.escape(str(lbl))}</th>" for lbl in summary_labels])
    body = []
    for r in rows:
        flag_cells = ""
        for c in admin_centers:
            flag_cells += f"<td class='matrix-flag-col'>{'☑' if r.get('flags', {}).get(c) else '☐'}</td>"
        if show_total_flag:
            src = r.get('source_row')
            total_enabled = bool(src.get('exibir_total_mes')) if src is not None else False
            flag_cells += f"<td class='matrix-flag-col'>{'☑' if total_enabled else '☐'}</td>"
        vals = "".join([f"<td class='matrix-num'>{html.escape(str(v or ''))}</td>" for v in r.get('values', [])])
        summary_values = r.get('summary_values')
        if summary_values is None:
            summary_values = [r.get('summary_value', '')]
        summary_vals = "".join([f"<td class='matrix-num'>{html.escape(str(v or ''))}</td>" for v in list(summary_values)])
        hidden_cls = " matrix-hidden-html" if r.get("hidden_row") else ""
        body.append(
            f"<tr class='{hidden_cls}'>"
            f"{flag_cells}"
            f"<td class='matrix-ind-col'>{r.get('indicador_html','')}</td>"
            f"{vals}"
            f"{summary_vals}"
            "</tr>"
        )
    table_html = (
        "<div class='matrix-scroll-wrap'>"
        "<table class='matrix-table'>"
        "<thead><tr>"
        f"{flag_header}"
        "<th class='matrix-ind-col'>Indicador</th>"
        f"{header_cells}"
        f"{summary_header}"
        "</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)


def render_long_group_visibility_editor(grupo: str, built_rows: list[dict[str, Any]], admin_centers: list[str], motivo: str) -> None:
    if not admin_centers or not built_rows:
        return
    group_key = hashlib.md5(str(grupo).encode("utf-8")).hexdigest()[:8]
    with st.expander("Flags de visibilidade por CD", expanded=False):
        st.caption("Edite as flags neste próprio bloco. Marcar ativa/exibe a linha no Painel Matricial; desmarcar oculta/desabilita para o CD. A coluna Total Mês habilita o acumulado mensal da linha.")
        records = []
        source_by_id: dict[int, Any] = {}
        for r in built_rows:
            rid = int(r["id"])
            source_by_id[rid] = r.get("source_row")
            src = r.get("source_row")
            rec = {
                "id": rid,
                "indicador": re.sub('<[^<]+?>', '', str(r.get("indicador_html", ""))).strip(),
                "total_mes": bool(src.get("exibir_total_mes")) if src is not None else False,
            }
            for c in admin_centers:
                rec[c] = bool(r.get("flags", {}).get(c))
            records.append(rec)
        df_flags = pd.DataFrame(records)
        edited = st.data_editor(
            df_flags,
            hide_index=True,
            use_container_width=True,
            key=f"matrix_flags_editor_{group_key}",
            disabled=["id", "indicador"],
            column_config={**{c: st.column_config.CheckboxColumn(c) for c in admin_centers}, "total_mes": st.column_config.CheckboxColumn("Total Mês")},
        )
        if st.button("Aplicar flags deste bloco", key=f"matrix_apply_flags_{group_key}", use_container_width=True):
            if not motivo.strip():
                st.error("Informe o motivo antes de aplicar as alterações de visibilidade.")
                return
            changes = 0
            orig = df_flags.set_index("id")
            for _, er in edited.iterrows():
                rid = int(er["id"])
                source = source_by_id.get(rid)
                if source is None:
                    continue
                for c in admin_centers:
                    new_val = bool(er[c])
                    old_val = bool(orig.loc[rid, c])
                    if new_val != old_val:
                        set_indicator_visibility_for_cd(source, c, new_val, motivo, st.session_state["user"]["username"])
                        changes += 1
                new_total = bool(er.get("total_mes", False))
                old_total = bool(orig.loc[rid, "total_mes"]) if "total_mes" in orig.columns else False
                if new_total != old_total:
                    conn = get_conn(); now = now_iso(); user = st.session_state["user"]["username"]
                    conn.execute("UPDATE indicator_config SET exibir_total_mes=?, updated_by=?, updated_at=? WHERE id=?", (int(new_total), user, now, rid))
                    conn.execute(
                        "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        ("indicator_config", source.get("cd"), source.get("grupo"), source.get("indicador"), "exibir_total_mes", str(int(old_total)), str(int(new_total)), motivo, user, now),
                    )
                    conn.commit(); conn.close()
                    changes += 1
            st.success(f"Flags atualizadas: {changes}.")
            st.rerun()



def update_matrix_quick_params(edited: pd.DataFrame, original: pd.DataFrame, motivo: str, user: str) -> int:
    """Salva parâmetros editados em grade no próprio Painel Matricial."""
    if not motivo.strip():
        raise ValueError("Informe o motivo antes de salvar os parâmetros.")

    editable_cols = [
        "tipo_campo",
        "formato",
        "exibir_painel_matricial",
        "exibir_dashboard",
        "exibir_dashboard_dia",
        "exibir_dashboard_mes",
        "exibir_referencia_card",
        "exibir_meta_como_linha",
        "exibir_total_mes",
        "exibir_atingimento_mes",
        "exibir_objetivo_mes_dashboard",
        "usar_sinaleira",
        "direcao_meta",
        "tolerancia_amarela",
        "ativo",
        "grupo_ordem",
        "indicador_ordem",
        "nivel",
    ]
    bool_cols = ["exibir_painel_matricial", "exibir_dashboard", "exibir_dashboard_dia", "exibir_dashboard_mes", "exibir_referencia_card", "exibir_meta_como_linha", "exibir_total_mes", "exibir_atingimento_mes", "exibir_objetivo_mes_dashboard", "usar_sinaleira", "ativo"]
    int_cols = ["grupo_ordem", "indicador_ordem", "nivel"]
    float_cols = ["tolerancia_amarela"]

    orig = original.set_index("id")
    conn = get_conn()
    now = now_iso()
    changes = 0

    for _, row in edited.iterrows():
        rid = int(row["id"])
        if rid not in orig.index:
            continue
        old = orig.loc[rid]
        updates: dict[str, Any] = {}

        for col in editable_cols:
            if col not in row.index or col not in old.index:
                continue
            new_val = row[col]
            old_val = old[col]
            if col in bool_cols:
                new_val = int(bool(new_val))
                old_cmp = int(bool(old_val))
            elif col in int_cols:
                try:
                    new_val = int(new_val)
                except Exception:
                    new_val = int(old_val or 0)
                old_cmp = int(old_val or 0)
            elif col in float_cols:
                try:
                    new_val = float(new_val)
                except Exception:
                    new_val = float(old_val or 0.0)
                old_cmp = float(old_val or 0.0)
            else:
                new_val = str(new_val or "")
                old_cmp = str(old_val or "")

            if str(new_val) != str(old_cmp):
                updates[col] = new_val

        if not updates:
            continue
        if updates.get("tipo_campo") and updates["tipo_campo"] not in TIPOS_CAMPO:
            continue
        if updates.get("formato") and updates["formato"] not in FORMATOS:
            continue
        if updates.get("direcao_meta") and updates["direcao_meta"] not in DIRECOES:
            continue

        set_clause = ", ".join([f"{c}=?" for c in updates] + ["updated_by=?", "updated_at=?"])
        params = list(updates.values()) + [user, now, rid]
        conn.execute(f"UPDATE indicator_config SET {set_clause} WHERE id=?", params)
        for col, new_val in updates.items():
            conn.execute(
                "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("indicator_config", old["cd"], old["grupo"], old["indicador"], col, str(old[col]), str(new_val), motivo, user, now),
            )
            changes += 1

    conn.commit()
    conn.close()
    return changes


def render_matrix_quick_params_editor(cfg_scope: pd.DataFrame, motivo: str) -> None:
    """Editor leve de parâmetros no próprio Painel Matricial.

    Substitui a necessidade de abrir a engrenagem para ajustes operacionais simples.
    A engrenagem permanece apenas para configuração avançada de fórmula/meta quando necessário.
    """
    if cfg_scope.empty:
        return
    editor_cols = [
        "id",
        "cd",
        "grupo",
        "indicador",
        "tipo_campo",
        "formato",
        "exibir_painel_matricial",
        "exibir_dashboard",
        "exibir_dashboard_dia",
        "exibir_dashboard_mes",
        "exibir_referencia_card",
        "exibir_meta_como_linha",
        "exibir_total_mes",
        "exibir_atingimento_mes",
        "exibir_objetivo_mes_dashboard",
        "usar_sinaleira",
        "direcao_meta",
        "tolerancia_amarela",
        "ativo",
        "grupo_ordem",
        "indicador_ordem",
        "nivel",
    ]
    present = [c for c in editor_cols if c in cfg_scope.columns]
    original = cfg_scope[present].copy()
    original = original[original["indicador"].ne("__CABECALHO__")].copy()
    if original.empty:
        return

    original = original.sort_values(["grupo_ordem", "indicador_ordem", "grupo", "indicador"], kind="stable")
    edited = st.data_editor(
        original,
        hide_index=True,
        use_container_width=True,
        height=min(420, 52 + 36 * max(4, len(original))),
        key="matrix_quick_params_editor",
        disabled=["id", "cd", "grupo", "indicador"],
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "cd": st.column_config.TextColumn("CD", width="small"),
            "grupo": st.column_config.TextColumn("Bloco", width="medium"),
            "indicador": st.column_config.TextColumn("Indicador", width="large"),
            "tipo_campo": st.column_config.SelectboxColumn("Tipo", options=TIPOS_CAMPO, width="medium"),
            "formato": st.column_config.SelectboxColumn("Formato", options=FORMATOS, width="small"),
            "exibir_painel_matricial": st.column_config.CheckboxColumn("Matriz", width="small"),
            "exibir_dashboard": st.column_config.CheckboxColumn("Dash", width="small"),
            "exibir_dashboard_dia": st.column_config.CheckboxColumn("Card dia", width="small"),
            "exibir_dashboard_mes": st.column_config.CheckboxColumn("Card mês", width="small"),
            "exibir_referencia_card": st.column_config.CheckboxColumn("Mostrar ref.", width="small"),
            "exibir_meta_como_linha": st.column_config.CheckboxColumn("Meta linha", width="small"),
            "exibir_total_mes": st.column_config.CheckboxColumn("Total mês", width="small"),
            "exibir_atingimento_mes": st.column_config.CheckboxColumn("% Meta mês", width="small"),
            "exibir_objetivo_mes_dashboard": st.column_config.CheckboxColumn("Resumo ger.", width="small"),
            "usar_sinaleira": st.column_config.CheckboxColumn("Sinaleira", width="small"),
            "direcao_meta": st.column_config.SelectboxColumn("Direção", options=DIRECOES, width="medium"),
            "tolerancia_amarela": st.column_config.NumberColumn("Tolerância", step=0.01, format="%.4f", width="small"),
            "ativo": st.column_config.CheckboxColumn("Ativo", width="small"),
            "grupo_ordem": st.column_config.NumberColumn("Ordem bloco", step=1, width="small"),
            "indicador_ordem": st.column_config.NumberColumn("Ordem linha", step=1, width="small"),
            "nivel": st.column_config.NumberColumn("Nível", step=1, width="small"),
        },
    )
    c1, c2 = st.columns([2, 1])
    with c1:
        st.caption("Ajustes em massa são salvos somente ao clicar no botão. Para fórmula, meta e referência de cálculo, use a configuração avançada da linha.")
    with c2:
        if st.button("Salvar parâmetros", type="primary", use_container_width=True, key="matrix_quick_params_save"):
            try:
                n = update_matrix_quick_params(edited, original, motivo, st.session_state["user"]["username"])
                st.success(f"Parâmetros salvos: {n} alteração(ões).")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

# ----------------------------- rótulos operacionais da matriz -----------------------------

def group_uses_next_workday_label(grupo: str) -> bool:
    """Identifica blocos cuja coluna exibida representa o próximo dia trabalhado.

    Exemplo: no bloco "Pedidos para separar hoje", o planejador preenche em 06/05
    os dados referentes à operação de 07/05. Portanto, na matriz essa coluna deve
    aparecer como 07/mai ou HOJE quando 07/05 for o dia atual.
    """
    g = str(grupo or "").strip().lower()
    return (
        "pedidos para separar hoje" in g
        or "separar hoje" in g
        or "visão das 09h" in g
        or "visao das 09h" in g
    )


def next_working_day(cd: str, ref: date) -> date:
    """Retorna o próximo dia trabalhado do CD após a data de preenchimento."""
    d = ref + timedelta(days=1)
    for _ in range(90):
        if is_working_day(cd, d):
            return d
        d += timedelta(days=1)
    return ref + timedelta(days=1)


def matrix_column_label(cd: str, grupo: str, day: date) -> str:
    """Rótulo da coluna no Painel Diário.

    Regra geral: mostra a própria data preenchida.
    Regra operacional para blocos de "hoje": mostra o próximo dia trabalhado; se
    esse próximo dia for a data atual, mostra HOJE.
    """
    display_day = next_working_day(cd, day) if group_uses_next_workday_label(grupo) else day
    if group_uses_next_workday_label(grupo) and display_day == date.today():
        return "HOJE"
    return br_date_label(display_day.isoformat())


def matrix_value_for_day(
    vals: pd.DataFrame,
    configs: pd.DataFrame,
    calc_by_date: dict[str, dict[tuple[str, str], float]],
    target_maps_by_date: dict[str, dict[tuple[str, str, str], dict]],
    cd: str,
    row: pd.Series | dict[str, Any],
    day: date,
) -> Optional[float]:
    """Valor exibido na matriz para uma linha/data.

    A função centraliza a regra para que o total do mês e o atingimento mensal
    usem exatamente a mesma base visual das colunas diárias.

    Importante: linhas classificadas como meta/parâmetro podem ser preenchidas
    diariamente no painel. Quando houver valor preenchido para a data, esse valor
    prevalece. A meta versionada fica como fallback, não como substituta do dado
    operacional preenchido.
    """
    ds = day.isoformat()
    grupo = str(row.get("grupo") or "")
    indicador = str(row.get("indicador") or "")
    tipo = str(row.get("tipo_campo") or "")

    def _filled_daily_value() -> Optional[float]:
        if vals is None or vals.empty:
            return None
        code = str(row.get("codigo_indicador") or "").strip()
        m = pd.DataFrame()
        if code and "codigo_indicador" in vals.columns:
            m = vals[
                (vals["data"].astype(str) == ds)
                & (vals["cd"].astype(str) == str(cd))
                & (vals["codigo_indicador"].fillna("").astype(str).str.strip() == code)
            ]
        if m.empty:
            m = vals[
                (vals["data"].astype(str) == ds)
                & (vals["cd"].astype(str) == str(cd))
                & (vals["grupo"].astype(str) == grupo)
                & (vals["indicador"].astype(str) == indicador)
            ]
        if not m.empty:
            m = m[m["valor"].notna()].copy()
        if not m.empty:
            return float(m.sort_values("id" if "id" in m.columns else "data").iloc[-1]["valor"])
        return None

    value = None
    if tipo in {"dado_diario", "meta", "parametro"}:
        value = _filled_daily_value()
        if value is None and tipo in {"meta", "parametro"} and day <= last_day_of_month():
            target = target_for_matrix_row_cached(cd, row, ds, target_maps_by_date.get(ds, {}))
            if target and target.get("valor_meta") is not None and not pd.isna(target.get("valor_meta")):
                value = float(target["valor_meta"])
    elif tipo == "calculo":
        value = calc_by_date.get(ds, {}).get((grupo, indicador))

    if value is None or pd.isna(value):
        return None
    return float(value)



def compute_matrix_period_totals(
    vals: pd.DataFrame,
    configs: pd.DataFrame,
    calc_by_date: dict[str, dict[tuple[str, str], float]],
    target_maps_by_date: dict[str, dict[tuple[str, str, str], dict]],
    cd: str,
    dates: list[date],
) -> dict[tuple[str, str], Optional[float]]:
    """Calcula o valor agregado do período usando a mesma regra operacional da matriz.

    Regra principal:
    - campos simples somam os valores diários exibidos;
    - campos calculados são recalculados sobre os totais dos componentes.

    Isso evita erro clássico em indicadores percentuais: somar 100,44% + 101,23%
    não representa o atingimento acumulado. O correto é recalcular a fórmula sobre
    os totais: total realizado / total previsto.
    """
    if configs is None or configs.empty or not dates:
        return {}

    cfg_cd = configs[configs["cd"].astype(str) == str(cd)].copy()
    if cfg_cd.empty:
        return {}
    cfg_cd = cfg_cd[cfg_cd["indicador"].astype(str).ne("__CABECALHO__")].copy()
    cfg_cd = cfg_cd.sort_values(["grupo_ordem", "indicador_ordem", "grupo", "indicador"], kind="stable")

    totals: dict[tuple[str, str], Optional[float]] = {}
    by_ind: dict[str, float] = {}

    def add_value_keys(row: pd.Series | dict[str, Any], valor: Optional[float]) -> None:
        if valor is None or pd.isna(valor):
            return
        try:
            fval = float(valor)
        except Exception:
            return
        grupo = str(row.get("grupo") or "")
        indicador = str(row.get("indicador") or "")
        by_ind[indicador] = fval
        by_ind[f"{grupo} · {indicador}"] = fval
        codigo = str(row.get("codigo_indicador") or "").strip()
        if codigo:
            by_ind[codigo] = fval
        try:
            by_ind[f"ID_{int(row.get('id'))}"] = fval
        except Exception:
            pass

    # 1) Totais-base: dado diário, meta e parâmetro somam exatamente o que aparece nas colunas.
    base_cfg = cfg_cd[cfg_cd["tipo_campo"].astype(str).ne("calculo")].copy()
    for _, r in base_cfg.iterrows():
        values: list[float] = []
        for d in dates:
            v = matrix_value_for_day(vals, configs, calc_by_date, target_maps_by_date, cd, r, d)
            if v is not None and not pd.isna(v):
                values.append(float(v))
        total = sum(values) if values else None
        key = (str(r["grupo"]), str(r["indicador"]))
        totals[key] = total
        add_value_keys(r, total)

    # 2) Cálculos: recalcula a fórmula usando os totais dos componentes.
    calc_cfg = cfg_cd[cfg_cd["tipo_campo"].astype(str).eq("calculo")].copy()
    for _ in range(3):
        changed = False
        for _, r in calc_cfg.iterrows():
            key = (str(r["grupo"]), str(r["indicador"]))
            formula = "" if pd.isna(r.get("formula")) else str(r.get("formula") or "")
            res = safe_eval_formula(formula, by_ind) if formula.strip() else None

            # Fallback: se não houver fórmula válida, soma os valores calculados por dia.
            if res is None:
                values: list[float] = []
                for d in dates:
                    v = matrix_value_for_day(vals, configs, calc_by_date, target_maps_by_date, cd, r, d)
                    if v is not None and not pd.isna(v):
                        values.append(float(v))
                res = sum(values) if values else None

            old = totals.get(key)
            if res is not None and (old is None or abs(float(old) - float(res)) > 1e-12):
                totals[key] = float(res)
                add_value_keys(r, float(res))
                changed = True
        if not changed:
            break

    return totals

def resolve_month_total_reference(configs: pd.DataFrame, cd: str, row: pd.Series | dict[str, Any]) -> Optional[pd.Series]:
    """Resolve o indicador de referência para cálculo de % Meta Mês."""
    ref_grupo = str(row.get("total_mes_ref_grupo") or "").strip()
    ref_indicador = str(row.get("total_mes_ref_indicador") or "").strip()
    if not ref_grupo or not ref_indicador or configs.empty:
        return None
    candidates = configs[
        (configs["cd"].astype(str) == str(cd))
        & (configs["grupo"].astype(str) == ref_grupo)
        & (configs["indicador"].astype(str) == ref_indicador)
    ].copy()
    if candidates.empty:
        return None
    return candidates.iloc[0]


def format_month_achievement(numerator: Optional[float], denominator: Optional[float], cfgrow: pd.Series | dict[str, Any]) -> str:
    """Formata atingimento mensal como percentual com sinaleira contra 100%."""
    if numerator is None or denominator is None or abs(float(denominator)) < 1e-12:
        return ""
    achievement = float(numerator) / float(denominator)
    try:
        cfg_tmp = pd.Series(dict(cfgrow))
    except Exception:
        cfg_tmp = pd.Series(cfgrow)
    cfg_tmp["formato"] = "percentual"
    cfg_tmp["direcao_meta"] = "maior_melhor"
    cfg_tmp["tipo_campo"] = "calculo"
    target = {
        "valor_meta": 1.0,
        "direcao_meta": "maior_melhor",
        "tolerancia_amarela": float(cfg_tmp.get("tolerancia_amarela") or 0.05),
    }
    emoji, _ = status_for_value(achievement, target, cfg_tmp)
    return (emoji + " " if emoji else "") + format_value(achievement, "percentual", "% atingimento mês")


# ----------------------------- páginas -----------------------------

def build_matrix_visual_export_rows(
    cfg: pd.DataFrame,
    vals: pd.DataFrame,
    cfg_all: pd.DataFrame,
    calc_by_date: dict[str, dict[tuple[str, str], float]],
    target_maps_by_date: dict[str, dict[tuple[str, str, str], dict]],
    period_total_lookup: dict[tuple[str, str], Optional[float]],
    cd: str,
    dates: list[date],
    can_configure: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if cfg is None or cfg.empty:
        return rows
    for grupo, gdf in cfg.groupby("grupo", sort=False):
        visible_rows = []
        for _, r in gdf.iterrows():
            tipo = str(r.get("tipo_campo") or "")
            if tipo == "parametro" and not bool(r.get("exibir_meta_como_linha")):
                continue
            visible_rows.append(r)
        if not visible_rows:
            continue
        rows.append({"indicador": str(grupo), "values": [""] * len(dates), "summary_values": [""], "group": True})
        for r in visible_rows:
            indicador = str(r.get("indicador") or "")
            tipo = str(r.get("tipo_campo") or "")
            row_hidden = not (bool(r.get("ativo")) and bool(r.get("exibir_painel_matricial")))
            if row_hidden and not can_configure:
                continue
            rendered_values: list[str] = []
            raw_values: list[float] = []
            for d in dates:
                ds = d.isoformat()
                value = matrix_value_for_day(vals, cfg_all, calc_by_date, target_maps_by_date, cd, r, d)
                target = target_for_matrix_row_cached(cd, r, ds, target_maps_by_date.get(ds, {}))
                emoji = ""
                if bool(r.get("usar_sinaleira")) and tipo != "meta":
                    emoji, _ = status_for_value(value, target, r)
                rendered_values.append(((emoji + " ") if emoji else "") + (format_value(value, str(r.get("formato") or "numero"), indicador) or ""))
                if value is not None and not pd.isna(value):
                    raw_values.append(float(value))
            period_value = period_total_lookup.get((str(r.get("grupo") or ""), indicador))
            if period_value is None and raw_values:
                period_value = sum(raw_values) / len(raw_values)
            summary = format_value(period_value, str(r.get("formato") or "numero"), indicador) or ""
            rows.append({"indicador": indicador + (" [oculto]" if row_hidden and can_configure else ""), "values": rendered_values, "summary_values": [summary], "group": False})
    return rows


def page_matrix() -> None:
    header_slot = st.empty()
    centers = [c for c in allowed_centers(st.session_state["user"]["username"])]
    if not centers:
        st.warning("Usuário sem CD liberado.")
        return

    can_configure = has_perm("configure_indicators")

    # Filtros executivos: CD por botões, visão de indicadores e período.
    with st.container(border=True):
        f1, f2, f3 = st.columns([1.25, 1.15, 1.25], gap="large")
        with f1:
            cd = center_button_selector("CD", centers, "matrix_cd_button")
        with header_slot.container():
            render_header("Painel Diário de Indicadores", cd=cd)
        cfg_all = load_indicator_config(cd, active_only=not can_configure)
        if cfg_all.empty:
            st.warning("Sem catálogo de indicadores configurado.")
            return
        with f2:
            view_label, view_id = view_selector("matricial", cd, "matrix_view_selector")
        # Painel Diário: por padrão, abre sempre no mês corrente, do primeiro dia
        # do mês até o último dia útil/trabalhado já encerrado para o CD.
        # Se o usuário quiser analisar outro mês, ele altera o período manualmente.
        max_data = previous_working_day(cd)
        today_ref = date.today()
        min_data = date(today_ref.year, today_ref.month, 1)
        if max_data < min_data:
            # Situação típica no primeiro dia do mês antes de haver dia útil encerrado.
            # Mantém a janela do mês corrente para não voltar automaticamente ao mês anterior.
            max_data = min_data
        with f3:
            period = st.date_input("Período", value=(min_data, max_data), key="matrix_period")

    if isinstance(period, tuple) and len(period) == 2:
        start, end = period
    else:
        start, end = min_data, max_data

    # Mesmo se o usuário selecionar hoje/futuro, a matriz corta no último dia útil/trabalhado.
    # O padrão é mês corrente; períodos históricos continuam disponíveis quando selecionados manualmente.
    last_workday = previous_working_day(cd)
    if end > last_workday:
        end = last_workday
    if start > end:
        start = end

    matrix_export_slot = st.empty()

    show_hidden_admin = bool(st.session_state.get("matrix_show_hidden_admin", True)) if can_configure else False
    motivo_visibilidade = str(st.session_state.get("matrix_quick_visibility_motivo", "") or "")
    admin_centers: list[str] = active_center_codes() if can_configure else []

    cfg_view_scope = apply_visualization_view(cfg_all, view_id)
    cfg = cfg_view_scope.copy()
    cfg = cfg[cfg["indicador"].ne("__CABECALHO__")]
    if can_configure:
        if not show_hidden_admin:
            cfg = cfg[cfg["exibir_painel_matricial"].eq(1) & cfg["ativo"].eq(1)]
    else:
        cfg = cfg[cfg["exibir_painel_matricial"].eq(1) & cfg["ativo"].eq(1)]
        cfg = cfg[~((cfg["tipo_campo"] == "parametro") & (cfg["exibir_meta_como_linha"] == 0))]

    if cfg.empty:
        st.info(f"A visão `{view_label}` não possui indicadores visíveis para o CD {cd}.")
        if can_configure:
            render_visualization_admin("matricial", cd, cfg_all, "matrix_empty")
        return

    all_dates = list(pd.date_range(start, end, freq="D").date)
    dates = [d for d in all_dates if is_working_day(cd, d)]
    ignored_dates = [d for d in all_dates if d not in dates]
    if not dates:
        st.info("Nenhum dia trabalhado encontrado para este CD no período selecionado. Ajuste o período ou o Calendário de Trabalho.")
        return

    vals = load_values([cd], str(start), str(end))
    updated = vals["updated_at"].dropna().max() if not vals.empty and "updated_at" in vals.columns else None
    ignored_txt = f" · Dias não trabalhados ocultos: {len(ignored_dates)}" if ignored_dates else ""
    st.caption(f"Atualizado em: {updated or 'sem carga'} · Visão: {view_label} · Somente dias trabalhados{ignored_txt}")

    # Pré-cálculos de renderização. O Streamlit reroda a página inteira ao clicar
    # na engrenagem; portanto, consultas e cálculos repetidos por linha/data deixam
    # a abertura lenta. Estes mapas são carregados uma vez por renderização.
    date_iso_list = [d.isoformat() for d in dates]
    visibility_lookup = build_visibility_lookup(admin_centers) if can_configure and admin_centers else {}
    target_maps_by_date = {ds: target_lookup_for_date([cd], ds) for ds in date_iso_list}
    has_calc_rows = not cfg[cfg["tipo_campo"].eq("calculo")].empty
    calc_by_date = {ds: compute_calculated_values(vals, cfg_all, cd, ds) for ds in date_iso_list} if has_calc_rows else {}
    period_total_lookup = compute_matrix_period_totals(vals, cfg_all, calc_by_date, target_maps_by_date, cd, dates)

    if can_configure:
        render_matrix_unsaved_warning()

    default_date_labels = [br_date_label(d.isoformat()) for d in dates]

    matrix_export_rows = build_matrix_visual_export_rows(cfg, vals, cfg_all, calc_by_date, target_maps_by_date, period_total_lookup, cd, dates, can_configure)
    matrix_export_headers = ["Indicador"] + default_date_labels + ["Média/Resumo"]
    matrix_export_png = _matrix_to_png(
        f"Painel Diário de Indicadores - CD {cd}",
        matrix_export_headers,
        matrix_export_rows,
        subtitle=f"Visão: {view_label} · Período: {br_date_label(start.isoformat())} a {br_date_label(end.isoformat())}",
    )
    with matrix_export_slot.container():
        render_visual_export_buttons(f"matrix_export_{cd}_{start.isoformat()}_{end.isoformat()}", f"painel_diario_{cd}_{start.isoformat()}_{end.isoformat()}", matrix_export_png)

    for grupo, gdf in cfg.groupby("grupo", sort=False):
        date_labels = [matrix_column_label(cd, str(grupo), d) for d in dates] if group_uses_next_workday_label(str(grupo)) else default_date_labels
        st.markdown(f"<div style='background:{BR_ORANGE};color:white;padding:10px 12px;border-radius:8px;font-weight:850;margin-top:20px;'>{grupo}</div>", unsafe_allow_html=True)
        visible_rows = []
        for _, r in gdf.iterrows():
            indicador = r["indicador"]
            tipo = r["tipo_campo"]
            if tipo == "parametro" and not bool(r["exibir_meta_como_linha"]):
                continue
            visible_rows.append(r)
        if not visible_rows:
            continue
        first_format = str(visible_rows[0].get("formato", ""))
        first_indicador = str(visible_rows[0].get("indicador", ""))
        summary_label = "Perf. Mês" if (first_format == "percentual" or "performance" in first_indicador.lower() or "atingimento" in first_indicador.lower()) else "Média"
        show_total_month_col = any(bool(r.get("exibir_total_mes")) for r in visible_rows)
        show_month_achievement_col = any(
            bool(r.get("exibir_atingimento_mes"))
            and bool(str(r.get("total_mes_ref_grupo") or "").strip())
            and bool(str(r.get("total_mes_ref_indicador") or "").strip())
            for r in visible_rows
        )
        summary_labels = [summary_label]
        if show_total_month_col:
            summary_labels.append("Total Mês")
        if show_month_achievement_col:
            summary_labels.append("% Meta Mês")
        built_rows = []
        for r in visible_rows:
            indicador = r["indicador"]
            tipo = r["tipo_campo"]
            indent_px = int(r.get("nivel", 0) or 0) * 18
            row_hidden = not (bool(r.get("ativo")) and bool(r.get("exibir_painel_matricial")))
            hidden_badge = " <span style='font-size:.72rem;color:#9ca3af;'>[oculto]</span>" if row_hidden and can_configure else ""
            last_target_lookup = target_maps_by_date.get(dates[-1].isoformat(), {}) if dates else {}
            meta_suffix = manual_calc_target_suffix(cd, r, dates[-1].isoformat(), last_target_lookup) if dates else ""
            label_html = f"<span style='padding-left:{indent_px}px;'>{html.escape(str(indicador) + meta_suffix)}{hidden_badge}</span>"
            rendered_values = []
            raw_values = []
            summary_target_values = []
            summary_target_template = None
            for d in dates:
                ds = d.isoformat()
                value = matrix_value_for_day(vals, cfg_all, calc_by_date, target_maps_by_date, cd, r, d)
                target = target_for_matrix_row_cached(cd, r, ds, target_maps_by_date.get(ds, {}))
                emoji = ""
                if bool(r["usar_sinaleira"]) and tipo != "meta":
                    emoji, _ = status_for_value(value, target, r)
                rendered_values.append((emoji + " " if emoji else "") + format_value(value, r["formato"], indicador))
                if value is not None and not pd.isna(value):
                    raw_values.append(float(value))
                    if bool(r["usar_sinaleira"]) and tipo != "meta" and target:
                        try:
                            summary_target_values.append(float(target["valor_meta"]))
                            summary_target_template = dict(target)
                        except Exception:
                            pass
            # Campo final da matriz: média dos resultados exibidos no mês/período filtrado.
            # Quando a linha tem sinaleira no dia a dia, a média também recebe sinaleira.
            if raw_values:
                summary_avg = sum(raw_values) / len(raw_values)
                summary_text = format_value(summary_avg, r["formato"], indicador)
                summary_emoji = ""
                if bool(r["usar_sinaleira"]) and tipo != "meta":
                    summary_target = None
                    if summary_target_values:
                        summary_target = dict(summary_target_template or {})
                        summary_target["valor_meta"] = sum(summary_target_values) / len(summary_target_values)
                    elif dates:
                        # fallback: usa a meta vigente no último dia exibido
                        last_ds = dates[-1].isoformat()
                        summary_target = target_for_matrix_row_cached(cd, r, last_ds, target_maps_by_date.get(last_ds, {}))
                    summary_emoji, _ = status_for_value(summary_avg, summary_target, r)
                summary_value = (summary_emoji + " " if summary_emoji else "") + summary_text
            else:
                summary_value = ""

            month_total_value = period_total_lookup.get((str(grupo), str(indicador)))
            if month_total_value is None and raw_values:
                month_total_value = sum(raw_values)

            total_month_text = ""
            if show_total_month_col and bool(r.get("exibir_total_mes")):
                total_month_text = format_value(month_total_value, r["formato"], indicador)
                if bool(r.get("usar_sinaleira")) and tipo != "meta" and total_month_text:
                    total_target = None
                    if dates:
                        last_ds = dates[-1].isoformat()
                        total_target = target_for_matrix_row_cached(cd, r, last_ds, target_maps_by_date.get(last_ds, {}))
                    total_emoji, _ = status_for_value(month_total_value, total_target, r)
                    if total_emoji:
                        total_month_text = f"{total_emoji} {total_month_text}"

            month_achievement_text = ""
            if show_month_achievement_col and bool(r.get("exibir_atingimento_mes")):
                ref_row = resolve_month_total_reference(cfg_all, cd, r)
                if ref_row is not None:
                    ref_total = period_total_lookup.get((str(ref_row["grupo"]), str(ref_row["indicador"])))
                    if ref_total is None:
                        ref_values = [
                            v for v in (matrix_value_for_day(vals, cfg_all, calc_by_date, target_maps_by_date, cd, ref_row, d) for d in dates)
                            if v is not None and not pd.isna(v)
                        ]
                        ref_total = sum(float(v) for v in ref_values) if ref_values else None
                    month_achievement_text = format_month_achievement(month_total_value, ref_total, r)

            summary_values = [summary_value]
            if show_total_month_col:
                summary_values.append(total_month_text)
            if show_month_achievement_col:
                summary_values.append(month_achievement_text)

            row_flags = {c: indicator_visible_for_cd_fast(r, c, visibility_lookup) for c in admin_centers} if can_configure else {}
            built_rows.append({"id": int(r["id"]), "indicador_html": label_html, "values": rendered_values, "summary_value": summary_value, "summary_values": summary_values, "source_row": r, "flags": row_flags, "hidden_row": row_hidden})
        if len(dates) > 8:
            if can_configure:
                render_long_group_visibility_editor(grupo, built_rows, admin_centers, motivo_visibilidade)
                cfg_labels = [f"{row['id']} · {grupo} · {re.sub('<[^<]+?>', '', row['indicador_html']).strip()}" for row in built_rows]
                reset_token = int(st.session_state.get("matrix_config_reset_counter", 0))
                group_key = hashlib.md5(str(grupo).encode("utf-8")).hexdigest()[:8]
                selected_cfg = st.selectbox(
                    "⚙️ Editar parâmetro deste bloco",
                    [""] + cfg_labels,
                    key=f"matrix_long_config_selector_{group_key}_{reset_token}",
                )
                if selected_cfg:
                    requested_id = int(selected_cfg.split(" · ")[0])
                    if st.session_state.get("matrix_config_record_id") != requested_id:
                        request_matrix_config(requested_id)
                        if st.session_state.get("matrix_config_record_id") != requested_id:
                            render_matrix_unsaved_warning()
                        else:
                            st.rerun()
                    if st.session_state.get("matrix_config_record_id") == requested_id:
                        with st.expander("⚙️ Configuração do indicador selecionado", expanded=True):
                            render_indicator_config_form(int(requested_id), location=f"matrix_long_{group_key}")
                elif st.session_state.get("matrix_config_record_id") in [row['id'] for row in built_rows]:
                    if _matrix_has_unsaved_config():
                        st.session_state["matrix_config_warning"] = "Existe uma configuração aberta com alterações não salvas. Salve antes de fechar."
                        render_matrix_unsaved_warning()
                    else:
                        st.session_state.pop("matrix_config_record_id", None)
            render_matrix_scroll_table(date_labels, summary_labels, built_rows, admin_centers if can_configure else [], show_total_flag=can_configure)
        else:
            render_matrix_header(date_labels, summary_labels, can_configure, admin_centers if can_configure else [], show_total_flag=can_configure)
            for row in built_rows:
                render_matrix_row(
                    row["id"],
                    row["indicador_html"],
                    row["values"],
                    row.get("summary_values", [row["summary_value"]]),
                    can_configure,
                    f"Configurar {grupo}",
                    source_row=row.get("source_row"),
                    admin_centers=admin_centers if can_configure else [],
                    motivo_visibilidade=motivo_visibilidade,
                    hidden_row=bool(row.get("hidden_row")),
                    visibility_lookup=visibility_lookup,
                    show_total_flag=can_configure,
                )
                if can_configure and st.session_state.get("matrix_config_record_id") == int(row["id"]):
                    st.markdown("<div class='config-alert'>Editando o indicador selecionado. Ao salvar, esta área será recolhida automaticamente.</div>", unsafe_allow_html=True)
                    render_indicator_config_form(int(row["id"]), location=f"matrix_row_{row['id']}")

    st.divider()
    if can_configure:
        with st.expander("Administração do painel", expanded=False):
            st.caption("Use esta área somente quando for alterar visibilidade, ordem, parâmetros ou visões. Ela fica no final para manter o painel limpo.")
            a1, a2, a3 = st.columns([2.5, 1, 1])
            with a1:
                st.text_input(
                    "Motivo para alterações",
                    key="matrix_quick_visibility_motivo",
                    placeholder="Opcional para flags rápidas. Ex.: ajuste de visibilidade, ordem, parâmetros ou visão executiva.",
                )
            with a2:
                st.checkbox("Mostrar ocultos/inativos", value=show_hidden_admin, key="matrix_show_hidden_admin")
            with a3:
                edit_params_mode = st.checkbox("Editar parâmetros rápidos", value=bool(st.session_state.get("matrix_edit_params_mode", False)), key="matrix_edit_params_mode")
            render_visualization_admin("matricial", cd, cfg_all, "matrix_admin")
            if st.session_state.get("matrix_quick_visibility_warning"):
                st.warning(st.session_state.pop("matrix_quick_visibility_warning"))
            if st.session_state.get("matrix_quick_visibility_success"):
                st.success(st.session_state.pop("matrix_quick_visibility_success"))
            if edit_params_mode and not st.session_state.get("matrix_config_record_id"):
                st.markdown("**Parâmetros rápidos da matriz**")
                render_matrix_quick_params_editor(cfg_view_scope.copy(), st.session_state.get("matrix_quick_visibility_motivo", ""))
            elif edit_params_mode and st.session_state.get("matrix_config_record_id"):
                st.info("Feche ou salve a configuração avançada aberta para editar a grade de parâmetros em massa.")

    with st.expander("Tabela mestre de layout dos indicadores", expanded=False):
        st.dataframe(cfg_all, use_container_width=True, hide_index=True)
        if has_perm("export_reports"):
            st.download_button("Baixar tabela mestre em CSV", cfg_all.to_csv(index=False).encode("utf-8-sig"), "tabela_mestre_indicadores.csv", "text/csv", use_container_width=True)


def month_ref_iso(ref_date: Any) -> str:
    """Retorna o primeiro dia do mês de referência em ISO."""
    d = pd.to_datetime(ref_date).date()
    return date(d.year, d.month, 1).isoformat()


def monthly_objective_for_card(cd: str, cfgrow: pd.Series | dict[str, Any], ref_date: Any) -> Optional[dict]:
    """Busca o objetivo mensal vigente para o card/indicador no mês de referência."""
    mes_ref = month_ref_iso(ref_date)
    code = str(cfgrow.get("codigo_indicador") or "").strip()
    grupo = str(cfgrow.get("grupo") or "").strip()
    indicador = str(cfgrow.get("indicador") or "").strip()
    conn = get_conn()
    try:
        row = None
        if code:
            row = conn.execute(
                """
                SELECT * FROM monthly_objectives
                WHERE cd=? AND codigo_indicador=? AND mes_ref=? AND active=1
                ORDER BY COALESCE(updated_at, created_at) DESC, id DESC LIMIT 1
                """,
                (str(cd), code, mes_ref),
            ).fetchone()
        if row is None:
            row = conn.execute(
                """
                SELECT * FROM monthly_objectives
                WHERE cd=? AND grupo=? AND indicador=? AND mes_ref=? AND active=1
                ORDER BY COALESCE(updated_at, created_at) DESC, id DESC LIMIT 1
                """,
                (str(cd), grupo, indicador, mes_ref),
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def load_monthly_objectives(cd: str, mes_ref: str) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM monthly_objectives WHERE cd=? AND mes_ref=? AND active=1 ORDER BY grupo, indicador",
        conn,
        params=(str(cd), str(mes_ref)),
    )
    conn.close()
    return df


def upsert_monthly_objective(
    cd: str,
    grupo: str,
    indicador: str,
    codigo_indicador: str,
    mes_ref: str,
    valor_objetivo: float,
    direcao_meta: str,
    tolerancia_amarela: float,
    motivo: str,
    user: str,
) -> None:
    if not str(motivo or "").strip():
        raise ValueError("Informe o motivo para salvar o objetivo mensal.")
    if abs(float(valor_objetivo)) < 1e-12:
        raise ValueError("O objetivo mensal precisa ser diferente de zero.")
    direcao_meta = str(direcao_meta or "maior_melhor")
    if direcao_meta not in DIRECOES:
        direcao_meta = "maior_melhor"
    now = now_iso()
    conn = get_conn()
    try:
        old = conn.execute(
            "SELECT * FROM monthly_objectives WHERE cd=? AND grupo=? AND indicador=? AND mes_ref=? ORDER BY id DESC LIMIT 1",
            (cd, grupo, indicador, mes_ref),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO monthly_objectives(
                cd, grupo, indicador, codigo_indicador, mes_ref, valor_objetivo,
                direcao_meta, tolerancia_amarela, active, motivo, created_by, created_at, updated_by, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            ON CONFLICT(cd, grupo, indicador, mes_ref) DO UPDATE SET
                codigo_indicador=excluded.codigo_indicador,
                valor_objetivo=excluded.valor_objetivo,
                direcao_meta=excluded.direcao_meta,
                tolerancia_amarela=excluded.tolerancia_amarela,
                active=1,
                motivo=excluded.motivo,
                updated_by=excluded.updated_by,
                updated_at=excluded.updated_at
            """,
            (
                cd, grupo, indicador, codigo_indicador or None, mes_ref, float(valor_objetivo),
                direcao_meta, float(tolerancia_amarela), str(motivo).strip(), user, now, user, now,
            ),
        )
        conn.execute(
            "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "monthly_objective",
                cd,
                grupo,
                indicador,
                mes_ref,
                "" if old is None else f"{old['valor_objetivo']}|{old['direcao_meta']}",
                f"{float(valor_objetivo)}|{direcao_meta}",
                str(motivo).strip(),
                user,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def set_dashboard_month_objective_flag(record_id: int, enabled: bool, motivo: str, user: str) -> None:
    if not str(motivo or "").strip():
        raise ValueError("Informe o motivo para alterar o vínculo do objetivo mensal no dashboard.")
    conn = get_conn()
    now = now_iso()
    try:
        old = conn.execute("SELECT * FROM indicator_config WHERE id=?", (int(record_id),)).fetchone()
        if old is None:
            raise ValueError("Indicador não encontrado.")
        old_val = int(old["exibir_objetivo_mes_dashboard"] or 0) if "exibir_objetivo_mes_dashboard" in old.keys() else 0
        new_val = int(bool(enabled))
        if old_val != new_val:
            conn.execute(
                "UPDATE indicator_config SET exibir_objetivo_mes_dashboard=?, updated_by=?, updated_at=? WHERE id=?",
                (new_val, user, now, int(record_id)),
            )
            conn.execute(
                "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("indicator_config", old["cd"], old["grupo"], old["indicador"], "exibir_objetivo_mes_dashboard", str(old_val), str(new_val), str(motivo).strip(), user, now),
            )
        conn.commit()
    finally:
        conn.close()


def objective_progress_status(progress: Optional[float], objective: Optional[dict]) -> tuple[str, str, str]:
    """Status do progresso contra o objetivo mensal. Retorna emoji, texto, classe visual."""
    if progress is None or objective is None:
        return "", "Sem objetivo", "none"
    direcao = str(objective.get("direcao_meta") or "maior_melhor")
    tol = float(objective.get("tolerancia_amarela") or 0.05)
    p = float(progress)
    if direcao == "menor_melhor":
        if p <= 1:
            return "🟢", "Dentro", "ok"
        if p <= 1 + tol:
            return "🟡", "Atenção", "warn"
        return "🔴", "Fora", "bad"
    if direcao == "igual":
        if abs(p - 1) <= tol:
            return "🟢", "Dentro", "ok"
        return "🔴", "Fora", "bad"
    if p >= 1:
        return "🟢", "Dentro", "ok"
    if p >= 1 - tol:
        return "🟡", "Atenção", "warn"
    return "🔴", "Fora", "bad"


def _dashboard_objective_payload(label: str, actual_value: Optional[float], cfgrow: pd.Series, objective: dict) -> dict[str, str]:
    objetivo = float(objective.get("valor_objetivo") or 0)
    if abs(objetivo) < 1e-12:
        return _dashboard_card_payload(label, actual_value, cfgrow, None)
    realizado = 0.0 if actual_value is None or pd.isna(actual_value) else float(actual_value)
    progresso = realizado / objetivo
    emoji, status, status_class = objective_progress_status(progresso, objective)
    objetivo_txt = format_value(objetivo, cfgrow.get("formato", "numero"), cfgrow.get("indicador", ""))
    realizado_txt = format_value(realizado, cfgrow.get("formato", "numero"), cfgrow.get("indicador", ""))
    periodo_txt = pd.to_datetime(objective.get("mes_ref")).strftime("%m/%Y") if objective.get("mes_ref") else "mês"
    return {
        "label": str(label or ""),
        "value": format_value(progresso, "percentual", "% objetivo mensal") or "—",
        "emoji": emoji,
        "status": f"{status} · Executado {realizado_txt} de {objetivo_txt} · {periodo_txt}",
        "class": status_class,
    }


def build_dashboard_objective_editor_df(cards_df: pd.DataFrame, cd: str, mes_ref: str) -> pd.DataFrame:
    if cards_df is None or cards_df.empty:
        return pd.DataFrame()
    current = load_monthly_objectives(cd, mes_ref)
    by_code = {}
    by_pair = {}
    if not current.empty:
        for _, r in current.iterrows():
            code = str(r.get("codigo_indicador") or "").strip().upper()
            if code:
                by_code[code] = r
            by_pair[(str(r.get("grupo") or ""), str(r.get("indicador") or ""))] = r
    rows = []
    for _, r in cards_df.iterrows():
        code = str(r.get("codigo_indicador") or "").strip()
        obj = by_code.get(code.upper()) if code else None
        if obj is None:
            obj = by_pair.get((str(r.get("grupo") or ""), str(r.get("indicador") or "")))
        rows.append({
            "id": int(r.get("id")),
            "cd": str(cd),
            "grupo": str(r.get("grupo") or ""),
            "indicador": str(r.get("indicador") or ""),
            "codigo_indicador": code,
            "formato": str(r.get("formato") or "numero"),
            "usar_objetivo_dashboard": bool(r.get("exibir_objetivo_mes_dashboard", 0)),
            "valor_objetivo": None if obj is None else float(obj.get("valor_objetivo")),
            "direcao_meta": str((obj.get("direcao_meta") if obj is not None else r.get("direcao_meta")) or "maior_melhor"),
            "tolerancia_amarela": float((obj.get("tolerancia_amarela") if obj is not None else r.get("tolerancia_amarela")) or 0.05),
        })
    return pd.DataFrame(rows)


def save_dashboard_monthly_objectives(edited: pd.DataFrame, original: pd.DataFrame, mes_ref: str, motivo: str, user: str) -> int:
    if edited is None or edited.empty:
        return 0
    if not str(motivo or "").strip():
        raise ValueError("Informe o motivo para salvar o resumo gerencial mensal.")
    orig = original.set_index("id") if original is not None and not original.empty else pd.DataFrame()
    changes = 0
    for _, r in edited.iterrows():
        rid = int(r.get("id"))
        enabled = bool(r.get("usar_objetivo_dashboard"))
        old_enabled = bool(orig.loc[rid, "usar_objetivo_dashboard"]) if not orig.empty and rid in orig.index else False
        valor = r.get("valor_objetivo")
        if pd.isna(valor):
            valor = None
        direcao = str(r.get("direcao_meta") or "maior_melhor")
        tolerancia = float(r.get("tolerancia_amarela") or 0.05)

        if enabled and valor is None:
            raise ValueError(f"Informe o valor objetivo para: {r.get('indicador')}.")
        if enabled and abs(float(valor)) < 1e-12:
            raise ValueError(f"O objetivo mensal precisa ser diferente de zero para: {r.get('indicador')}.")

        if enabled != old_enabled:
            set_dashboard_month_objective_flag(rid, enabled, motivo, user)
            changes += 1

        # Salva o objetivo quando habilitado. Mesmo que o flag não tenha mudado, o valor pode ter sido atualizado.
        if enabled:
            old_val = None
            old_dir = None
            old_tol = None
            if not orig.empty and rid in orig.index:
                old_val = orig.loc[rid, "valor_objetivo"]
                old_dir = orig.loc[rid, "direcao_meta"]
                old_tol = orig.loc[rid, "tolerancia_amarela"]
            value_changed = (pd.isna(old_val) if old_val is not None else True) or abs(float(old_val or 0) - float(valor)) > 1e-12
            dir_changed = str(old_dir or "") != direcao
            tol_changed = abs(float(old_tol or 0) - tolerancia) > 1e-12
            if value_changed or dir_changed or tol_changed:
                upsert_monthly_objective(
                    str(r.get("cd") or ""),
                    str(r.get("grupo") or ""),
                    str(r.get("indicador") or ""),
                    str(r.get("codigo_indicador") or ""),
                    str(mes_ref),
                    float(valor),
                    direcao,
                    tolerancia,
                    motivo,
                    user,
                )
                changes += 1
    return changes


def dashboard_value(df: pd.DataFrame, cfgrow: pd.Series, cd: str, start: str, end: str, agg: str) -> Optional[float]:
    grupo, indicador, tipo = cfgrow["grupo"], cfgrow["indicador"], cfgrow["tipo_campo"]
    if tipo == "calculo":
        if agg == "latest":
            d = end
            return compute_calculated_values(df, load_indicator_config(cd), cd, d).get((grupo, indicador))
        vals = []
        for d in pd.date_range(start, end, freq="D").date:
            v = compute_calculated_values(df, load_indicator_config(cd), cd, d.isoformat()).get((grupo, indicador))
            if v is not None:
                vals.append(v)
        return sum(vals) / len(vals) if vals else None
    sub = df[(df["cd"] == cd) & (df["grupo"] == grupo) & (df["indicador"] == indicador)]
    if sub.empty:
        return None
    sub_nonnull = sub[sub["valor"].notna()].copy()
    if sub_nonnull.empty:
        return None
    if agg == "sum":
        return float(sub_nonnull["valor"].sum())
    if agg == "mean":
        return float(sub_nonnull["valor"].mean())
    return float(sub_nonnull.sort_values("data").iloc[-1]["valor"])



def _dashboard_card_view_tables_ready() -> None:
    """Garante tabelas de visões pessoais de cards em bancos antigos."""
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dashboard_card_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            cd TEXT NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            UNIQUE(username, cd, nome)
        );
        CREATE TABLE IF NOT EXISTS dashboard_card_view_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            view_id INTEGER NOT NULL,
            cd TEXT NOT NULL,
            grupo TEXT NOT NULL,
            indicador TEXT NOT NULL,
            codigo_indicador TEXT,
            sort_order INTEGER NOT NULL DEFAULT 999,
            FOREIGN KEY(view_id) REFERENCES dashboard_card_views(id) ON DELETE CASCADE,
            UNIQUE(view_id, cd, grupo, indicador)
        );
        """
    )
    cols = [r[1] for r in conn.execute("PRAGMA table_info(dashboard_card_views)").fetchall()]
    if "is_default" not in cols:
        conn.execute("ALTER TABLE dashboard_card_views ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0")
    conn.commit(); conn.close()


def load_dashboard_card_views(username: str, cd: str) -> pd.DataFrame:
    _dashboard_card_view_tables_ready()
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM dashboard_card_views WHERE active=1 AND username=? AND cd=? ORDER BY is_default DESC, nome",
        conn,
        params=(username, cd),
    )
    conn.close()
    return df

def load_dashboard_card_views_for_user(username: str, cd: str) -> pd.DataFrame:
    """Carrega visões pessoais e visões globais do CD.

    As visões globais usam GLOBAL_DASHBOARD_USERNAME e voltam a aparecer para todos os usuários.
    """
    _dashboard_card_view_tables_ready()
    owners = [GLOBAL_DASHBOARD_USERNAME]
    if str(username) != GLOBAL_DASHBOARD_USERNAME:
        owners.append(str(username))
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT *,
               CASE WHEN username=? THEN 'Todos os usuários' ELSE 'Somente para mim' END AS escopo_visao
          FROM dashboard_card_views
         WHERE active=1 AND cd=? AND username IN (%s)
         ORDER BY CASE WHEN username=? THEN 0 ELSE 1 END, is_default DESC, nome
        """ % ",".join(["?"] * len(owners)),
        conn,
        params=(GLOBAL_DASHBOARD_USERNAME, cd, *owners, GLOBAL_DASHBOARD_USERNAME),
    )
    conn.close()
    return df


def can_manage_global_dashboard_view() -> bool:
    user = st.session_state.get("user", {})
    return (
        user.get("role") == "admin"
        or has_perm("configure_indicators")
        or has_perm("configure_targets")
    )


def load_dashboard_card_view_items(view_id: int) -> pd.DataFrame:
    _dashboard_card_view_tables_ready()
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM dashboard_card_view_items WHERE view_id=? ORDER BY sort_order, grupo, indicador",
        conn,
        params=(int(view_id),),
    )
    conn.close()
    return df


def save_dashboard_card_view(username: str, cd: str, nome: str, selected_df: pd.DataFrame, descricao: str = "", is_default: bool = False) -> int:
    """Salva a composição de cards para um CD específico.

    A seleção pode ter sido montada olhando outro CD. Por isso os itens são
    gravados com o CD de destino, mas preservam o codigo_indicador como chave
    principal para reabrir a mesma visão em qualquer CD compatível.
    """
    if not str(nome).strip():
        raise ValueError("Informe um nome para a visão.")
    if selected_df.empty:
        raise ValueError("Selecione ao menos um card para salvar a visão.")
    _dashboard_card_view_tables_ready()
    now = now_iso()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO dashboard_card_views(username, cd, nome, descricao, active, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(username, cd, nome) DO UPDATE SET descricao=excluded.descricao, active=1, is_default=excluded.is_default, updated_at=excluded.updated_at
            """,
            (username, cd, nome.strip(), descricao.strip(), 1 if is_default else 0, now, now),
        )
        if is_default:
            conn.execute(
                "UPDATE dashboard_card_views SET is_default=0, updated_at=? WHERE username=? AND cd=? AND nome<>?",
                (now, username, cd, nome.strip()),
            )
        view_id = int(conn.execute(
            "SELECT id FROM dashboard_card_views WHERE username=? AND cd=? AND nome=?",
            (username, cd, nome.strip()),
        ).fetchone()["id"])
        conn.execute("DELETE FROM dashboard_card_view_items WHERE view_id=?", (view_id,))
        seen: set[str] = set()
        order = 1
        for _, r in selected_df.iterrows():
            code = str(r.get("codigo_indicador") or "").strip()
            identity = code or f"{r.get('grupo')}|{r.get('indicador')}"
            if identity in seen:
                continue
            seen.add(identity)
            conn.execute(
                """
                INSERT INTO dashboard_card_view_items(view_id, cd, grupo, indicador, codigo_indicador, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (view_id, cd, str(r["grupo"]), str(r["indicador"]), code, order),
            )
            order += 1
        conn.execute(
            "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("dashboard_card_view", cd, None, None, "cards", None, nome.strip(), descricao.strip() or "Visão de cards salva pelo usuário", username, now),
        )
        conn.commit()
        return view_id
    finally:
        conn.close()



def update_dashboard_card_view(view_id: int, username: str, cd: str, nome: str, selected_df: pd.DataFrame, descricao: str = "", is_default: bool = False) -> None:
    """Edita uma visão pessoal de cards já existente no CD atual."""
    if not str(nome).strip():
        raise ValueError("Informe um nome para a visão.")
    if selected_df.empty:
        raise ValueError("Selecione ao menos um card para atualizar a visão.")
    _dashboard_card_view_tables_ready()
    now = now_iso()
    conn = get_conn()
    try:
        current = conn.execute(
            "SELECT id FROM dashboard_card_views WHERE id=? AND username=? AND cd=?",
            (int(view_id), username, cd),
        ).fetchone()
        if current is None:
            raise ValueError("Visão salva não encontrada para edição.")
        if is_default:
            conn.execute(
                "UPDATE dashboard_card_views SET is_default=0, updated_at=? WHERE username=? AND cd=? AND id<>?",
                (now, username, cd, int(view_id)),
            )
        conn.execute(
            """
            UPDATE dashboard_card_views
               SET nome=?, descricao=?, is_default=?, active=1, updated_at=?
             WHERE id=? AND username=? AND cd=?
            """,
            (nome.strip(), descricao.strip(), 1 if is_default else 0, now, int(view_id), username, cd),
        )
        conn.execute("DELETE FROM dashboard_card_view_items WHERE view_id=?", (int(view_id),))
        seen: set[str] = set()
        order = 1
        for _, r in selected_df.iterrows():
            code = str(r.get("codigo_indicador") or "").strip()
            identity = code or f"{r.get('grupo')}|{r.get('indicador')}"
            if identity in seen:
                continue
            seen.add(identity)
            conn.execute(
                """
                INSERT INTO dashboard_card_view_items(view_id, cd, grupo, indicador, codigo_indicador, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (int(view_id), cd, str(r["grupo"]), str(r["indicador"]), code, order),
            )
            order += 1
        conn.execute(
            "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("dashboard_card_view", cd, None, None, "cards", None, nome.strip(), descricao.strip() or "Edição de visão pessoal de cards", username, now),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def save_dashboard_card_view_for_cds(username: str, cds: list[str], nome: str, selected_df: pd.DataFrame, descricao: str = "", is_default: bool = False) -> list[str]:
    """Salva a mesma visão pessoal para um ou mais CDs.

    Usado quando o usuário está configurando, por exemplo, o RS, mas quer que a
    mesma composição de cards fique disponível também para SBC ou para todos os
    CDs liberados no seu perfil.
    """
    cds_clean = [str(x).strip() for x in cds if str(x).strip()]
    cds_clean = list(dict.fromkeys(cds_clean))
    if not cds_clean:
        raise ValueError("Selecione ao menos um CD para salvar a visão.")
    saved: list[str] = []
    for target_cd in cds_clean:
        save_dashboard_card_view(username, target_cd, nome, selected_df, descricao, is_default=is_default)
        saved.append(target_cd)
    return saved


def inactivate_dashboard_card_view(username: str, cd: str, view_id: int) -> None:
    _dashboard_card_view_tables_ready()
    conn = get_conn(); now = now_iso()
    conn.execute("UPDATE dashboard_card_views SET active=0, updated_at=? WHERE id=? AND username=? AND cd=?", (now, int(view_id), username, cd))
    conn.execute(
        "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("dashboard_card_view", cd, None, None, "active", "1", "0", "Inativação de visão pessoal de cards", username, now),
    )
    conn.commit(); conn.close()



def ordered_dashboard_df_from_labels(candidates: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    """Retorna os cards na ordem definida pelo usuário.

    O filtro via isin() do pandas preserva a ordem original do cadastro, não a
    ordem escolhida pelo usuário. Esta função reconstrói a seleção respeitando a
    sequência dos rótulos selecionados/reordenados.
    """
    if candidates is None or candidates.empty or not labels:
        return candidates.iloc[0:0].copy() if candidates is not None else pd.DataFrame()
    label_to_idx: dict[str, Any] = {}
    for idx, r in candidates.iterrows():
        label = str(r.get("__card_label") or "")
        if label and label not in label_to_idx:
            label_to_idx[label] = idx
    ordered_idx = []
    seen: set[str] = set()
    for label in labels:
        label = str(label)
        if label in seen:
            continue
        seen.add(label)
        if label in label_to_idx:
            ordered_idx.append(label_to_idx[label])
    if not ordered_idx:
        return candidates.iloc[0:0].copy()
    return candidates.loc[ordered_idx].copy()


def dashboard_labels_from_saved_items(items: pd.DataFrame, candidates: pd.DataFrame) -> list[str]:
    """Converte os itens salvos em labels na ordem gravada da visão."""
    if items is None or items.empty or candidates is None or candidates.empty:
        return []
    labels: list[str] = []
    seen: set[str] = set()
    cand = candidates.copy()
    cand["__codigo_norm"] = cand.get("codigo_indicador", "").fillna("").astype(str).str.strip().str.upper()
    for _, item in items.iterrows():
        code = str(item.get("codigo_indicador") or "").strip().upper()
        grupo = str(item.get("grupo") or "")
        indicador = str(item.get("indicador") or "")
        match = pd.DataFrame()
        if code:
            match = cand[cand["__codigo_norm"].eq(code)]
        if match.empty:
            match = cand[(cand["grupo"].astype(str).eq(grupo)) & (cand["indicador"].astype(str).eq(indicador))]
        if match.empty:
            continue
        label = str(match.iloc[0].get("__card_label") or "")
        if label and label not in seen:
            labels.append(label)
            seen.add(label)
    return labels


def render_dashboard_card_order_control(selected_labels: list[str], key_prefix: str) -> list[str]:
    """Permite ao usuário reorganizar a ordem dos cards antes de salvar/exibir.

    Se o pacote opcional streamlit-sortables estiver instalado, usa drag-and-drop.
    Caso contrário, usa uma tabela leve com a coluna Ordem, sem quebrar o app.
    """
    labels = [str(x) for x in selected_labels if str(x).strip()]
    labels = list(dict.fromkeys(labels))
    if len(labels) <= 1:
        return labels

    with st.expander("Organizar ordem dos cards", expanded=False):
        st.caption("Arraste os cards para definir a sequência. Se o recurso de arrastar não estiver disponível neste ambiente, altere a coluna Ordem.")
        try:
            from streamlit_sortables import sort_items  # type: ignore
            ordered = sort_items(labels, direction="vertical", key=f"{key_prefix}_sortable_cards")
            ordered = [str(x) for x in ordered if str(x) in labels]
            if ordered:
                return ordered
        except Exception:
            order_df = pd.DataFrame({"ordem": list(range(1, len(labels) + 1)), "card": labels})
            edited_order = st.data_editor(
                order_df,
                hide_index=True,
                use_container_width=True,
                key=f"{key_prefix}_card_order_editor",
                disabled=["card"],
                column_config={
                    "ordem": st.column_config.NumberColumn("Ordem", min_value=1, step=1, required=True),
                    "card": st.column_config.TextColumn("Card", disabled=True),
                },
            )
            edited_order["ordem"] = pd.to_numeric(edited_order["ordem"], errors="coerce").fillna(9999)
            ordered = edited_order.sort_values(["ordem", "card"], kind="stable")["card"].astype(str).tolist()
            return [x for x in ordered if x in labels]
    return labels


def dashboard_card_title(cfgrow: pd.Series) -> str:
    """Título executivo exibido no card do dashboard.

    O administrador pode alterar esse título no Dashboard Executivo. A alteração
    fica gravada em indicator_config.dashboard_titulo e passa a valer para todos
    os usuários que visualizam o mesmo indicador/código.
    """
    custom = str(cfgrow.get("dashboard_titulo") or "").strip()
    if custom and custom.lower() not in {"nan", "none"}:
        return custom
    return str(cfgrow.get("indicador") or "")


def save_dashboard_card_titles(edited_df: pd.DataFrame, base_df: pd.DataFrame, admin_user: str) -> int:
    """Grava títulos customizados de cards em indicator_config.

    A atualização é global por código do indicador quando o código existe. Isso
    faz o novo título valer para todos os usuários e para todos os CDs que usem o
    mesmo código. Se não houver código, atualiza apenas a linha id correspondente.
    """
    if edited_df is None or edited_df.empty:
        return 0
    required = {"id", "codigo_indicador", "indicador", "dashboard_titulo"}
    for col in required:
        if col not in edited_df.columns:
            edited_df[col] = ""
    base_titles = {}
    if base_df is not None and not base_df.empty:
        tmp = base_df.copy()
        if "dashboard_titulo" not in tmp.columns:
            tmp["dashboard_titulo"] = ""
        base_titles = {int(r["id"]): str(r.get("dashboard_titulo") or "").strip() for _, r in tmp.iterrows() if not pd.isna(r.get("id"))}

    conn = get_conn()
    now = now_iso()
    updates = 0
    try:
        for _, r in edited_df.iterrows():
            try:
                row_id = int(r.get("id"))
            except Exception:
                continue
            new_title = str(r.get("dashboard_titulo") or "").strip()
            if new_title.lower() in {"nan", "none"}:
                new_title = ""
            old_title = base_titles.get(row_id, "")
            if new_title == old_title:
                continue
            code = str(r.get("codigo_indicador") or "").strip()
            indicador = str(r.get("indicador") or "").strip()
            grupo = str(r.get("grupo") or "").strip()
            cd = str(r.get("cd") or "").strip()
            if code:
                rows = conn.execute(
                    "SELECT id, cd, grupo, indicador, COALESCE(dashboard_titulo, '') AS dashboard_titulo FROM indicator_config WHERE codigo_indicador=?",
                    (code,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, cd, grupo, indicador, COALESCE(dashboard_titulo, '') AS dashboard_titulo FROM indicator_config WHERE id=?",
                    (row_id,),
                ).fetchall()
            if not rows:
                continue
            for row in rows:
                conn.execute(
                    "UPDATE indicator_config SET dashboard_titulo=?, updated_by=?, updated_at=? WHERE id=?",
                    (new_title, admin_user, now, int(row["id"])),
                )
                conn.execute(
                    "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "indicator_config",
                        str(row["cd"]),
                        str(row["grupo"]),
                        str(row["indicador"]),
                        "dashboard_titulo",
                        str(row["dashboard_titulo"] or ""),
                        new_title,
                        "Alteração de título do card no Dashboard Executivo",
                        admin_user,
                        now,
                    ),
                )
            updates += 1
        conn.commit()
        return updates
    finally:
        conn.close()


def _card_status_class(status: str) -> str:
    s = str(status or "").lower()
    if "dentro" in s:
        return "ok"
    if "aten" in s:
        return "warn"
    if "fora" in s:
        return "bad"
    return "none"


def render_card_html(label: str, value: Optional[float], cfgrow: pd.Series, target: Optional[dict]) -> str:
    emoji, status = status_for_value(value, target, cfgrow) if bool(cfgrow["usar_sinaleira"]) else ("", "")
    meta_txt = ""
    if target:
        if bool(target.get("exibir_dashboard")) or bool(cfgrow.get("exibir_dashboard")):
            if bool(target.get("exibir_meta_como_linha")):
                meta_txt = f"Meta: {format_value(target['valor_meta'], cfgrow['formato'], cfgrow['indicador'])} · "
            elif bool(target.get("usar_sinaleira")):
                meta_txt = "Meta interna · "
    value_txt = format_value(value, cfgrow["formato"], cfgrow["indicador"]) or "—"
    emoji_html = f'<span class="dashboard-card-emoji">{html.escape(emoji)}</span>' if emoji else ""
    status_html = f"{html.escape(meta_txt + status)}" if (meta_txt or status) else "&nbsp;"
    return f"""
    <div class="dashboard-card dashboard-card-{_card_status_class(status)}">
      <div class="dashboard-card-label">{html.escape(str(label))}</div>
      <div class="dashboard-card-value"><span class="dashboard-card-status">{emoji_html}<span>{html.escape(value_txt)}</span></span></div>
      <div class="dashboard-card-sub">{status_html}</div>
    </div>
    """


def _dashboard_card_payload(label: str, value: Optional[float], cfgrow: pd.Series, target: Optional[dict]) -> dict[str, str]:
    emoji, status = status_for_value(value, target, cfgrow) if bool(cfgrow["usar_sinaleira"]) else ("", "")
    meta_txt = ""
    if target:
        if bool(target.get("exibir_dashboard")) or bool(cfgrow.get("exibir_dashboard")):
            if bool(target.get("exibir_meta_como_linha")):
                meta_txt = f"Meta: {format_value(target['valor_meta'], cfgrow['formato'], cfgrow['indicador'])} · "
            elif bool(target.get("usar_sinaleira")):
                meta_txt = "Meta interna · "
    value_txt = format_value(value, cfgrow["formato"], cfgrow["indicador"]) or "—"
    return {
        "label": str(label or ""),
        "value": str(value_txt),
        "emoji": str(emoji or ""),
        "status": str((meta_txt + status) if (meta_txt or status) else ""),
        "class": _card_status_class(status),
    }


def render_dashboard_card_native(payload: dict[str, str]) -> None:
    status_class = payload.get("class", "none")
    border_color = {
        "ok": "#22c55e",
        "warn": "#f5b301",
        "bad": "#e11d48",
        "none": BR_ORANGE,
    }.get(status_class, BR_ORANGE)
    tooltip = str(payload.get("tooltip") or "").strip()
    tooltip_attr = ""
    alert_html = ""
    cursor_style = "default"
    if tooltip:
        safe_tooltip = html.escape(tooltip, quote=True).replace(chr(10), "&#10;")
        tooltip_attr = f' title="{safe_tooltip}" tabindex="0"'
        cursor_style = "help"
        alert_html = (
            '<span style="position:absolute; top:10px; right:12px; font-size:.95rem; line-height:1; '
            'color:#f59e0b; filter:drop-shadow(0 1px 1px rgba(0,0,0,.12));" '
            'aria-label="Informação complementar">⚠</span>'
        )
    emoji = str(payload.get("emoji") or "").strip()
    emoji_html = f'<span style="font-size:1.7rem; line-height:1;">{html.escape(emoji)}</span>' if emoji else ""
    status_html = html.escape(payload.get("status", "") or "") or "&nbsp;"
    card_html = f"""
    <div class="dashboard-card-native"{tooltip_attr} style="position:relative; border:1px solid rgba(246,134,32,.26); border-left:5px solid {border_color}; border-radius:18px; padding:16px 18px; min-height:156px; background:linear-gradient(180deg,#fff,{BR_LIGHT}); box-shadow:0 8px 22px rgba(51,51,51,.055); display:flex; flex-direction:column; justify-content:space-between; cursor:{cursor_style};">
      {alert_html}
      <div style="font-size:.74rem; line-height:1.35; color:#737373; text-transform:uppercase; letter-spacing:.055em; font-weight:850; min-height:2.05rem; padding-right:1.3rem;">{html.escape(payload.get('label', ''))}</div>
      <div style="font-size:1.75rem; line-height:1.1; color:{BR_DARK}; font-weight:900; margin:.45rem 0 .3rem 0; font-variant-numeric:tabular-nums; display:flex; align-items:center; gap:.45rem;">
        {emoji_html}<span>{html.escape(payload.get('value', '—'))}</span>
      </div>
      <div style="font-size:.82rem; color:#6b7280; min-height:1.15rem;">{status_html}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def dashboard_aggregation_mode(cfgrow: pd.Series | dict[str, Any], agg_mode: str) -> str:
    """Define a agregação usada nos cards sem misturar leitura diária e mensal."""
    if agg_mode != "auto_month":
        return agg_mode
    formato = str(cfgrow.get("formato") or "")
    indicador = str(cfgrow.get("indicador") or "").lower()
    tipo = str(cfgrow.get("tipo_campo") or "")
    if formato == "percentual" or "performance" in indicador or "atingimento" in indicador:
        return "mean"
    if tipo == "calculo" and ("/" in str(cfgrow.get("formula") or "")):
        return "mean"
    return "sum"


def build_dashboard_runtime_cache(vals: pd.DataFrame, configs: pd.DataFrame, cd: str, start_iso: str, end_iso: str) -> dict[str, Any]:
    """Pré-calcula calendário, metas e cálculos do dashboard em lote."""
    try:
        start_d = pd.to_datetime(start_iso).date()
        end_d = pd.to_datetime(end_iso).date()
    except Exception:
        return {"cd": cd, "dates": [], "date_iso": [], "target_maps_by_date": {}, "calc_by_date": {}}
    if end_d < start_d:
        return {"cd": cd, "dates": [], "date_iso": [], "target_maps_by_date": {}, "calc_by_date": {}}
    dates = working_days_between(cd, start_d, end_d)
    if not dates:
        dates = [end_d]
    date_iso = [d.isoformat() for d in dates]
    target_maps_by_date = target_lookup_for_dates([cd], date_iso)
    has_calc = configs is not None and not configs.empty and not configs[configs["tipo_campo"].astype(str).eq("calculo")].empty
    calc_by_date = {ds: compute_calculated_values(vals, configs, cd, ds) for ds in date_iso} if has_calc else {}
    return {
        "cd": str(cd),
        "start": start_d,
        "end": end_d,
        "dates": dates,
        "date_iso": date_iso,
        "target_maps_by_date": target_maps_by_date,
        "calc_by_date": calc_by_date,
    }


def dashboard_value_matrix_rule(
    vals: pd.DataFrame,
    configs: pd.DataFrame,
    cd: str,
    cfgrow: pd.Series | dict[str, Any],
    start_iso: str,
    end_iso: str,
    agg: str,
    runtime_cache: Optional[dict[str, Any]] = None,
) -> Optional[float]:
    """Valor do card usando a mesma regra operacional da matriz diária.

    Isso permite que comparativos do dashboard também enxerguem dado diário,
    cálculo, meta e parâmetro. Para acumulado mensal, considera apenas dias
    trabalhados do CD no período selecionado.
    """
    try:
        start_d = pd.to_datetime(start_iso).date()
        end_d = pd.to_datetime(end_iso).date()
    except Exception:
        return None
    if end_d < start_d:
        return None

    cache_ok = (
        runtime_cache is not None
        and str(runtime_cache.get("cd")) == str(cd)
        and runtime_cache.get("dates") is not None
        and runtime_cache.get("target_maps_by_date") is not None
    )
    if cache_ok:
        all_dates = list(runtime_cache.get("dates") or [])
        dates = [d for d in all_dates if start_d <= d <= end_d]
        if not dates and start_d == end_d:
            dates = [start_d]
        target_maps_by_date = runtime_cache.get("target_maps_by_date") or {}
        calc_by_date = runtime_cache.get("calc_by_date") or {}
    else:
        dates = working_days_between(cd, start_d, end_d)
        if not dates:
            dates = [end_d]
        date_iso = [d.isoformat() for d in dates]
        target_maps_by_date = target_lookup_for_dates([cd], date_iso)
        calc_by_date: dict[str, dict[tuple[str, str], float]] = {}
        if str(cfgrow.get("tipo_campo") or "") == "calculo" or not configs[configs["tipo_campo"].astype(str).eq("calculo")].empty:
            calc_by_date = {ds: compute_calculated_values(vals, configs, cd, ds) for ds in date_iso}

    values: list[float] = []
    for d in dates:
        v = matrix_value_for_day(vals, configs, calc_by_date, target_maps_by_date, cd, cfgrow, d)
        if v is not None and not pd.isna(v):
            values.append(float(v))

    if not values:
        return None
    if agg == "sum":
        return float(sum(values))
    if agg == "mean":
        return float(sum(values) / len(values))
    return float(values[-1])


def _bool_setting(row: pd.Series | dict[str, Any], field: str, default: bool = True) -> bool:
    try:
        value = row.get(field)
    except Exception:
        value = None
    if value is None:
        return bool(default)
    try:
        if pd.isna(value):
            return bool(default)
    except Exception:
        pass
    try:
        return bool(int(value))
    except Exception:
        return bool(value)


def _find_config_row_for_ref(
    configs: pd.DataFrame,
    cd: str,
    grupo: str | None = None,
    indicador: str | None = None,
    codigo: str | None = None,
    active_only: bool = True,
) -> Optional[pd.Series]:
    if configs is None or configs.empty:
        return None
    scope = configs[configs["cd"].astype(str).eq(str(cd))].copy()
    if scope.empty:
        return None
    if active_only and "ativo" in scope.columns:
        scope = scope[scope["ativo"].fillna(1).astype(int).eq(1)].copy()
    if "indicador" in scope.columns:
        scope = scope[scope["indicador"].astype(str).ne("__CABECALHO__")].copy()
    if scope.empty:
        return None

    code = str(codigo or "").strip().upper()
    if code and "codigo_indicador" in scope.columns:
        hit = scope[scope["codigo_indicador"].fillna("").astype(str).str.strip().str.upper().eq(code)]
        if not hit.empty:
            return hit.iloc[0]

    g = _formula_key(grupo or "")
    i = _formula_key(indicador or "")
    if g and i:
        hit = scope[
            scope["grupo"].astype(str).map(_formula_key).eq(g)
            & scope["indicador"].astype(str).map(_formula_key).eq(i)
        ]
        if not hit.empty:
            return hit.iloc[0]
    return None


def _auto_reference_for_card(configs: pd.DataFrame, cd: str, cfgrow: pd.Series | dict[str, Any]) -> Optional[pd.Series]:
    """Procura automaticamente uma base Realizado → Necessário/Planejado/Previsto."""
    if configs is None or configs.empty:
        return None
    scope = configs[configs["cd"].astype(str).eq(str(cd))].copy()
    if scope.empty:
        return None
    if "ativo" in scope.columns:
        scope = scope[scope["ativo"].fillna(1).astype(int).eq(1)].copy()
    scope = scope[scope["indicador"].astype(str).ne("__CABECALHO__")].copy()
    if scope.empty:
        return None

    grupo = str(cfgrow.get("grupo") or "")
    indicador = str(cfgrow.get("indicador") or "")
    code = str(cfgrow.get("codigo_indicador") or "").strip().upper()
    if code and "codigo_indicador" in scope.columns:
        scope = scope[~scope["codigo_indicador"].fillna("").astype(str).str.strip().str.upper().eq(code)].copy()
    scope = scope[~((scope["grupo"].astype(str).eq(grupo)) & (scope["indicador"].astype(str).eq(indicador)))].copy()
    if scope.empty:
        return None

    ind_norm = _formula_key(indicador)
    grp_norm = _formula_key(grupo)
    wanted_terms = ["NECESSARIO", "NECESSARIA", "PLANEJADO", "PLANEJADA", "PROJETADO", "PROJETADA", "PREVISTO", "PREVISTA", "META"]
    actual_terms = ["REALIZADO", "REALIZADA", "FATURADO", "FATURADA", "EXECUTADO", "EXECUTADA", "PRODUZIDO", "PRODUZIDA", "PLANEJADAS"]

    target_names: set[str] = set()
    for old_term in actual_terms:
        if old_term in ind_norm:
            for new_term in wanted_terms:
                target_names.add(ind_norm.replace(old_term, new_term))

    best_idx = None
    best_score = -1
    for idx, cand in scope.iterrows():
        cand_ind = _formula_key(cand.get("indicador"))
        cand_grp = _formula_key(cand.get("grupo"))
        score = 0
        if cand_grp == grp_norm:
            score += 35
        if cand_ind in target_names:
            score += 90
        if any(w in cand_ind for w in wanted_terms):
            score += 25
        for token in [t for t in ind_norm.split() if len(t) >= 4 and t not in actual_terms and t not in wanted_terms]:
            if token in cand_ind:
                score += 5
        if any(t in cand_ind for t in ["REALIZADO", "REALIZADA", "EXECUTADO", "EXECUTADA"]):
            score -= 35
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_idx is not None and best_score >= 40:
        return scope.loc[best_idx]
    return None


def dashboard_reference_for_card(configs: pd.DataFrame, cd: str, cfgrow: pd.Series | dict[str, Any]) -> Optional[pd.Series]:
    """Resolve a referência do card: específica → % Meta Mês → automática."""
    if not _bool_setting(cfgrow, "exibir_referencia_card", True):
        return None

    ref_grupo = str(cfgrow.get("card_ref_grupo") or "").strip()
    ref_indicador = str(cfgrow.get("card_ref_indicador") or "").strip()
    if ref_grupo and ref_indicador:
        found = _find_config_row_for_ref(configs, cd, ref_grupo, ref_indicador)
        if found is not None:
            return found

    total_grupo = str(cfgrow.get("total_mes_ref_grupo") or "").strip()
    total_indicador = str(cfgrow.get("total_mes_ref_indicador") or "").strip()
    if total_grupo and total_indicador:
        found = _find_config_row_for_ref(configs, cd, total_grupo, total_indicador)
        if found is not None:
            return found

    return _auto_reference_for_card(configs, cd, cfgrow)


def dashboard_card_enabled_for_context(row: pd.Series | dict[str, Any], agg_mode: str) -> bool:
    if agg_mode == "latest":
        return _bool_setting(row, "exibir_dashboard_dia", True)
    if agg_mode == "auto_month":
        return _bool_setting(row, "exibir_dashboard_mes", True)
    return True


def _row_visible_for_tooltip(row: pd.Series | dict[str, Any]) -> bool:
    if str(row.get("indicador") or "") == "__CABECALHO__":
        return False
    if not _bool_setting(row, "ativo", True):
        return False
    # Linha ocultada no painel/matriz não deve aparecer no detalhamento do tooltip.
    if not _bool_setting(row, "exibir_painel_matricial", True):
        return False
    return True


def _resolve_formula_component_row(configs: pd.DataFrame, cd: str, token: str) -> Optional[pd.Series]:
    token_txt = str(token or "").strip()
    if not token_txt or configs is None or configs.empty:
        return None
    scope = configs[configs["cd"].astype(str).eq(str(cd))].copy()
    if scope.empty:
        return None

    token_norm = _formula_key(token_txt)
    token_code = _formula_code_key(token_txt)
    for _, cand in scope.iterrows():
        if not _row_visible_for_tooltip(cand):
            continue
        candidates = {
            _formula_key(cand.get("indicador")),
            _formula_key(cand.get("grupo")),
            _formula_key(f"{cand.get('grupo')} · {cand.get('indicador')}"),
            _formula_key(cand.get("codigo_indicador")),
            _formula_code_key(cand.get("codigo_indicador")),
        }
        try:
            candidates.add(_formula_key(f"ID_{int(cand.get('id'))}"))
            candidates.add(_formula_code_key(f"ID_{int(cand.get('id'))}"))
        except Exception:
            pass
        if token_norm in candidates or token_code in candidates:
            return cand
    return None


def dashboard_card_tooltip(
    cfgrow: pd.Series | dict[str, Any],
    configs: pd.DataFrame,
    vals: pd.DataFrame,
    cd: str,
    start_iso: str,
    end_iso: str,
    agg_mode: str,
    runtime_cache: Optional[dict[str, Any]] = None,
) -> str:
    """Tooltip de card calculado: mostra apenas componentes visíveis e maiores que zero."""
    if str(cfgrow.get("tipo_campo") or "") != "calculo":
        return ""
    formula = str(cfgrow.get("formula") or "").strip()
    if not formula:
        return ""
    tokens = re.findall(r"\[([^\]]+)\]", formula)
    if not tokens:
        return ""

    lines: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        token_txt = str(token or "").strip()
        token_key = _formula_key(token_txt)
        if not token_txt or token_key in seen:
            continue
        seen.add(token_key)
        comp = _resolve_formula_component_row(configs, cd, token_txt)
        if comp is None:
            continue
        comp_agg = dashboard_aggregation_mode(comp, agg_mode)
        comp_val = dashboard_value_matrix_rule(vals, configs, cd, comp, start_iso, end_iso, comp_agg, runtime_cache=runtime_cache)
        if comp_val is None or pd.isna(comp_val) or abs(float(comp_val)) <= 1e-12:
            continue
        label = dashboard_card_title(pd.Series(dict(comp)))
        value_txt = format_value(comp_val, str(comp.get("formato") or "numero"), str(comp.get("indicador") or label)) or "—"
        lines.append(f"{label}: {value_txt}")
    return "\n".join(lines)


def dashboard_comparison_payload(
    label: str,
    actual_value: Optional[float],
    reference_value: Optional[float],
    cfgrow: pd.Series | dict[str, Any],
    reference_row: pd.Series | dict[str, Any],
) -> dict[str, str]:
    """Card executivo com leitura Realizado x Necessário/Planejado."""
    if reference_value is None or pd.isna(reference_value) or abs(float(reference_value)) < 1e-12:
        return _dashboard_card_payload(label, actual_value, pd.Series(dict(cfgrow)), None)

    actual = 0.0 if actual_value is None or pd.isna(actual_value) else float(actual_value)
    ref = float(reference_value)
    ratio = actual / ref

    cfg_tmp = pd.Series(dict(cfgrow))
    cfg_tmp["formato"] = "percentual"
    cfg_tmp["tipo_campo"] = "calculo"
    target = {
        "valor_meta": 1.0,
        "direcao_meta": str(cfgrow.get("direcao_meta") or "maior_melhor"),
        "tolerancia_amarela": float(cfgrow.get("tolerancia_amarela") or 0.05),
    }
    emoji, status = status_for_value(ratio, target, cfg_tmp)
    status_class = _card_status_class(status)

    actual_txt = format_value(actual, str(cfgrow.get("formato") or "numero"), str(cfgrow.get("indicador") or ""))
    ref_txt = format_value(ref, str(cfgrow.get("formato") or "numero"), str(cfgrow.get("indicador") or ""))
    ratio_txt = format_value(ratio, "percentual", "% atingimento")
    ref_name = dashboard_card_title(pd.Series(dict(reference_row))) if isinstance(reference_row, (pd.Series, dict)) else "referência"

    # No card comparativo, o valor realizado deve ser o foco visual.
    # O planejado e o percentual de atingimento ficam como informação secundária,
    # evitando que o card pareça ser apenas um card percentual.
    comparison_txt = f"Planejado {ref_txt} ({emoji} {ratio_txt})".replace("  ", " ").strip()

    return {
        "label": str(label or ""),
        "value": actual_txt or "—",
        "emoji": "",
        "status": comparison_txt,
        "class": status_class,
        "reference": str(ref_name),
        "comparison_status": str(status or ""),
    }


def _dashboard_direct_filled_value_for_row(
    vals: pd.DataFrame,
    cd: str,
    row: pd.Series | dict[str, Any],
    start_iso: str,
    end_iso: str,
    agg: str,
) -> Optional[float]:
    """Lê somente valor preenchido em values_indicators, ignorando target_versions."""
    if vals is None or vals.empty:
        return None
    try:
        start_d = pd.to_datetime(start_iso).date()
        end_d = pd.to_datetime(end_iso).date()
    except Exception:
        return None
    if end_d < start_d:
        return None
    grupo = str(row.get("grupo") or "")
    indicador = str(row.get("indicador") or "")
    codigo = str(row.get("codigo_indicador") or "").strip()
    scope = vals[
        (vals["cd"].astype(str).eq(str(cd)))
        & (pd.to_datetime(vals["data"]).dt.date >= start_d)
        & (pd.to_datetime(vals["data"]).dt.date <= end_d)
    ].copy()
    if scope.empty:
        return None
    if codigo and "codigo_indicador" in scope.columns:
        by_code = scope[scope["codigo_indicador"].fillna("").astype(str).str.strip().eq(codigo)].copy()
    else:
        by_code = pd.DataFrame()
    if by_code.empty:
        by_code = scope[(scope["grupo"].astype(str).eq(grupo)) & (scope["indicador"].astype(str).eq(indicador))].copy()
    if by_code.empty or "valor" not in by_code.columns:
        return None
    by_code = by_code[by_code["valor"].notna()].copy()
    if by_code.empty:
        return None
    by_code["__data"] = pd.to_datetime(by_code["data"]).dt.date
    # Se houver mais de um lançamento para o mesmo dia, usa o último ID.
    sort_cols = ["__data"] + (["id"] if "id" in by_code.columns else [])
    by_code = by_code.sort_values(sort_cols)
    daily = by_code.groupby("__data", as_index=False).tail(1)
    values = [float(v) for v in daily["valor"].tolist() if v is not None and not pd.isna(v)]
    if not values:
        return None
    if agg == "sum":
        return float(sum(values))
    if agg == "mean":
        return float(sum(values) / len(values))
    return float(values[-1])


def _dashboard_reference_value_guard(
    vals: pd.DataFrame,
    configs: pd.DataFrame,
    cd: str,
    cfgrow: pd.Series | dict[str, Any],
    reference_row: pd.Series | dict[str, Any],
    actual_value: Optional[float],
    reference_value: Optional[float],
    start_iso: str,
    end_iso: str,
    agg_mode: str,
    runtime_cache: Optional[dict[str, Any]] = None,
) -> tuple[Optional[float], pd.Series | dict[str, Any]]:
    """Corrige referência numérica absurda no Dashboard.

    Caso real que motivou a regra: cards de volume, como Pedidos Programados,
    estavam buscando uma meta versionada igual a 1 em vez da linha diária
    Planejada/Prevista preenchida no painel. Quando o realizado é volumétrico
    e a referência volta como 0/1, o método procura uma linha planejada diária
    equivalente no mesmo CD/grupo e usa o valor efetivamente preenchido.
    """
    try:
        actual = None if actual_value is None or pd.isna(actual_value) else float(actual_value)
    except Exception:
        actual = None
    try:
        current_ref = None if reference_value is None or pd.isna(reference_value) else float(reference_value)
    except Exception:
        current_ref = None

    # Referências percentuais legítimas costumam comparar valores pequenos.
    # Só aplicamos a correção quando o realizado é claramente volumétrico.
    if actual is None or abs(actual) <= 10:
        return reference_value, reference_row
    if current_ref is not None and abs(current_ref) > 1.5:
        return reference_value, reference_row
    if configs is None or configs.empty:
        return reference_value, reference_row

    scope = configs[configs["cd"].astype(str).eq(str(cd))].copy()
    if scope.empty:
        return reference_value, reference_row
    if "ativo" in scope.columns:
        scope = scope[scope["ativo"].fillna(1).astype(int).eq(1)].copy()
    scope = scope[scope["indicador"].astype(str).ne("__CABECALHO__")].copy()
    if scope.empty:
        return reference_value, reference_row

    actual_ind = _formula_key(cfgrow.get("indicador"))
    actual_grp = _formula_key(cfgrow.get("grupo"))
    ref_ind = _formula_key(reference_row.get("indicador"))
    ref_grp = _formula_key(reference_row.get("grupo"))

    planned_stems = ["PLANEJ", "PREVIST", "NECESS", "PROJET", "OBJETIVO", "META"]
    actual_stems = ["PROGRAM", "REALIZ", "EXECUT", "FATUR", "PRODUZ", "SEPAR", "CONSOLID"]
    target_names: set[str] = set()
    for old in ["PROGRAMADOS", "PROGRAMADAS", "PROGRAMADO", "PROGRAMADA", "REALIZADO", "REALIZADA", "EXECUTADO", "EXECUTADA"]:
        if old in actual_ind:
            for new in ["PLANEJADOS", "PLANEJADAS", "PLANEJADO", "PLANEJADA", "PREVISTOS", "PREVISTAS", "NECESSARIO", "NECESSARIA"]:
                target_names.add(actual_ind.replace(old, new))

    focus_tokens = [
        t for t in actual_ind.split()
        if len(t) >= 4
        and not any(stem in t for stem in planned_stems + actual_stems)
    ]

    best_row = reference_row
    best_value = reference_value
    best_score = -1
    seen: set[tuple[str, str, str]] = set()

    for _, cand in scope.iterrows():
        key = (str(cand.get("cd") or ""), str(cand.get("grupo") or ""), str(cand.get("indicador") or ""))
        if key in seen:
            continue
        seen.add(key)
        cand_ind = _formula_key(cand.get("indicador"))
        cand_grp = _formula_key(cand.get("grupo"))
        score = 0
        if cand_grp == actual_grp:
            score += 45
        if cand_grp == ref_grp:
            score += 30
        if cand_ind == ref_ind:
            score += 25
        if cand_ind in target_names:
            score += 90
        if any(stem in cand_ind for stem in planned_stems):
            score += 40
        if focus_tokens and any(tok in cand_ind for tok in focus_tokens):
            score += 25
        # Evita trocar por outra linha realizada/programada quando procuramos planejado.
        if any(stem in cand_ind for stem in ["REALIZ", "EXECUT", "PROGRAM"]):
            score -= 35
        if score < 55:
            continue
        cand_agg = dashboard_aggregation_mode(cand, agg_mode)
        try:
            cand_value = dashboard_value_matrix_rule(vals, configs, cd, cand, start_iso, end_iso, cand_agg, runtime_cache=runtime_cache)
        except Exception:
            cand_value = None
        try:
            cand_float = None if cand_value is None or pd.isna(cand_value) else float(cand_value)
        except Exception:
            cand_float = None

        # Para linhas meta/parâmetro, se a regra normal caiu na meta versionada 0/1,
        # tenta recuperar o valor efetivamente preenchido no painel diário.
        if cand_float is None or abs(cand_float) <= 1.5:
            direct_value = _dashboard_direct_filled_value_for_row(vals, cd, cand, start_iso, end_iso, cand_agg)
            try:
                direct_float = None if direct_value is None or pd.isna(direct_value) else float(direct_value)
            except Exception:
                direct_float = None
            if direct_float is not None and abs(direct_float) > 1.5:
                cand_float = direct_float

        if cand_float is None or abs(cand_float) <= 1.5:
            continue
        # Referência operacional deve ter ordem de grandeza minimamente compatível.
        if abs(actual) > 100 and abs(cand_float) < abs(actual) * 0.05:
            continue
        if score > best_score:
            best_score = score
            best_row = cand
            best_value = cand_float

    return best_value, best_row


def _dashboard_reference_value_with_daily_priority(
    vals: pd.DataFrame,
    cd: str,
    reference_row: pd.Series | dict[str, Any],
    reference_value: Optional[float],
    start_iso: str,
    end_iso: str,
    ref_agg: str,
) -> Optional[float]:
    """Prioriza valor preenchido no Painel Diário para a linha de referência.

    Corrige casos em que uma linha de meta/parâmetro possui meta versionada 1,
    mas o planejado operacional do dia foi preenchido na matriz como 1.179, 14.779 etc.
    Para comparativo de card, quando existe dado preenchido no período, ele é a fonte correta.
    """
    direct_value = _dashboard_direct_filled_value_for_row(vals, cd, reference_row, start_iso, end_iso, ref_agg)
    try:
        direct_float = None if direct_value is None or pd.isna(direct_value) else float(direct_value)
    except Exception:
        direct_float = None
    if direct_float is None:
        return reference_value

    ref_tipo = str(reference_row.get("tipo_campo") or "")
    try:
        ref_float = None if reference_value is None or pd.isna(reference_value) else float(reference_value)
    except Exception:
        ref_float = None

    # Meta/parâmetro preenchido no painel sempre prevalece sobre target_versions.
    if ref_tipo in {"meta", "parametro"}:
        return direct_float

    # Também corrige qualquer referência volumétrica que tenha caído em 0/1 por meta versionada.
    if ref_float is not None and abs(ref_float) <= 1.5 and abs(direct_float) > 1.5:
        return direct_float
    return reference_value


def build_dashboard_card_payloads(selected: pd.DataFrame, vals: pd.DataFrame, configs: pd.DataFrame, cd: str, start_iso: str, end_iso: str, agg_mode: str, runtime_cache: Optional[dict[str, Any]] = None) -> list[dict[str, str]]:
    payloads: list[dict[str, str]] = []
    if selected is None or selected.empty:
        return payloads
    for _, r in selected.iterrows():
        if not dashboard_card_enabled_for_context(r, agg_mode):
            continue
        agg = dashboard_aggregation_mode(r, agg_mode)
        value = dashboard_value_matrix_rule(vals, configs, cd, r, start_iso, end_iso, agg, runtime_cache=runtime_cache)
        reference_row = dashboard_reference_for_card(configs, cd, r)
        if reference_row is not None:
            ref_agg = dashboard_aggregation_mode(reference_row, agg_mode)
            reference_value = dashboard_value_matrix_rule(vals, configs, cd, reference_row, start_iso, end_iso, ref_agg, runtime_cache=runtime_cache)
            reference_value = _dashboard_reference_value_with_daily_priority(
                vals, cd, reference_row, reference_value, start_iso, end_iso, ref_agg
            )
            reference_value, reference_row = _dashboard_reference_value_guard(
                vals, configs, cd, r, reference_row, value, reference_value, start_iso, end_iso, agg_mode, runtime_cache=runtime_cache
            )
            payload = dashboard_comparison_payload(dashboard_card_title(r), value, reference_value, r, reference_row)
        else:
            target = target_for_matrix_row(cd, r, end_iso)
            payload = _dashboard_card_payload(dashboard_card_title(r), value, r, target)
        tooltip = dashboard_card_tooltip(r, configs, vals, cd, start_iso, end_iso, agg_mode, runtime_cache=runtime_cache)
        if tooltip:
            payload["tooltip"] = tooltip
        payloads.append(payload)
    return payloads


def render_dashboard_card_grid(title: str, selected: pd.DataFrame, vals: pd.DataFrame, configs: pd.DataFrame, cd: str, start_iso: str, end_iso: str, agg_mode: str, runtime_cache: Optional[dict[str, Any]] = None) -> None:
    st.subheader(title)
    payloads = build_dashboard_card_payloads(selected, vals, configs, cd, start_iso, end_iso, agg_mode, runtime_cache=runtime_cache)

    if not payloads:
        st.info("Nenhum card para exibir.")
        return

    cards_per_row = 4
    for start in range(0, len(payloads), cards_per_row):
        row_payloads = payloads[start:start + cards_per_row]
        cols = st.columns(cards_per_row, gap="medium")
        for idx, col in enumerate(cols):
            with col:
                if idx < len(row_payloads):
                    render_dashboard_card_native(row_payloads[idx])
                else:
                    st.empty()


def _visual_font(size: int, bold: bool = False):
    from PIL import ImageFont
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "arial.ttf",
    ]
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_visual_text(draw, text: str, font, max_width: int) -> list[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        try:
            width = draw.textbbox((0, 0), trial, font=font)[2]
        except Exception:
            width = len(trial) * 8
        if width <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _payload_sections_to_png(title: str, sections: list[tuple[str, list[dict[str, str]]]], subtitle: str = "") -> bytes:
    from PIL import Image, ImageDraw
    width = 1600
    margin = 42
    gap = 22
    card_w = int((width - margin * 2 - gap * 3) / 4)
    card_h = 150
    title_font = _visual_font(34, True)
    section_font = _visual_font(22, True)
    label_font = _visual_font(15, True)
    value_font = _visual_font(30, True)
    sub_font = _visual_font(16, False)
    small_font = _visual_font(14, False)

    rows_count = 0
    for _heading, payloads in sections:
        rows_count += 1 + max(1, (len(payloads) + 3) // 4)
    height = margin + 58 + (22 if subtitle else 0) + rows_count * (card_h + 56) + margin
    img = Image.new("RGB", (width, max(height, 520)), "#fffaf6")
    draw = ImageDraw.Draw(img)

    y = margin
    draw.text((margin, y), title, fill="#333333", font=title_font)
    y += 46
    if subtitle:
        draw.text((margin, y), subtitle, fill="#6b7280", font=small_font)
        y += 32

    color_map = {"ok": "#22c55e", "warn": "#f5b301", "bad": "#e11d48", "none": "#f68620"}
    for heading, payloads in sections:
        y += 10
        draw.text((margin, y), heading, fill="#333333", font=section_font)
        y += 36
        if not payloads:
            payloads = [{"label": "Sem cards", "value": "—", "status": "", "class": "none"}]
        for idx, p in enumerate(payloads):
            col = idx % 4
            row = idx // 4
            x = margin + col * (card_w + gap)
            cy = y + row * (card_h + gap)
            klass = str(p.get("class") or "none")
            border = color_map.get(klass, "#f68620")
            draw.rounded_rectangle((x, cy, x + card_w, cy + card_h), radius=18, fill="#ffffff", outline="#f3d4bd", width=1)
            draw.rectangle((x, cy, x + 7, cy + card_h), fill=border)
            tx = x + 22
            ty = cy + 18
            for line in _wrap_visual_text(draw, str(p.get("label") or ""), label_font, card_w - 42)[:2]:
                draw.text((tx, ty), line.upper(), fill="#737373", font=label_font)
                ty += 18
            value_text = (str(p.get("emoji") or "") + " " + str(p.get("value") or "—")).strip()
            draw.text((tx, cy + 66), value_text, fill="#333333", font=value_font)
            status_text = str(p.get("status") or "")
            for line in _wrap_visual_text(draw, status_text, sub_font, card_w - 42)[:2]:
                draw.text((tx, cy + 116), line, fill="#6b7280", font=sub_font)
                cy += 18
        y += ((len(payloads) + 3) // 4) * (card_h + gap) + 20

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _matrix_to_png(title: str, headers: list[str], rows: list[dict[str, Any]], subtitle: str = "") -> bytes:
    from PIL import Image, ImageDraw
    width = 1800
    margin = 34
    row_h = 36
    title_font = _visual_font(32, True)
    header_font = _visual_font(15, True)
    cell_font = _visual_font(14, False)
    small_font = _visual_font(13, False)
    max_rows = min(len(rows), 90)
    height = margin + 72 + (22 if subtitle else 0) + (max_rows + 1) * row_h + margin
    img = Image.new("RGB", (width, max(height, 520)), "#fffaf6")
    draw = ImageDraw.Draw(img)
    y = margin
    draw.text((margin, y), title, fill="#333333", font=title_font)
    y += 44
    if subtitle:
        draw.text((margin, y), subtitle, fill="#6b7280", font=small_font)
        y += 28

    indicator_w = 420
    remaining_w = width - margin * 2 - indicator_w
    other_w = max(96, int(remaining_w / max(1, len(headers) - 1)))
    col_widths = [indicator_w] + [other_w] * (len(headers) - 1)
    x = margin
    draw.rectangle((margin, y, width - margin, y + row_h), fill="#f8f9fb", outline="#e5e7eb")
    for h, w in zip(headers, col_widths):
        draw.text((x + 8, y + 10), str(h), fill="#6b7280", font=header_font)
        x += w
    y += row_h
    for r in rows[:max_rows]:
        bg = "#ffffff" if rows.index(r) % 2 == 0 else "#fff4ea"
        draw.rectangle((margin, y, width - margin, y + row_h), fill=bg, outline="#eeeeee")
        values = [str(r.get("indicador") or "")] + [str(v or "") for v in r.get("values", [])] + [str(v or "") for v in r.get("summary_values", [])]
        x = margin
        for val, w in zip(values, col_widths):
            safe = val.replace("🟢", "OK ").replace("🟡", "ATENCAO ").replace("🔴", "FORA ")
            draw.text((x + 8, y + 10), safe[:48], fill="#333333", font=cell_font)
            x += w
        y += row_h
    if len(rows) > max_rows:
        draw.text((margin, y + 8), f"Exportação visual limitada aos primeiros {max_rows} registros de {len(rows)}.", fill="#6b7280", font=small_font)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _png_to_pdf_bytes(png_bytes: bytes) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PDF")
    return out.getvalue()


def _png_to_xlsx_bytes(png_bytes: bytes, sheet_name: str = "Visao") -> bytes:
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]
    img_stream = io.BytesIO(png_bytes)
    xl_img = XLImage(img_stream)
    ws.add_image(xl_img, "A1")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def render_visual_export_buttons(key_prefix: str, base_filename: str, png_bytes: bytes) -> None:
    """Botões visíveis de exportação da área útil, em formato de print estruturado."""
    with st.container(border=True):
        st.markdown("**Exportar visão atual**")
        st.caption("Exporta somente a área útil dos dados/cards em formato visual, como um print estruturado. Não inclui navegador nem menu lateral.")
        c1, c2 = st.columns(2, gap="small")
        with c1:
            st.download_button(
                "📷 Exportar imagem (PNG)",
                data=png_bytes,
                file_name=f"{base_filename}.png",
                mime="image/png",
                use_container_width=True,
                key=f"{key_prefix}_png",
            )
        with c2:
            st.download_button(
                "📄 Exportar PDF",
                data=_png_to_pdf_bytes(png_bytes),
                file_name=f"{base_filename}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"{key_prefix}_pdf",
            )
    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

def total_working_days_in_month(cd: str, ref_day: date) -> int:
    start_month = date(ref_day.year, ref_day.month, 1)
    end_month = last_day_of_month(ref_day)
    return len(working_days_between(cd, start_month, end_month))


def latest_filled_date_from_values(vals: pd.DataFrame, ref_day: date) -> Optional[date]:
    if vals is None or vals.empty or "data" not in vals.columns:
        return None
    tmp = vals.copy()
    if "valor" in tmp.columns:
        tmp = tmp[tmp["valor"].notna()].copy()
    if tmp.empty:
        return None
    try:
        tmp_dates = pd.to_datetime(tmp["data"]).dt.date
        tmp_dates = tmp_dates[tmp_dates <= ref_day]
        return tmp_dates.max() if not tmp_dates.empty else None
    except Exception:
        return None


def _find_monthly_objective_by_terms(cd: str, ref_day: date, terms: list[str] | tuple[str, ...]) -> Optional[dict]:
    try:
        objectives = load_monthly_objectives(cd, month_ref_iso(ref_day))
    except Exception:
        return None
    if objectives is None or objectives.empty:
        return None
    norm_terms = [_formula_key(t) for t in terms if str(t or "").strip()]
    best_row = None
    best_score = 0
    for _, r in objectives.iterrows():
        text = _formula_key(" ".join(str(r.get(c) or "") for c in ["grupo", "indicador", "codigo_indicador"]))
        score = 0
        for term in norm_terms:
            if term and term in text:
                score += 10 + len(term)
        if score > best_score:
            best_score = score
            best_row = r
    return dict(best_row) if best_row is not None and best_score > 0 else None


def _find_indicator_by_terms(configs: pd.DataFrame, cd: str, required_terms: list[str] | tuple[str, ...], avoid_terms: list[str] | tuple[str, ...] = ()) -> Optional[pd.Series]:
    if configs is None or configs.empty:
        return None
    scope = configs[configs["cd"].astype(str).eq(str(cd))].copy()
    if scope.empty:
        return None
    if "ativo" in scope.columns:
        scope = scope[scope["ativo"].fillna(1).astype(int).eq(1)].copy()
    scope = scope[scope["indicador"].astype(str).ne("__CABECALHO__")].copy()
    req = [_formula_key(t) for t in required_terms if str(t or "").strip()]
    avoid = [_formula_key(t) for t in avoid_terms if str(t or "").strip()]
    best_idx = None
    best_score = -1
    for idx, r in scope.iterrows():
        text = _formula_key(" ".join(str(r.get(c) or "") for c in ["grupo", "indicador", "codigo_indicador"]))
        score = 0
        for term in req:
            if term in text:
                score += 20 + len(term)
        for term in avoid:
            if term in text:
                score -= 25
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_idx is not None and best_score > 0:
        return scope.loc[best_idx]
    return None


def _north_metric_html(label: str, value: str, sub: str = "", status_class: str = "none", tooltip: str = "") -> str:
    top_color = {
        "ok": "#22c55e",
        "warn": "#f5b301",
        "bad": "#e11d48",
        "none": BR_ORANGE,
    }.get(status_class, BR_ORANGE)
    tooltip = str(tooltip or "").strip()
    title_attr = ""
    alert_html = ""
    cursor_style = "default"
    if tooltip:
        safe_tooltip = html.escape(tooltip, quote=True).replace(chr(10), "&#10;")
        title_attr = f' title="{safe_tooltip}" tabindex="0"'
        cursor_style = "help"
        alert_html = (
            '<span style="position:absolute; top:10px; right:12px; font-size:.92rem; line-height:1; '
            'color:#f59e0b; filter:drop-shadow(0 1px 1px rgba(0,0,0,.12));" '
            'aria-label="Informação complementar">⚠</span>'
        )
    return f"""
    <div{title_attr} style="position:relative; border:1px solid rgba(246,134,32,.20); border-top:4px solid {top_color}; border-radius:18px; padding:14px 16px; min-height:118px; background:linear-gradient(135deg,#ffffff 0%, #fff8f1 100%); box-shadow:0 8px 20px rgba(51,51,51,.045); cursor:{cursor_style};">
      {alert_html}
      <div style="font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; color:#7a7a7a; font-weight:850; min-height:2rem; padding-right:1.3rem;">{html.escape(str(label))}</div>
      <div style="font-size:1.35rem; color:{BR_DARK}; font-weight:900; margin:.35rem 0 .2rem 0; line-height:1.15;">{html.escape(str(value))}</div>
      <div style="font-size:.80rem; color:#6b7280;">{html.escape(str(sub or ''))}</div>
    </div>
    """


def _objective_metric_payload(
    label: str,
    objective: Optional[dict],
    actual_row: Optional[pd.Series],
    configs: pd.DataFrame,
    vals: pd.DataFrame,
    cd: str,
    ref_day: date,
    actual_label: str,
    default_format: str,
    runtime_cache: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    if objective is None:
        return {"label": label, "value": "—", "sub": "Objetivo não cadastrado", "class": "none", "tooltip": ""}
    objetivo = float(objective.get("valor_objetivo") or 0)
    formato = default_format
    indicador = str(objective.get("indicador") or label)
    actual_value = None
    if actual_row is not None:
        formato = str(actual_row.get("formato") or formato)
        indicador = str(actual_row.get("indicador") or indicador)
        month_start = date(ref_day.year, ref_day.month, 1)
        agg = dashboard_aggregation_mode(actual_row, "auto_month")
        actual_value = dashboard_value_matrix_rule(vals, configs, cd, actual_row, month_start.isoformat(), ref_day.isoformat(), agg, runtime_cache=runtime_cache)
    actual = 0.0 if actual_value is None or pd.isna(actual_value) else float(actual_value)
    progress = actual / objetivo if abs(objetivo) > 1e-12 else None

    direcao = str(objective.get("direcao_meta") or "maior_melhor")
    tol = float(objective.get("tolerancia_amarela") or 0.05)
    last_fill = latest_filled_date_from_values(vals, ref_day) or ref_day
    if last_fill.year != ref_day.year or last_fill.month != ref_day.month:
        last_fill = ref_day
    total_days = max(total_working_days_in_month(cd, ref_day), 1)
    done_days = max(elapsed_working_days_in_month(cd, min(last_fill, ref_day)), 1)
    remaining_days = max(total_days - done_days, 0)

    if progress is None:
        emoji, status_class = "", "none"
    elif direcao == "menor_melhor":
        avg_done = actual / done_days if done_days > 0 else None
        saldo_permitido = max(objetivo - actual, 0.0)
        avg_allowed = (saldo_permitido / remaining_days) if remaining_days > 0 else (0.0 if actual <= objetivo else -1.0)
        if actual <= objetivo and (remaining_days == 0 or avg_done is None or avg_done <= avg_allowed * (1 + tol)):
            emoji, status_class = "🟢", "ok"
        elif actual <= objetivo:
            emoji, status_class = "🟡", "warn"
        else:
            emoji, status_class = "🔴", "bad"
    else:
        avg_done = actual / done_days if done_days > 0 else None
        saldo = max(objetivo - actual, 0.0)
        avg_needed = (saldo / remaining_days) if remaining_days > 0 else (0.0 if actual >= objetivo else None)
        if actual >= objetivo:
            emoji, status_class = "🟢", "ok"
        elif avg_done is not None and avg_needed is not None and avg_needed <= avg_done:
            emoji, status_class = "🟢", "ok"
        elif avg_done is not None and avg_needed is not None and avg_needed <= avg_done * (1 + tol):
            emoji, status_class = "🟡", "warn"
        else:
            emoji, status_class = "🔴", "bad"

    obj_txt = format_value(objetivo, formato, indicador) or "—"
    if progress is None:
        sub = "Sem referência operacional"
        tooltip = ""
    else:
        sub = f"{actual_label} {format_value(actual, formato, indicador)} · {emoji} {format_value(progress, 'percentual', '% objetivo')}".replace("  ", " ").strip()
        if direcao == "menor_melhor":
            saldo_txt = format_value(max(objetivo - actual, 0.0), formato, indicador) or "—"
            tooltip = (
                f"No CD {cd}, {indicador} está em {format_value(actual, formato, indicador) or '—'} "
                f"de um limite mensal de {format_value(objetivo, formato, indicador) or '—'}. "
                f"Considerando {remaining_days} dias úteis restantes, ainda há saldo permitido de {saldo_txt}."
            )
        else:
            saldo = max(objetivo - actual, 0.0)
            avg_needed = (saldo / remaining_days) if remaining_days > 0 else (0.0 if actual >= objetivo else None)
            tooltip = (
                f"No CD {cd}, você já executou {format_value(actual, formato, indicador) or '—'} "
                f"de {format_value(objetivo, formato, indicador) or '—'} projetado. "
                f"Considerando que faltam {remaining_days} dias úteis até o final do mês, "
                f"você precisa executar em média {format_value(avg_needed, formato, indicador) or '—'}/dia para atingir a meta."
            )
    return {"label": label, "value": obj_txt, "sub": sub, "class": status_class, "tooltip": tooltip}


def dashboard_month_north_metrics_payload(cd: str, configs: pd.DataFrame, vals: pd.DataFrame, ref_day: date, runtime_cache: Optional[dict[str, Any]] = None) -> list[dict[str, str]]:
    total_days = total_working_days_in_month(cd, ref_day)
    last_fill = latest_filled_date_from_values(vals, ref_day)
    done_days = elapsed_working_days_in_month(cd, last_fill) if last_fill and last_fill.month == ref_day.month and last_fill.year == ref_day.year else 0

    fat_obj = _find_monthly_objective_by_terms(cd, ref_day, ["FATURAMENTO"])
    linhas_obj = _find_monthly_objective_by_terms(cd, ref_day, ["LINHAS", "PREVISTAS"])
    fat_actual = _find_indicator_by_terms(configs, cd, ["FATURAMENTO", "REALIZADO"], ["NECESSARIO", "PREVISTO", "PLANEJADO", "META"])
    linhas_actual = _find_indicator_by_terms(configs, cd, ["LINHAS", "PLANEJADAS"], ["PREVISTAS", "NECESSARIO", "META"])
    if linhas_actual is None:
        linhas_actual = _find_indicator_by_terms(configs, cd, ["LINHAS", "PRODUZIDAS"], ["PREVISTAS", "NECESSARIO", "META"])

    return [
        {"label": "Dias úteis do mês", "value": str(int(total_days)), "sub": pd.to_datetime(ref_day).strftime("%m/%Y"), "class": "none", "tooltip": ""},
        {"label": "Dias úteis realizados", "value": str(int(done_days)), "sub": f"Até {last_fill.strftime('%d/%m/%Y')}" if last_fill else "Sem preenchimento no mês", "class": "none", "tooltip": ""},
        _objective_metric_payload("Objetivo de faturamento do mês", fat_obj, fat_actual, configs, vals, cd, ref_day, "Realizado", "moeda", runtime_cache=runtime_cache),
        _objective_metric_payload("Objetivo de linhas previstas do mês", linhas_obj, linhas_actual, configs, vals, cd, ref_day, "Planejado", "numero", runtime_cache=runtime_cache),
    ]


def render_dashboard_month_north_metrics(cd: str, configs: pd.DataFrame, vals: pd.DataFrame, ref_day: date, runtime_cache: Optional[dict[str, Any]] = None) -> None:
    metrics = dashboard_month_north_metrics_payload(cd, configs, vals, ref_day, runtime_cache=runtime_cache)

    st.markdown("### Norteadores do mês")
    cols = st.columns(4, gap="medium")
    for col, item in zip(cols, metrics):
        with col:
            st.markdown(_north_metric_html(item["label"], item["value"], item.get("sub", ""), item.get("class", "none"), item.get("tooltip", "")), unsafe_allow_html=True)


def save_dashboard_card_display_flags(edited: pd.DataFrame, original: pd.DataFrame, motivo: str, user: str) -> int:
    if edited is None or edited.empty:
        return 0
    if not str(motivo or "").strip():
        raise ValueError("Informe o motivo para salvar a exibição dos cards.")
    orig = original.set_index("id") if original is not None and not original.empty else pd.DataFrame()
    conn = get_conn()
    now = now_iso()
    changes = 0
    fields = ["exibir_dashboard_dia", "exibir_dashboard_mes", "exibir_referencia_card"]
    try:
        for _, row in edited.iterrows():
            rid = int(row["id"])
            if rid not in orig.index:
                continue
            old = orig.loc[rid]
            updates = {}
            for field in fields:
                new_val = int(bool(row.get(field)))
                old_val = int(old.get(field) if field in old.index and pd.notna(old.get(field)) else 1)
                if new_val != old_val:
                    updates[field] = new_val
            if not updates:
                continue
            set_clause = ", ".join([f"{c}=?" for c in updates] + ["updated_by=?", "updated_at=?"])
            params = list(updates.values()) + [user, now, rid]
            conn.execute(f"UPDATE indicator_config SET {set_clause} WHERE id=?", params)
            for field, new_val in updates.items():
                conn.execute(
                    "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("indicator_config", old["cd"], old["grupo"], old["indicador"], field, str(old.get(field, "")), str(new_val), str(motivo).strip(), user, now),
                )
                changes += 1
        conn.commit()
    finally:
        conn.close()
    return changes


def build_card_reference_editor_df(cards_df: pd.DataFrame, configs: pd.DataFrame, cd: str) -> tuple[pd.DataFrame, list[str], dict[str, tuple[str, str]]]:
    if cards_df is None or cards_df.empty or configs is None or configs.empty:
        return pd.DataFrame(), [], {}
    candidates = configs[configs["cd"].astype(str).eq(str(cd))].copy()
    if "ativo" in candidates.columns:
        candidates = candidates[candidates["ativo"].fillna(1).astype(int).eq(1)].copy()
    candidates = candidates[candidates["indicador"].astype(str).ne("__CABECALHO__")].copy()
    candidates = candidates.sort_values(["grupo_ordem", "grupo", "indicador_ordem", "indicador"], kind="stable")
    ref_options = [""]
    ref_map: dict[str, tuple[str, str]] = {}
    for _, r in candidates.iterrows():
        label = f"{r['grupo']} · {dashboard_card_title(r)}"
        code = str(r.get("codigo_indicador") or "").strip()
        if code:
            label = f"{label} · {code}"
        # Mantém rótulos únicos sem perder legibilidade.
        if label in ref_map:
            label = f"{label} · ID {int(r['id'])}"
        ref_options.append(label)
        ref_map[label] = (str(r["grupo"]), str(r["indicador"]))

    rows = []
    for _, r in cards_df.iterrows():
        current = ""
        cg = str(r.get("card_ref_grupo") or r.get("total_mes_ref_grupo") or "").strip()
        ci = str(r.get("card_ref_indicador") or r.get("total_mes_ref_indicador") or "").strip()
        if cg and ci:
            for label, pair in ref_map.items():
                if pair == (cg, ci):
                    current = label
                    break
        rows.append({
            "id": int(r["id"]),
            "grupo": str(r.get("grupo") or ""),
            "indicador": str(r.get("indicador") or ""),
            "card": dashboard_card_title(r),
            "referencia_card": current,
        })
    return pd.DataFrame(rows), ref_options, ref_map


def save_dashboard_card_references(edited: pd.DataFrame, original: pd.DataFrame, ref_map: dict[str, tuple[str, str]], motivo: str, user: str) -> int:
    if edited is None or edited.empty:
        return 0
    if not str(motivo or "").strip():
        raise ValueError("Informe o motivo para salvar o comparativo dos cards.")
    orig = original.set_index("id") if original is not None and not original.empty else pd.DataFrame()
    conn = get_conn()
    now = now_iso()
    changes = 0
    try:
        for _, row in edited.iterrows():
            rid = int(row["id"])
            if rid not in orig.index:
                continue
            old = orig.loc[rid]
            label = str(row.get("referencia_card") or "")
            new_grupo, new_ind = ref_map.get(label, (None, None)) if label else (None, None)
            old_label = str(old.get("referencia_card") or "")
            old_grupo, old_ind = ref_map.get(old_label, (None, None)) if old_label else (None, None)
            if (new_grupo or None, new_ind or None) == (old_grupo or None, old_ind or None):
                continue
            conn.execute(
                "UPDATE indicator_config SET card_ref_grupo=?, card_ref_indicador=?, exibir_referencia_card=1, updated_by=?, updated_at=? WHERE id=?",
                (new_grupo, new_ind, user, now, rid),
            )
            conn.execute(
                "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("indicator_config", old["cd"], old["grupo"], old["indicador"], "card_ref", old_label, label, str(motivo).strip(), user, now),
            )
            changes += 1
        conn.commit()
    finally:
        conn.close()
    return changes

def remaining_working_days_in_month(cd: str, ref_day: date) -> int:
    """Conta dias úteis/trabalhados restantes após a data de corte até o fim do mês."""
    end_month = last_day_of_month(ref_day)
    d = ref_day + timedelta(days=1)
    count = 0
    while d <= end_month:
        if is_working_day(cd, d):
            count += 1
        d += timedelta(days=1)
    return count


def elapsed_working_days_in_month(cd: str, ref_day: date) -> int:
    """Conta dias trabalhados já corridos no mês, incluindo a data de referência quando trabalhada."""
    start_month = date(ref_day.year, ref_day.month, 1)
    return max(len(working_days_between(cd, start_month, ref_day)), 1)


def management_average_status(
    media_necessaria: Optional[float],
    media_realizada: Optional[float],
    objective: dict,
    objetivo_atingido: bool = False,
    limite_ultrapassado: bool = False,
) -> tuple[str, str, str]:
    """Compara a média necessária/restante com a média realizada nos dias úteis já corridos.

    Para metas de produção/faturamento (`maior_melhor`), verde significa que a média
    necessária restante é menor ou igual à média já realizada. Para limites
    (`menor_melhor`), verde significa que a média realizada até agora é menor ou igual
    à média máxima permitida no restante do mês.
    """
    if objetivo_atingido:
        return "🟢", "Ritmo suficiente", "ok"
    if limite_ultrapassado:
        return "🔴", "Limite ultrapassado", "bad"
    if media_necessaria is None or media_realizada is None or pd.isna(media_necessaria) or pd.isna(media_realizada):
        return "", "Sem base de ritmo", "none"

    direcao = str(objective.get("direcao_meta") or "maior_melhor")
    tol = float(objective.get("tolerancia_amarela") or 0.05)
    nec = float(media_necessaria)
    rea = float(media_realizada)

    if direcao == "menor_melhor":
        # Aqui `nec` é a média máxima permitida para o restante do mês.
        if rea <= nec:
            return "🟢", "Ritmo dentro", "ok"
        if nec > 0 and rea <= nec * (1 + tol):
            return "🟡", "Ritmo em atenção", "warn"
        return "🔴", "Ritmo acima do limite", "bad"

    # maior_melhor/igual: a necessidade diária restante precisa caber no ritmo atual.
    if nec <= rea:
        return "🟢", "Ritmo suficiente", "ok"
    if rea > 0 and nec <= rea * (1 + tol):
        return "🟡", "Ritmo em atenção", "warn"
    return "🔴", "Ritmo insuficiente", "bad"


def build_management_summary_df(selected: pd.DataFrame, vals: pd.DataFrame, configs: pd.DataFrame, cd: str, ref_day: date, runtime_cache: Optional[dict[str, Any]] = None) -> pd.DataFrame:
    """Monta a leitura gerencial mensal para cards vinculados a objetivo total do mês.

    Esta leitura não muda o valor dos cards. Ela explica o avanço acumulado contra
    o objetivo mensal total e calcula a média diária necessária nos dias úteis restantes.
    A cor do resumo é baseada no ritmo: média necessária/restante versus média já realizada.
    """
    if selected is None or selected.empty:
        return pd.DataFrame()

    month_start = date(ref_day.year, ref_day.month, 1)
    remaining_days = remaining_working_days_in_month(cd, ref_day)
    elapsed_days = elapsed_working_days_in_month(cd, ref_day)
    rows: list[dict[str, Any]] = []

    for _, r in selected.iterrows():
        if not bool(r.get("exibir_objetivo_mes_dashboard", 0)):
            continue
        objective = monthly_objective_for_card(cd, r, ref_day.isoformat())
        if not objective:
            continue
        objetivo = float(objective.get("valor_objetivo") or 0)
        if abs(objetivo) < 1e-12:
            continue

        agg = dashboard_aggregation_mode(r, "auto_month")
        realizado = dashboard_value_matrix_rule(vals, configs, cd, r, month_start.isoformat(), ref_day.isoformat(), agg, runtime_cache=runtime_cache)
        realizado = 0.0 if realizado is None or pd.isna(realizado) else float(realizado)
        progresso = realizado / objetivo
        emoji_objetivo, status_objetivo, _ = objective_progress_status(progresso, objective)

        formato = str(r.get("formato") or "numero")
        indicador = str(r.get("indicador") or "")
        titulo = dashboard_card_title(r)
        realizado_txt = format_value(realizado, formato, indicador)
        objetivo_txt = format_value(objetivo, formato, indicador)
        progresso_txt = format_value(progresso, "percentual", "% objetivo mensal")
        direcao = str(objective.get("direcao_meta") or r.get("direcao_meta") or "maior_melhor")
        media_realizada = realizado / elapsed_days if elapsed_days > 0 else None
        media_realizada_txt = format_value(media_realizada, formato, indicador) if media_realizada is not None else "—"

        media_referencia = None
        if direcao == "menor_melhor":
            saldo = objetivo - realizado
            saldo_txt = format_value(saldo, formato, indicador)
            media_referencia = max(saldo, 0.0) / remaining_days if remaining_days > 0 else None
            media_txt = format_value(media_referencia, formato, indicador) if media_referencia is not None else "—"
            emoji_media, status_media, status_class = management_average_status(
                media_referencia,
                media_realizada,
                objective,
                limite_ultrapassado=saldo < 0,
            )
            if saldo >= 0:
                leitura = (
                    f"No CD {cd}, {titulo} consumiu {realizado_txt} de {objetivo_txt} do limite mensal. "
                    f"Restam {remaining_days} dia(s) útil(eis); o saldo permitido é {saldo_txt}, média máxima de {media_txt}/dia."
                )
            else:
                leitura = (
                    f"No CD {cd}, {titulo} já ultrapassou o limite mensal em {format_value(abs(saldo), formato, indicador)}. "
                    "A prioridade é conter novas ocorrências e explicar o desvio."
                )
        else:
            falta = objetivo - realizado
            if falta <= 0:
                media_referencia = 0.0
                media_txt = "0"
                emoji_media, status_media, status_class = management_average_status(
                    media_referencia,
                    media_realizada,
                    objective,
                    objetivo_atingido=True,
                )
                leitura = (
                    f"No CD {cd}, {titulo} já atingiu o objetivo mensal: {realizado_txt} de {objetivo_txt}. "
                    f"Excedente atual: {format_value(abs(falta), formato, indicador)}."
                )
            elif remaining_days > 0:
                media_referencia = falta / remaining_days
                media_txt = format_value(media_referencia, formato, indicador)
                emoji_media, status_media, status_class = management_average_status(media_referencia, media_realizada, objective)
                leitura = (
                    f"No CD {cd}, {titulo} está em {realizado_txt} de {objetivo_txt} projetado. "
                    f"Considerando que faltam {remaining_days} dia(s) útil(eis) até o final do mês, "
                    f"é necessário executar em média {media_txt}/dia para atingir a meta."
                )
            else:
                media_txt = "—"
                emoji_media, status_media, status_class = objective_progress_status(progresso, objective)
                leitura = (
                    f"No CD {cd}, {titulo} encerrou o mês em {realizado_txt} de {objetivo_txt}. "
                    f"Diferença contra objetivo: {format_value(falta, formato, indicador)}."
                )

        rows.append({
            "indicador": titulo,
            "status": f"{emoji_objetivo} {status_objetivo}".strip(),
            "status_ritmo": f"{emoji_media} {status_media}".strip(),
            "status_class": status_class,
            "executado": realizado_txt,
            "objetivo_mensal": objetivo_txt,
            "%_objetivo": progresso_txt,
            "dias_uteis_corridos": elapsed_days,
            "dias_uteis_restantes": remaining_days,
            "media_realizada_dia": media_realizada_txt,
            "media_necessaria_dia": media_txt,
            "leitura_gerencial": leitura,
        })

    return pd.DataFrame(rows)


def render_management_summary(selected: pd.DataFrame, vals: pd.DataFrame, configs: pd.DataFrame, cd: str, ref_day: date, runtime_cache: Optional[dict[str, Any]] = None) -> None:
    summary = build_management_summary_df(selected, vals, configs, cd, ref_day, runtime_cache=runtime_cache)
    if summary.empty:
        return

    st.markdown("### Resumo gerencial do mês")
    valid_classes = {"ok", "warn", "bad", "none"}
    for _, r in summary.iterrows():
        status_class = str(r.get("status_class") or "none")
        if status_class not in valid_classes:
            status_class = "none"
        meta = (
            f"Ritmo: {str(r.get('status_ritmo') or '—')} · "
            f"Média realizada: {str(r.get('media_realizada_dia') or '—')}/dia · "
            f"Média necessária/restante: {str(r.get('media_necessaria_dia') or '—')}/dia"
        )
        st.markdown(
            f"""
            <div class='mgmt-summary-card mgmt-summary-{status_class}'>
              <div class='mgmt-summary-title'>
                <span>{html.escape(str(r['indicador']))}</span>
              </div>
              <div class='mgmt-summary-text'>{html.escape(str(r['leitura_gerencial']))}</div>
              <div class='mgmt-summary-meta'>{html.escape(meta)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_card(label: str, value: Optional[float], cfgrow: pd.Series, target: Optional[dict]) -> None:
    emoji, status = status_for_value(value, target, cfgrow) if bool(cfgrow["usar_sinaleira"]) else ("", "")
    meta_txt = ""
    if target:
        if bool(target.get("exibir_dashboard")) or bool(cfgrow.get("exibir_dashboard")):
            if bool(target.get("exibir_meta_como_linha")):
                meta_txt = f"Meta: {format_value(target['valor_meta'], cfgrow['formato'], cfgrow['indicador'])} · "
            elif bool(target.get("usar_sinaleira")):
                meta_txt = "Meta interna · "
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{emoji} {format_value(value, cfgrow['formato'], cfgrow['indicador']) or '—'}</div>
          <div class="kpi-sub">{meta_txt}{status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



# ----------------------------- preenchimento diário -----------------------------

def is_working_day(cd: str, day: date) -> bool:
    """Retorna se a data é trabalhada para o CD.

    Regra padrão: segunda a sexta. O calendário cadastrado sobrescreve essa regra.
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT trabalhado FROM work_calendar WHERE cd=? AND data=?",
        (str(cd).upper(), day.isoformat()),
    ).fetchone()
    conn.close()
    if row is not None:
        return bool(int(row["trabalhado"]))
    return day.weekday() < 5


def working_days_between(cd: str, start_day: date, end_day: date) -> list[date]:
    """Dias trabalhados do CD no período em uma consulta única ao calendário."""
    if end_day < start_day:
        return []
    conn = get_conn()
    rows = conn.execute(
        "SELECT data, trabalhado FROM work_calendar WHERE cd=? AND data BETWEEN ? AND ?",
        (str(cd).upper(), start_day.isoformat(), end_day.isoformat()),
    ).fetchall()
    conn.close()
    overrides = {str(r["data"]): bool(int(r["trabalhado"])) for r in rows}
    out: list[date] = []
    for ts in pd.date_range(start_day, end_day, freq="D"):
        d = ts.date()
        worked = overrides.get(d.isoformat(), d.weekday() < 5)
        if worked:
            out.append(d)
    return out


def previous_working_day(cd: str, ref: Optional[date] = None) -> date:
    ref = ref or date.today()
    d = ref - timedelta(days=1)
    for _ in range(90):
        if is_working_day(cd, d):
            return d
        d -= timedelta(days=1)
    return ref - timedelta(days=1)


def required_daily_fields(cd: str) -> pd.DataFrame:
    cfg = load_indicator_config(cd, active_only=False).copy()
    if cfg.empty:
        return cfg
    cfg = cfg[
        (cfg["tipo_campo"].astype(str).eq("dado_diario"))
        & (cfg["ativo"].fillna(0).astype(int).eq(1))
        & (cfg["exibir_painel_matricial"].fillna(0).astype(int).eq(1))
    ].copy()
    if "codigo_indicador" not in cfg.columns:
        cfg["codigo_indicador"] = ""
    cfg = cfg.sort_values(["grupo_ordem", "grupo", "indicador_ordem", "indicador"], kind="stable")
    return cfg


def existing_values_for_day(cd: str, day: date) -> dict[str, Optional[float]]:
    """Retorna valores do dia por codigo_indicador, com fallback por grupo/indicador.

    A tela de preenchimento usa codigo_indicador como chave. Isso garante que o
    valor salvo alimente a mesma linha exibida na matriz, mesmo que o admin altere
    descrições ou reorganize o layout.
    """
    vals = load_values([cd], day.isoformat(), day.isoformat())
    if vals.empty:
        return {}
    cfg = load_indicator_config(cd, active_only=False)
    code_by_pair = {}
    if not cfg.empty and "codigo_indicador" in cfg.columns:
        for _, r in cfg.iterrows():
            code = str(r.get("codigo_indicador") or "").strip()
            if code:
                code_by_pair[(str(r["grupo"]), str(r["indicador"]))] = code
    out: dict[str, Optional[float]] = {}
    for _, r in vals.iterrows():
        val = None if pd.isna(r["valor"]) else float(r["valor"])
        code = str(r.get("codigo_indicador") or "").strip() if "codigo_indicador" in vals.columns else ""
        if not code:
            code = code_by_pair.get((str(r["grupo"]), str(r["indicador"])), "")
        if code:
            out[code] = val
        # fallback técnico para bases antigas sem código
        out[f"{str(r['grupo'])}||{str(r['indicador'])}"] = val
    return out


def parse_required_editor_value(x: Any) -> Optional[float]:
    # Nesta tela, vazio não é permitido. Zero deve ser digitado como 0.
    return parse_number(x)


def render_fill_data_tab() -> None:
    centers = allowed_centers(st.session_state["user"]["username"])
    if not centers:
        st.error("Usuário sem CD habilitado.")
        return

    c1, c2, c3 = st.columns([1.1, 1.1, 2.8])
    with c1:
        cd = st.selectbox("CD", centers, key="fill_cd")
    default_day = previous_working_day(cd)
    with c2:
        work_date = st.date_input("Data de referência", value=default_day, key=f"fill_date_{cd}")
    with c3:
        st.info("Preencha todos os campos. Quando o dado operacional vier em branco, lance 0. Use Tab para avançar rapidamente entre os campos.")

    fields = required_daily_fields(cd)
    if fields.empty:
        st.warning("Não há indicadores ativos classificados como dado_diario para este CD.")
        return

    # Garante código único e explícito para cada linha de input.
    fields = fields.copy()
    fields["codigo_indicador"] = fields["codigo_indicador"].fillna("").astype(str).str.strip()
    missing_code = fields["codigo_indicador"].eq("")
    if missing_code.any():
        fields.loc[missing_code, "codigo_indicador"] = fields[missing_code].apply(
            lambda r: build_indicator_code(int(r.get("grupo_ordem") or 999), int(r.get("indicador_ordem") or 999), str(r.get("indicador") or "indicador")),
            axis=1,
        )

    duplicated = fields[fields["codigo_indicador"].duplicated(keep=False)]
    if not duplicated.empty:
        st.error("Existem códigos duplicados no cadastro. Corrija antes de preencher para evitar salvar dado na linha errada.")
        st.dataframe(duplicated[["cd", "codigo_indicador", "grupo", "indicador"]], use_container_width=True, hide_index=True)
        return

    existing = existing_values_for_day(cd, work_date)
    rows = []
    for _, r in fields.iterrows():
        code = str(r.get("codigo_indicador") or "").strip()
        current = existing.get(code)
        if current is None:
            current = existing.get(f"{str(r['grupo'])}||{str(r['indicador'])}")
        rows.append({
            "id": int(r["id"]),
            "codigo_indicador": code,
            "grupo": str(r["grupo"]),
            "indicador": str(r["indicador"]),
            "formato": str(r.get("formato") or "numero"),
            "valor": "" if current is None else current,
        })
    editor_df = pd.DataFrame(rows)

    total = len(editor_df)
    filled_existing = sum(1 for r in rows if str(r["valor"]).strip() != "")
    st.markdown(f"**Campos obrigatórios:** {total} · **já preenchidos nesta data/CD:** {filled_existing}")

    with st.expander("Conferência técnica dos vínculos código → matriz", expanded=False):
        st.caption("Esta conferência usa codigo_indicador como chave. O valor salvo alimenta a linha da matriz correspondente ao mesmo código.")
        st.dataframe(editor_df[["codigo_indicador", "grupo", "indicador", "formato"]], use_container_width=True, hide_index=True, height=260)

    values_by_code: dict[str, str] = {}
    invalid_format_rows = []
    last_group = None
    for idx, r in editor_df.iterrows():
        if r["grupo"] != last_group:
            st.markdown(f"#### {html.escape(str(r['grupo']))}")
            last_group = r["grupo"]
        c_ind, c_val, c_fmt = st.columns([4.6, 1.35, .85])
        with c_ind:
            indent = "&nbsp;" * (2 * max(0, str(r["indicador"]).count(".") - 1))
            st.markdown(f"<div style='padding-top:0.45rem;font-size:.88rem'>{indent}<b>{html.escape(str(r['indicador']))}</b><br><span style='font-size:.72rem;color:#6b7280'>{html.escape(str(r['codigo_indicador']))}</span></div>", unsafe_allow_html=True)
        key = f"fill_val_{cd}_{work_date.isoformat()}_{r['codigo_indicador']}"
        default_val = "" if pd.isna(r["valor"]) else str(r["valor"]).replace(".", ",")
        if key not in st.session_state:
            st.session_state[key] = default_val
        with c_val:
            val_str = st.text_input("Valor", key=key, label_visibility="collapsed", placeholder="0")
        with c_fmt:
            st.caption(str(r["formato"]))
        values_by_code[str(r["codigo_indicador"])] = val_str

    motivo_default = "Preenchimento diário" if filled_existing == 0 else "Correção/atualização de dado diário"
    motivo = st.text_area("Motivo / observação da gravação", value=motivo_default, key=f"fill_motivo_{cd}_{work_date.isoformat()}")

    salvar = st.button("Salvar dados do CD", type="primary", use_container_width=True, key=f"save_fill_{cd}_{work_date.isoformat()}")
    if salvar:
        if not motivo.strip():
            st.error("Informe o motivo/observação para auditoria.")
            return
        upload_rows = []
        missing = []
        invalid_rows = []
        for _, r in editor_df.iterrows():
            code = str(r["codigo_indicador"])
            raw_val = values_by_code.get(code, "")
            if str(raw_val).strip() == "":
                missing.append({"codigo_indicador": code, "grupo": r["grupo"], "indicador": r["indicador"], "valor": raw_val})
                continue
            parsed = parse_required_editor_value(raw_val)
            if parsed is None:
                invalid_rows.append({"codigo_indicador": code, "grupo": r["grupo"], "indicador": r["indicador"], "valor": raw_val})
                continue
            upload_rows.append({
                "data": work_date.isoformat(),
                "cd": cd,
                "codigo_indicador": code,
                "grupo": r["grupo"],
                "indicador": r["indicador"],
                "valor": parsed,
            })
        if missing:
            st.error(f"Faltam {len(missing)} campo(s) obrigatórios. Preencha com o valor real ou com 0.")
            st.dataframe(pd.DataFrame(missing), use_container_width=True, hide_index=True, height=260)
            return
        if invalid_rows:
            st.error("Há valores inválidos. Use números, vírgula decimal ou 0.")
            st.dataframe(pd.DataFrame(invalid_rows), use_container_width=True, hide_index=True, height=260)
            return
        upload_df = pd.DataFrame(upload_rows)
        batch_id = str(uuid.uuid4())
        ins, upd = upsert_values(upload_df, st.session_state["user"]["username"], f"preenchimento_tela_{cd}_{work_date.isoformat()}", batch_id, motivo)
        st.success(f"Dados salvos. Inseridos: {ins}. Atualizados: {upd}. Data: {work_date.isoformat()} · CD: {cd}")
        st.rerun()

def render_calendar_tab() -> None:
    if not (has_perm("manage_centers") or has_perm("edit_data") or st.session_state.get("user", {}).get("role") == "admin"):
        st.error("Sem permissão para configurar calendário de trabalho.")
        return
    centers = allowed_centers(st.session_state["user"]["username"])
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        cd = st.selectbox("CD do calendário", centers, key="cal_cd")
    today = date.today()
    with c2:
        inicio = st.date_input("Início", value=today.replace(day=1), key="cal_start")
    with c3:
        fim = st.date_input("Fim", value=(today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1), key="cal_end")
    if fim < inicio:
        st.error("Fim menor que início.")
        return
    dates = pd.date_range(inicio, fim, freq="D")
    conn = get_conn()
    current = pd.read_sql_query("SELECT data, trabalhado, observacao FROM work_calendar WHERE cd=? AND data BETWEEN ? AND ?", conn, params=(cd, inicio.isoformat(), fim.isoformat()))
    conn.close()
    cur_map = {str(r["data"]): r for _, r in current.iterrows()} if not current.empty else {}
    rows = []
    for d in dates:
        iso = d.date().isoformat()
        row = cur_map.get(iso)
        rows.append({
            "data": iso,
            "dia_semana": ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"][d.weekday()],
            "trabalhado": bool(int(row["trabalhado"])) if row is not None else d.weekday() < 5,
            "observacao": "" if row is None or pd.isna(row.get("observacao")) else str(row.get("observacao")),
        })
    cal_df = pd.DataFrame(rows)
    edited = st.data_editor(
        cal_df,
        use_container_width=True,
        hide_index=True,
        height=min(650, 120 + len(cal_df) * 35),
        disabled=["data", "dia_semana"],
        column_config={"trabalhado": st.column_config.CheckboxColumn("Dia trabalhado")},
        key=f"calendar_editor_{cd}_{inicio}_{fim}",
    )
    motivo = st.text_input("Motivo da alteração do calendário", value="Configuração de calendário operacional", key="cal_motivo")
    if st.button("Salvar calendário do período", type="primary", use_container_width=True):
        if not motivo.strip():
            st.error("Informe o motivo.")
            return
        conn = get_conn()
        now = now_iso()
        user = st.session_state["user"]["username"]
        for _, r in edited.iterrows():
            conn.execute(
                """
                INSERT INTO work_calendar(cd, data, trabalhado, observacao, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cd, data) DO UPDATE SET trabalhado=excluded.trabalhado, observacao=excluded.observacao, updated_by=excluded.updated_by, updated_at=excluded.updated_at
                """,
                (cd, str(r["data"]), int(bool(r["trabalhado"])), str(r.get("observacao") or ""), user, now),
            )
            conn.execute(
                "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("work_calendar", cd, None, None, str(r["data"]), None, f"trabalhado={int(bool(r['trabalhado']))};obs={str(r.get('observacao') or '')}", motivo, user, now),
            )
        conn.commit(); conn.close()
        st.success("Calendário salvo.")
        st.rerun()


def page_fill_data() -> None:
    render_header("Preencher Dados", "Input diário obrigatório por CD, com edição auditada para datas anteriores.")
    render_panel(
        "Nova regra operacional",
        "O planejador preenche os campos obrigatórios diretamente no sistema. Campo vazio bloqueia o salvamento; quando não houver valor, preencha 0. A tela abre no dia trabalhado anterior do CD.",
        ["sem upload em massa", "por CD", "auditável", "chave por código"],
    )
    render_fill_data_tab()


def page_calendar() -> None:
    render_header("Calendário de Trabalho", "Configuração independente de dias trabalhados por CD.")
    render_panel(
        "Calendário operacional por CD",
        "Use esta tela para cadastrar feriados, sábados trabalhados, paradas e exceções. A tela Preencher Dados usa este calendário para sugerir o dia trabalhado anterior.",
        ["por CD", "feriados", "exceções", "auditoria"],
    )
    render_calendar_tab()

def page_dashboard() -> None:
    header_slot = st.empty()
    centers = allowed_centers(st.session_state["user"]["username"])
    if not centers:
        st.warning("Usuário sem CD liberado.")
        return

    username = st.session_state["user"]["username"]

    with st.container(border=True):
        f1, f2 = st.columns([1, 1.65], gap="large")
        with f1:
            cd = center_button_selector("CD", centers, "dashboard_cd_button")
        with header_slot.container():
            render_header("Dashboard Executivo", cd=cd)

        cfg_all = load_indicator_config(cd)
        saved_views = load_dashboard_card_views_for_user(username, cd)

        # A seleção principal do dashboard agora mistura duas naturezas de visão:
        # 1) visões pessoais de cards salvas pelo usuário;
        # 2) visões administrativas de indicadores configuradas pelo admin.
        # Isso evita que o usuário escolha uma visão salva em outro componente e
        # tenha de abrir a configuração para os cards aparecerem.
        option_meta: dict[str, tuple[str, Optional[int]]] = {}
        options: list[str] = []

        if not saved_views.empty:
            for _, r in saved_views.iterrows():
                owner = str(r.get("username") or "")
                is_global = owner == GLOBAL_DASHBOARD_USERNAME
                if is_global:
                    prefix = "⭐ Padrão geral" if int(r.get("is_default", 0) or 0) == 1 else "Todos usuários"
                else:
                    prefix = "⭐ Minha visão" if int(r.get("is_default", 0) or 0) == 1 else "Minha visão"
                label = f"{prefix} · {str(r['nome'])}"
                if label in option_meta:
                    label = f"{label} · {int(r['id'])}"
                options.append(label)
                option_meta[label] = ("saved", int(r["id"]))

        options.append("Indicadores · Todos")
        option_meta["Indicadores · Todos"] = ("indicator", None)

        indicator_views = load_visualization_views("dashboard", cd)
        if not indicator_views.empty:
            for _, r in indicator_views.iterrows():
                nome = str(r.get("nome") or "").strip()
                if not nome or nome.lower() == "todos":
                    continue
                suffix = "" if str(r.get("contexto") or "") == "global" else f" · {str(r.get('contexto')).capitalize()}"
                label = f"Indicadores · {nome}{suffix}"
                if label in option_meta:
                    label = f"{label} · {str(r.get('cd') or '')}"
                options.append(label)
                option_meta[label] = ("indicator", int(r["id"]))

        default_choice = "Indicadores · Todos"
        if not saved_views.empty and "is_default" in saved_views.columns:
            global_default = saved_views[
                saved_views["username"].astype(str).eq(GLOBAL_DASHBOARD_USERNAME)
                & saved_views["is_default"].fillna(0).astype(int).eq(1)
            ]
            personal_default = saved_views[
                saved_views["username"].astype(str).eq(str(username))
                & saved_views["is_default"].fillna(0).astype(int).eq(1)
            ]
            default_rows = global_default if not global_default.empty else personal_default
            if not default_rows.empty:
                default_id = int(default_rows.iloc[0]["id"])
                for label, meta in option_meta.items():
                    if meta == ("saved", default_id):
                        default_choice = label
                        break

        view_key = f"dashboard_main_view_choice_{cd}"
        if st.session_state.get(view_key) not in options:
            st.session_state[view_key] = default_choice

        with f2:
            view_choice = st.selectbox("Visão do dashboard", options, key=view_key)

    dashboard_export_slot = st.empty()

    today = date.today()
    yesterday = previous_working_day(cd, today)
    month_start = today.replace(day=1)

    selected_kind, selected_obj_id = option_meta.get(str(view_choice), ("indicator", None))
    selected_saved_id: int | None = int(selected_obj_id) if selected_kind == "saved" and selected_obj_id is not None else None
    selected_saved_name = ""
    selected_saved_default = False
    selected_saved_owner = username
    selected_saved_is_global = False
    if selected_saved_id is not None and not saved_views.empty:
        saved_match = saved_views[saved_views["id"].astype(int).eq(int(selected_saved_id))]
        if not saved_match.empty:
            selected_saved_name = str(saved_match.iloc[0].get("nome") or "")
            selected_saved_default = bool(int(saved_match.iloc[0].get("is_default", 0) or 0))
            selected_saved_owner = str(saved_match.iloc[0].get("username") or username)
            selected_saved_is_global = selected_saved_owner == GLOBAL_DASHBOARD_USERNAME

    view_id = int(selected_obj_id) if selected_kind == "indicator" and selected_obj_id is not None else None
    cfg_view = cfg_all.copy() if selected_saved_id is not None else apply_visualization_view(cfg_all, view_id)

    card_types = ["dado_diario", "calculo", "meta", "parametro"]
    all_candidates = cfg_view[cfg_view["tipo_campo"].isin(card_types)].copy()
    if "ativo" in all_candidates.columns:
        all_candidates = all_candidates[all_candidates["ativo"].fillna(1).astype(int).eq(1)].copy()
    all_candidates = all_candidates.sort_values(["grupo_ordem", "grupo", "indicador_ordem", "indicador"], kind="stable")

    def _card_label(r: pd.Series) -> str:
        code = str(r.get("codigo_indicador") or "").strip()
        titulo = dashboard_card_title(r)
        base = f"{r['grupo']} · {titulo}"
        return f"{base} · {code}" if code else base

    if not all_candidates.empty:
        all_candidates["__card_label"] = all_candidates.apply(_card_label, axis=1)

    default_candidates = all_candidates[all_candidates["exibir_dashboard"].fillna(0).astype(int).eq(1)].copy() if not all_candidates.empty else pd.DataFrame()
    default_labels = default_candidates["__card_label"].tolist() if not default_candidates.empty else []
    if not default_labels and not all_candidates.empty:
        default_labels = all_candidates["__card_label"].head(8).tolist()

    selected_labels: list[str] = []
    if selected_saved_id is not None:
        saved_items = load_dashboard_card_view_items(selected_saved_id)
        loaded_saved_labels = dashboard_labels_from_saved_items(saved_items, all_candidates)
        edit_key = f"dashboard_edit_saved_cards_{selected_saved_id}"
        if edit_key in st.session_state:
            selected_labels = [x for x in st.session_state.get(edit_key, []) if x in set(all_candidates.get("__card_label", pd.Series(dtype=str)).tolist())]
        else:
            selected_labels = loaded_saved_labels
    else:
        mode_key = f"dashboard_card_mode_{cd}_{view_id or 'todos'}"
        card_mode = st.session_state.get(mode_key, "Padrão da visão")
        if card_mode not in ["Padrão da visão", "Todos os cards da visão", "Selecionar manualmente"]:
            card_mode = "Padrão da visão"
        if card_mode == "Todos os cards da visão" and not all_candidates.empty:
            selected_labels = all_candidates["__card_label"].tolist()
        elif card_mode == "Selecionar manualmente" and not all_candidates.empty:
            manual_key = f"dashboard_cards_session_{cd}_{view_id or 'todos'}"
            selected_labels = st.session_state.get(manual_key, default_labels)
            selected_labels = [x for x in selected_labels if x in set(all_candidates["__card_label"].tolist())]
        else:
            selected_labels = default_labels

    selected = ordered_dashboard_df_from_labels(all_candidates, selected_labels) if not all_candidates.empty else pd.DataFrame()

    vals = load_values([cd], month_start.isoformat(), today.isoformat())
    latest_filled_dashboard = latest_filled_date_from_values(vals, today)
    if latest_filled_dashboard is not None and latest_filled_dashboard >= month_start:
        ref_day_dashboard = latest_filled_dashboard
    else:
        ref_day_dashboard = yesterday if yesterday >= month_start else today
    runtime_cache = build_dashboard_runtime_cache(vals, cfg_all, cd, month_start.isoformat(), today.isoformat())

    if selected.empty:
        st.warning("Nenhum card selecionado para exibição nesta visão.")
    else:
        north_payloads = dashboard_month_north_metrics_payload(cd, cfg_all, vals, ref_day_dashboard, runtime_cache=runtime_cache)
        day_payloads = build_dashboard_card_payloads(
            selected,
            vals,
            cfg_all,
            cd,
            ref_day_dashboard.isoformat(),
            ref_day_dashboard.isoformat(),
            "latest",
            runtime_cache=runtime_cache,
        )
        month_payloads = build_dashboard_card_payloads(
            selected,
            vals,
            cfg_all,
            cd,
            month_start.isoformat(),
            today.isoformat(),
            "auto_month",
            runtime_cache=runtime_cache,
        )
        export_png = _payload_sections_to_png(
            f"Dashboard Executivo - CD {cd}",
            [
                ("Norteadores do mês", north_payloads),
                (f"Resultado de ontem · {br_date_label(ref_day_dashboard.isoformat())}", day_payloads),
                ("Acumulado do mês", month_payloads),
            ],
            subtitle=f"Visão: {view_choice} · Referência: {br_date_label(ref_day_dashboard.isoformat())}",
        )
        with dashboard_export_slot.container():
            render_visual_export_buttons(f"dashboard_export_{cd}_{ref_day_dashboard.isoformat()}", f"dashboard_{cd}_{ref_day_dashboard.isoformat()}", export_png)

        render_dashboard_month_north_metrics(cd, cfg_all, vals, ref_day_dashboard, runtime_cache=runtime_cache)
        render_dashboard_card_grid(
            f"Resultado de ontem · {br_date_label(ref_day_dashboard.isoformat())}",
            selected,
            vals,
            cfg_all,
            cd,
            ref_day_dashboard.isoformat(),
            ref_day_dashboard.isoformat(),
            "latest",
            runtime_cache=runtime_cache,
        )
        render_dashboard_card_grid(
            "Acumulado do mês",
            selected,
            vals,
            cfg_all,
            cd,
            month_start.isoformat(),
            today.isoformat(),
            "auto_month",
            runtime_cache=runtime_cache,
        )
        render_management_summary(selected, vals, cfg_all, cd, ref_day_dashboard, runtime_cache=runtime_cache)

    st.divider()
    with st.expander("Configurar cards da visão", expanded=False):
        if all_candidates.empty:
            st.info("A visão selecionada não possui indicadores disponíveis para cards.")
        else:
            if selected_saved_id is not None:
                st.caption(f"Editando visão salva `{selected_saved_name}` para o CD {cd}.")
                edit_key = f"dashboard_edit_saved_cards_{selected_saved_id}"
                selected_labels = st.multiselect(
                    "Cards desta visão",
                    all_candidates["__card_label"].tolist(),
                    default=selected_labels,
                    key=edit_key,
                )
            else:
                mode_key = f"dashboard_card_mode_{cd}_{view_id or 'todos'}"
                current_mode = st.session_state.get(mode_key, "Padrão da visão")
                if current_mode not in ["Padrão da visão", "Todos os cards da visão", "Selecionar manualmente"]:
                    current_mode = "Padrão da visão"
                card_mode = st.radio(
                    "Modo de exibição dos cards",
                    ["Padrão da visão", "Todos os cards da visão", "Selecionar manualmente"],
                    horizontal=True,
                    key=mode_key,
                    index=["Padrão da visão", "Todos os cards da visão", "Selecionar manualmente"].index(current_mode),
                )
                if card_mode == "Todos os cards da visão":
                    selected_labels = all_candidates["__card_label"].tolist()
                    st.caption(f"Exibindo todos os {len(selected_labels)} cards disponíveis nesta visão.")
                elif card_mode == "Selecionar manualmente":
                    manual_key = f"dashboard_cards_session_{cd}_{view_id or 'todos'}"
                    selected_labels = st.multiselect(
                        "Cards visíveis",
                        all_candidates["__card_label"].tolist(),
                        default=st.session_state.get(manual_key, default_labels),
                        key=manual_key,
                    )
                else:
                    selected_labels = default_labels
                    st.caption("Exibindo os cards marcados como padrão para dashboard nesta visão.")

            selected_labels = render_dashboard_card_order_control(selected_labels, "dashboard")

            if st.session_state.get("user", {}).get("role") == "admin":
                with st.expander("Editar títulos dos cards — admin", expanded=False):
                    st.caption("Altere o título executivo do card. Ao salvar, o novo nome passa a valer para todos os usuários. Deixe em branco para usar o nome original do indicador.")
                    title_cols = ["id", "cd", "grupo", "indicador", "codigo_indicador", "dashboard_titulo"]
                    title_base = all_candidates[[c for c in title_cols if c in all_candidates.columns]].copy()
                    if "dashboard_titulo" not in title_base.columns:
                        title_base["dashboard_titulo"] = ""
                    title_base["dashboard_titulo"] = title_base["dashboard_titulo"].fillna("").astype(str).replace({"nan": ""})
                    title_base = title_base.sort_values(["grupo", "indicador"], kind="stable")
                    edited_titles = st.data_editor(
                        title_base,
                        use_container_width=True,
                        hide_index=True,
                        key="dashboard_card_titles_editor",
                        disabled=["id", "cd", "grupo", "indicador", "codigo_indicador"],
                        column_config={
                            "id": st.column_config.NumberColumn("ID", disabled=True),
                            "cd": st.column_config.TextColumn("CD", disabled=True),
                            "grupo": st.column_config.TextColumn("Grupo", disabled=True),
                            "indicador": st.column_config.TextColumn("Indicador original", disabled=True),
                            "codigo_indicador": st.column_config.TextColumn("Código", disabled=True),
                            "dashboard_titulo": st.column_config.TextColumn("Título do card"),
                        },
                    )
                    if st.button("Salvar títulos dos cards", type="primary", use_container_width=True, key="dashboard_save_card_titles_btn"):
                        qtd = save_dashboard_card_titles(edited_titles, title_base, username)
                        st.success(f"Título(s) atualizado(s): {qtd}. A alteração vale para todos os usuários.")
                        st.rerun()

            selected_preview = ordered_dashboard_df_from_labels(all_candidates, selected_labels)

            can_manage_card_settings = (
                has_perm("configure_indicators")
                or has_perm("configure_targets")
                or st.session_state.get("user", {}).get("role") == "admin"
            )
            if can_manage_card_settings and selected_preview is not None and not selected_preview.empty:
                with st.expander("Exibição dos cards — dia, acumulado e referência", expanded=False):
                    flag_cols = [
                        "id", "cd", "grupo", "indicador", "codigo_indicador",
                        "exibir_dashboard_dia", "exibir_dashboard_mes", "exibir_referencia_card",
                    ]
                    flags_base = selected_preview[[c for c in flag_cols if c in selected_preview.columns]].copy()
                    for col_name in ["exibir_dashboard_dia", "exibir_dashboard_mes", "exibir_referencia_card"]:
                        if col_name not in flags_base.columns:
                            flags_base[col_name] = True
                    edited_flags = st.data_editor(
                        flags_base,
                        use_container_width=True,
                        hide_index=True,
                        key=f"dashboard_card_display_flags_editor_{cd}",
                        disabled=["id", "cd", "grupo", "indicador", "codigo_indicador"],
                        column_config={
                            "id": st.column_config.NumberColumn("ID", width="small", disabled=True),
                            "cd": st.column_config.TextColumn("CD", width="small", disabled=True),
                            "grupo": st.column_config.TextColumn("Grupo", width="medium", disabled=True),
                            "indicador": st.column_config.TextColumn("Card", width="large", disabled=True),
                            "codigo_indicador": st.column_config.TextColumn("Código", width="medium", disabled=True),
                            "exibir_dashboard_dia": st.column_config.CheckboxColumn("Card dia", width="small"),
                            "exibir_dashboard_mes": st.column_config.CheckboxColumn("Card mês", width="small"),
                            "exibir_referencia_card": st.column_config.CheckboxColumn("Mostrar ref.", width="small"),
                        },
                    )
                    motivo_flags = st.text_input(
                        "Motivo para salvar exibição dos cards",
                        value="Ajuste de exibição dos cards do dashboard",
                        key=f"dashboard_card_display_flags_motivo_{cd}",
                    )
                    if st.button("Salvar exibição dos cards", type="primary", use_container_width=True, key=f"dashboard_card_display_flags_save_{cd}"):
                        try:
                            n = save_dashboard_card_display_flags(edited_flags, flags_base, motivo_flags, username)
                            st.success(f"Exibição dos cards salva: {n} alteração(ões).")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

                with st.expander("Comparativo dos cards — Realizado x Planejado/Necessário", expanded=False):
                    ref_base, ref_options, ref_map = build_card_reference_editor_df(selected_preview, cfg_all, cd)
                    if ref_base.empty:
                        st.info("Selecione ao menos um card para configurar comparativo.")
                    else:
                        edited_refs = st.data_editor(
                            ref_base,
                            use_container_width=True,
                            hide_index=True,
                            key=f"dashboard_card_references_editor_{cd}",
                            disabled=["id", "grupo", "indicador", "card"],
                            column_config={
                                "id": st.column_config.NumberColumn("ID", width="small", disabled=True),
                                "grupo": st.column_config.TextColumn("Grupo", width="medium", disabled=True),
                                "indicador": st.column_config.TextColumn("Indicador original", width="large", disabled=True),
                                "card": st.column_config.TextColumn("Card", width="large", disabled=True),
                                "referencia_card": st.column_config.SelectboxColumn("Linha base planejada/necessária", options=ref_options, width="large"),
                            },
                        )
                        motivo_refs = st.text_input(
                            "Motivo para salvar comparativo dos cards",
                            value="Ajuste de referência dos cards do dashboard",
                            key=f"dashboard_card_references_motivo_{cd}",
                        )
                        if st.button("Salvar comparativo dos cards", type="primary", use_container_width=True, key=f"dashboard_card_references_save_{cd}"):
                            try:
                                n = save_dashboard_card_references(edited_refs, ref_base, ref_map, motivo_refs, username)
                                st.success(f"Comparativo dos cards salvo: {n} alteração(ões).")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

            can_manage_monthly_objectives = (
                has_perm("configure_targets")
                or has_perm("configure_indicators")
                or st.session_state.get("user", {}).get("role") == "admin"
            )
            if can_manage_monthly_objectives:
                with st.expander("Resumo gerencial mensal", expanded=False):
                    st.caption(
                        "Use esta área para vincular indicadores a um objetivo total do mês. "
                        "O card continua exibindo Realizado x Necessário quando houver linha base; "
                        "o objetivo mensal alimenta o Resumo Gerencial com projeção, saldo e média diária necessária."
                    )
                    obj_month = st.date_input(
                        "Mês de referência",
                        value=date.today().replace(day=1),
                        key="dashboard_objective_month_ref",
                    )
                    obj_month_ref = month_ref_iso(obj_month)
                    obj_cards_base = selected_preview.copy() if selected_preview is not None and not selected_preview.empty else pd.DataFrame()
                    if obj_cards_base.empty:
                        st.info("Selecione ao menos um card nesta visão para cadastrar o resumo gerencial mensal.")
                    else:
                        obj_base = build_dashboard_objective_editor_df(obj_cards_base, cd, obj_month_ref)
                        edited_obj = st.data_editor(
                            obj_base,
                            use_container_width=True,
                            hide_index=True,
                            key=f"dashboard_month_objectives_editor_{cd}_{obj_month_ref}",
                            disabled=["id", "cd", "grupo", "indicador", "codigo_indicador", "formato"],
                            column_config={
                                "id": st.column_config.NumberColumn("ID", width="small", disabled=True),
                                "cd": st.column_config.TextColumn("CD", width="small", disabled=True),
                                "grupo": st.column_config.TextColumn("Grupo", width="medium", disabled=True),
                                "indicador": st.column_config.TextColumn("Card / indicador", width="large", disabled=True),
                                "codigo_indicador": st.column_config.TextColumn("Código", width="medium", disabled=True),
                                "formato": st.column_config.TextColumn("Formato", width="small", disabled=True),
                                "usar_objetivo_dashboard": st.column_config.CheckboxColumn("Exibir resumo", width="medium"),
                                "valor_objetivo": st.column_config.NumberColumn("Objetivo mensal", format="%.6f", width="medium"),
                                "direcao_meta": st.column_config.SelectboxColumn("Direção", options=DIRECOES, width="medium"),
                                "tolerancia_amarela": st.column_config.NumberColumn("Tolerância", step=0.01, format="%.4f", width="small"),
                            },
                        )
                        motivo_obj = st.text_input(
                            "Motivo para salvar resumo gerencial",
                            value="Cadastro de objetivo mensal para resumo gerencial",
                            key=f"dashboard_month_objectives_motivo_{cd}_{obj_month_ref}",
                        )
                        if st.button("Salvar resumo gerencial", type="primary", use_container_width=True, key=f"dashboard_month_objectives_save_{cd}_{obj_month_ref}"):
                            try:
                                n = save_dashboard_monthly_objectives(edited_obj, obj_base, obj_month_ref, motivo_obj, username)
                                st.success(f"Resumo gerencial salvo: {n} alteração(ões).")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))

            st.markdown('<div class="dashboard-save-box">', unsafe_allow_html=True)
            s1, s2, s3 = st.columns([1.2, 1.4, .9])
            with s1:
                save_name = st.text_input("Nome da visualização", value=selected_saved_name, placeholder="Ex.: Visão operação diária", key="dashboard_save_view_name")
            with s2:
                save_desc = st.text_input("Descrição", placeholder="Opcional", key="dashboard_save_view_desc")
            with s3:
                save_scope = st.selectbox(
                    "Salvar para",
                    ["CD atual", "Selecionar CDs", "Todos os CDs liberados"],
                    key="dashboard_save_scope",
                )

            is_main_view = st.checkbox(
                "Visão principal",
                value=bool(selected_saved_default),
                key=f"dashboard_main_view_flag_{selected_saved_id or 'new'}",
                help="Quando marcado, esta passa a ser a visão padrão na abertura do dashboard para o CD salvo.",
            )
            global_allowed = can_manage_global_dashboard_view()
            default_owner_label = "Todos os usuários" if selected_saved_is_global else "Somente para mim"
            if default_owner_label == "Todos os usuários" and not global_allowed:
                default_owner_label = "Somente para mim"
            owner_options = ["Somente para mim"] + (["Todos os usuários"] if global_allowed else [])
            owner_scope = st.radio(
                "Escopo da visão",
                owner_options,
                index=owner_options.index(default_owner_label) if default_owner_label in owner_options else 0,
                horizontal=True,
                key=f"dashboard_view_owner_scope_{selected_saved_id or 'new'}",
                help="Use 'Todos os usuários' para criar uma visão geral do CD. Se ela for principal, todos abrem o dashboard nela.",
            )
            save_owner_username = GLOBAL_DASHBOARD_USERNAME if owner_scope == "Todos os usuários" else username

            if save_scope == "Todos os CDs liberados":
                target_cds = list(centers)
                st.caption("A visão será salva para: " + ", ".join(target_cds))
            elif save_scope == "Selecionar CDs":
                target_cds = st.multiselect(
                    "CDs que receberão esta visão",
                    list(centers),
                    default=[cd],
                    key="dashboard_save_target_cds",
                )
            else:
                target_cds = [cd]

            b1, b2 = st.columns(2, gap="medium")
            with b1:
                if selected_saved_id is not None and st.button("Atualizar visão selecionada", type="primary", use_container_width=True, key="dashboard_update_card_view_btn"):
                    try:
                        if selected_saved_is_global and not global_allowed:
                            raise ValueError("Você não tem permissão para editar uma visão geral.")
                        update_owner = selected_saved_owner
                        update_dashboard_card_view(selected_saved_id, update_owner, cd, save_name, selected_preview, save_desc, is_default=is_main_view)
                        st.success("Visão atualizada. A configuração vale para o CD atual.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            with b2:
                if st.button("Salvar como visão", type="secondary" if selected_saved_id is not None else "primary", use_container_width=True, key="dashboard_save_card_view_btn"):
                    try:
                        saved_cds = save_dashboard_card_view_for_cds(save_owner_username, target_cds, save_name, selected_preview, save_desc, is_default=is_main_view)
                        st.success("Visão de cards salva para: " + ", ".join(saved_cds) + ".")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            if not saved_views.empty:
                saved_label_to_meta: dict[str, tuple[int, str, bool]] = {}
                for _, r in saved_views.iterrows():
                    is_global_row = str(r.get("username") or "") == GLOBAL_DASHBOARD_USERNAME
                    label_remove = ("Todos usuários · " if is_global_row else "Minha visão · ") + str(r["nome"])
                    if label_remove in saved_label_to_meta:
                        label_remove = f"{label_remove} · {int(r['id'])}"
                    saved_label_to_meta[label_remove] = (int(r["id"]), str(r.get("username") or username), is_global_row)
                d1, d2 = st.columns([2.6, .9])
                with d1:
                    remove_saved = st.selectbox("Inativar visão salva", [""] + list(saved_label_to_meta.keys()), key="dashboard_remove_saved_view")
                with d2:
                    st.write("")
                    if st.button("Inativar", use_container_width=True, key="dashboard_remove_saved_btn") and remove_saved:
                        remove_id, remove_owner, remove_is_global = saved_label_to_meta[remove_saved]
                        if remove_is_global and not global_allowed:
                            st.error("Você não tem permissão para inativar uma visão geral.")
                        else:
                            inactivate_dashboard_card_view(remove_owner, cd, remove_id)
                            st.success("Visão inativada.")
                            st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    if has_perm("configure_indicators"):
        st.divider()
        render_visualization_admin("dashboard", cd, load_indicator_config(cd, active_only=False), "dashboard_admin")


def page_import() -> None:
    render_header("Importar Dados", "Carga diária por código do indicador, com valores em branco permitidos.")
    render_panel("Regra operacional", "A chave preferencial do upload é codigo_indicador + cd + data. O arquivo não precisa vir na ordem do painel e pode conter valores em branco; esses registros sobem como branco. Metas e cálculos continuam fora da carga diária.", ["codigo_indicador", "valores em branco", "multi-CD", "auditoria"])
    if DADOS_DIARIOS_CSV.exists():
        st.download_button("Baixar modelo diário ajustado", DADOS_DIARIOS_CSV.read_bytes(), DADOS_DIARIOS_CSV.name, "text/csv", use_container_width=True)
    centers = allowed_centers(st.session_state["user"]["username"])
    default_cd = st.selectbox("CD padrão para arquivo sem coluna CD", centers)
    uploaded = st.file_uploader("Suba CSV ou Excel", type=["csv", "xlsx", "xlsm", "xls"])
    motivo = st.text_input("Motivo da importação", value="Carga operacional diária")
    if uploaded:
        try:
            raw = parse_uploaded_file(uploaded, default_cd)
            accepted, rejected = filter_import_by_config(raw, st.session_state["user"]["username"])
            blank_count = int(accepted["valor"].isna().sum()) if not accepted.empty else 0
            st.success(f"Registros aceitos: {len(accepted):,}. Em branco: {blank_count:,}. Rejeitados por classificação/permissão: {len(rejected):,}.".replace(",", "."))
            st.dataframe(accepted.head(300), use_container_width=True, hide_index=True, height=260)
            if not rejected.empty:
                with st.expander("Ver rejeitados", expanded=False):
                    st.dataframe(rejected.head(500), use_container_width=True, hide_index=True)
            if st.button("Confirmar importação", type="primary", use_container_width=True):
                if not motivo.strip():
                    st.error("Informe o motivo.")
                elif accepted.empty:
                    st.error("Nenhum registro aceito para importar.")
                else:
                    batch = str(uuid.uuid4())
                    ins, upd = upsert_values(accepted, st.session_state["user"]["username"], uploaded.name, batch, motivo)
                    st.success(f"Importação concluída. Inseridos: {ins:,}. Atualizados: {upd:,}.".replace(",", "."))
        except Exception as exc:
            st.error(f"Falha na leitura: {exc}")



def render_indicator_config_form(record_id: int, location: str = "page") -> None:
    """Tela resumida de configuração do indicador.

    A versão anterior usava st.form, o que impedia a tela de reagir imediatamente
    quando o usuário alterava o tipo para meta/cálculo. Esta versão usa widgets
    reativos e organiza tudo em quadrantes compactos.
    """
    cfg_all = load_indicator_config(active_only=False)
    selected = cfg_all[cfg_all["id"] == record_id]
    if selected.empty:
        st.error("Indicador não encontrado na tabela de configuração.")
        return
    row = selected.iloc[0]
    # Para configuração de cálculo, a lista precisa ser completa: traz todas as linhas
    # do mesmo CD, inclusive ocultas/inativas, exceto cabeçalhos e a própria linha.
    # Isso evita campos "sumirem" da pesquisa por causa de classificação ou visibilidade.
    same_cd = cfg_all[cfg_all["cd"].astype(str) == str(row["cd"])].copy()
    same_cd = same_cd[same_cd["indicador"].astype(str).ne("__CABECALHO__")].copy()

    def _clean_text(value: object) -> str:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass
        return str(value)

    def _formula_token(c: pd.Series) -> str:
        codigo = _clean_text(c.get("codigo_indicador")).strip()
        # O código é a chave mais estável. Quando não existir, usa ID interno
        # para não colidir com indicadores que tenham o mesmo nome.
        return f"[{codigo or ('ID_' + str(int(c['id'])))}]"

    # Campos disponíveis para cálculo: todos os campos possíveis do mesmo CD.
    formula_candidates = same_cd[same_cd["id"] != record_id].copy()
    formula_label_to_token: dict[str, str] = {}
    token_to_label: dict[str, str] = {}
    for _, c in formula_candidates.sort_values(["grupo_ordem", "indicador_ordem", "grupo", "indicador"], kind="stable").iterrows():
        token = _formula_token(c)
        codigo = _clean_text(c.get("codigo_indicador")).strip() or f"ID_{int(c['id'])}"
        status = "ativo" if int(c.get("ativo") or 0) == 1 else "inativo"
        label = f"{codigo} · {c['grupo']} · {c['indicador']} · {c['tipo_campo']} · {status}"
        formula_label_to_token[label] = token
        token_to_label[token] = label
        # Compatibilidade com fórmulas antigas que usavam [nome do indicador].
        legacy_token = f"[{c['indicador']}]"
        token_to_label.setdefault(legacy_token, label)
    formula_label_options = sorted(formula_label_to_token.keys())

    existing_raw_formula = row.get("formula")
    existing_formula = "" if existing_raw_formula is None or pd.isna(existing_raw_formula) else str(existing_raw_formula)
    existing_tokens = re.findall(r"\[[^\]]+\]", existing_formula)
    existing_labels = []
    for t in existing_tokens:
        if t in token_to_label and token_to_label[t] in formula_label_options:
            existing_labels.append(token_to_label[t])

    # Campos de referência: todos os campos ativos do mesmo CD, exceto o próprio indicador.
    # Para meta/parâmetro, normalmente o usuário escolhe o dado real balizado.
    # Para cálculo com sinaleira, o usuário pode escolher uma linha de meta/parâmetro
    # ou o próprio dado operacional que possui meta cadastrada.
    ref_candidates = same_cd[(same_cd["id"] != record_id) & (same_cd["ativo"] == 1)].copy()
    ref_labels: list[str] = []
    ref_map: dict[str, tuple[str, str, str, str]] = {}
    for _, c in ref_candidates.iterrows():
        label = f"{c['grupo']} · {c['indicador']} ({c['tipo_campo']})"
        ref_labels.append(label)
        ref_map[label] = (str(c["grupo"]), str(c["indicador"]), str(c["formato"]), str(c["tipo_campo"]))
    ref_labels = sorted(ref_labels)
    meta_ref_labels = [lbl for lbl in ref_labels if ref_map[lbl][3] in {"meta", "parametro"}]

    current_ref_label = ""
    # Meta/parâmetro agora é input manual na própria linha. A referência abaixo
    # fica reservada para cálculo com sinaleira, que escolhe qual meta usar.
    if str(row.get("meta_ref_grupo") or "") and str(row.get("meta_ref_indicador") or ""):
        prefix = f"{row['meta_ref_grupo']} · {row['meta_ref_indicador']}"
        for label in ref_labels:
            if label.startswith(prefix + " ("):
                current_ref_label = label
                break
    current_total_ref_label = ""
    if str(row.get("total_mes_ref_grupo") or "") and str(row.get("total_mes_ref_indicador") or ""):
        prefix = f"{row['total_mes_ref_grupo']} · {row['total_mes_ref_indicador']}"
        for label in ref_labels:
            if label.startswith(prefix + " ("):
                current_total_ref_label = label
                break

    atual_meta_ref = current_target(str(row["cd"]), str(row["grupo"]), str(row["indicador"]))

    base_key = f"cfg_{location}_{record_id}"
    current_tipo = str(row.get("tipo_campo") or "dado_diario")

    st.markdown(
        f"""
        <div class='config-box'>
            <div style='font-size:0.78rem;color:#6b7280;font-weight:800;text-transform:uppercase;'>Indicador selecionado</div>
            <div style='font-weight:850;font-size:1.02rem;color:#333;margin-top:2px;'>{row['grupo']}</div>
            <div style='font-size:.94rem;margin-top:3px;'>{row['indicador']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    q1, q2 = st.columns(2)

    with q1:
        with st.container(border=True):
            st.markdown("**1. Classificação**")
            tipo = st.selectbox(
                "Tipo de campo",
                TIPOS_CAMPO,
                index=TIPOS_CAMPO.index(current_tipo) if current_tipo in TIPOS_CAMPO else 0,
                key=f"{base_key}_tipo",
            )
            formato = st.selectbox(
                "Formato",
                FORMATOS,
                index=FORMATOS.index(row["formato"]) if row["formato"] in FORMATOS else 0,
                key=f"{base_key}_formato",
            )
            st.caption("Mudar o tipo atualiza imediatamente os quadrantes de meta ou cálculo.")

    with q2:
        with st.container(border=True):
            st.markdown("**2. Visualização e sinaleira**")
            v1, v2 = st.columns(2)
            with v1:
                ex_mat = st.checkbox("Painel Matricial", value=bool(row["exibir_painel_matricial"]), key=f"{base_key}_ex_mat")
                ex_dash = st.checkbox("Dashboard", value=bool(row["exibir_dashboard"]), key=f"{base_key}_ex_dash")
                ex_meta_linha = st.checkbox("Mostrar meta como linha/valor", value=bool(row["exibir_meta_como_linha"]), key=f"{base_key}_ex_meta")
            with v2:
                sinal = st.checkbox("Usar sinaleira", value=bool(row["usar_sinaleira"]), key=f"{base_key}_sinal")
                direcao = st.selectbox(
                    "Direção",
                    DIRECOES,
                    index=DIRECOES.index(row["direcao_meta"]) if row["direcao_meta"] in DIRECOES else 0,
                    key=f"{base_key}_direcao",
                )
                tol = st.number_input(
                    "Tolerância amarela",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(row["tolerancia_amarela"] or 0.05),
                    step=0.01,
                    key=f"{base_key}_tol",
                )
            st.markdown("---")
            st.markdown("**Resumo mensal da matriz**")
            m1, m2 = st.columns(2)
            with m1:
                ex_total_mes = st.checkbox(
                    "Mostrar Total Mês",
                    value=bool(row.get("exibir_total_mes", 0)),
                    key=f"{base_key}_ex_total_mes",
                    help="Adiciona a coluna Total Mês para esta linha no Painel Diário.",
                )
            with m2:
                ex_atingimento_mes = st.checkbox(
                    "Mostrar % Meta Mês",
                    value=bool(row.get("exibir_atingimento_mes", 0)),
                    key=f"{base_key}_ex_atingimento_mes",
                    help="Compara o total desta linha contra o total mensal de outra linha, por exemplo Realizado ÷ Necessário.",
                )
            total_ref_label = ""
            if ex_atingimento_mes:
                total_ref_label = st.selectbox(
                    "Linha base para % Meta Mês",
                    [""] + ref_labels,
                    index=([""] + ref_labels).index(current_total_ref_label) if current_total_ref_label in ref_labels else 0,
                    key=f"{base_key}_total_ref_label",
                    help="Exemplo: na linha Faturamento Realizado, selecione Faturamento Necessário. O sistema calcula Total Realizado ÷ Total Necessário no período.",
                )
                if total_ref_label:
                    rg, ri, rf, rt = ref_map[total_ref_label]
                    st.caption(f"Base mensal: {rg} · {ri} · {rt} · {rf}")
            else:
                total_ref_label = ""

            st.markdown("---")
            ex_objetivo_mes_dashboard = st.checkbox(
                "Resumo gerencial no Dashboard",
                value=bool(row.get("exibir_objetivo_mes_dashboard", 0)),
                key=f"{base_key}_ex_objetivo_mes_dashboard",
                help="Exibe este indicador no Resumo Gerencial do mês usando um objetivo mensal total cadastrado.",
            )

    q3, q4 = st.columns(2)

    valor_meta_cfg = 0.0
    inicio_meta_cfg = date.today()
    gravar_meta_cfg = False
    ref_label = ""
    calc_meta_mode = "Referenciar campo de meta/parâmetro"
    calc_manual_meta_cfg = 0.0
    calc_manual_inicio_cfg = date.today()
    gravar_calc_manual_meta_cfg = False

    with q3:
        with st.container(border=True):
            if tipo in {"meta", "parametro"}:
                st.markdown("**3. Meta / parâmetro**")
                st.caption("Informe a meta diretamente nesta linha. Ela será tratada como input manual versionado, sem precisar apontar para outro indicador.")
                if atual_meta_ref:
                    st.info(f"Meta vigente: {format_value(atual_meta_ref['valor_meta'], formato, row['indicador'])} desde {atual_meta_ref['data_inicio']}.")
                default_meta = float(atual_meta_ref["valor_meta"]) if atual_meta_ref else 0.0
                default_inicio_meta = pd.to_datetime(atual_meta_ref["data_inicio"]).date() if atual_meta_ref else date.today()
                valor_meta_cfg = st.number_input(
                    "Valor exato da meta/parâmetro",
                    value=default_meta,
                    format="%.6f",
                    key=f"{base_key}_valor_meta",
                )
                inicio_meta_cfg = st.date_input("Início da vigência", value=default_inicio_meta, key=f"{base_key}_inicio_meta")
                gravar_meta_cfg = st.checkbox("Gravar nova versão da meta ao salvar", value=True, key=f"{base_key}_gravar_meta")
            elif tipo == "calculo":
                st.markdown("**3. Meta para sinaleira do cálculo**")
                if not sinal:
                    st.info("Ative **Usar sinaleira** para configurar a meta comparativa deste cálculo.")
                    st.caption("Sem sinaleira, o cálculo é exibido sem comparação visual.")
                else:
                    st.caption("Escolha se este cálculo será comparado contra uma linha de meta já cadastrada ou contra uma meta manual exclusiva desta própria linha.")
                    calc_meta_mode_options = ["Referenciar campo de meta/parâmetro", "Informar meta manual para este cálculo"]
                    own_calc_target = current_target(str(row["cd"]), str(row["grupo"]), str(row["indicador"]))
                    default_mode_idx = 0 if current_ref_label else (1 if own_calc_target else 0)
                    calc_meta_mode = st.radio(
                        "Base da sinaleira",
                        calc_meta_mode_options,
                        index=default_mode_idx,
                        key=f"{base_key}_calc_meta_mode",
                        horizontal=True,
                    )
                    if calc_meta_mode == "Referenciar campo de meta/parâmetro":
                        calc_ref_options = meta_ref_labels
                        if not calc_ref_options:
                            st.warning("Ainda não existe campo classificado como meta/parâmetro neste CD. Crie/classifique uma linha de meta ou use a opção de meta manual.")
                        ref_label = st.selectbox(
                            "Campo meta/parâmetro de referência",
                            [""] + calc_ref_options,
                            index=([""] + calc_ref_options).index(current_ref_label) if current_ref_label in calc_ref_options else 0,
                            key=f"{base_key}_calc_ref_label",
                            disabled=not bool(calc_ref_options),
                        )
                        if ref_label:
                            ref_grupo_preview, ref_ind_preview, ref_formato_preview, ref_tipo_preview = ref_map[ref_label]
                            resolved_meta = current_target(str(row["cd"]), ref_grupo_preview, ref_ind_preview, date.today().isoformat())
                            if resolved_meta:
                                st.info(f"Meta para sinaleira: {format_value(resolved_meta['valor_meta'], row['formato'], row['indicador'])} desde {resolved_meta['data_inicio']}.")
                            else:
                                st.warning("Este campo de meta/parâmetro ainda não possui valor vigente. Preencha a meta manualmente na própria linha de meta.")
                    else:
                        if own_calc_target:
                            st.info(f"Meta manual vigente desta linha: {format_value(own_calc_target['valor_meta'], formato, row['indicador'])} desde {own_calc_target['data_inicio']}.")
                        default_calc_meta = float(own_calc_target["valor_meta"]) if own_calc_target else 0.0
                        default_calc_inicio = pd.to_datetime(own_calc_target["data_inicio"]).date() if own_calc_target else date.today()
                        calc_manual_meta_cfg = st.number_input(
                            "Valor manual da meta para a sinaleira",
                            value=default_calc_meta,
                            format="%.6f",
                            key=f"{base_key}_calc_manual_meta",
                        )
                        if formato == "percentual":
                            st.caption("Para percentual, pode informar 1,00 ou 100 para 100%; 0,99 ou 99 para 99%. O sistema normaliza para comparar a sinaleira.")
                        calc_manual_inicio_cfg = st.date_input(
                            "Início da vigência da meta manual",
                            value=default_calc_inicio,
                            key=f"{base_key}_calc_manual_inicio",
                        )
                        gravar_calc_manual_meta_cfg = st.checkbox(
                            "Gravar/atualizar meta manual ao salvar",
                            value=True,
                            key=f"{base_key}_calc_gravar_manual_meta",
                        )
                        st.caption("Esta meta manual será usada somente como balizador da sinaleira deste cálculo. Ela não precisa aparecer como uma linha separada no painel.")
            else:
                st.markdown("**3. Meta / parâmetro**")
                st.info("Ative quando o Tipo de campo for **meta**, **parametro** ou **calculo com sinaleira**.")
                st.caption("Metas são inputs manuais. Cálculos com sinaleira escolhem uma linha de meta/parâmetro como referência.")

    formula_final_input = ""
    with q4:
        with st.container(border=True):
            st.markdown("**4. Cálculo**")
            if tipo == "calculo":
                st.caption("Selecione campos e gere uma fórmula base. Depois ajuste manualmente se necessário.")
                selected_labels = st.multiselect(
                    "Campos disponíveis",
                    formula_label_options,
                    default=existing_labels,
                    key=f"{base_key}_tokens",
                    placeholder="Pesquise por código, bloco, indicador, tipo ou status",
                )
                selected_tokens = [formula_label_to_token[label] for label in selected_labels if label in formula_label_to_token]
                c_op, c_preview = st.columns([1, 3])
                with c_op:
                    operador = st.selectbox("Operador", ["+", "-", "*", "/"], index=0, key=f"{base_key}_operador")
                formula_sugerida = f" {operador} ".join(selected_tokens)
                with c_preview:
                    st.caption("Prévia")
                    st.code(formula_sugerida or "Selecione campos", language="text")
                usar_sugerida = st.checkbox(
                    "Usar prévia como fórmula final",
                    value=bool(formula_sugerida and not existing_formula),
                    key=f"{base_key}_usar_sugerida",
                )
                formula = st.text_area(
                    "Fórmula final",
                    value=formula_sugerida if (formula_sugerida and not existing_formula) else existing_formula,
                    key=f"{base_key}_formula",
                    height=92,
                )
                formula_final_input = formula_sugerida.strip() if usar_sugerida and formula_sugerida.strip() else formula.strip()
                with st.expander("Diretriz rápida", expanded=False):
                    st.markdown(
                        """
                        - Use `+`, `-`, `*`, `/` e parênteses.
                        - Cada campo deve ficar entre colchetes.
                        - Para percentual, o resultado deve ser decimal: `0,99 = 99%`.
                        - Exemplo: `([Separados] / [Demanda Total])`.
                        """
                    )
            else:
                st.info("Ative quando o Tipo de campo for **calculo**.")
                st.caption("O cálculo usa campos do próprio CD. Fórmulas são auditadas.")

    with st.container(border=True):
        st.markdown("**5. Registro da alteração**")
        motivo = st.text_area(
            "Motivo obrigatório",
            placeholder="Ex.: ajuste de meta, fórmula ou classificação após revisão do modelo.",
            key=f"{base_key}_motivo",
            height=80,
        )
        submitted = st.button("Salvar configuração", type="primary", use_container_width=True, key=f"{base_key}_salvar")

    # Controle de alteração não salva para a configuração inline do Painel Matricial.
    ref_grupo_preview = ref_indicador_preview = None
    if ref_label:
        ref_grupo_preview, ref_indicador_preview, _, _ = ref_map[ref_label]
    total_ref_grupo_preview = total_ref_indicador_preview = None
    if total_ref_label:
        total_ref_grupo_preview, total_ref_indicador_preview, _, _ = ref_map[total_ref_label]
    target_dirty = False
    if tipo in {"meta", "parametro"} and gravar_meta_cfg:
        tgt_now = current_target(str(row["cd"]), str(row["grupo"]), str(row["indicador"]))
        tgt_val = float(tgt_now["valor_meta"]) if tgt_now else 0.0
        tgt_inicio = pd.to_datetime(tgt_now["data_inicio"]).date() if tgt_now else date.today()
        target_dirty = (abs(float(valor_meta_cfg) - tgt_val) > 1e-12) or (inicio_meta_cfg != tgt_inicio)
    if tipo == "calculo" and bool(sinal) and calc_meta_mode == "Informar meta manual para este cálculo" and gravar_calc_manual_meta_cfg:
        tgt_now = current_target(str(row["cd"]), str(row["grupo"]), str(row["indicador"]))
        tgt_val = float(tgt_now["valor_meta"]) if tgt_now else 0.0
        tgt_inicio = pd.to_datetime(tgt_now["data_inicio"]).date() if tgt_now else date.today()
        target_dirty = target_dirty or (abs(float(calc_manual_meta_cfg) - tgt_val) > 1e-12) or (calc_manual_inicio_cfg != tgt_inicio)

    formula_compare = formula_final_input if tipo == "calculo" else None
    row_formula_compare = str(row.get("formula") or "") if str(row.get("tipo_campo") or "") == "calculo" else None
    config_dirty = any([
        str(tipo) != str(row.get("tipo_campo") or ""),
        str(formato) != str(row.get("formato") or ""),
        str(direcao) != str(row.get("direcao_meta") or ""),
        int(bool(ex_mat)) != int(row.get("exibir_painel_matricial") or 0),
        int(bool(ex_dash)) != int(row.get("exibir_dashboard") or 0),
        int(bool(ex_meta_linha)) != int(row.get("exibir_meta_como_linha") or 0),
        int(bool(ex_total_mes)) != int(row.get("exibir_total_mes") or 0),
        int(bool(ex_atingimento_mes)) != int(row.get("exibir_atingimento_mes") or 0),
        int(bool(ex_objetivo_mes_dashboard)) != int(row.get("exibir_objetivo_mes_dashboard") or 0),
        (total_ref_grupo_preview if ex_atingimento_mes else None) != (str(row.get("total_mes_ref_grupo") or "") or None),
        (total_ref_indicador_preview if ex_atingimento_mes else None) != (str(row.get("total_mes_ref_indicador") or "") or None),
        int(bool(sinal)) != int(row.get("usar_sinaleira") or 0),
        abs(float(tol) - float(row.get("tolerancia_amarela") or 0.0)) > 1e-12,
        (formula_compare or "") != (row_formula_compare or ""),
        (ref_grupo_preview if tipo == "calculo" else None) != (str(row.get("meta_ref_grupo") or "") or None),
        (ref_indicador_preview if tipo == "calculo" else None) != (str(row.get("meta_ref_indicador") or "") or None),
        target_dirty,
    ])
    if str(location).startswith("matrix") and st.session_state.get("matrix_config_record_id") == int(record_id):
        st.session_state["matrix_config_dirty"] = bool(config_dirty)
        if config_dirty:
            st.session_state["matrix_config_dirty_record_id"] = int(record_id)
        else:
            st.session_state.pop("matrix_config_dirty_record_id", None)
            if not st.session_state.get("matrix_config_pending_record_id"):
                st.session_state.pop("matrix_config_warning", None)

    if submitted:
        if not motivo.strip():
            st.error("Informe o motivo da alteração.")
            return
        ref_grupo = ref_indicador = None
        if ref_label and not (tipo == "calculo" and bool(sinal) and calc_meta_mode == "Informar meta manual para este cálculo"):
            ref_grupo, ref_indicador, _, _ = ref_map[ref_label]
        if tipo == "calculo" and not formula_final_input:
            st.error("Campo cálculo exige fórmula.")
            return
        if tipo == "calculo" and bool(sinal) and calc_meta_mode == "Referenciar campo de meta/parâmetro" and not ref_label:
            st.error("Campo cálculo com sinaleira exige selecionar o campo meta/parâmetro de referência ou usar meta manual.")
            return
        if tipo == "calculo" and bool(sinal) and calc_meta_mode == "Informar meta manual para este cálculo" and not gravar_calc_manual_meta_cfg and not current_target(str(row["cd"]), str(row["grupo"]), str(row["indicador"])):
            st.error("Para usar meta manual na sinaleira, grave uma meta manual inicial.")
            return
        total_ref_grupo = total_ref_indicador = None
        if ex_atingimento_mes:
            if not total_ref_label:
                st.error("Para mostrar % Meta Mês, selecione a linha base mensal. Exemplo: Faturamento Necessário.")
                return
            total_ref_grupo, total_ref_indicador, _, _ = ref_map[total_ref_label]
        updates = {
            "tipo_campo": tipo,
            "formato": formato,
            "direcao_meta": direcao,
            "exibir_painel_matricial": int(ex_mat),
            "exibir_dashboard": int(ex_dash),
            "exibir_meta_como_linha": int(ex_meta_linha),
            "exibir_total_mes": int(ex_total_mes),
            "exibir_atingimento_mes": int(ex_atingimento_mes),
            "exibir_objetivo_mes_dashboard": int(ex_objetivo_mes_dashboard),
            "total_mes_ref_grupo": total_ref_grupo if ex_atingimento_mes else None,
            "total_mes_ref_indicador": total_ref_indicador if ex_atingimento_mes else None,
            "usar_sinaleira": int(sinal),
            "tolerancia_amarela": float(tol),
            "formula": formula_final_input if tipo == "calculo" else None,
            "meta_ref_grupo": ref_grupo if tipo == "calculo" else None,
            "meta_ref_indicador": ref_indicador if tipo == "calculo" else None,
        }
        user_name = st.session_state["user"]["username"]
        save_indicator_config(record_id, updates, motivo, user_name)
        meta_manual_gravada = False
        if tipo in {"meta", "parametro"} and gravar_meta_cfg:
            create_target_version(
                str(row["cd"]),
                str(row["grupo"]),
                str(row["indicador"]),
                float(valor_meta_cfg),
                direcao,
                inicio_meta_cfg.isoformat(),
                bool(ex_dash),
                bool(ex_mat),
                bool(ex_meta_linha),
                bool(sinal),
                float(tol),
                motivo,
                user_name,
            )
            meta_manual_gravada = True
        if tipo == "calculo" and bool(sinal) and calc_meta_mode == "Informar meta manual para este cálculo" and gravar_calc_manual_meta_cfg:
            create_target_version(
                str(row["cd"]),
                str(row["grupo"]),
                str(row["indicador"]),
                float(calc_manual_meta_cfg),
                direcao,
                calc_manual_inicio_cfg.isoformat(),
                False,
                False,
                False,
                True,
                float(tol),
                motivo,
                user_name,
            )
            meta_manual_gravada = True
        if meta_manual_gravada:
            st.success("Configuração salva. A meta manual foi gravada com vigência e será usada pela matriz/sinaleira conforme a regra da linha.")
        else:
            st.success("Configuração salva e auditada.")
        if str(location).startswith("matrix"):
            st.session_state.pop("matrix_config_record_id", None)
            st.session_state["matrix_config_reset_counter"] = int(st.session_state.get("matrix_config_reset_counter", 0)) + 1
        st.rerun()


def create_manual_indicator(
    cd: str,
    grupo: str,
    indicador: str,
    tipo_campo: str,
    formato: str,
    nivel: int,
    grupo_ordem: int,
    indicador_ordem: int,
    exibir_painel_matricial: bool,
    exibir_dashboard: bool,
    codigo_indicador: str,
    motivo: str,
    user: str,
) -> int:
    if not motivo.strip():
        raise ValueError("Informe o motivo da criação/alteração.")
    grupo = normalize_text(grupo)
    indicador = normalize_text(indicador)
    if not grupo or not indicador:
        raise ValueError("Grupo e indicador são obrigatórios.")
    if tipo_campo not in TIPOS_CAMPO:
        tipo_campo = "dado_diario"
    if formato not in FORMATOS:
        formato = "numero"
    conn = get_conn()
    code_base = codigo_indicador.strip().upper() if codigo_indicador and codigo_indicador.strip() else build_indicator_code(grupo_ordem, indicador_ordem, indicador)
    code = ensure_unique_indicator_code(conn, cd, code_base)
    now = now_iso()
    cur = conn.execute(
        """
        INSERT INTO indicator_config(
            cd, grupo, indicador, codigo_indicador, grupo_ordem, indicador_ordem, nivel,
            tipo_campo, formato, direcao_meta, exibir_painel_matricial, exibir_dashboard,
            exibir_meta_como_linha, usar_sinaleira, tolerancia_amarela, formula,
            meta_ref_grupo, meta_ref_indicador, ativo, updated_by, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0.05, NULL, NULL, NULL, 1, ?, ?)
        """,
        (
            cd, grupo, indicador, code, int(grupo_ordem), int(indicador_ordem), int(nivel),
            tipo_campo, formato, "maior_melhor", int(exibir_painel_matricial), int(exibir_dashboard),
            user, now,
        ),
    )
    new_id = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("indicator_config", cd, grupo, indicador, "criação", None, f"{code} · {tipo_campo}", motivo, user, now),
    )
    conn.commit()
    conn.close()
    return new_id


def next_group_order(cd: str) -> int:
    conn = get_conn()
    row = conn.execute("SELECT COALESCE(MAX(grupo_ordem), 0) + 1 FROM indicator_config WHERE cd=?", (cd,)).fetchone()
    conn.close()
    return int(row[0] or 1)


def next_indicator_order(cd: str, grupo: str) -> int:
    conn = get_conn()
    row = conn.execute("SELECT COALESCE(MAX(indicador_ordem), 0) + 1 FROM indicator_config WHERE cd=? AND grupo=?", (cd, grupo)).fetchone()
    conn.close()
    return int(row[0] or 1)


def update_indicator_layout_rows(edited: pd.DataFrame, original: pd.DataFrame, motivo: str, user: str) -> None:
    if not motivo.strip():
        raise ValueError("Informe o motivo da alteração.")
    editable_cols = ["codigo_indicador", "grupo_ordem", "indicador_ordem", "nivel", "exibir_painel_matricial", "exibir_dashboard", "ativo"]
    orig = original.set_index("id")
    conn = get_conn()
    now = now_iso()
    for _, row in edited.iterrows():
        rid = int(row["id"])
        if rid not in orig.index:
            continue
        old = orig.loc[rid]
        updates = {}
        for col in editable_cols:
            new_val = row[col]
            old_val = old[col]
            if pd.isna(new_val) and pd.isna(old_val):
                continue
            if str(new_val) != str(old_val):
                updates[col] = new_val
        if not updates:
            continue
        if "codigo_indicador" in updates:
            proposed = str(updates["codigo_indicador"] or "").strip().upper()
            updates["codigo_indicador"] = ensure_unique_indicator_code(conn, str(old["cd"]), proposed or build_indicator_code(int(row["grupo_ordem"]), int(row["indicador_ordem"]), str(old["indicador"])), rid)
        set_clause = ", ".join([f"{c}=?" for c in updates] + ["updated_by=?", "updated_at=?"])
        params = list(updates.values()) + [user, now, rid]
        conn.execute(f"UPDATE indicator_config SET {set_clause} WHERE id=?", params)
        for col, new_val in updates.items():
            conn.execute(
                "INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("indicator_config", old["cd"], old["grupo"], old["indicador"], col, str(old[col]), str(new_val), motivo, user, now),
            )
    conn.commit()
    conn.close()




def rename_indicator_group(cds: list[str] | str, old_group: str, new_group: str, motivo: str, user: str) -> int:
    """Renomeia um cabeçalho/bloco propagando o nome para dados, metas e visões.

    O nome do grupo é usado como chave textual em várias tabelas do app. Por isso,
    a alteração precisa ser transacional e atualizar não apenas o catálogo, mas
    também dados já carregados, objetivos mensais, metas e itens de visões salvas.
    """
    if isinstance(cds, str):
        cd_list = [cds]
    else:
        cd_list = [str(cd).strip().upper() for cd in cds if str(cd).strip()]
    cd_list = list(dict.fromkeys(cd_list))
    old_group = normalize_text(old_group)
    new_group = normalize_text(new_group)

    if not cd_list:
        raise ValueError("Selecione ao menos um CD para renomear o grupo.")
    if not old_group:
        raise ValueError("Selecione o grupo atual.")
    if not new_group:
        raise ValueError("Informe o novo nome do grupo.")
    if old_group == new_group:
        raise ValueError("O novo nome é igual ao nome atual.")
    if not str(motivo or "").strip():
        raise ValueError("Informe o motivo para auditoria.")

    conn = get_conn()
    now = now_iso()
    try:
        conn.execute("BEGIN")

        # Validação prévia para evitar colisões no UNIQUE(cd, grupo, indicador).
        for cd in cd_list:
            old_rows = conn.execute(
                "SELECT id, indicador FROM indicator_config WHERE cd=? AND grupo=?",
                (cd, old_group),
            ).fetchall()
            if not old_rows:
                raise ValueError(f"Grupo `{old_group}` não encontrado no CD {cd}.")
            old_indicators = {str(r["indicador"]) for r in old_rows}
            new_rows = conn.execute(
                "SELECT indicador FROM indicator_config WHERE cd=? AND grupo=?",
                (cd, new_group),
            ).fetchall()
            conflicts = sorted(old_indicators.intersection({str(r["indicador"]) for r in new_rows}))
            if conflicts:
                preview = ", ".join(conflicts[:5])
                raise ValueError(
                    f"Não é possível renomear no CD {cd}: já existe indicador com o mesmo nome no grupo de destino. Conflitos: {preview}."
                )

        total_rows = 0
        for cd in cd_list:
            changed = conn.execute(
                "UPDATE indicator_config SET grupo=?, updated_by=?, updated_at=? WHERE cd=? AND grupo=?",
                (new_group, user, now, cd, old_group),
            ).rowcount
            total_rows += int(changed or 0)

            # Referências internas usadas por sinaleira, total mensal e comparativos de card.
            conn.execute(
                "UPDATE indicator_config SET meta_ref_grupo=?, updated_by=?, updated_at=? WHERE cd=? AND meta_ref_grupo=?",
                (new_group, user, now, cd, old_group),
            )
            conn.execute(
                "UPDATE indicator_config SET total_mes_ref_grupo=?, updated_by=?, updated_at=? WHERE cd=? AND total_mes_ref_grupo=?",
                (new_group, user, now, cd, old_group),
            )

            # Tabelas que carregam o grupo como chave textual.
            for table in [
                "values_indicators",
                "target_versions",
                "monthly_objectives",
                "user_card_config",
                "visualization_view_items",
                "dashboard_card_view_items",
            ]:
                try:
                    conn.execute(
                        f"UPDATE {table} SET grupo=? WHERE cd=? AND grupo=?",
                        (new_group, cd, old_group),
                    )
                except sqlite3.OperationalError:
                    # Mantém compatibilidade com bancos antigos ou tabelas opcionais.
                    pass

            conn.execute(
                """
                INSERT INTO config_audit(entidade, cd, grupo, indicador, campo, valor_anterior, valor_novo, motivo, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "indicator_group",
                    cd,
                    old_group,
                    None,
                    "grupo",
                    old_group,
                    new_group,
                    str(motivo).strip(),
                    user,
                    now,
                ),
            )

        conn.commit()
        return total_rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def render_global_indicator_admin_tools() -> None:
    """Ferramenta global no menu lateral para criação/visibilidade de indicadores.

    Fica disponível em todas as telas para usuários com permissão de configurar indicadores.
    """
    if not has_perm("configure_indicators"):
        return
    user_name = st.session_state["user"]["username"]
    centers = allowed_centers(user_name)
    if not centers:
        return
    with st.sidebar.expander("➕ Indicadores", expanded=False):
        mode = st.radio("Ação", ["Adicionar linha", "Adicionar cabeçalho/bloco", "Ocultar/Reexibir"], key="global_ind_mode")
        cd = st.selectbox("CD", centers, key="global_ind_cd")
        cfg_all = load_indicator_config(cd, active_only=False)
        grupos = sorted(cfg_all["grupo"].dropna().unique().tolist()) if not cfg_all.empty else []
        if mode == "Adicionar cabeçalho/bloco":
            with st.form("global_add_group_form"):
                grupo = st.text_input("Nome do novo cabeçalho/bloco")
                ordem = st.number_input("Ordem do cabeçalho", min_value=1, value=next_group_order(cd), step=1)
                codigo = st.text_input("Código interno opcional", placeholder="Ex.: G010_CARTEIRA")
                motivo = st.text_area("Motivo", height=70, placeholder="Ex.: inclusão de novo bloco operacional.")
                if st.form_submit_button("Criar cabeçalho", use_container_width=True):
                    try:
                        # Placeholder oculto: cria o bloco para uso imediato, sem poluir a matriz.
                        create_manual_indicator(cd, grupo, "__CABECALHO__", "parametro", "numero", 0, int(ordem), 0, False, False, codigo or f"G{int(ordem):03d}_HEADER", motivo, user_name)
                        st.success("Cabeçalho/bloco criado. Adicione linhas dentro dele quando necessário.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
        elif mode == "Adicionar linha":
            with st.form("global_add_indicator_form"):
                grupo_sel = st.selectbox("Cabeçalho/bloco", ["<novo>"] + grupos)
                novo_grupo = st.text_input("Novo cabeçalho/bloco", disabled=grupo_sel != "<novo>")
                grupo = novo_grupo if grupo_sel == "<novo>" else grupo_sel
                indicador = st.text_input("Nome da nova linha/indicador")
                parent_options = [""]
                parent_map = {}
                if grupo and not cfg_all.empty:
                    sub = cfg_all[(cfg_all["grupo"] == grupo) & (cfg_all["indicador"] != "__CABECALHO__")].copy()
                    for _, pr in sub.iterrows():
                        label = f"{int(pr['id'])} · {pr['indicador']}"
                        parent_options.append(label)
                        parent_map[label] = pr
                parent = st.selectbox("Item pai/nível superior opcional", parent_options)
                c1, c2 = st.columns(2)
                with c1:
                    tipo = st.selectbox("Tipo", TIPOS_CAMPO, index=0)
                    formato = st.selectbox("Formato", FORMATOS, index=0)
                    vis_mat = st.checkbox("Exibir na matriz", value=True)
                with c2:
                    if parent:
                        pr = parent_map[parent]
                        default_nivel = int(pr["nivel"] or 0) + 1
                        default_grupo_ordem = int(pr["grupo_ordem"] or next_group_order(cd))
                    else:
                        default_nivel = 0
                        default_grupo_ordem = int(cfg_all[cfg_all["grupo"] == grupo]["grupo_ordem"].min()) if grupo and not cfg_all[cfg_all["grupo"] == grupo].empty else next_group_order(cd)
                    nivel = st.number_input("Nível/indentação", min_value=0, max_value=6, value=default_nivel, step=1)
                    grupo_ordem = st.number_input("Ordem do cabeçalho", min_value=1, value=default_grupo_ordem, step=1)
                    indicador_ordem = st.number_input("Ordem da linha", min_value=0, value=next_indicator_order(cd, grupo) if grupo else 1, step=1)
                codigo = st.text_input("Código do indicador", placeholder="Deixe em branco para gerar automaticamente")
                motivo = st.text_area("Motivo", height=70, placeholder="Ex.: inclusão manual de novo indicador operacional.")
                if st.form_submit_button("Adicionar indicador", type="primary", use_container_width=True):
                    try:
                        create_manual_indicator(cd, grupo, indicador, tipo, formato, int(nivel), int(grupo_ordem), int(indicador_ordem), bool(vis_mat), False, codigo, motivo, user_name)
                        st.success("Indicador criado.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
        else:
            if cfg_all.empty:
                st.info("Não há indicadores neste CD.")
            else:
                labels = cfg_all.apply(lambda r: f"{int(r['id'])} · {r['codigo_indicador'] or 'SEM_COD'} · {r['grupo']} · {r['indicador']}", axis=1).tolist()
                selected = st.selectbox("Linha", labels, key="global_vis_row")
                rid = int(selected.split(" · ")[0])
                row = cfg_all[cfg_all["id"].eq(rid)].iloc[0]
                with st.form("global_visibility_form"):
                    vis_mat = st.checkbox("Exibir no Painel Matricial", value=bool(row["exibir_painel_matricial"]))
                    vis_dash = st.checkbox("Exibir no Dashboard", value=bool(row["exibir_dashboard"]))
                    ativo = st.checkbox("Ativo / disponível para importação e configuração", value=bool(row["ativo"]))
                    ordem = st.number_input("Ordem da linha", min_value=0, value=int(row["indicador_ordem"] or 0), step=1)
                    nivel = st.number_input("Nível/indentação", min_value=0, max_value=6, value=int(row["nivel"] or 0), step=1)
                    motivo = st.text_area("Motivo", height=70, placeholder="Ex.: ocultar linha da visão executiva.")
                    if st.form_submit_button("Salvar visibilidade", use_container_width=True):
                        try:
                            edited = pd.DataFrame([{**row.to_dict(), "exibir_painel_matricial": int(vis_mat), "exibir_dashboard": int(vis_dash), "ativo": int(ativo), "indicador_ordem": int(ordem), "nivel": int(nivel)}])
                            original = pd.DataFrame([row.to_dict()])
                            update_indicator_layout_rows(edited, original, motivo, user_name)
                            st.success("Linha atualizada.")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))


def page_indicators() -> None:
    render_header("Indicadores", "Governança de dado diário, meta, cálculo, ordem, códigos e visibilidade.")
    cfg = load_indicator_config(active_only=False)
    if cfg.empty:
        st.info("Sem indicadores configurados. Use o menu lateral ➕ Indicadores para criar o primeiro registro.")
        return
    cd = st.selectbox("CD", sorted(cfg["cd"].unique()))
    cfg_cd = cfg[cfg["cd"] == cd].copy()
    tabs = st.tabs(["Configurar indicador", "Grupos", "Ordem e visibilidade", "Tabela completa"])

    with tabs[0]:
        label = st.selectbox(
            "Indicador",
            cfg_cd.apply(lambda x: f"{int(x['id'])} · {x.get('codigo_indicador') or 'SEM_COD'} · {x['grupo']} · {x['indicador']}", axis=1).tolist(),
        )
        record_id = int(label.split(" · ")[0])
        render_indicator_config_form(record_id, "indicators")

    with tabs[1]:
        st.info("Renomeie cabeçalhos/blocos sem perder vínculo com dados, metas, objetivos mensais e visões salvas.")
        group_summary = (
            cfg_cd.groupby("grupo", dropna=False)
            .agg(
                ordem=("grupo_ordem", "min"),
                linhas=("indicador", lambda s: int((s.astype(str) != "__CABECALHO__").sum())),
                ativos=("ativo", lambda s: int(pd.Series(s).fillna(0).astype(int).sum())),
            )
            .reset_index()
            .sort_values(["ordem", "grupo"], kind="stable")
        )
        st.dataframe(group_summary, use_container_width=True, hide_index=True, height=min(360, 90 + len(group_summary) * 35))

        group_options = group_summary["grupo"].dropna().astype(str).tolist()
        if not group_options:
            st.warning("Nenhum grupo disponível para renomear.")
        else:
            with st.form("rename_group_form"):
                old_group = st.selectbox("Grupo atual", group_options, key="rename_group_old")
                new_group = st.text_input("Novo nome do grupo", value=old_group, key="rename_group_new")
                matching_cds = sorted(cfg[cfg["grupo"].astype(str).eq(str(old_group))]["cd"].dropna().astype(str).unique().tolist())
                apply_all = st.checkbox(
                    "Aplicar a todos os CDs que usam este mesmo nome de grupo",
                    value=False,
                    help="Use quando o mesmo bloco existe em SBC, RS ou outros CDs e precisa manter a mesma nomenclatura.",
                )
                if apply_all:
                    st.caption("CDs afetados: " + ", ".join(matching_cds))
                motivo_grupo = st.text_area(
                    "Motivo obrigatório",
                    placeholder="Ex.: ajuste de nomenclatura do bloco para padronização executiva.",
                    height=80,
                    key="rename_group_reason",
                )
                submitted_group = st.form_submit_button("Renomear grupo", type="primary", use_container_width=True)
            if submitted_group:
                try:
                    cds_to_update = matching_cds if apply_all else [cd]
                    n = rename_indicator_group(cds_to_update, old_group, new_group, motivo_grupo, st.session_state["user"]["username"])
                    st.success(f"Grupo renomeado. Linhas de catálogo atualizadas: {n}.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tabs[2]:
        st.info("Edite código, ordem, indentação e visibilidade. O código do indicador é a chave preferencial para importação de planilhas.")
        view_cols = ["id", "codigo_indicador", "grupo", "indicador", "grupo_ordem", "indicador_ordem", "nivel", "tipo_campo", "exibir_painel_matricial", "exibir_dashboard", "ativo"]
        editable = cfg_cd[view_cols].copy()
        edited = st.data_editor(
            editable,
            use_container_width=True,
            hide_index=True,
            height=520,
            disabled=["id", "grupo", "indicador", "tipo_campo"],
            column_config={
                "grupo_ordem": st.column_config.NumberColumn("Ordem cabeçalho", min_value=0, step=1),
                "indicador_ordem": st.column_config.NumberColumn("Ordem linha", min_value=0, step=1),
                "nivel": st.column_config.NumberColumn("Nível", min_value=0, max_value=6, step=1),
                "exibir_painel_matricial": st.column_config.CheckboxColumn("Matriz"),
                "exibir_dashboard": st.column_config.CheckboxColumn("Dashboard"),
                "ativo": st.column_config.CheckboxColumn("Ativo"),
            },
            key="indicator_layout_editor",
        )
        motivo = st.text_area("Motivo para aplicar alterações de ordem/visibilidade", placeholder="Ex.: reorganização do painel executivo.", key="indicator_layout_motivo")
        if st.button("Aplicar alterações", type="primary", use_container_width=True):
            try:
                update_indicator_layout_rows(edited, cfg_cd, motivo, st.session_state["user"]["username"])
                ensure_indicator_codes()
                st.success("Ordem, códigos e visibilidade atualizados.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with tabs[3]:
        st.dataframe(cfg_cd, use_container_width=True, hide_index=True, height=520)
        st.download_button(
            "Baixar catálogo com códigos",
            cfg_cd.to_csv(index=False).encode("utf-8-sig"),
            f"catalogo_indicadores_{cd}.csv",
            "text/csv",
            use_container_width=True,
        )


def page_targets() -> None:
    render_header("Metas", "Cadastro interno de metas manuais com vigência, histórico e controle de visibilidade.")
    tabs = st.tabs(["Cadastrar nova meta", "Metas vigentes", "Histórico de metas", "Carga em massa"])
    cfg = load_indicator_config(active_only=True)
    targetable = cfg[cfg["tipo_campo"].isin(["meta", "parametro"])].copy()
    with tabs[0]:
        if targetable.empty:
            st.info("Não há campos classificados como meta/parâmetro. Classifique ou crie uma linha de meta antes de cadastrar valores.")
            return
        st.info("Selecione a própria linha de meta/parâmetro e informe o valor manual. Cálculos com sinaleira poderão usar esta linha como referência.")
        cd = st.selectbox("CD", sorted(targetable["cd"].unique()), key="target_cd")
        sub = targetable[targetable["cd"] == cd].copy()
        target_labels: list[str] = []
        target_map: dict[str, tuple[str, str, pd.Series]] = {}
        for _, r in sub.iterrows():
            label = f"{r['grupo']} · {r['indicador']}"
            target_labels.append(label)
            target_map[label] = (str(r["grupo"]), str(r["indicador"]), r)
        target_label = st.selectbox("Campo de meta/parâmetro", target_labels, key="target_indicator_exact")
        grupo, indicador, cfgrow = target_map[target_label]
        atual = current_target(cd, grupo, indicador)
        if atual:
            st.info(f"Meta atual neste campo: {format_value(atual['valor_meta'], cfgrow['formato'], indicador)} desde {atual['data_inicio']}")
        with st.form("new_target_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                meta = st.number_input("Valor exato da meta", value=float(atual["valor_meta"]) if atual else 0.0, format="%.6f")
                inicio = st.date_input("Vigência inicial", value=date.today())
            with c2:
                direcao = st.selectbox("Direção", DIRECOES, index=DIRECOES.index(atual["direcao_meta"]) if atual and atual["direcao_meta"] in DIRECOES else DIRECOES.index(cfgrow["direcao_meta"]))
                tol = st.number_input("Tolerância amarela", min_value=0.0, max_value=1.0, value=float(atual["tolerancia_amarela"]) if atual else float(cfgrow["tolerancia_amarela"]), step=0.01)
            with c3:
                vis_dash = st.checkbox("Exibir meta no dashboard", value=bool(atual["exibir_dashboard"]) if atual else bool(cfgrow["exibir_dashboard"]))
                vis_mat = st.checkbox("Usar no painel matricial", value=True)
                vis_linha = st.checkbox("Exibir meta como linha/valor", value=bool(atual["exibir_meta_como_linha"]) if atual else bool(cfgrow["exibir_meta_como_linha"]))
                sinal = st.checkbox("Usar como sinaleira", value=True)
            st.caption("Exemplo: crie a linha `Meta Embarque no Prazo`, informe `0,99` e depois use essa linha como referência da sinaleira do cálculo de performance.")
            motivo = st.text_area("Motivo obrigatório", placeholder="Ex.: Nova meta definida para ciclo operacional.")
            submitted = st.form_submit_button("Salvar nova versão de meta", type="primary", use_container_width=True)
        if submitted:
            if not motivo.strip():
                st.error("Informe o motivo.")
            else:
                create_target_version(cd, grupo, indicador, meta, direcao, inicio.isoformat(), vis_dash, vis_mat, vis_linha, sinal, tol, motivo, st.session_state["user"]["username"])
                st.success("Nova meta salva. A versão anterior foi encerrada automaticamente, se existia.")
                st.rerun()
    with tabs[1]:
        hist = load_target_history()
        vig = hist[(hist["ativo"] == 1) & (hist["data_inicio"] <= date.today().isoformat()) & (hist["data_fim"].isna() | (hist["data_fim"] >= date.today().isoformat()))]
        st.dataframe(vig, use_container_width=True, hide_index=True)
    with tabs[2]:
        hist = load_target_history()
        st.dataframe(hist, use_container_width=True, hide_index=True)
        if has_perm("export_reports") and not hist.empty:
            st.download_button("Baixar histórico de metas", hist.to_csv(index=False).encode("utf-8-sig"), "historico_metas.csv", "text/csv", use_container_width=True)
    with tabs[3]:
        st.caption("O Excel deixa de ser a fonte principal. Use apenas para carga inicial ou manutenção em massa.")
        if METAS_AJUSTADAS_CSV.exists():
            st.download_button("Baixar modelo de metas ajustado", METAS_AJUSTADAS_CSV.read_bytes(), METAS_AJUSTADAS_CSV.name, "text/csv", use_container_width=True)

def page_daily() -> None:
    render_header("Visão Dia a Dia", "Consulta detalhada dos dados importados.")
    vals = load_values(allowed_centers(st.session_state["user"]["username"]))
    st.dataframe(vals, use_container_width=True, hide_index=True, height=650)


def page_monthly() -> None:
    render_header("Visão Mensal", "Consolidado mês a mês por indicador, CD e visão executiva.")
    centers = allowed_centers(st.session_state["user"]["username"])
    if not centers:
        st.warning("Usuário sem CD liberado.")
        return
    with st.container(border=True):
        f1, f2 = st.columns([1.15, 1.25], gap="large")
        with f1:
            cd_choice = center_button_selector("CD", centers, "monthly_cd_button", include_all=True)
        cd_for_view = centers[0] if cd_choice == "Todos" else cd_choice
        with f2:
            view_label, view_id = view_selector("mensal", cd_for_view, "monthly_view_selector")
        st.caption("Use Todos para comparar CDs. A visão limita a lista de indicadores disponíveis.")
    selected_cds = centers if cd_choice == "Todos" else [cd_choice]
    vals = load_values(selected_cds)
    if vals.empty:
        st.info("Sem dados.")
        if has_perm("configure_indicators"):
            st.divider()
            render_visualization_admin("mensal", cd_for_view, load_indicator_config(cd_for_view, active_only=False), "monthly_admin")
        return
    cfg_scope = load_indicator_config(cd_for_view)
    cfg_scope = apply_visualization_view(cfg_scope, view_id)
    if cfg_scope.empty:
        st.info(f"A visão `{view_label}` não possui indicadores para o CD selecionado.")
        if has_perm("configure_indicators"):
            st.divider()
            render_visualization_admin("mensal", cd_for_view, load_indicator_config(cd_for_view, active_only=False), "monthly_admin")
        return
    allowed_indicators = cfg_scope["indicador"].dropna().astype(str).unique().tolist()
    vals = vals[vals["indicador"].astype(str).isin(allowed_indicators)].copy()
    if vals.empty:
        st.info("Sem dados carregados para os indicadores desta visão.")
        if has_perm("configure_indicators"):
            st.divider()
            render_visualization_admin("mensal", cd_for_view, load_indicator_config(cd_for_view, active_only=False), "monthly_admin")
        return
    vals["mes"] = pd.to_datetime(vals["data"]).dt.to_period("M").astype(str)
    indicador = st.selectbox("Indicador", sorted(vals["indicador"].unique()), key="monthly_indicator")
    sub = vals[vals["indicador"] == indicador]
    monthly = sub.groupby(["mes", "cd"], as_index=False)["valor"].mean()
    fig = px.bar(monthly, x="mes", y="valor", color="cd", barmode="group", title=indicador, color_discrete_sequence=[BR_ORANGE, BR_DARK, "#7A7A7A"])
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(monthly, use_container_width=True, hide_index=True)

    if has_perm("configure_indicators"):
        st.divider()
        render_visualization_admin("mensal", cd_for_view, load_indicator_config(cd_for_view, active_only=False), "monthly_admin")


def page_edit() -> None:
    render_header("Editar Indicador", "Correção manual de dado diário com motivo obrigatório.")
    vals = load_values(allowed_centers(st.session_state["user"]["username"]))
    if vals.empty:
        st.info("Sem dados.")
        return
    label = st.selectbox("Registro", vals.apply(lambda x: f"{int(x['id'])} · {x['data']} · {x['cd']} · {x['indicador']} · {format_value(x['valor'])}", axis=1).tolist())
    rid = int(label.split(" · ")[0])
    row = vals[vals["id"] == rid].iloc[0]
    with st.form("edit_data"):
        new_val = st.number_input("Novo valor", value=float(row["valor"]), format="%.6f")
        motivo = st.text_area("Motivo obrigatório")
        submitted = st.form_submit_button("Salvar", type="primary", use_container_width=True)
    if submitted:
        if not motivo.strip():
            st.error("Informe o motivo.")
        else:
            conn = get_conn()
            conn.execute("UPDATE values_indicators SET valor=?, updated_by=?, updated_at=? WHERE id=?", (new_val, st.session_state["user"]["username"], now_iso(), rid))
            conn.execute("INSERT INTO audit_changes(data, cd, grupo, indicador, valor_anterior, valor_novo, motivo, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (row["data"], row["cd"], row["grupo"], row["indicador"], row["valor"], new_val, motivo, st.session_state["user"]["username"], now_iso()))
            conn.commit(); conn.close()
            st.success("Alterado e auditado.")
            st.rerun()


def page_centers() -> None:
    render_header("Centros de Distribuição", "Cadastro de CDs.")
    with st.form("center_form"):
        code = st.text_input("Código")
        name = st.text_input("Nome")
        submitted = st.form_submit_button("Salvar", type="primary", use_container_width=True)
    if submitted and code.strip() and name.strip():
        conn = get_conn()
        conn.execute("INSERT INTO centers(code, name, active, created_at, created_by) VALUES (?, ?, 1, ?, ?) ON CONFLICT(code) DO UPDATE SET name=excluded.name, active=1", (code.strip().upper(), name.strip(), now_iso(), st.session_state["user"]["username"]))
        conn.commit(); conn.close()
        seed_permissions()
        st.success("CD salvo.")
    st.dataframe(list_centers(False), use_container_width=True, hide_index=True)


def page_users() -> None:
    render_header("Usuários e Permissões", "Controle de navegação, permissões e escopo por CD.")
    conn = get_conn()
    users = pd.read_sql_query("SELECT username, full_name, role, active, created_at FROM users ORDER BY username", conn)
    centers = list_centers()["code"].tolist()
    conn.close()
    tab1, tab2 = st.tabs(["Usuários", "Permissões"])
    with tab1:
        with st.form("new_user"):
            c1, c2, c3 = st.columns(3)
            with c1:
                username = st.text_input("Usuário")
                full = st.text_input("Nome")
            with c2:
                pwd = st.text_input("Senha", type="password")
                role = st.selectbox("Perfil", ["admin", "gestor", "planejamento", "operacao", "auditoria", "operador"])
            with c3:
                active = st.checkbox("Ativo", value=True)
                user_cds = st.multiselect("CDs", centers, default=centers)
            submitted = st.form_submit_button("Criar/atualizar usuário", type="primary", use_container_width=True)
        if submitted:
            if not username.strip() or not full.strip() or not pwd.strip():
                st.error("Informe usuário, nome e senha.")
            else:
                conn = get_conn()
                conn.execute("INSERT INTO users(username, full_name, password_hash, role, active, created_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(username) DO UPDATE SET full_name=excluded.full_name, password_hash=excluded.password_hash, role=excluded.role, active=excluded.active", (username.strip().lower(), full.strip(), hash_password(pwd), role, int(active), now_iso()))
                for p in PERMISSIONS:
                    default = int(role == "admin" or p.startswith("view_"))
                    conn.execute("INSERT OR IGNORE INTO user_permissions(username, permission, enabled, updated_by, updated_at) VALUES (?, ?, ?, ?, ?)", (username.strip().lower(), p, default, st.session_state["user"]["username"], now_iso()))
                for cd in centers:
                    conn.execute("INSERT INTO user_centers(username, cd, enabled) VALUES (?, ?, ?) ON CONFLICT(username, cd) DO UPDATE SET enabled=excluded.enabled", (username.strip().lower(), cd, int(cd in user_cds)))
                conn.commit(); conn.close()
                st.success("Usuário salvo.")
                st.rerun()
        st.dataframe(users, use_container_width=True, hide_index=True)
    with tab2:
        selected_user = st.selectbox("Usuário para editar permissões", users["username"].tolist())
        conn = get_conn()
        perm_df = pd.read_sql_query("SELECT permission, enabled FROM user_permissions WHERE username=?", conn, params=(selected_user,))
        center_df = pd.read_sql_query("SELECT cd, enabled FROM user_centers WHERE username=?", conn, params=(selected_user,))
        conn.close()
        if perm_df.empty:
            seed_permissions(); st.rerun()
        perm_df["descrição"] = perm_df["permission"].map(PERMISSIONS)
        edited = st.data_editor(perm_df[["permission", "descrição", "enabled"]], use_container_width=True, hide_index=True, disabled=["permission", "descrição"], column_config={"enabled": st.column_config.CheckboxColumn("Liberado")})
        st.subheader("Escopo por CD")
        center_edited = st.data_editor(center_df, use_container_width=True, hide_index=True, disabled=["cd"], column_config={"enabled": st.column_config.CheckboxColumn("Liberado")})
        if st.button("Salvar permissões", type="primary", use_container_width=True):
            conn = get_conn()
            for r in edited.to_dict("records"):
                conn.execute("UPDATE user_permissions SET enabled=?, updated_by=?, updated_at=? WHERE username=? AND permission=?", (int(bool(r["enabled"])), st.session_state["user"]["username"], now_iso(), selected_user, r["permission"]))
            for r in center_edited.to_dict("records"):
                conn.execute("INSERT INTO user_centers(username, cd, enabled) VALUES (?, ?, ?) ON CONFLICT(username, cd) DO UPDATE SET enabled=excluded.enabled", (selected_user, r["cd"], int(bool(r["enabled"]))))
            conn.commit(); conn.close()
            st.success("Permissões salvas.")


def page_audit() -> None:
    render_header("Auditoria", "Histórico de dados, metas, configurações e permissões.")
    conn = get_conn()
    data_audit = pd.read_sql_query("SELECT * FROM audit_changes ORDER BY changed_at DESC LIMIT 1000", conn)
    config_audit = pd.read_sql_query("SELECT * FROM config_audit ORDER BY changed_at DESC LIMIT 1000", conn)
    imports = pd.read_sql_query("SELECT * FROM imports ORDER BY imported_at DESC LIMIT 1000", conn)
    conn.close()
    t1, t2, t3 = st.tabs(["Dados", "Configurações/Metas", "Importações"])
    with t1:
        st.dataframe(data_audit, use_container_width=True, hide_index=True, height=580)
    with t2:
        st.dataframe(config_audit, use_container_width=True, hide_index=True, height=580)
    with t3:
        st.dataframe(imports, use_container_width=True, hide_index=True, height=580)

# ----------------------------- main -----------------------------

def main() -> None:
    init_db()
    if not require_login():
        return
    page = sidebar_nav()
    if page in {"Painel Diário de Indicadores", "Painel Matricial"}:
        page_matrix()
    elif page == "Dashboard Executivo":
        page_dashboard()
    elif page == "Visão Dia a Dia":
        page_daily()
    elif page == "Visão Mensal":
        page_monthly()
    elif page == "Preencher Dados":
        page_fill_data()
    elif page == "Calendário de Trabalho":
        page_calendar()
    elif page == "Indicadores":
        page_indicators()
    elif page == "Metas":
        page_targets()
    elif page == "Usuários e Permissões":
        page_users()
    elif page == "Centros de Distribuição":
        page_centers()
    elif page == "Auditoria":
        page_audit()

if __name__ == "__main__":
    main()
