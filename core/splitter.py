"""Split input into the units the pipeline translates and pairs up for display.

Normal mode: one unit per paragraph. A paragraph is one line, except that
lines broken in the middle of a sentence (text copied from a PDF, OCR output)
are joined back first. Blank lines stay as passthrough units so the output
keeps the original spacing.

Markdown mode: one unit per Markdown block (heading, paragraph, list,
blockquote, table). Code, quotes that contain code, and reference link
definitions are protected from translation; reference links are rewritten
as inline links so every block renders on its own.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List


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

_FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})")
_LIST_MARKER_RE = re.compile(r"^ {0,3}(?:[-+*]\s+\S|\d+[.)]\s+\S)")
_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:\s|$)")
_ANY_LIST_MARKER_RE = re.compile(r"^ *(?P<marker>[-+*]|\d+[.)])\s+\S")
_DEFINITION_START_RE = re.compile(r"^ {0,3}\[[^\]]+\]:[ \t]*$")
_DEFINITION_TITLE_RE = re.compile(r"""^[ \t]*("[^"]*"|'[^']*'|\([^)]*\))[ \t]*$""")


def _is_blank(line: str) -> bool:
    return not line.strip()


def _is_indented(line: str) -> bool:
    return line.startswith("    ") or line.startswith("\t")


def _is_list_marker(line: str) -> bool:
    return _LIST_MARKER_RE.match(line) is not None


def _is_list_continuation(line: str) -> bool:
    return line.startswith("  ") or line.startswith("\t")


def _is_heading(line: str) -> bool:
    return _HEADING_RE.match(line) is not None


def _is_any_fence(line: str) -> bool:
    """A code fence at any indentation, including one nested in a list item."""
    stripped = line.lstrip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def _without_list_marker(line: str) -> str:
    match = _LIST_MARKER_RE.match(line)
    return line[match.end() - 1:] if match else line


def _starts_item_with_code(line: str) -> bool:
    """`- ```python`: a list item whose first line opens a code fence."""
    return _is_list_marker(line) and _is_any_fence(_without_list_marker(line))


def _take_list_item_with_code(lines: List[str], start: int) -> tuple[List[str], int]:
    fence = _without_list_marker(lines[start]).lstrip()
    marker = fence[0] * (len(fence) - len(fence.lstrip(fence[0])))
    index = start + 1
    while index < len(lines):
        if lines[index].lstrip().startswith(marker):
            return lines[start:index + 1], index + 1
        index += 1
    return lines[start:], len(lines)


def list_items(text: str) -> List[str]:
    """Split a list block into its top-level items; sub-items and continuation lines stay with their item."""
    lines = text.split("\n")
    top = _indent(lines[0])
    items: List[str] = []
    for line in lines:
        if not items or (_ANY_LIST_MARKER_RE.match(line) and _indent(line) <= top):
            items.append(line)
        else:
            items[-1] += "\n" + line
    return items


def _quote_contains_code(block: List[str]) -> bool:
    """Fenced or indented code anywhere inside a (possibly nested) blockquote."""
    for line in block:
        content = line
        while content.lstrip().startswith(">"):
            content = content.lstrip()[1:]
            if content.startswith(" "):
                content = content[1:]
        if _is_any_fence(_without_list_marker(content)) or (_is_indented(content) and content.strip()):
            return True
    return False


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped:
        return False

    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if not cells:
        return False

    return all(re.fullmatch(r":?-{3,}:?", cell or "") is not None for cell in cells)


def _is_table_start(lines: List[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and "|" in lines[index]
        and _is_table_separator(lines[index + 1])
    )


def _starts_new_block(lines: List[str], index: int) -> bool:
    """Lines that end a lazy continuation of a list or blockquote."""
    line = lines[index]
    return (
        _FENCE_RE.match(line) is not None
        or _is_indented(line)
        or _is_table_start(lines, index)
        or _is_heading(line)
    )


def _take_fenced_code(lines: List[str], start: int) -> tuple[List[str], int]:
    match = _FENCE_RE.match(lines[start])
    if match is None:
        return [lines[start]], start + 1

    fence = match.group("fence")
    fence_char = fence[0]
    close_re = re.compile(rf"^ {{0,3}}{re.escape(fence_char) * len(fence)}{fence_char}*[ \t]*$")

    index = start + 1
    while index < len(lines):
        if close_re.match(lines[index]):
            return lines[start:index + 1], index + 1
        index += 1

    return lines[start:], len(lines)


def _take_indented_code(lines: List[str], start: int) -> tuple[List[str], int]:
    index = start
    block: List[str] = []

    while index < len(lines):
        line = lines[index]
        if _is_indented(line):
            block.append(line)
            index += 1
            continue
        if _is_blank(line) and index + 1 < len(lines) and _is_indented(lines[index + 1]):
            block.append(line)
            index += 1
            continue
        break

    return block, index


def _take_table(lines: List[str], start: int) -> tuple[List[str], int]:
    index = start
    block: List[str] = []

    while index < len(lines) and not _is_blank(lines[index]) and "|" in lines[index]:
        block.append(lines[index])
        index += 1

    return block, index


def _take_blockquote(lines: List[str], start: int) -> tuple[List[str], int]:
    index = start
    block: List[str] = []

    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith(">"):
            block.append(line)
            index += 1
            continue
        if not _is_blank(line) and not _starts_new_block(lines, index) and not _is_list_marker(line):
            block.append(line)
            index += 1
            continue
        if _is_blank(line) and index + 1 < len(lines) and lines[index + 1].lstrip().startswith(">"):
            block.append(line)
            index += 1
            continue
        break

    return block, index


def _indent(line: str) -> int:
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip(" "))


def _continues_item(indent: int, open_levels: List[int]) -> bool:
    return any(level <= indent < level + 4 for level in open_levels)


def _close_deeper(open_levels: List[int], indent: int) -> None:
    while open_levels and open_levels[-1] > indent:
        open_levels.pop()


def _take_list(lines: List[str], start: int) -> tuple[List[str], int]:
    index = start
    block: List[str] = []
    # Where the text of each open item starts, outermost first. A paragraph
    # after a blank line belongs to the list when it is indented to one of
    # these levels (and less than four more, which would make it code). Going
    # back to a shallower indent closes the deeper items.
    open_levels: List[int] = []

    while index < len(lines):
        line = lines[index]
        # Code nested in a list item becomes its own protected block.
        if _is_any_fence(line) or (block and _starts_item_with_code(line)):
            break
        marker = _ANY_LIST_MARKER_RE.match(line)
        # A marker indented four past the deepest item text is code, not an item.
        if marker and (not open_levels or _indent(line) < open_levels[-1] + 4):
            _close_deeper(open_levels, _indent(line))
            open_levels.append(marker.end("marker") + 1)
            block.append(line)
            index += 1
            continue
        if _is_list_continuation(line) and not _is_blank(line):
            block.append(line)
            index += 1
            continue
        if not _is_blank(line) and not _starts_new_block(lines, index) and not line.lstrip().startswith(">"):
            block.append(line)
            index += 1
            continue
        if _is_blank(line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if _is_list_marker(next_line) or (
                not _is_blank(next_line) and _continues_item(_indent(next_line), open_levels)
            ):
                if not _is_list_marker(next_line):
                    _close_deeper(open_levels, _indent(next_line))
                block.append(line)
                index += 1
                continue
        break

    return block, index


def _take_text(lines: List[str], start: int) -> tuple[List[str], int]:
    index = start
    block: List[str] = []

    while index < len(lines):
        line = lines[index]
        if _is_blank(line):
            break
        if block and (
            _FENCE_RE.match(line)
            or _is_table_start(lines, index)
            or line.lstrip().startswith(">")
            or _is_list_marker(line)
            or _is_heading(line)
        ):
            break
        block.append(line)
        index += 1

    return block, index


def split_markdown_blocks(text: str) -> List[Segment]:
    """Split Markdown into blocks. Code blocks are protected; everything else is translated."""
    if not text:
        return []

    lines = text.splitlines()
    segments: List[Segment] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if _is_blank(line):
            index += 1
            continue

        protected = False
        if _FENCE_RE.match(line):
            block, index = _take_fenced_code(lines, index)
            protected, kind = True, "fenced_code"
        elif _is_indented(line):
            block, index = _take_indented_code(lines, index)
            protected, kind = True, "indented_code"
        elif _is_heading(line):
            block, index = [line], index + 1
            kind = "heading"
        elif _is_table_start(lines, index):
            block, index = _take_table(lines, index)
            kind = "table"
        elif line.lstrip().startswith(">"):
            block, index = _take_blockquote(lines, index)
            kind = "blockquote"
            # A quote that contains code is kept whole; splitting it would break the quote.
            if _quote_contains_code(block):
                protected = True
        elif _starts_item_with_code(line):
            block, index = _take_list_item_with_code(lines, index)
            protected, kind = True, "list"
        elif _is_list_marker(line):
            block, index = _take_list(lines, index)
            kind = "list"
        else:
            block, index = _take_text(lines, index)
            kind = "text"
            # Reference link definitions carry URLs, not prose.
            if _is_definition_block(block):
                protected, kind = True, "link_definitions"

        segments.append(Segment(text="\n".join(block), protected=protected, kind=kind))

    return _inline_reference_links(segments)


_DEFINITION_RE = re.compile(
    r"""^ {0,3}\[(?P<label>[^\]]+)\]:[ \t]*(?P<url><[^>\n]*>|\S+)(?:[ \t]+(?P<title>"[^"\n]*"|'[^'\n]*'|\([^)\n]*\)))?[ \t]*$"""
)
# [text][label], [text][] and [text]; not the label half of another link, and
# not an inline link or a definition.
_REFERENCE_LINK_RE = re.compile(r"(?<![\]\\])\[(?P<text>(?:[^\[\]\\]|\\.)+)\](?:\[(?P<label>[^\[\]]*)\])?(?![(:\[])")
_CODE_SPAN_RE = re.compile(r"(`+).+?\1", re.DOTALL)


def _is_definition_block(block: List[str]) -> bool:
    """Every line belongs to a definition: `[label]: url "title"`, or the URL
    and title on following lines. A definition cannot interrupt a paragraph,
    so a block that starts with prose is not one."""
    if not block:
        return False
    after_start = after_definition = False
    for line in block:
        if _DEFINITION_RE.match(line):
            after_start, after_definition = False, True
        elif _DEFINITION_START_RE.match(line):
            after_start, after_definition = True, False
        elif after_start and line[:1].isspace() and line.strip():
            after_definition = True
        elif not (after_definition and _DEFINITION_TITLE_RE.match(line)):
            return False
    return True


def _normalize_label(label: str) -> str:
    return " ".join(label.split()).lower()


def _inline_reference_links(segments: List[Segment]) -> List[Segment]:
    """Rewrite reference links as inline links: `[the docs][site]` -> `[the docs](https://...)`.

    A reference link only works with its definition, which lives in another
    block, and its label is easy for a model to translate. As an inline link
    each block carries its own URL and renders on its own. Code spans are left
    alone; definitions spread over several lines are not rewritten.
    """
    targets = {}
    for segment in segments:
        if segment.kind != "link_definitions":
            continue
        for line in segment.text.splitlines():
            match = _DEFINITION_RE.match(line)
            if match:
                url = match.group("url")  # <...> stays: it is valid in an inline link too
                title = f" {match.group('title')}" if match.group("title") else ""
                targets.setdefault(_normalize_label(match.group("label")), f"{url}{title}")
    if not targets:
        return segments

    def inline(match: re.Match) -> str:
        label = match.group("label")
        target = targets.get(_normalize_label(label if label else match.group("text")))
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
