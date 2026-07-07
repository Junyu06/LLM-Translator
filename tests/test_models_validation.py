from __future__ import annotations

import unittest

from python_backend.models import AppConfig, TranslationRequest


class ModelValidationTests(unittest.TestCase):
    def test_translation_request_rejects_invalid_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "mode"):
            TranslationRequest(text="hello", mode="bad")

    def test_translation_request_rejects_invalid_languages(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_lang"):
            TranslationRequest(text="hello", source_lang="xx")
        with self.assertRaisesRegex(ValueError, "target_lang"):
            TranslationRequest(text="hello", target_lang="auto")

    def test_translation_request_rejects_invalid_enum_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "output_mode"):
            TranslationRequest(text="hello", output_mode="both")
        with self.assertRaisesRegex(ValueError, "translation_mode"):
            TranslationRequest(text="hello", translation_mode="rich")

    def test_translation_request_rejects_wrong_primitive_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "use_context"):
            TranslationRequest(text="hello", use_context="yes")
        with self.assertRaisesRegex(ValueError, "max_chars"):
            TranslationRequest(text="hello", max_chars="500")

    def test_app_config_rejects_invalid_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "layout"):
            AppConfig(layout="grid")
        with self.assertRaisesRegex(ValueError, "theme"):
            AppConfig(theme="sepia")
        with self.assertRaisesRegex(ValueError, "ui_lang"):
            AppConfig(ui_lang="jp")
        with self.assertRaisesRegex(ValueError, "font_size"):
            AppConfig(font_size="large")


if __name__ == "__main__":
    unittest.main()
