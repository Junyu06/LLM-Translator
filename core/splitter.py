from dataclasses import dataclass
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