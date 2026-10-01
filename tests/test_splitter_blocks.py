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

    def test_quote_with_code_is_kept_whole(self):
        segments = split_markdown_blocks("> Run this:\n> ```bash\n> npm run keep\n> ```")
        self.assertEqual([(s.kind, s.protected) for s in segments], [("blockquote", True)])

    def test_reference_links_become_inline_links(self):
        segments = split_markdown_blocks(
            "See [the docs][site], [Site][] and [site], plus ![logo][img].\n\n"
            "[site]: https://example.com/docs \"Docs\"\n[img]: <https://example.com/logo.png>"
        )
        self.assertEqual(
            segments[0].text,
            'See [the docs](https://example.com/docs "Docs"), [Site](https://example.com/docs "Docs") '
            'and [site](https://example.com/docs "Docs"), plus ![logo](<https://example.com/logo.png>).',
        )
        self.assertEqual((segments[1].kind, segments[1].protected), ("link_definitions", True))

    def test_inline_code_and_inline_links_are_left_alone(self):
        segments = split_markdown_blocks("Use `[site]` or [x](https://a.b) and [site].\n\n[site]: https://example.com")
        self.assertEqual(segments[0].text, "Use `[site]` or [x](https://a.b) and [site](https://example.com).")

    def test_multi_line_definition_is_protected(self):
        segments = split_markdown_blocks("Text.\n\n[site]:\n  https://example.com\n  \"Title\"")
        self.assertEqual((segments[1].kind, segments[1].protected), ("link_definitions", True))

    def test_nested_quote_with_code_is_kept_whole(self):
        segments = split_markdown_blocks("> > Example:\n> > ```\n> > keep()\n> > ```")
        self.assertTrue(segments[0].protected)

    def test_quote_with_indented_code_is_kept_whole(self):
        segments = split_markdown_blocks('> Example:\n>\n>     print("keep")')
        self.assertTrue(segments[0].protected)

    def test_plain_quote_is_translated(self):
        segments = split_markdown_blocks("> Note: the first launch is slow.\n> It gets faster.")
        self.assertFalse(segments[0].protected)

    def test_brackets_without_a_definition_are_left_alone(self):
        segments = split_markdown_blocks("Press [Enter] to continue.")
        self.assertEqual(segments[0].text, "Press [Enter] to continue.")

    def test_angle_bracket_destination_is_kept_intact(self):
        segments = split_markdown_blocks("See [spec].\n\n[spec]: <https://example.com/a b)c>")
        self.assertEqual(segments[0].text, "See [spec](<https://example.com/a b)c>).")

    def test_list_item_opening_with_a_code_fence_is_protected(self):
        text = "- ```python\n  keep()\n  ```\n- Translate this item."
        segments = split_markdown_blocks(text)
        self.assertEqual([(s.kind, s.protected) for s in segments], [("list", True), ("list", False)])
        self.assertEqual(segments[1].text, "- Translate this item.")

    def test_quote_with_list_item_code_is_kept_whole(self):
        segments = split_markdown_blocks("> - ```python\n>   keep()\n>   ```")
        self.assertTrue(segments[0].protected)

    def test_definition_with_title_on_next_line_is_protected(self):
        segments = split_markdown_blocks('Text.\n\n[site]: https://example.com\n"Title"')
        self.assertEqual((segments[1].kind, segments[1].protected), ("link_definitions", True))


if __name__ == "__main__":
    unittest.main()
