import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workpulse import ai_analyzer, reporter


class AnalyzerTests(unittest.TestCase):
    def test_analyze_period_returns_findings_and_suggestions(self):
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
                    platform TEXT NOT NULL
                )
            """)
            rows = [
                ("2026-03-31T16:00:00+00:00", "Slack", "project-a", "沟通", 0, "windows"),
                ("2026-03-31T16:00:30+00:00", "Chrome", "YouTube", "娱乐", 0, "windows"),
                ("2026-03-31T16:01:00+00:00", "Chrome", "Docs", "浏览", 0, "windows"),
                ("2026-03-31T16:01:30+00:00", "Chrome", "Docs", "浏览", 0, "windows"),
                ("2026-03-31T16:02:00+00:00", "Code", "main.py", "编码", 0, "windows"),
                ("2026-03-31T16:02:30+00:00", "Code", "main.py", "编码", 0, "windows"),
            ]
            conn.executemany(
                """
                INSERT INTO activities (timestamp, app_name, window_title, category, is_idle, platform)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            conn.close()

            def fake_get_db():
                db = sqlite3.connect(str(db_path))
                db.row_factory = sqlite3.Row
                return db

            fake_snapshot = {
                "period": "today",
                "label": "今日",
                "time_range": {
                    "start": "2026-03-31T16:00:00+00:00",
                    "end": "2026-04-01T16:00:00+00:00",
                },
                "total_samples": 6,
                "active_total": 180,
                "idle_time": 0,
                "categories": [
                    {"category": "编码", "seconds": 60, "pct": 33.3},
                    {"category": "浏览", "seconds": 60, "pct": 33.3},
                    {"category": "沟通", "seconds": 30, "pct": 16.7},
                    {"category": "娱乐", "seconds": 30, "pct": 16.7},
                ],
                "apps": [
                    {"app_name": "Chrome", "samples": 3, "category": "多种(浏览)"},
                    {"app_name": "Code", "samples": 2, "category": "编码"},
                    {"app_name": "Slack", "samples": 1, "category": "沟通"},
                ],
                "titles": [
                    {"app_name": "Chrome", "window_title": "Docs", "samples": 2},
                    {"app_name": "Code", "window_title": "main.py", "samples": 2},
                    {"app_name": "Chrome", "window_title": "YouTube", "samples": 1},
                    {"app_name": "Slack", "window_title": "project-a", "samples": 1},
                ],
            }

            with mock.patch.object(reporter, "get_report_snapshot", return_value=fake_snapshot):
                with mock.patch.object(ai_analyzer, "get_report_snapshot", return_value=fake_snapshot):
                    with mock.patch.object(ai_analyzer, "get_db", side_effect=fake_get_db):
                        analysis = ai_analyzer.analyze_period("today")

            self.assertTrue(analysis["findings"])
            self.assertTrue(analysis["suggestions"])
            self.assertIn("跨多个分类", "".join(analysis["findings"]))

    def test_analyze_period_uses_llm_when_requested(self):
        fake_snapshot = {
            "period": "today",
            "label": "今日",
            "time_range": {"start": "a", "end": "b"},
            "total_samples": 1,
            "active_total": 60,
            "idle_time": 0,
            "categories": [{"category": "编码", "seconds": 60, "pct": 100.0}],
            "apps": [{"app_name": "Code", "samples": 2, "seconds": 60, "category": "编码"}],
            "titles": [{"app_name": "Code", "window_title": "main.py", "samples": 2, "seconds": 60}],
        }

        with mock.patch.object(ai_analyzer, "get_report_snapshot", return_value=fake_snapshot):
            with mock.patch.object(ai_analyzer, "_count_context_switches", return_value=0):
                with mock.patch("workpulse.ai_analyzer.llm_is_configured", return_value=True):
                    with mock.patch("workpulse.ai_analyzer.analyze_with_llm", return_value={
                        "summary": "LLM 总结",
                        "findings": ["LLM 观察"],
                        "suggestions": ["LLM 建议"],
                    }):
                        analysis = ai_analyzer.analyze_period("today", provider="llm")

        self.assertEqual(analysis["source"], "llm")
        self.assertEqual(analysis["summary"]["overview"], "LLM 总结")
        self.assertEqual(analysis["findings"], ["LLM 观察"])


if __name__ == "__main__":
    unittest.main()
