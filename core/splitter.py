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
import threading
from typing import List, Tuple

from markdown_it import MarkdownIt, rules_inline


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

    text = inline_reference_links(text)
    tokens = _MD.parse(text)
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

    return segments


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


# ---------- reference links ----------
#
# `[the docs][site]`, `[Site][]` and `[site]` only work next to their
# definition, and a model translating `[常见问题][]` breaks the second and
# third kind. So before splitting, every reference link becomes an inline link
# (`[the docs](<https://...>)`). markdown-it-py finds them with the same
# CommonMark rules that render them, so code spans, URLs, inline links and
# nested brackets are handled the way the display handles them. Only the part
# after the link text changes (`[site]`, `[]` or nothing becomes `(<url>)`),
# which never crosses a line or touches container markers.

_recorder = threading.local()
_URL_START_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
# What follows the link text of a reference link: nothing, `[]`, or `[label]`.
_LABEL_TAIL_RE = re.compile(r"(?:\[[^\[\]\n]*\])?")


def _recording(rule, label_offset: int, disable_nested: bool, url_attr: str):
    def wrapped(state, silent):
        start = state.pos
        first_token = len(state.tokens)
        label_end = state.md.helpers.parseLinkLabel(state, start + label_offset, disable_nested) if state.src[start:start + label_offset + 1].endswith("[") else -1
        ok = rule(state, silent)
        spans = getattr(_recorder, "spans", None)
        if not ok or silent or spans is None or label_end < 0 or len(state.tokens) <= first_token:
            return ok
        end = state.pos
        tail = state.src[label_end + 1:end]
        if tail.startswith("(") and tail.endswith(")"):
            # An inline link already; its destination is not plain text.
            _recorder.not_text.append((state.src, start, end))
            return ok
        # Anything else after the link text means the parser recovered from
        # broken syntax (`[a]( ...`) and swallowed text; replacing it would
        # delete that text, so such a link is left as it is.
        if not _LABEL_TAIL_RE.fullmatch(tail):
            _recorder.unsafe = True
            return ok
        # Pending plain text is flushed first, so the link is not always the first new token.
        token = next((t for t in state.tokens[first_token:] if t.type in ("link_open", "image")), None)
        url = token.attrGet(url_attr) if token else None
        if url is not None:
            spans.append((state.src, start, label_end + 1, end, str(url), str(token.attrGet("title") or "")))
        return ok

    return wrapped


def _not_text(rule):
    """Record where a code span or an autolink sits: a URL there is not a bare URL."""
    def wrapped(state, silent):
        start = state.pos
        ok = rule(state, silent)
        if ok and not silent and getattr(_recorder, "spans", None) is not None:
            _recorder.not_text.append((state.src, start, state.pos))
        return ok

    return wrapped


_MD.inline.ruler.at("link", _recording(rules_inline.link, 0, True, "href"))
_MD.inline.ruler.at("image", _recording(rules_inline.image, 1, False, "src"))
_MD.inline.ruler.at("backticks", _not_text(rules_inline.backtick))
_MD.inline.ruler.at("autolink", _not_text(rules_inline.autolink))


def _has_open_inline_link(content: str, not_text: List[Tuple[int, int]]) -> bool:
    """`](` that is not part of a finished inline link, code span or autolink."""
    for match in re.finditer(r"\]\(", content):
        if not any(start <= match.start() < end for start, end in not_text):
            return True
    return False


def _inside_bare_url(content: str, link_start: int, not_text: List[Tuple[int, int]]) -> bool:
    """Whether a URL in plain text runs, without a space, up to the link.

    The display renders such a URL as one autolink (GitHub style), the
    brackets included. A URL inside a code span or a link destination is not
    plain text and does not count.
    """
    run_start = link_start
    while run_start > 0 and not content[run_start - 1].isspace() and content[run_start - 1] != "<":
        run_start -= 1
    for match in _URL_START_RE.finditer(content, run_start, link_start):
        if not any(start <= match.start() < end for start, end in not_text):
            return True
    return False


def _markdown_literal(value: str) -> str:
    """Write a parsed (already decoded) value back so it parses to itself:
    no entity is decoded twice, no pipe splits a table cell, no line break
    splits the block."""
    return (
        value.replace("\\", "\\\\").replace("&", "&amp;").replace("|", "\\|")
        .replace("\r", "&#13;").replace("\n", "&#10;")
    )


def _inline_destination(url: str, title: str) -> str:
    destination = _markdown_literal(url).replace("<", "\\<").replace(">", "\\>")
    if not title:
        return f"(<{destination}>)"
    return f'(<{destination}> "{_markdown_literal(title).replace(chr(34), chr(92) + chr(34))}")'


def _content_line_starts(lines: List[str], first: int, content: str, cursors: dict, in_table: bool) -> List[int | None]:
    """Where each line of an inline token's content starts in the text, or None if it cannot be placed.

    A paragraph line is the end of its source line (container markers come
    first). Table cells share a line, so each is looked for after the one
    before it (`cursors` remembers how far each line has been used).
    """
    starts: List[int | None] = []
    offset = sum(len(line) + 1 for line in lines[:first])
    for index, content_line in enumerate(content.split("\n")):
        number = first + index
        if number >= len(lines):
            starts.append(None)
            continue
        line = lines[number]
        if in_table and "\\|" in line:
            # A table cell's content has `\|` unescaped, so it no longer matches
            # its source and could match across cells. Leave such a line alone.
            cursors[number] = len(line) + 1
            starts.append(None)
            offset += len(line) + 1
            continue
        from_column = cursors.get(number, 0)
        suffix = len(line.rstrip()) - len(content_line)
        if line.rstrip().endswith(content_line) and suffix >= from_column and line.find(content_line, from_column) == suffix:
            column = suffix
        else:
            found = line.find(content_line, from_column)
            column = found if found >= 0 else None
        # A cell that cannot be placed (an escaped pipe, a tab) leaves the rest
        # of its line unplaced too, so no later cell is looked for inside it.
        cursors[number] = len(line) + 1 if column is None else column + len(content_line)
        starts.append(None if column is None else offset + column)
        offset += len(line) + 1
    return starts


def inline_reference_links(text: str) -> str:
    env: dict = {}
    tokens = _MD.parse(text, env)
    if not env.get("references"):
        return text
    lines = text.split("\n")
    edits = []
    cursors: dict = {}
    in_table = False
    for token in tokens:
        if token.type in ("table_open", "table_close"):
            in_table = token.type == "table_open"
        if token.type != "inline" or token.map is None:
            continue
        _recorder.spans = []
        _recorder.not_text = []
        _recorder.unsafe = False
        try:
            _MD.inline.parse(token.content, _MD, env, [])
            spans = _recorder.spans
            not_text = [(start, end) for source, start, end in _recorder.not_text if source is token.content]
        finally:
            _recorder.spans = None
        # Placed even without links, so the next cell on the line is looked for after this one.
        line_starts = _content_line_starts(lines, token.map[0], token.content, cursors, in_table)
        # An unfinished `[text](` would be completed by the `)` an inline link
        # adds, turning text before it into a link. Leave such a paragraph alone.
        if not spans or _recorder.unsafe or _has_open_inline_link(token.content, not_text):
            continue
        content_offsets = []
        offset = 0
        for content_line in token.content.split("\n"):
            content_offsets.append(offset)
            offset += len(content_line) + 1
        for source, link_start, start, end, url, title in spans:
            # Image alt text is parsed on its own, with its own positions.
            if source is not token.content:
                continue
            # Inside a bare URL the display (GFM autolinks) shows one link; leave it.
            if _inside_bare_url(token.content, link_start, not_text):
                continue
            index = max(i for i, value in enumerate(content_offsets) if value <= start)
            if line_starts[index] is None or "\n" in token.content[start:end]:
                continue
            at = line_starts[index] + start - content_offsets[index]
            if text[at:at + end - start] != token.content[start:end]:
                continue
            edits.append((at, at + end - start, _inline_destination(url, title)))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text
