"""Split input into the units the pipeline translates and pairs up for display.

Normal mode: one unit per paragraph. A paragraph is one line, except that
lines broken in the middle of a sentence (text copied from a PDF, OCR output)
are joined back first. Blank lines stay as passthrough units so the output
keeps the original spacing.

Markdown mode: one unit per Markdown block (heading, paragraph, list,
blockquote, table), found by markdown-it-py with the same CommonMark rules
the display uses. Code, quotes that contain code, HTML blocks, thematic
breaks and reference link definitions are protected from translation;
reference links are rewritten as inline links so every block renders on
its own.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple

from markdown_it import MarkdownIt
from markdown_it.common.utils import normalizeReference


@dataclass
class Segment:
    text: str
    protected: bool = False
    kind: str = "text"

    @property
    def translatable(self) -> bool:
        return not self.protected and bool(self.text.strip())


# ---------- normal mode ----------

# A line ending in one of these closes a sentence or clause, so the next line
# starts a new paragraph.
_CLOSING_CHARS = set(".!?;:。！？；：…\"'”’)）]】」』")
_LINE_MARKER_RE = re.compile(r"^(?:[-*+•·▪●]\s|\d+[.)、]\s?|[a-zA-Z][.)]\s|#{1,6}\s|>)")
# Lines shorter than this share of the longest line in the text are headings
# or short items, not lines wrapped by the page width.
_WRAPPED_LINE_RATIO = 0.7
# Text whose longest line is narrower than this was not wrapped by a page.
_MIN_WRAP_WIDTH = 40


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _is_cjk(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in "WF"


def _continues_on_next_line(line: str, wrap_width: int) -> bool:
    stripped = line.rstrip()
    if not stripped or stripped[-1] in _CLOSING_CHARS:
        return False
    return wrap_width >= _MIN_WRAP_WIDTH and _width(stripped) >= wrap_width * _WRAPPED_LINE_RATIO


def _join_wrapped(left: str, right: str) -> str:
    if _is_cjk(left[-1]) and _is_cjk(right[0]):
        return left + right
    if left.endswith("-") and left[-2:-1].isalpha():
        return left + right
    return f"{left} {right}"


def reflow_lines(lines: List[str], wrap_width: int) -> List[str]:
    """Join lines that were broken by page width, not by the author.

    `lines` is one run of non-blank, stripped lines. `wrap_width` is the
    widest line of the whole text: a page wraps every paragraph at the same
    width, while a short run on its own (a label, a counter) says nothing
    about wrapping.
    """
    if len(lines) < 2:
        return list(lines)
    paragraphs = [lines[0]]
    previous = lines[0]
    for line in lines[1:]:
        if _continues_on_next_line(previous, wrap_width) and not _LINE_MARKER_RE.match(line):
            paragraphs[-1] = _join_wrapped(paragraphs[-1], line)
        else:
            paragraphs.append(line)
        previous = line
    return paragraphs


def split_paragraphs(text: str) -> List[Segment]:
    segments: List[Segment] = []
    run: List[str] = []
    wrap_width = max((_width(line.strip()) for line in text.splitlines()), default=0)

    def flush() -> None:
        segments.extend(Segment(text=paragraph) for paragraph in reflow_lines(run, wrap_width))
        run.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            run.append(stripped)
            continue
        flush()
        segments.append(Segment(text="", protected=True, kind="blank"))
    flush()
    return segments


# ---------- Markdown mode ----------

_MD = MarkdownIt("commonmark").enable("table")

_BLOCK_KINDS = {
    "paragraph_open": "text",
    "heading_open": "heading",
    "bullet_list_open": "list",
    "ordered_list_open": "list",
    "blockquote_open": "blockquote",
    "table_open": "table",
    "fence": "fenced_code",
    "code_block": "indented_code",
    "html_block": "html",
    "hr": "hr",
}
_PROTECTED_KINDS = {"fenced_code", "indented_code", "html", "hr"}
_CODE_TOKENS = {"fence", "code_block"}


def _top_level_blocks(tokens) -> List[Tuple[str, int, int, list]]:
    """(kind, first line, end line, tokens inside) for every top-level block."""
    blocks = []
    for index, token in enumerate(tokens):
        if token.level != 0 or token.map is None or token.type not in _BLOCK_KINDS:
            continue
        inner = []
        if token.nesting == 1:
            depth = 0
            for inner_token in tokens[index:]:
                depth += inner_token.nesting
                inner.append(inner_token)
                if depth == 0:
                    break
        blocks.append((_BLOCK_KINDS[token.type], token.map[0], token.map[1], inner))
    return blocks


def _lines_text(lines: List[str], start: int, end: int) -> str:
    part = lines[start:end]
    while part and not part[-1].strip():
        part.pop()
    while part and not part[0].strip():
        part.pop(0)
    return "\n".join(part)


def _split_list(lines: List[str], start: int, end: int, inner) -> List[Segment]:
    """A list with code in it: the code becomes its own protected block.

    An item whose first line opens the code (`- ```python`) is protected as a
    whole, marker included.
    """
    item_starts = {token.map[0] for token in inner if token.type == "list_item_open"}
    code = sorted({tuple(token.map) for token in inner if token.type in _CODE_TOKENS and token.map})
    segments: List[Segment] = []
    cursor = start
    for code_start, code_end in code:
        if code_start < cursor:
            continue  # code nested in code already taken
        before = _lines_text(lines, cursor, code_start)
        if before:
            segments.append(Segment(text=before, kind="list"))
        opens_item = code_start in item_starts
        token = next(t for t in inner if t.type in _CODE_TOKENS and t.map and t.map[0] == code_start)
        kind = "list" if opens_item else _BLOCK_KINDS[token.type]
        segments.append(Segment(text=_lines_text(lines, code_start, code_end), protected=True, kind=kind))
        cursor = code_end
    rest = _lines_text(lines, cursor, end)
    if rest:
        segments.append(Segment(text=rest, kind="list"))
    return segments


def split_markdown_blocks(text: str) -> List[Segment]:
    """Split Markdown into blocks. Code and other non-prose blocks are protected; the rest is translated."""
    if not text:
        return []

    env: dict = {}
    tokens = _MD.parse(text, env)
    lines = text.split("\n")
    segments: List[Segment] = []
    covered_until = 0

    def add_definitions(until: int) -> None:
        # Lines no block covers are reference link definitions (markdown-it
        # keeps them in env, not in the token stream).
        definitions = _lines_text(lines, covered_until, until)
        if definitions:
            segments.append(Segment(text=definitions, protected=True, kind="link_definitions"))

    for kind, start, end, inner in _top_level_blocks(tokens):
        add_definitions(start)
        covered_until = end
        block = _lines_text(lines, start, end)
        if not block:
            continue
        has_code = any(token.type in _CODE_TOKENS for token in inner)
        if kind == "list" and has_code:
            segments.extend(_split_list(lines, start, end, inner))
            continue
        # A quote that contains code is kept whole; splitting it would break the quote.
        protected = kind in _PROTECTED_KINDS or (kind == "blockquote" and has_code)
        segments.append(Segment(text=block, protected=protected, kind=kind))
    add_definitions(len(lines))

    return _inline_reference_links(segments, env.get("references", {}))


def list_items(text: str) -> List[str]:
    """Split a list block into its top-level items; sub-items and continuation lines stay with their item."""
    lines = text.split("\n")
    starts = [
        token.map[0]
        for token in _MD.parse(text)
        if token.type == "list_item_open" and token.level == 1 and token.map
    ]
    if not starts:
        return [text]
    starts[0] = 0
    bounds = starts + [len(lines)]
    return ["\n".join(lines[bounds[i]:bounds[i + 1]]).rstrip("\n") for i in range(len(starts))]


_DEFINITION_RE = re.compile(
    r"""^ {0,3}\[(?P<label>[^\]]+)\]:[ \t]*(?P<url><[^>\n]*>|\S+)(?:[ \t]+(?P<title>"[^"\n]*"|'[^'\n]*'|\([^)\n]*\)))?[ \t]*$"""
)
# [text][label], [text][] and [text]; not the label half of another link, and
# not an inline link or a definition.
_REFERENCE_LINK_RE = re.compile(r"(?<![\]\\])\[(?P<text>(?:[^\[\]\\]|\\.)+)\](?:\[(?P<label>[^\[\]]*)\])?(?![(:\[])")
_CODE_SPAN_RE = re.compile(r"(`+).+?\1", re.DOTALL)


def _link_targets(segments: List[Segment], references: Dict[str, dict]) -> Dict[str, str]:
    """Label -> inline link destination. One-line definitions keep their exact
    text (an `<...>` destination stays valid); others use markdown-it's parse."""
    targets: Dict[str, str] = {}
    for segment in segments:
        if segment.kind != "link_definitions":
            continue
        for line in segment.text.splitlines():
            match = _DEFINITION_RE.match(line)
            if match:
                title = f" {match.group('title')}" if match.group("title") else ""
                targets.setdefault(normalizeReference(match.group("label")), f"{match.group('url')}{title}")
    for label, reference in references.items():
        if label not in targets:
            title = reference.get("title") or ""
            title = ' "{}"'.format(title.replace('"', '\\"')) if title else ""
            targets[label] = f"<{reference['href']}>{title}"
    return targets


def _inline_reference_links(segments: List[Segment], references: Dict[str, dict]) -> List[Segment]:
    """Rewrite reference links as inline links: `[the docs][site]` -> `[the docs](https://...)`.

    A reference link only works with its definition, which lives in another
    block, and its label is easy for a model to translate. As an inline link
    each block carries its own URL and renders on its own. Code spans are left
    alone.
    """
    targets = _link_targets(segments, references)
    if not targets:
        return segments

    def inline(match: re.Match) -> str:
        label = match.group("label")
        target = targets.get(normalizeReference(label if label else match.group("text")))
        return f"[{match.group('text')}]({target})" if target else match.group(0)

    def rewrite(text: str) -> str:
        parts, last = [], 0
        for code in _CODE_SPAN_RE.finditer(text):
            parts.append(_REFERENCE_LINK_RE.sub(inline, text[last:code.start()]))
            parts.append(code.group(0))
            last = code.end()
        parts.append(_REFERENCE_LINK_RE.sub(inline, text[last:]))
        return "".join(parts)

    for segment in segments:
        if segment.translatable:
            segment.text = rewrite(segment.text)
    return segments
