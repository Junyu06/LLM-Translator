from __future__ import annotations

import unittest
from unittest.mock import patch

from core.prompt import PromptPreset
from python_backend.models import TranslationRequest
from python_backend.services.translation_service import TranslationService


class TranslationServiceTests(unittest.TestCase):
    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_translate_returns_rendered_output(self, backend_cls):
        backend = backend_cls.return_value
        backend.stream_generate.side_effect = [
            iter(["译文：Hello"]),
            iter(["译文：World"]),
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
        backend.stream_generate.return_value = iter(["译文：A"])

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

    @patch("python_backend.services.translation_service.build_prompt")
    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_markdown_mode_uses_single_prompt_and_markdown_preset(self, backend_cls, build_prompt_mock):
        backend = backend_cls.return_value
        backend.stream_generate.return_value = iter(["# 标题\n\n段落"])
        build_prompt_mock.side_effect = lambda text, opt: f"{opt.preset}:{text}"

        service = TranslationService()
        response = service.translate(
            TranslationRequest(
                text="# Title\n\nParagraph one.\n\n- item 1\n- item 2",
                source_lang="en",
                target_lang="zh",
                translation_mode="markdown",
            )
        )

        self.assertEqual(len(response.segments), 1)
        self.assertEqual(response.output_text, "# 标题\n\n段落")
        self.assertEqual(build_prompt_mock.call_count, 1)
        self.assertEqual(build_prompt_mock.call_args[0][0], "# Title\n\nParagraph one.\n\n- item 1\n- item 2")
        self.assertEqual(build_prompt_mock.call_args[0][1].preset, PromptPreset.MARKDOWN)


if __name__ == "__main__":
    unittest.main()
