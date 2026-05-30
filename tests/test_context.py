import unittest

from workpulse.context import summarize_text_outputs, terminal_evidence


class ContextEvidenceTests(unittest.TestCase):
    def test_summarize_text_outputs_uses_recent_text_files(self):
        context = {
            "projects": [
                {
                    "name": "workpulse",
                    "recent_files": ["README.md", "dist/app.bin", "src/workpulse/tracker.py"],
                }
            ]
        }

        summary = summarize_text_outputs(context)

        self.assertIn("workpulse:README.md", summary)
        self.assertIn("workpulse:src/workpulse/tracker.py", summary)
        self.assertNotIn("app.bin", summary)

    def test_terminal_evidence_uses_terminal_window_title(self):
        self.assertEqual(
            terminal_evidence("Terminal", "zsh - ~/Projects/workpulse"),
            "Terminal: zsh - ~/Projects/workpulse",
        )
        self.assertEqual(terminal_evidence("Code", "main.py"), "")


if __name__ == "__main__":
    unittest.main()
