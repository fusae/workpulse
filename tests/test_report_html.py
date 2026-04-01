import unittest
from unittest import mock

from workpulse import reporter


class ReportHtmlTests(unittest.TestCase):
    def test_generate_html_report_includes_analysis(self):
        fake_snapshot = {
            "period": "today",
            "label": "今日",
            "time_range": {"start": "", "end": ""},
            "total_samples": 3,
            "active_total": 90,
            "idle_time": 30,
            "categories": [{"category": "编码", "seconds": 90, "pct": 100.0}],
            "apps": [{"app_name": "Code", "samples": 3, "category": "编码"}],
            "titles": [{"app_name": "Code", "window_title": "main.py", "samples": 3}],
        }
        fake_analysis = {
            "findings": ["主要时间投入在编码。"],
            "suggestions": ["减少上下文切换。"],
        }

        with mock.patch.object(reporter, "get_report_snapshot", return_value=fake_snapshot):
            with mock.patch("workpulse.ai_analyzer.analyze_period", return_value=fake_analysis):
                output = reporter.generate_report("today", fmt="html", include_analysis=True)

        self.assertIn("<!doctype html>", output.lower())
        self.assertIn("WorkPulse 今日报告", output)
        self.assertIn("分析摘要", output)
        self.assertIn("主要时间投入在编码。", output)


if __name__ == "__main__":
    unittest.main()
