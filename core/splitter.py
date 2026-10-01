"""Split input into the units the pipeline translates and pairs up for display.

Normal mode: one unit per paragraph. A paragraph is one line, except that
lines broken in the middle of a sentence (text copied from a PDF, OCR output)
are joined back first. Blank lines stay as passthrough units so the output
keeps the original spacing.

Markdown mode: one unit per Markdown block (heading, paragraph, list,
blockquote, table). Only code is protected from translation.
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
# Lines shorter than this share of the longest line in their run are headings
# or short items, not lines wrapped by the page width.
_WRAPPED_LINE_RATIO = 0.7
_MIN_WRAP_WIDTH = 30


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


def reflow_lines(lines: List[str]) -> List[str]:
    """Join lines that were broken by page width, not by the author.

    `lines` is one run of non-blank, stripped lines.
    """
    if len(lines) < 2:
        return list(lines)
    wrap_width = max(_width(line) for line in lines)
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

    def flush() -> None:
        segments.extend(Segment(text=paragraph) for paragraph in reflow_lines(run))
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


def _take_list(lines: List[str], start: int) -> tuple[List[str], int]:
    index = start
    block: List[str] = []

    while index < len(lines):
        line = lines[index]
        if _is_list_marker(line) or (_is_list_continuation(line) and not _is_blank(line)):
            block.append(line)
            index += 1
            continue
        if not _is_blank(line) and not _starts_new_block(lines, index) and not line.lstrip().startswith(">"):
            block.append(line)
            index += 1
            continue
        if _is_blank(line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if _is_list_marker(next_line) or (_is_list_continuation(next_line) and not _is_indented(next_line)):
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
        elif _is_list_marker(line):
            block, index = _take_list(lines, index)
            kind = "list"
        else:
            block, index = _take_text(lines, index)
            kind = "text"

        segments.append(Segment(text="\n".join(block), protected=protected, kind=kind))

    return segments
