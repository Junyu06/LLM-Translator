import unittest

from core.splitter import split_markdown_blocks


class MarkdownBlockSplitterTests(unittest.TestCase):
    def test_groups_fenced_code_as_protected_segment(self):
        text = "Intro paragraph.\n\n```python\nif value:\n    print(value)\n```\n\nOutro paragraph."

        segments = split_markdown_blocks(text)

        self.assertEqual([segment.kind for segment in segments], ["text", "fenced_code", "text"])
        self.assertFalse(segments[0].protected)
        self.assertTrue(segments[1].protected)
        self.assertEqual(segments[1].text, "```python\nif value:\n    print(value)\n```")

    def test_groups_indented_code_and_preserves_indentation(self):
        text = "Before\n\n    def example():\n        return 1\n\nAfter"

        segments = split_markdown_blocks(text)

        self.assertEqual([segment.kind for segment in segments], ["text", "indented_code", "text"])
        self.assertTrue(segments[1].protected)
        self.assertEqual(segments[1].text, "    def example():\n        return 1")

    def test_groups_markdown_table_as_protected_segment(self):
        text = "Before\n\n| Name | Value |\n| --- | --- |\n| One | 1 |\n\nAfter"

        segments = split_markdown_blocks(text)

        self.assertEqual([segment.kind for segment in segments], ["text", "table", "text"])
        self.assertTrue(segments[1].protected)
        self.assertEqual(segments[1].text, "| Name | Value |\n| --- | --- |\n| One | 1 |")

    def test_groups_blockquote_as_protected_segment(self):
        text = "Before\n\n> Quote line one\n> Quote line two\n\nAfter"

        segments = split_markdown_blocks(text)

        self.assertEqual([segment.kind for segment in segments], ["text", "blockquote", "text"])
        self.assertTrue(segments[1].protected)
        self.assertEqual(segments[1].text, "> Quote line one\n> Quote line two")

    def test_groups_list_with_indented_continuation_and_blank_line(self):
        text = "Before\n\n- item one\n  continuation line\n\n  second paragraph\n- item two\n\nAfter"

        segments = split_markdown_blocks(text)

        self.assertEqual([segment.kind for segment in segments], ["text", "list", "text"])
        self.assertTrue(segments[1].protected)
        self.assertEqual(
            segments[1].text,
            "- item one\n  continuation line\n\n  second paragraph\n- item two",
        )


if __name__ == "__main__":
    unittest.main()
