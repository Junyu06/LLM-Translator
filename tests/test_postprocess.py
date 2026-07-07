from __future__ import annotations

import unittest

from core.postprocess import PostProcessOptions, extract_translation


class PostProcessTests(unittest.TestCase):
    def test_body_translation_marker_is_preserved(self):
        raw = "Translation: The body says Translation: keep this phrase."

        self.assertEqual(
            extract_translation(raw),
            "The body says Translation: keep this phrase.",
        )

    def test_marker_is_extracted_only_at_start_after_whitespace(self):
        raw = "Intro sentence.\n\nTranslation: this is part of the body."

        self.assertEqual(extract_translation(raw), raw)

    def test_paired_wrapping_quotes_are_removed(self):
        self.assertEqual(extract_translation('"Hello"'), "Hello")
        self.assertEqual(extract_translation("'Hello'"), "Hello")
        self.assertEqual(extract_translation("“Hello”"), "Hello")
        self.assertEqual(extract_translation("‘Hello’"), "Hello")

    def test_unpaired_quotes_are_preserved(self):
        self.assertEqual(extract_translation('"Hello'), '"Hello')
        self.assertEqual(extract_translation("Hello'"), "Hello'")
        self.assertEqual(extract_translation("“Hello"), "“Hello")
        self.assertEqual(extract_translation("Hello’"), "Hello’")


if __name__ == "__main__":
    unittest.main()
