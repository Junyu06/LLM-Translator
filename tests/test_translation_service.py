from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.errors import BackendRequestError
from python_backend.models import TranslationRequest
from python_backend.services.translation_service import TranslationFailed, TranslationService


def streaming(*replies):
    """A fake OllamaBackend.stream_chat that answers requests in order."""
    queue = list(replies)
    calls = []

    def stream_chat(messages):
        calls.append(messages)
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        yield reply

    stream_chat.calls = calls
    return stream_chat


class TranslationServiceTests(unittest.TestCase):
    def run_service(self, backend_cls, request, *replies):
        fake = streaming(*replies)
        backend_cls.return_value.stream_chat.side_effect = fake
        events = list(TranslationService().stream_translate(request))
        return events, fake.calls

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_paragraphs_are_translated_together_and_paired(self, backend_cls):
        events, calls = self.run_service(
            backend_cls,
            TranslationRequest(text="你好\n世界", source_lang="zh", target_lang="en", model="index-translate:2b"),
            "Hello\n\nWorld",
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(events[0]["event"], "started")
        self.assertEqual(events[-1]["event"], "completed")
        self.assertEqual(events[-1]["output_text"], "Hello\nWorld")
        self.assertEqual(
            events[-1]["segments"],
            [{"source": "你好", "target": "Hello", "done": True}, {"source": "世界", "target": "World", "done": True}],
        )

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_model_family_picks_the_prompt(self, backend_cls):
        _, calls = self.run_service(
            backend_cls,
            TranslationRequest(text="Hello.", target_lang="zh", model="index-translate:2b-q4_K_M"),
            "你好。",
        )
        self.assertTrue(calls[0][-1]["content"].startswith("请将以下文本翻译为中文，直接输出翻译结果"))

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_local_mode_ignores_the_saved_remote_host(self, backend_cls):
        self.run_service(
            backend_cls,
            TranslationRequest(text="Hello.", model="m", mode="local", host="http://10.0.0.5:11434"),
            "你好。",
        )
        self.assertEqual(backend_cls.call_args[0][0].host, "http://127.0.0.1:11434")

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_blank_lines_are_kept_in_output(self, backend_cls):
        events, _ = self.run_service(
            backend_cls,
            TranslationRequest(text="\nOne.\n\nTwo.\n\n", target_lang="zh", model="m"),
            "一。\n\n二。",
        )
        self.assertEqual(events[-1]["output_text"], "一。\n\n二。")

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_interleaved_output(self, backend_cls):
        events, _ = self.run_service(
            backend_cls,
            TranslationRequest(text="One.\nTwo.", target_lang="zh", model="m", output_mode="interleaved"),
            "一。\n\n二。",
        )
        self.assertEqual(events[-1]["output_text"], "One.\n一。\n\nTwo.\n二。")

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_markdown_translates_lists_and_keeps_code(self, backend_cls):
        events, calls = self.run_service(
            backend_cls,
            TranslationRequest(
                text="Intro.\n\n- Step one\n- Step two\n\n```python\nprint('keep')\n```",
                target_lang="zh",
                model="m",
                translation_mode="markdown",
            ),
            "介绍。\n\n- 第一步\n- 第二步",
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(events[-1]["output_text"], "介绍。\n\n- 第一步\n- 第二步\n\n```python\nprint('keep')\n```")

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_backend_error_ends_the_stream_with_one_error_event(self, backend_cls):
        events, _ = self.run_service(
            backend_cls,
            TranslationRequest(text="hello", model="m"),
            BackendRequestError("bad json", code="invalid_backend_json"),
        )
        self.assertEqual([e["event"] for e in events], ["started", "error"])
        self.assertEqual(events[-1]["code"], "invalid_backend_json")

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_translate_raises_on_error(self, backend_cls):
        backend_cls.return_value.stream_chat.side_effect = streaming(BackendRequestError("down", code="ollama_unavailable"))
        with self.assertRaises(TranslationFailed) as ctx:
            TranslationService().translate(TranslationRequest(text="hello", model="m"))
        self.assertEqual(ctx.exception.code, "ollama_unavailable")

    def test_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            list(TranslationService().stream_translate(TranslationRequest(text="   ")))

    def test_rejects_input_over_max_chars(self):
        with self.assertRaisesRegex(ValueError, "Input is too large"):
            list(TranslationService().stream_translate(TranslationRequest(text="abcdef", max_chars=5)))

    def test_rejects_segment_over_max_segment_chars(self):
        with self.assertRaisesRegex(ValueError, "segment is too large"):
            list(TranslationService().stream_translate(TranslationRequest(text="abcdef", max_segment_chars=5)))

    def test_rejects_too_many_segments(self):
        with self.assertRaisesRegex(ValueError, "Too many translation segments"):
            list(TranslationService().stream_translate(
                TranslationRequest(text="One.\n\nTwo.", translation_mode="markdown", max_segments=1)
            ))


class SourceLanguageDetectionTests(unittest.TestCase):
    def test_counts_scripts_instead_of_first_character(self):
        detect = TranslationService()._detect_source_lang
        self.assertEqual(detect("The word 中文 appears once in this English sentence."), "en")
        self.assertEqual(detect("这是一段中文，里面有一个 English word。"), "zh")
        self.assertEqual(detect("これは日本語の文章です。"), "ja")
        self.assertEqual(detect("한국어 문장입니다."), "ko")


if __name__ == "__main__":
    unittest.main()
