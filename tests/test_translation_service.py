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
            [
                {"source": "你好", "target": "Hello", "done": True, "kept": False},
                {"source": "世界", "target": "World", "done": True, "kept": False},
            ],
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
            TranslationRequest(text="Hello.", model="m", mode="local", host="http://192.0.2.10:11434"),
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
    def test_long_markdown_paragraph_is_split_too(self, backend_cls):
        text = "这是一句很长的测试句子，用来确认 Markdown 模式也会切分。" * 200
        backend_cls.return_value.stream_chat.side_effect = lambda messages: iter(["译文"])
        events = list(TranslationService().stream_translate(
            TranslationRequest(text=text, model="m", translation_mode="markdown")
        ))
        self.assertGreater(len(events[-1]["segments"]), 1)

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

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_glossary_and_picked_prompt_reach_the_request(self, backend_cls):
        _, calls = self.run_service(
            backend_cls,
            TranslationRequest(text="The medium setting.", target_lang="zh", model="someone/quant:q4",
                               prompt_style="index", glossary="medium setting = 思考档位"),
            "思考档位。",
        )
        self.assertIn("术语使用固定译法（medium setting 固定译为“思考档位”）", calls[0][-1]["content"])

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_custom_prompt_is_used(self, backend_cls):
        _, calls = self.run_service(
            backend_cls,
            TranslationRequest(text="Hello.", model="m", prompt_style="custom", custom_prompt="To {target_lang}: {text}"),
            "你好。",
        )
        self.assertEqual(calls[0][-1]["content"], "To Chinese: Hello.")

    def test_custom_style_needs_a_template(self):
        with self.assertRaisesRegex(ValueError, "custom prompt is empty"):
            TranslationRequest(text="Hello.", prompt_style="custom", custom_prompt="  ")

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_retranslate_sends_context_and_temperature(self, backend_cls):
        _, calls = self.run_service(
            backend_cls,
            TranslationRequest(text="Second.", model="m", temperature=0.3,
                               context=[{"source": "First.", "target": "第一。"}, {"source": "", "target": ""}]),
            "第二。",
        )
        self.assertEqual([m["role"] for m in calls[0]], ["user", "assistant", "user"])
        self.assertEqual(calls[0][1]["content"], "第一。")
        self.assertEqual(backend_cls.call_args[0][0].options, {"temperature": 0.3})

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_a_block_is_translated_as_is_and_keeps_its_indent(self, backend_cls):
        events, calls = self.run_service(
            backend_cls,
            TranslationRequest(text="     Then restart the app.", model="m", translation_mode="markdown", as_block=True),
            "然后重启应用。",
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(events[-1]["output_text"], "     然后重启应用。")

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_list_piece_after_code_keeps_its_indent(self, backend_cls):
        text = "1. Install:\n   ```bash\n   npm i\n   ```\n   Then restart.\n   - Child\n2. Open."
        events, _ = self.run_service(
            backend_cls,
            TranslationRequest(text=text, model="m", translation_mode="markdown"),
            "1. 安装：",
            "然后重启。\n   - 子项\n2. 打开。",
        )
        self.assertEqual(events[-1]["event"], "completed")
        targets = [segment["target"] for segment in events[-1]["segments"]]
        self.assertEqual(targets[-1], "   然后重启。\n   - 子项\n2. 打开。")

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_kept_marks_blocks_shown_as_they_are_not_unchanged_translations(self, backend_cls):
        events, _ = self.run_service(
            backend_cls,
            TranslationRequest(text="Ollama\n\n```\ncode\n```", model="m", translation_mode="markdown"),
            "Ollama",
        )
        self.assertEqual([s["kept"] for s in events[-1]["segments"]], [False, True])

    @patch("python_backend.services.translation_service.OllamaBackend")
    def test_tab_indented_block_keeps_its_tab(self, backend_cls):
        events, _ = self.run_service(
            backend_cls,
            TranslationRequest(text="\tThen restart.", model="m", translation_mode="markdown", as_block=True),
            "然后重启。",
        )
        self.assertEqual(events[-1]["output_text"], "\t然后重启。")

    def test_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            list(TranslationService().stream_translate(TranslationRequest(text="   ")))

    def test_rejects_input_over_max_chars(self):
        with self.assertRaisesRegex(ValueError, "Input is too large"):
            list(TranslationService().stream_translate(TranslationRequest(text="abcdef", max_chars=5)))

    def test_rejects_segment_over_max_segment_chars(self):
        with self.assertRaisesRegex(ValueError, "segment is too large"):
            list(TranslationService().stream_translate(TranslationRequest(text="abcdef", max_segment_chars=5)))

    def test_rejects_a_block_too_long_for_one_request(self):
        with self.assertRaisesRegex(ValueError, "too long to translate in one request"):
            list(TranslationService().stream_translate(
                TranslationRequest(text="# " + "长" * 3000, translation_mode="markdown", model="m")
            ))

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
