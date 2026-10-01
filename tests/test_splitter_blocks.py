import unittest

from core.splitter import split_markdown_blocks


def kinds(text):
    return [(segment.kind, segment.protected) for segment in split_markdown_blocks(text)]


class MarkdownBlockSplitterTests(unittest.TestCase):
    def test_fenced_code_is_the_only_protected_block_type(self):
        text = "Intro paragraph.\n\n```python\nif value:\n    print(value)\n```\n\nOutro paragraph."
        segments = split_markdown_blocks(text)
        self.assertEqual(kinds(text), [("text", False), ("fenced_code", True), ("text", False)])
        self.assertEqual(segments[1].text, "```python\nif value:\n    print(value)\n```")

    def test_indented_code_is_protected_and_keeps_indentation(self):
        text = "Before\n\n    def example():\n        return 1\n\nAfter"
        segments = split_markdown_blocks(text)
        self.assertEqual(kinds(text), [("text", False), ("indented_code", True), ("text", False)])
        self.assertEqual(segments[1].text, "    def example():\n        return 1")

    def test_lists_quotes_and_tables_are_translated(self):
        text = (
            "- Download the app\n- Drag it into Applications\n\n"
            "> Note: the first launch is slow.\n\n"
            "| Option | Meaning |\n|---|---|\n| Fast | Lower quality |"
        )
        self.assertEqual(kinds(text), [("list", False), ("blockquote", False), ("table", False)])

    def test_heading_ends_a_list(self):
        text = "- Keep\n# Translate heading\nNew paragraph"
        segments = split_markdown_blocks(text)
        self.assertEqual([s.kind for s in segments], ["list", "heading", "text"])
        self.assertEqual(segments[1].text, "# Translate heading")

    def test_heading_followed_by_paragraph_without_blank_line(self):
        segments = split_markdown_blocks("## Install\nRun the installer.")
        self.assertEqual([s.text for s in segments], ["## Install", "Run the installer."])

    def test_list_with_indented_continuation_and_blank_line(self):
        text = "Before\n\n- item one\n  continuation line\n\n  second paragraph\n- item two\n\nAfter"
        segments = split_markdown_blocks(text)
        self.assertEqual([s.kind for s in segments], ["text", "list", "text"])
        self.assertEqual(segments[1].text, "- item one\n  continuation line\n\n  second paragraph\n- item two")

    def test_list_with_lazy_continuation(self):
        segments = split_markdown_blocks("Before\n\n- item one\ncontinued line\n- item two\n\nAfter")
        self.assertEqual(segments[1].text, "- item one\ncontinued line\n- item two")

    def test_blockquote_with_lazy_continuation(self):
        segments = split_markdown_blocks("Before\n\n> quoted line\nlazy continuation\n> quoted again\n\nAfter")
        self.assertEqual(segments[1].text, "> quoted line\nlazy continuation\n> quoted again")

    def test_leading_indented_code_stays_code(self):
        segments = split_markdown_blocks("    indented = True\n\nText")
        self.assertEqual(kinds("    indented = True\n\nText"), [("indented_code", True), ("text", False)])
        self.assertEqual(segments[0].text, "    indented = True")

    def test_code_fence_inside_a_list_item_stays_protected(self):
        text = "1. Install:\n   ```bash\n   npm run build\n   ```\n2. Open the app."
        segments = split_markdown_blocks(text)
        self.assertEqual([(s.kind, s.protected) for s in segments], [("list", False), ("fenced_code", True), ("list", False)])
        self.assertNotIn("npm", segments[0].text)
        self.assertEqual(segments[1].text, "   ```bash\n   npm run build\n   ```")

    def test_reference_link_definitions_are_not_translated(self):
        segments = split_markdown_blocks("Read [the docs][site].\n\n[site]: https://example.com/docs")
        self.assertEqual([(s.kind, s.protected) for s in segments], [("text", False), ("link_definitions", True)])


if __name__ == "__main__":
    unittest.main()
