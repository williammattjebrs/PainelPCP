from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.getenv("PCP_DB_PATH", ROOT / "modernizacao" / "api" / "runtime" / "indicadores_teste.db")).resolve()
MANIFEST = DB.with_suffix(".manifest.json")


def main() -> int:
    if not DB.is_file() or not MANIFEST.is_file():
        raise SystemExit("Banco de teste ou manifesto não encontrado.")
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        counts = {table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) for table in tables}
        dates = conn.execute("SELECT MIN(data), MAX(data) FROM values_indicators").fetchone()
    finally:
        conn.close()
    ok = (
        result == "ok"
        and counts == expected["table_counts"]
        and dates[0] == expected["values_date_min"]
        and dates[1] == expected["values_date_max"]
    )
    print(json.dumps({
        "integrity_check": result,
        "counts_match": counts == expected["table_counts"],
        "date_range_match": dates[0] == expected["values_date_min"] and dates[1] == expected["values_date_max"],
        "status": "ok" if ok else "divergent",
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
