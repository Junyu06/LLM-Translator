from dataclasses import dataclass
import re
from typing import List


@dataclass
class SplitOptions:
    strip_each_line: bool = True
    drop_empty_lines: bool = True


@dataclass
class ContextOptions:
    min_context_chars: int = 120   # 如果上一段不足这个长度，才补上上段
    max_context_chars: int = 800   # 最终 context 上限（兜底裁剪）


@dataclass
class Segment:
    text: str
    context: str = ""
    protected: bool = False
    kind: str = "text"


def _normalize_lines(text: str, opt: SplitOptions) -> List[str]:
    if not text:
        return []
    lines = text.splitlines()
    if opt.strip_each_line:
        lines = [ln.strip() for ln in lines]
    if opt.drop_empty_lines:
        lines = [ln for ln in lines if ln]
    return lines


def split_plain(text: str, opt: SplitOptions = SplitOptions()) -> List[Segment]:
    """
    每段独立翻译，不带任何上文。
    """
    lines = _normalize_lines(text, opt)
    return [Segment(text=ln, context="") for ln in lines]


def split_with_limited_context(
    text: str,
    split_opt: SplitOptions = SplitOptions(),
    ctx_opt: ContextOptions = ContextOptions(),
) -> List[Segment]:
    """
    每段翻译时：
    - 优先使用上一段作为 context
    - 如果上一段字符数 < min_context_chars, 则补上上上一段
    - 最多只用两段上文
    """
    lines = _normalize_lines(text, split_opt)
    segments: List[Segment] = []

    for i, ln in enumerate(lines):
        context_parts: List[str] = []

        # 上一段
        if i - 1 >= 0:
            prev_1 = lines[i - 1]
            context_parts.insert(0, prev_1)

            # 不够长 → 补上上段
            if len(prev_1) < ctx_opt.min_context_chars and i - 2 >= 0:
                prev_2 = lines[i - 2]
                context_parts.insert(0, prev_2)

        context = "\n".join(context_parts).strip()

        # 最终兜底裁剪（保留末尾，更相关）
        if ctx_opt.max_context_chars > 0 and len(context) > ctx_opt.max_context_chars:
            context = context[-ctx_opt.max_context_chars:]

        segments.append(Segment(text=ln, context=context))

    return segments


_FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})")
_LIST_MARKER_RE = re.compile(r"^ {0,3}(?:[-+*]\s+\S|\d+[.)]\s+\S)")


def _segment_text(lines: List[str], protected: bool = False, kind: str = "text") -> Segment:
    return Segment(text="\n".join(lines), context="", protected=protected, kind=kind)


def _apply_segment_options(lines: List[str], opt: SplitOptions) -> List[str]:
    if opt.strip_each_line:
        lines = [ln.strip() for ln in lines]
    if opt.drop_empty_lines:
        lines = [ln for ln in lines if ln]
    return lines


def _is_blank(line: str) -> bool:
    return not line.strip()


def _is_indented(line: str) -> bool:
    return line.startswith("    ") or line.startswith("\t")


def _is_list_marker(line: str) -> bool:
    return _LIST_MARKER_RE.match(line) is not None


def _is_list_continuation(line: str) -> bool:
    return line.startswith("  ") or line.startswith("\t")


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


def _starts_non_lazy_block(lines: List[str], index: int) -> bool:
    line = lines[index]
    return (
        _FENCE_RE.match(line) is not None
        or _is_indented(line)
        or _is_table_start(lines, index)
    )


def _take_fenced_code(lines: List[str], start: int) -> tuple[List[str], int]:
    first = lines[start]
    match = _FENCE_RE.match(first)
    if match is None:
        return [first], start + 1

    fence = match.group("fence")
    fence_char = fence[0]
    min_length = len(fence)
    close_re = re.compile(rf"^ {{0,3}}{re.escape(fence_char) * min_length}{fence_char}*[ \t]*$")

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
        if not _is_blank(line) and not _starts_non_lazy_block(lines, index):
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
        if _is_list_marker(line) or _is_list_continuation(line):
            block.append(line)
            index += 1
            continue
        if not _is_blank(line) and not _starts_non_lazy_block(lines, index):
            block.append(line)
            index += 1
            continue
        if _is_blank(line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if _is_list_marker(next_line) or _is_list_continuation(next_line):
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
        if (
            _FENCE_RE.match(line)
            or _is_indented(line)
            or _is_table_start(lines, index)
            or line.lstrip().startswith(">")
            or _is_list_marker(line)
        ):
            break
        block.append(line)
        index += 1

    return block, index


def split_markdown_blocks(
    text: str,
    opt: SplitOptions = SplitOptions(strip_each_line=False, drop_empty_lines=False),
) -> List[Segment]:
    """
    Split Markdown into translation-ready blocks.

    Code, table, blockquote, and list structures are protected passthrough
    segments so later translation stages can skip them without losing layout.
    """
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
        kind = "text"

        if _FENCE_RE.match(line):
            block, index = _take_fenced_code(lines, index)
            protected = True
            kind = "fenced_code"
        elif _is_indented(line):
            block, index = _take_indented_code(lines, index)
            protected = True
            kind = "indented_code"
        elif _is_table_start(lines, index):
            block, index = _take_table(lines, index)
            protected = True
            kind = "table"
        elif line.lstrip().startswith(">"):
            block, index = _take_blockquote(lines, index)
            protected = True
            kind = "blockquote"
        elif _is_list_marker(line):
            block, index = _take_list(lines, index)
            protected = True
            kind = "list"
        else:
            block, index = _take_text(lines, index)

        block = _apply_segment_options(block, opt)
        if block or not opt.drop_empty_lines:
            segments.append(_segment_text(block, protected=protected, kind=kind))

    return segments

if __name__ == "__main__":
    text = """第一句很短
    这是第二句，但它比较长一些，用来模拟超过阈值的情况。
    第三句"""

    segs = split_with_limited_context(
        text,
        ctx_opt=ContextOptions(min_context_chars=20)
    )

    for s in segs:
        print("TEXT:", s.text)
        print("CTX:", repr(s.context))
        print("---")
