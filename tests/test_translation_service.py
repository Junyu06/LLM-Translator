from __future__ import annotations

import unittest
from unittest.mock import patch

from python_backend.models import TranslationRequest
from python_backend.services.translation_service import TranslationService


class TranslationServiceTests(unittest.TestCase):
    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_translate_returns_rendered_output(self, backend_cls):
        backend = backend_cls.return_value
        backend.generate.side_effect = [
            "译文：Hello",
            "译文：World",
        ]

        service = TranslationService()
        response = service.translate(
            TranslationRequest(
                text="你好\n世界",
                source_lang="zh",
                target_lang="en",
                output_mode="translations_only",
            )
        )

        self.assertEqual(response.output_text, "Hello\nWorld")
        self.assertEqual(len(response.segments), 2)
        self.assertEqual(response.segments[0].target, "Hello")

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_translate_collapse_newlines(self, backend_cls):
        backend = backend_cls.return_value
        backend.generate.return_value = "译文：A"

        service = TranslationService()
        response = service.translate(
            TranslationRequest(
                text="第一段\n\n\n",
                source_lang="zh",
                target_lang="en",
                collapse_newlines=True,
            )
        )

        self.assertEqual(response.output_text, "A")

    def test_translate_rejects_empty_input(self):
        service = TranslationService()
        with self.assertRaises(ValueError):
            service.translate(TranslationRequest(text="   "))


if __name__ == "__main__":
    unittest.main()
