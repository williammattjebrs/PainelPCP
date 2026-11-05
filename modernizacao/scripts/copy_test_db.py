from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.getenv("PCP_SOURCE_DB", ROOT / "data" / "indicadores.db")).resolve()
DEST = Path(os.getenv("PCP_DB_PATH", ROOT / "modernizacao" / "api" / "runtime" / "indicadores_teste.db")).resolve()
MANIFEST = DEST.with_suffix(".manifest.json")


def snapshot_info(path: Path) -> dict:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        check = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        counts = {table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) for table in tables}
        dates = None
        if "values_indicators" in tables:
            try:
                dates = conn.execute("SELECT MIN(data), MAX(data) FROM values_indicators").fetchone()
            except sqlite3.Error:
                dates = None
        return {
            "integrity_check": check,
            "table_counts": counts,
            "values_date_min": dates[0] if dates else None,
            "values_date_max": dates[1] if dates else None,
            "source_size_bytes": path.stat().st_size,
        }
    finally:
        conn.close()


def main() -> int:
    production = (ROOT / "data" / "indicadores.db").resolve()
    if SOURCE != production:
        print(f"Origem recusada: use o banco versionado esperado em {production}", file=sys.stderr)
        return 2
    if not SOURCE.is_file():
        print(f"Banco de origem não encontrado: {SOURCE}", file=sys.stderr)
        return 2
    if DEST == SOURCE:
        print("Destino não pode ser o banco operacional.", file=sys.stderr)
        return 2
    if DEST.exists():
        print(f"O destino já existe; não será sobrescrito: {DEST}", file=sys.stderr)
        return 2

    DEST.parent.mkdir(parents=True, exist_ok=True)
    temp = DEST.with_suffix(DEST.suffix + ".copying")
    src = sqlite3.connect(f"file:{SOURCE.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(temp)
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()

    info = snapshot_info(temp)
    if info["integrity_check"] != "ok":
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"Cópia reprovada no integrity_check: {info['integrity_check']}")
    temp.replace(DEST)
    info["source"] = str(SOURCE)
    info["created_at"] = __import__("datetime").datetime.now().astimezone().isoformat()
    MANIFEST.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Cópia de teste criada: {DEST}")
    print(f"Manifesto local: {MANIFEST}")
    print(f"Tabelas: {len(info['table_counts'])}; valores: {info['table_counts'].get('values_indicators', 0)}")
    print(f"Período: {info['values_date_min']} a {info['values_date_max']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
