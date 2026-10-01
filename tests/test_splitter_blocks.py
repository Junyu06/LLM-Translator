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
            'See [the docs](<https://example.com/docs> "Docs"), [Site](<https://example.com/docs> "Docs") '
            'and [site](<https://example.com/docs> "Docs"), plus ![logo](<https://example.com/logo.png>).',
        )
        self.assertEqual((segments[1].kind, segments[1].protected), ("link_definitions", True))

    def test_inline_code_and_inline_links_are_left_alone(self):
        segments = split_markdown_blocks("Use `[site]` or [x](https://a.b) and [site].\n\n[site]: https://example.com")
        self.assertEqual(segments[0].text, "Use `[site]` or [x](https://a.b) and [site](<https://example.com>).")

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

    def test_angle_bracket_destination_stays_one_destination(self):
        segments = split_markdown_blocks("See [spec].\n\n[spec]: <https://example.com/a b)c>")
        self.assertEqual(segments[0].text, "See [spec](<https://example.com/a%20b)c>).")

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

    def test_indented_paragraph_after_a_blank_line_stays_in_the_list(self):
        text = "1. Install the app.\n\n    Then open it once so macOS asks for permissions.\n2. Copy text twice."
        segments = split_markdown_blocks(text)
        self.assertEqual([(s.kind, s.protected) for s in segments], [("list", False)])

    def test_parent_paragraph_after_a_nested_list_stays_with_its_item(self):
        text = (
            "- Install the app.\n"
            "  - On macOS, drag it to Applications.\n"
            "  - On Windows, run the installer.\n"
            "\n"
            "  Restart the app after installation.\n"
            "\n"
            "- Configure the model."
        )
        segments = split_markdown_blocks(text)
        self.assertEqual([(s.kind, s.protected) for s in segments], [("list", False)])
        self.assertIn("  Restart the app after installation.", segments[0].text)

    def test_numbered_parent_paragraph_after_a_nested_list(self):
        text = "1. Install.\n   - macOS\n   - Windows\n\n   Restart afterwards.\n2. Configure."
        self.assertEqual([s.kind for s in split_markdown_blocks(text)], ["list"])

    def test_code_after_a_later_item_is_not_taken_for_an_earlier_sub_item(self):
        text = "- Install.\n  - macOS\n\n- Configure.\n\n1. Run:\n\n       npm run build\n\n2. Open."
        kinds = [(s.kind, s.protected) for s in split_markdown_blocks(text)]
        self.assertIn(("indented_code", True), kinds)

    def test_code_indented_past_the_item_text_is_protected(self):
        text = "1. Run:\n\n       npm run build\n\n2. Open the app."
        segments = split_markdown_blocks(text)
        self.assertIn(("indented_code", True), [(s.kind, s.protected) for s in segments])

    def test_html_blocks_and_thematic_breaks_are_protected(self):
        text = "Intro.\n\n<details>\n<summary>More</summary>\n</details>\n\n---\n\nOutro."
        self.assertEqual(kinds(text), [("text", False), ("html", True), ("hr", True), ("text", False)])

    def test_multi_line_definition_becomes_an_inline_link(self):
        segments = split_markdown_blocks('See [the site][x].\n\n[x]:\n  https://example.com/a\n  "Home"')
        self.assertEqual(segments[0].text, 'See [the site](<https://example.com/a> "Home").')

    def test_rewritten_title_keeps_quotes_and_backslashes_escaped(self):
        segments = split_markdown_blocks('See [a][x].\n\n[x]:\n  https://example.com\n  "say \\"hi\\" \\\\"')
        self.assertEqual(segments[0].text, 'See [a](<https://example.com> "say \\"hi\\" \\\\").')

    def test_urls_and_link_destinations_are_not_rewritten(self):
        segments = split_markdown_blocks(
            "[search](https://example.com/?tag=[site]) <https://a.b/[site]> https://c.d/[site] and [site].\n\n[site]:\n  https://example.com/s"
        )
        self.assertEqual(
            segments[0].text,
            "[search](https://example.com/?tag=[site]) <https://a.b/[site]> https://c.d/[site] and [site](<https://example.com/s>).",
        )

    def test_link_text_with_brackets_is_rewritten(self):
        segments = split_markdown_blocks("See [the **[docs]**][site].\n\n[site]: https://example.com")
        self.assertEqual(segments[0].text, "See [the **[docs]**](<https://example.com>).")

    def test_links_in_urls_brackets_and_images(self):
        defs = "\n\n[site]: https://target.example\n[docs]: https://docs.example"
        cases = {
            "[search](https://example.com/(v1)/[site])": "[search](https://example.com/(v1)/[site])",
            "[https://example.com][site]": "[https://example.com](<https://target.example>)",
            # docs is defined, so CommonMark makes the inner [docs] the link, not the outer one.
            "[the [API [docs]]][site]": "[the [API [docs](<https://docs.example>)]][site](<https://target.example>)",
            "[![CI][docs]][site]": "[![CI](<https://docs.example>)](<https://target.example>)",
        }
        for source, expected in cases.items():
            self.assertEqual(split_markdown_blocks(source + defs)[0].text, expected, source)
        only_site = split_markdown_blocks("[the [API [docs]]][site]\n\n[site]: https://target.example")
        self.assertEqual(only_site[0].text, "[the [API [docs]]](<https://target.example>)")

    def test_alt_text_bare_urls_and_repeated_table_cells(self):
        defs = "\n\n[site]: /target"
        self.assertEqual(
            split_markdown_blocks("https://example.com/path ![x [site]](/image)" + defs)[0].text,
            "https://example.com/path ![x [site]](/image)",
        )
        self.assertEqual(
            split_markdown_blocks("(https://example.com/(v1)/[site]/manual)" + defs)[0].text,
            "(https://example.com/(v1)/[site]/manual)",
        )
        table = "| [site] | [site] |\n|---|---|\n| a | b |" + defs
        self.assertEqual(split_markdown_blocks(table)[0].text.splitlines()[0], "| [site](</target>) | [site](</target>) |")

    def test_links_after_code_spans_and_inline_links(self):
        defs = "\n\n[site]: /target"
        table = "| `[site]` | [site] |\n|---|---|\n| a | b |" + defs
        self.assertEqual(split_markdown_blocks(table)[0].text.splitlines()[0], "| `[site]` | [site](</target>) |")
        self.assertEqual(
            split_markdown_blocks("[x](https://example.com)[site]" + defs)[0].text,
            "[x](https://example.com)[site](</target>)",
        )
        self.assertEqual(
            split_markdown_blocks("`https://example.com`[site]" + defs)[0].text,
            "`https://example.com`[site](</target>)",
        )

    def test_escaped_pipes_and_several_links_in_one_url(self):
        defs = "\n\n[site]: /target\n[docs]: /manual"
        table = "| `\\| [site]` | [site] |\n|---|---|\n| a | b |" + defs
        self.assertEqual(split_markdown_blocks(table)[0].text.splitlines()[0], "| `\\| [site]` | [site] |")
        url = "https://example.com/?a=[site]&b=[docs]"
        self.assertEqual(split_markdown_blocks(url + defs)[0].text, url)
        self.assertEqual(split_markdown_blocks("word[site]" + defs)[0].text, "word[site](</target>)")

    def test_escaped_pipe_rows_and_links_after_autolinks(self):
        defs = "\n\n[site]: /target"
        table = "| a\\|b | [site] | a|b | `[site]` |\n|---|---|---|---|---|\n|1|2|3|4|5|" + defs
        self.assertEqual(split_markdown_blocks(table)[0].text.splitlines()[0], "| a\\|b | [site] | a|b | `[site]` |")
        self.assertEqual(split_markdown_blocks("<https://example.com>[site]" + defs)[0].text, "<https://example.com>[site](</target>)")

    def test_reference_inside_a_list_and_a_quote(self):
        text = "- See [the docs][site]\n  and [site].\n\n> Quote [site].\n\n[site]: https://e.example"
        segments = split_markdown_blocks(text)
        self.assertEqual(segments[0].text, "- See [the docs](<https://e.example>)\n  and [site](<https://e.example>).")
        self.assertEqual(segments[1].text, "> Quote [site](<https://e.example>).")

    def test_setext_heading_is_one_block(self):
        self.assertEqual(kinds("Title\n=====\n\nText."), [("heading", False), ("text", False)])


if __name__ == "__main__":
    unittest.main()
