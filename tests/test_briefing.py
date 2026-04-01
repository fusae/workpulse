import unittest
from unittest import mock

from workpulse import briefing


class BriefingTests(unittest.TestCase):
    def test_generate_brief_markdown(self):
        fake_analysis = {
            "period": "today",
            "label": "今日",
            "summary": {"active_time": "3h 0m", "idle_time": "30m", "context_switches": 8},
            "findings": ["主要时间投入在编码。"],
            "suggestions": ["减少沟通打断。"],
            "snapshot": {
                "categories": [{"category": "编码", "pct": 75.0}],
            },
        }

        with mock.patch("workpulse.briefing.analyze_period", return_value=fake_analysis):
            output = briefing.generate_brief("today", fmt="markdown")

        self.assertIn("# WorkPulse 今日摘要", output)
        self.assertIn("主要时间投入在编码。", output)
        self.assertIn("减少沟通打断。", output)


if __name__ == "__main__":
    unittest.main()
