import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from workpulse import reporter


class ReporterTests(unittest.TestCase):
    def test_today_uses_local_timezone_boundaries(self):
        now = datetime(2026, 4, 1, 9, 30, tzinfo=timezone(timedelta(hours=8)))

        start, end = reporter._get_time_range("today", now=now)

        self.assertEqual(start, "2026-03-31T16:00:00+00:00")
        self.assertEqual(end, "2026-04-01T01:30:00+00:00")

    def test_app_summary_marks_multi_category_apps(self):
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
            rows = [
                ("2026-03-31T16:05:00+00:00", "Chrome", "Docs", "浏览", 0, "macos", 30),
                ("2026-03-31T16:05:30+00:00", "Chrome", "Docs", "浏览", 0, "macos", 30),
                ("2026-03-31T16:06:00+00:00", "Chrome", "YouTube", "娱乐", 0, "macos", 30),
                ("2026-03-31T16:06:30+00:00", "Code", "main.py", "编码", 0, "macos", 15),
            ]
            conn.executemany(
                """
                INSERT INTO activities (timestamp, app_name, window_title, category, is_idle, platform, sample_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            conn.close()

            def fake_get_db():
                db = sqlite3.connect(str(db_path))
                db.row_factory = sqlite3.Row
                return db

            with mock.patch.object(reporter, "get_db", side_effect=fake_get_db):
                output = reporter.generate_report(period="today", fmt="markdown")

            self.assertIn("| Chrome | 1m | 多种(浏览) |", output)
            self.assertIn("| Code | 0m | 编码 |", output)

    def test_report_uses_sample_seconds_instead_of_fixed_poll_interval(self):
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
            conn.executemany(
                """
                INSERT INTO activities (timestamp, app_name, window_title, category, is_idle, platform, sample_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("2026-03-31T16:05:00+00:00", "Code", "a.py", "编码", 0, "macos", 10),
                    ("2026-03-31T16:05:10+00:00", "Code", "a.py", "编码", 0, "macos", 10),
                    ("2026-03-31T16:05:20+00:00", "Code", "a.py", "编码", 0, "macos", 10),
                ],
            )
            conn.commit()
            conn.close()

            def fake_get_db():
                db = sqlite3.connect(str(db_path))
                db.row_factory = sqlite3.Row
                return db

            with mock.patch.object(reporter, "get_db", side_effect=fake_get_db):
                output = reporter.generate_report(period="today", fmt="markdown")

            self.assertIn("- **活跃时间**: 0m", output)
            self.assertIn("| Code | 0m | 编码 |", output)


if __name__ == "__main__":
    unittest.main()
