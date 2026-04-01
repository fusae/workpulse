import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workpulse import exporter


class ExporterTests(unittest.TestCase):
    def test_export_csv_from_active_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "activity.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("""
                CREATE TABLE activities (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    app_name TEXT NOT NULL,
                    window_title TEXT,
                    category TEXT,
                    is_idle BOOLEAN DEFAULT FALSE,
                    platform TEXT NOT NULL,
                    sample_seconds INTEGER NOT NULL DEFAULT 30
                )
            """)
            conn.execute("""
                INSERT INTO activities (timestamp, app_name, window_title, category, is_idle, platform, sample_seconds)
                VALUES ('2026-03-31T16:05:00+00:00', 'Code', 'main.py', '编码', 0, 'windows', 45)
            """)
            conn.commit()
            conn.close()

            def fake_get_db():
                db = sqlite3.connect(str(db_path))
                db.row_factory = sqlite3.Row
                return db

            with mock.patch.object(exporter, "get_db", side_effect=fake_get_db):
                output = exporter.export_activities(fmt="csv", source="active", start_date="2026-04-01", end_date="2026-04-01")

            self.assertIn("timestamp,app_name,window_title,category,is_idle,platform,sample_seconds", output)
            self.assertIn("Code", output)
            self.assertIn("45", output)


if __name__ == "__main__":
    unittest.main()
