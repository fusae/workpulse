import json
import unittest

from workpulse.intent import infer_intent, intent_label


class IntentTests(unittest.TestCase):
    def test_infer_coding_from_editor_title(self):
        intent, evidence = infer_intent("Code", "workpulse/tracker.py")

        self.assertEqual(intent, "coding")
        self.assertIn("code", json.loads(evidence)["matched_keywords"])
        self.assertEqual(intent_label(intent), "编码开发")

    def test_project_context_defaults_to_coding(self):
        intent, evidence = infer_intent("Preview", "WorkPulse", project_name="workpulse")

        self.assertEqual(intent, "coding")
        self.assertEqual(json.loads(evidence)["project"], "workpulse")


if __name__ == "__main__":
    unittest.main()
