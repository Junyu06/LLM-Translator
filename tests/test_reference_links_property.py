"""Rewriting reference links as inline links must not change what a document renders to.

Random documents are built from fragments that broke earlier versions: code
spans, autolinks, bare URLs, entities, escaped pipes, nested brackets, broken
inline links, tables, lists and quotes. Each must render to the same HTML
before and after the rewrite.
"""

import random
import unittest

from markdown_it import MarkdownIt

from core.splitter import inline_reference_links, split_markdown_blocks

FRAGMENTS = [
    "[site]", "[Site][]", "[the docs][site]", "[the [API [docs]]][site]", "![alt][docs]", "[![CI][docs]][ci]",
    "[x](https://e.example/(v1)/[site])", "<https://a.b/[site]>", "https://c.d/[site]", "(https://e.example/(v1)/[site]/m)",
    "`[site]`", "`https://x.y`[site]", "[x](https://e.example)[site]", "\\[site]", "[site\\]", "[undefined]",
    "word[site]", "https://q.example/?a=[site]&b=[docs]", "&amp; &copy;", "a\\|b", "**[site]**", "_[docs]_",
    "[ci][]", "[DOCS]", "text", "<span>[site]</span>", "[a\nb][site]", "[site](", "[]", "~~[site]~~",
    "www.example.com/[site]",
]
DEFINITIONS = [
    '[site]: https://target.example "T \\"q\\" \\\\"',
    '[site]: /target "left\\|right"',
    "[site]: </search?q=&amp;copy;>",
    "[site]: <https://t.example/a b> (paren title)",
    "[site]:\n  https://ml.example\n  'multi'",
    "[docs]: <https://docs.example/a b>",
    '[docs]: https://d.example/x_(y) "a & b"',
    "[docs]: /p?x=1&y=2",
    "[ci]: https://ci.example 'CI'",
    '[ci]: /target "a&#10;b"',
    '[docs]: /target "first\nsecond"',
    '[ci]: <a\\>b> "t\\\\"',
]


def _block(rng: random.Random) -> str:
    words = " ".join(rng.choice(FRAGMENTS) for _ in range(rng.randint(1, 4)))
    one = lambda: rng.choice(FRAGMENTS).replace("\n", " ")
    return rng.choice([
        lambda: words,
        lambda: f"- {words}\n- {one()}",
        lambda: f"1. {words}\n   {one()}",
        lambda: f"> {words}\n> {one()}",
        lambda: f"- top\n  - {words}\n\n  {one()}",
        lambda: "## " + words.replace("\n", " "),
        lambda: f"> {words}\n{one()}",
        lambda: f"```\n{words}\n```",
        lambda: f"| {one()} | {one()} |\n|---|---|\n| {one()} | {one()} |",
    ])()


def random_document(rng: random.Random) -> str:
    blocks = [_block(rng) for _ in range(rng.randint(1, 4))]
    definitions = rng.sample(DEFINITIONS, rng.randint(0, 4))
    return "\n\n".join(blocks + (["\n".join(definitions)] if definitions else []))


class ReferenceLinkRewriteTests(unittest.TestCase):
    def test_rewriting_never_changes_the_rendered_document(self):
        md = MarkdownIt("commonmark").enable("table")
        rng = random.Random(20261001)
        rewritten = 0
        for _ in range(400):
            document = random_document(rng)
            result = inline_reference_links(document)
            rewritten += result != document
            self.assertEqual(md.render(result), md.render(document), document)
        self.assertGreater(rewritten, 200)

    def test_a_line_break_in_a_title_stays_inside_the_link(self):
        segments = split_markdown_blocks('# [x]\n\n[x]: /target "a&#10;b"')
        self.assertEqual(segments[0].text, '# [x](</target> "a&#10;b")')

    def test_text_swallowed_by_broken_syntax_is_never_deleted(self):
        text = "[site]( ~~[site]~~ `[site]`\n\n[site]:\n 'multi'"
        self.assertEqual(split_markdown_blocks(text)[0].text, "[site]( ~~[site]~~ `[site]`")


if __name__ == "__main__":
    unittest.main()
