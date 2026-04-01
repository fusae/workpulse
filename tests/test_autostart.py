import plistlib
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from workpulse import autostart


class AutostartTests(unittest.TestCase):
    def test_macos_launch_agent_payload(self):
        payload = autostart._build_launch_agent_payload()
        self.assertEqual(payload["Label"], autostart.MACOS_LABEL)
        self.assertEqual(payload["ProgramArguments"][1:], ["-m", "workpulse.tracker"])

    def test_enable_autostart_writes_launch_agent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plist_path = Path(tmpdir) / "workpulse.plist"

            with mock.patch.object(autostart.sys, "platform", "darwin"):
                with mock.patch.object(autostart, "_launch_agent_path", return_value=plist_path):
                    with mock.patch.object(autostart.subprocess, "run"):
                        autostart.enable_autostart()

            self.assertTrue(plist_path.exists())
            with open(plist_path, "rb") as f:
                payload = plistlib.load(f)
            self.assertEqual(payload["Label"], autostart.MACOS_LABEL)

    def test_windows_status_reads_registry_value(self):
        fake_winreg = types.SimpleNamespace(
            HKEY_CURRENT_USER=object(),
            KEY_READ=object(),
            OpenKey=lambda *args, **kwargs: _DummyKey(),
            QueryValueEx=lambda key, name: (autostart._tracker_command(), None),
        )

        with mock.patch.object(autostart.sys, "platform", "win32"):
            with mock.patch.dict("sys.modules", {"winreg": fake_winreg}):
                self.assertTrue(autostart.autostart_status())


class _DummyKey:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


if __name__ == "__main__":
    unittest.main()
