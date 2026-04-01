import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from workpulse import tracker


def _init_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    tracker._init_db(conn)
    return conn


class TrackerArchiveTests(unittest.TestCase):
    def test_archive_old_activities_moves_rows_and_records_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "activity.db"
            conn = _init_conn(db_path)
            old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
            new_ts = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
            conn.executemany(
                """
                INSERT INTO activities (timestamp, app_name, window_title, category, is_idle, platform)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (old_ts, "Code", "legacy.py", "编码", 0, "windows"),
                    (new_ts, "Chrome", "Recent", "浏览", 0, "windows"),
                ],
            )
            conn.commit()

            archived = tracker.archive_old_activities(conn=conn)

            self.assertEqual(archived, 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM activities").fetchone()["cnt"],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM activity_archive").fetchone()["cnt"],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS cnt FROM tracker_events WHERE event_type = 'archive_completed'"
                ).fetchone()["cnt"],
                1,
            )
            conn.close()

    def test_recover_previous_session_records_event_for_stale_pid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_path = Path(tmpdir) / "workpulse.pid"
            pid_path.write_text("4321", encoding="utf-8")
            db_path = Path(tmpdir) / "activity.db"

            def fake_get_db():
                return _init_conn(db_path)

            with mock.patch.object(tracker, "PID_PATH", pid_path):
                with mock.patch.object(tracker, "get_db", side_effect=fake_get_db):
                    with mock.patch.object(tracker, "_process_exists", return_value=False):
                        tracker._recover_previous_session()

            conn = _init_conn(db_path)
            event = conn.execute(
                "SELECT event_type, details FROM tracker_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(event["event_type"], "recovered_stale_pid")
            self.assertFalse(pid_path.exists())
            conn.close()


if __name__ == "__main__":
    unittest.main()
