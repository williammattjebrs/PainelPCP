from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("PCP_PASSWORD_SALT", "test-salt")
os.environ.setdefault("PCP_AUTH_SECRET", "test-secret-do-not-use-in-production")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as api


class HistorySafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "preview.db"
        api.DB_PATH = self.db
        api.PRODUCTION_DB = root / "production.db"
        conn = sqlite3.connect(self.db)
        conn.executescript("""
            CREATE TABLE values_indicators(
                id INTEGER PRIMARY KEY, data TEXT, cd TEXT, grupo TEXT, indicador TEXT,
                valor REAL, updated_by TEXT, updated_at TEXT
            );
            CREATE TABLE audit_changes(
                id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, cd TEXT NOT NULL,
                grupo TEXT NOT NULL, indicador TEXT NOT NULL, valor_anterior REAL,
                valor_novo REAL, motivo TEXT NOT NULL, changed_by TEXT NOT NULL, changed_at TEXT NOT NULL
            );
            INSERT INTO values_indicators(id,data,cd,grupo,indicador,valor) VALUES(1,'2026-01-02','SBC','Operação','Pedidos',10);
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_value_correction_keeps_previous_value_in_audit(self):
        actor = {"username": "tester", "role": "admin", "centers": []}
        result = api.correct_value(1, api.CorrectionInput(value=12.5, reason="Correção conferida"), actor)
        conn = sqlite3.connect(self.db)
        current = conn.execute("SELECT valor FROM values_indicators WHERE id=1").fetchone()[0]
        audit = conn.execute("SELECT valor_anterior,valor_novo,motivo,changed_by FROM audit_changes").fetchone()
        conn.close()
        self.assertEqual(result["audited"], True)
        self.assertEqual(current, 12.5)
        self.assertEqual(audit, (10.0, 12.5, "Correção conferida", "tester"))

    def test_preview_refuses_operational_database_path(self):
        api.DB_PATH = api.PRODUCTION_DB
        with self.assertRaises(api.HTTPException) as error:
            api._db()
        self.assertEqual(error.exception.status_code, 503)

    def test_new_password_hash_is_salted_and_verifiable(self):
        stored = api._password_hash("senha-local-forte-123")
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))
        self.assertEqual(api._verify_password(stored, "senha-local-forte-123"), (True, False))
        self.assertEqual(api._verify_password(stored, "senha-incorreta"), (False, False))

    def test_legacy_hash_is_recognized_for_upgrade(self):
        legacy = __import__("hashlib").sha256("test-salt:senha-antiga".encode()).hexdigest()
        self.assertEqual(api._verify_password(legacy, "senha-antiga"), (True, True))


if __name__ == "__main__":
    unittest.main()
