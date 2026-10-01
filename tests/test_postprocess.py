from __future__ import annotations

import unittest

from core.postprocess import extract_translation


class PostProcessTests(unittest.TestCase):
    def test_leading_label_is_removed(self):
        self.assertEqual(extract_translation("译文：你好"), "你好")
        self.assertEqual(extract_translation("Translation: Hello"), "Hello")

    def test_label_inside_body_is_preserved(self):
        raw = "Translation: The body says Translation: keep this phrase."
        self.assertEqual(extract_translation(raw), "The body says Translation: keep this phrase.")

    def test_text_starting_with_the_word_translation_is_kept(self):
        # Only labels with a colon are stripped; "译文是..." is a real sentence.
        self.assertEqual(extract_translation("译文是作者自己校对的。"), "译文是作者自己校对的。")

    def test_wrapping_quotes_added_by_the_model_are_removed(self):
        self.assertEqual(extract_translation('"Hello"', "你好"), "Hello")
        self.assertEqual(extract_translation("“你好”", "Hello"), "你好")

    def test_quotes_that_were_in_the_source_are_kept(self):
        source = '"I never said it was a bad idea," she said. "I said it was a bad lab."'
        raw = "“我从没说过这是个坏主意，”她说，“我说的是实验室很糟。”"
        self.assertEqual(extract_translation(raw, source), raw)

    def test_unpaired_quotes_are_preserved(self):
        self.assertEqual(extract_translation('"Hello'), '"Hello')
        self.assertEqual(extract_translation("Hello’"), "Hello’")

    def test_think_block_is_dropped(self):
        self.assertEqual(extract_translation("<think>\n\n</think>\n\n你好"), "你好")

    def test_keep_format_leaves_markdown_alone(self):
        self.assertEqual(extract_translation("Translation: # Title", keep_format=True), "Translation: # Title")

    def test_reference_link_labels_are_restored_in_markdown(self):
        source = "Read [the docs][site] and [the guide][guide]."
        self.assertEqual(
            extract_translation("阅读[文档][网站]和[指南][指引]。", source, keep_format=True),
            "阅读[文档][site]和[指南][guide]。",
        )

    def test_reference_labels_left_alone_when_counts_differ(self):
        source = "Read [the docs][site]."
        self.assertEqual(extract_translation("阅读文档。", source, keep_format=True), "阅读文档。")

    def test_correct_labels_are_not_swapped_when_the_model_reorders_links(self):
        source = "Read [the guide][guide] after [the docs][docs]."
        raw = "先读[文档][docs]，再读[指南][guide]。"
        self.assertEqual(extract_translation(raw, source, keep_format=True), raw)


if __name__ == "__main__":
    unittest.main()
