import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from workpulse import tracker


class TrackerTests(unittest.TestCase):
    def test_is_running_uses_psutil_on_windows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_path = Path(tmpdir) / "workpulse.pid"
            pid_path.write_text("4321", encoding="utf-8")
            fake_psutil = types.SimpleNamespace(pid_exists=lambda pid: pid == 4321)

            with mock.patch.object(tracker, "PID_PATH", pid_path):
                with mock.patch.object(tracker.sys, "platform", "win32"):
                    with mock.patch.dict("sys.modules", {"psutil": fake_psutil}):
                        self.assertTrue(tracker.is_running())

    def test_pause_status_expires_and_cleans_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pause_path = Path(tmpdir) / "pause.json"
            pause_path.write_text(
                '{"paused": true, "until": "2026-04-01T00:00:00+00:00"}',
                encoding="utf-8",
            )

            with mock.patch.object(tracker, "PAUSE_PATH", pause_path):
                status = tracker.get_pause_status(
                    now=datetime(2026, 4, 1, 0, 1, tzinfo=timezone.utc)
                )

            self.assertFalse(status["paused"])
            self.assertFalse(pause_path.exists())

    def test_record_skips_collection_when_paused(self):
        instance = tracker.Tracker()

        with mock.patch.object(tracker, "get_pause_status", return_value={"paused": True, "until": None}):
            with mock.patch.object(instance.platform, "get_active_window") as active_window:
                instance._record()

        active_window.assert_not_called()


if __name__ == "__main__":
    unittest.main()
