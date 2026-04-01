import unittest
from unittest import mock

from workpulse import doctor


class DoctorTests(unittest.TestCase):
    def test_collect_diagnostics_contains_database_check(self):
        with mock.patch("workpulse.doctor._check_dependencies", return_value=[]):
            with mock.patch("workpulse.doctor._check_data_dir", return_value={"name": "data_dir", "status": "ok", "message": "ok"}):
                with mock.patch("workpulse.doctor._check_settings", return_value={"name": "settings", "status": "ok", "message": "ok"}):
                    with mock.patch("workpulse.doctor._check_rules", return_value={"name": "rules", "status": "ok", "message": "ok"}):
                        with mock.patch("workpulse.doctor._check_database", return_value={"name": "database", "status": "ok", "message": "ok"}):
                            report = doctor.collect_diagnostics()

        check_names = [item["name"] for item in report["checks"]]
        self.assertIn("database", check_names)
        self.assertEqual(report["overall"], "ok")


if __name__ == "__main__":
    unittest.main()
