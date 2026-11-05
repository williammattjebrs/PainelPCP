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
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import app as api
import copy_test_db


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

    def test_copy_script_preserves_synthetic_history_without_overwrite(self):
        source = Path(self.tmp.name) / "synthetic_source.db"
        destination = Path(self.tmp.name) / "isolated" / "preview.db"
        conn = sqlite3.connect(source)
        conn.executescript("""
            CREATE TABLE values_indicators(data TEXT, cd TEXT, indicador TEXT, valor REAL);
            INSERT INTO values_indicators VALUES('2025-01-01','SBC','Pedidos',4);
            INSERT INTO values_indicators VALUES('2025-01-02','SBC','Pedidos',9);
            CREATE TABLE audit_changes(id INTEGER PRIMARY KEY, motivo TEXT);
            INSERT INTO audit_changes(motivo) VALUES('amostra');
        """)
        conn.commit()
        conn.close()
        source_info = copy_test_db.snapshot_info(source)
        copied_info = copy_test_db.copy_database(source, destination)
        self.assertEqual(source_info["table_counts"], copied_info["table_counts"])
        self.assertEqual(source_info["values_date_min"], copied_info["values_date_min"])
        self.assertEqual(source_info["values_date_max"], copied_info["values_date_max"])
        self.assertEqual(copied_info["integrity_check"], "ok")
        self.assertTrue(destination.with_suffix(".manifest.json").is_file())
        with self.assertRaises(FileExistsError):
            copy_test_db.copy_database(source, destination)

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
