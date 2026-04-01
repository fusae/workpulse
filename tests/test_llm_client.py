import io
import json
import os
import unittest
from unittest import mock

from workpulse import llm_client


class LLMClientTests(unittest.TestCase):
    def test_llm_is_configured_checks_api_key_env(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            self.assertTrue(llm_client.llm_is_configured())

    def test_analyze_with_llm_parses_openai_compatible_response(self):
        fake_body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "总结",
                                "findings": ["观察"],
                                "suggestions": ["建议"],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse(json.dumps(fake_body).encode("utf-8"))):
                result = llm_client.analyze_with_llm({"foo": "bar"}, {"findings": [], "suggestions": []})

        self.assertEqual(result["summary"], "总结")
        self.assertEqual(result["findings"], ["观察"])
        self.assertEqual(result["suggestions"], ["建议"])
