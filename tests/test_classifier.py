import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workpulse import classifier


class ClassifierTests(unittest.TestCase):
    def test_creates_rules_file_from_packaged_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = Path(tmpdir) / "rules.yaml"

            with mock.patch.object(classifier, "RULES_PATH", rules_path):
                engine = classifier.Classifier()

            self.assertTrue(rules_path.exists())
            self.assertEqual(engine.classify("Code", "main.py"), "编码")


if __name__ == "__main__":
    unittest.main()
