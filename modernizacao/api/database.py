from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def connect(database_path: Path, production_path: Path) -> sqlite3.Connection:
    database_path = database_path.resolve()
    if database_path == production_path.resolve():
        raise RuntimeError("A API de preview não pode abrir o banco operacional.")
    if not database_path.is_file():
        raise RuntimeError(f"Banco de teste ausente: {database_path}")
    conn = sqlite3.connect(str(database_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def transaction(database_path: Path, production_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(database_path, production_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_database(database_path: Path, production_path: Path, required_tables: set[str]) -> dict:
    database_path = database_path.resolve()
    if database_path == production_path.resolve():
        return {"ok": False, "reason": "production_path"}
    if not database_path.is_file():
        return {"ok": False, "reason": "test_database_missing", "path": str(database_path)}
    conn = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        absent = sorted(required_tables - tables)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if absent or integrity != "ok":
            return {"ok": False, "reason": "invalid_database", "missing_tables": absent, "integrity": integrity}
        return {"ok": True, "integrity": integrity, "table_count": len(tables)}
    finally:
        conn.close()
