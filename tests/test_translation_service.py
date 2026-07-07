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
    def test_markdown_mode_splits_prose_blocks_and_passthrough_protected_blocks(self, backend_cls, build_prompt_mock):
        backend = backend_cls.return_value
        backend.stream_generate.side_effect = [
            iter(["译文：第一段"]),
            iter(["译文：第二段"]),
        ]
        build_prompt_mock.side_effect = lambda text, opt: f"{opt.preset}:{text}"

        service = TranslationService()
        response = service.translate(
            TranslationRequest(
                text="Paragraph one.\n\n```python\nprint('keep')\n```\n\nParagraph two.",
                source_lang="en",
                target_lang="zh",
                translation_mode="markdown",
            )
        )

        self.assertEqual(len(response.segments), 3)
        self.assertEqual(response.segments[0].target, "第一段")
        self.assertEqual(response.segments[1].target, "```python\nprint('keep')\n```")
        self.assertEqual(response.segments[2].target, "第二段")
        self.assertEqual(response.output_text, "第一段\n\n```python\nprint('keep')\n```\n\n第二段")
        self.assertEqual(backend.stream_generate.call_count, 2)
        self.assertEqual(build_prompt_mock.call_count, 2)
        self.assertEqual(build_prompt_mock.call_args_list[0][0][0], "Paragraph one.")
        self.assertEqual(build_prompt_mock.call_args_list[0][0][1].preset, PromptPreset.MARKDOWN)

    def test_translate_rejects_input_over_max_chars(self):
        service = TranslationService()

        with self.assertRaisesRegex(ValueError, "Input is too large"):
            service.translate(TranslationRequest(text="abcdef", max_chars=5))

    def test_translate_rejects_segment_over_max_segment_chars(self):
        service = TranslationService()

        with self.assertRaisesRegex(ValueError, "segment is too large"):
            service.translate(TranslationRequest(text="abcdef", max_segment_chars=5))

    def test_markdown_mode_rejects_too_many_segments(self):
        service = TranslationService()

        with self.assertRaisesRegex(ValueError, "Too many translation segments"):
            service.translate(
                TranslationRequest(
                    text="One.\n\nTwo.",
                    translation_mode="markdown",
                    max_segments=1,
                )
            )


if __name__ == "__main__":
    unittest.main()
