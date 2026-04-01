import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workpulse import settings


class SettingsTests(unittest.TestCase):
    def test_load_settings_creates_default_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.yaml"
            with mock.patch.object(settings, "DATA_DIR", Path(tmpdir)):
                with mock.patch.object(settings, "SETTINGS_PATH", settings_path):
                    loaded = settings.load_settings()

            self.assertTrue(settings_path.exists())
            self.assertEqual(loaded.poll_interval_seconds, 30)
            self.assertEqual(loaded.archive_retention_days, 90)

    def test_load_settings_applies_bounds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.yaml"
            settings_path.write_text(
                "poll_interval_seconds: 1\narchive_retention_days: 0\n",
                encoding="utf-8",
            )

            with mock.patch.object(settings, "DATA_DIR", Path(tmpdir)):
                with mock.patch.object(settings, "SETTINGS_PATH", settings_path):
                    loaded = settings.load_settings()

            self.assertEqual(loaded.poll_interval_seconds, 5)
            self.assertEqual(loaded.archive_retention_days, 1)


if __name__ == "__main__":
    unittest.main()
