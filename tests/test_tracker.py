import tempfile
import types
import unittest
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


if __name__ == "__main__":
    unittest.main()
