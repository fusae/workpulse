import unittest
from unittest import mock

from workpulse import daily_report


class DailyReportTests(unittest.TestCase):
    def test_generate_daily_report_markdown(self):
        fake_analysis = {
            "period": "today",
            "label": "今日",
            "source": "heuristic",
            "summary": {
                "active_time": "3h 0m",
                "idle_time": "30m",
                "context_switches": 6,
                "overview": "编码投入最多。",
            },
            "findings": ["编码投入最多。"],
            "suggestions": ["减少切换。"],
            "snapshot": {
                "active_total": 10800,
                "idle_time": 1800,
                "categories": [{"category": "编码", "pct": 75.0}],
                "titles": [{"app_name": "Code", "window_title": "main.py"}],
            },
        }

        with mock.patch("workpulse.daily_report.analyze_period", return_value=fake_analysis):
            output = daily_report.generate_daily_report("today")

        self.assertIn("# WorkPulse 今日日报", output)
        self.assertIn("## 今日概述", output)
        self.assertIn("## 下一步", output)

    def test_build_daily_report_uses_llm_when_available(self):
        fake_analysis = {
            "period": "today",
            "label": "今日",
            "source": "heuristic",
            "summary": {
                "active_time": "3h 0m",
                "idle_time": "30m",
                "context_switches": 6,
                "overview": "编码投入最多。",
            },
            "findings": ["编码投入最多。"],
            "suggestions": ["减少切换。"],
            "snapshot": {
                "active_total": 10800,
                "idle_time": 1800,
                "categories": [{"category": "编码", "pct": 75.0}],
                "titles": [{"app_name": "Code", "window_title": "main.py"}],
            },
        }

        with mock.patch("workpulse.daily_report.analyze_period", return_value=fake_analysis):
            with mock.patch("workpulse.daily_report.llm_is_configured", return_value=True):
                with mock.patch("workpulse.daily_report.request_json", return_value={
                    "title": "LLM 日报",
                    "summary": "LLM 总结",
                    "completed": ["LLM 完成"],
                    "outputs": ["LLM 产出"],
                    "blockers": ["LLM 阻塞"],
                    "next_steps": ["LLM 下一步"],
                }):
                    report = daily_report.build_daily_report("today", provider="llm")

        self.assertEqual(report["source"], "llm")
        self.assertEqual(report["title"], "LLM 日报")
