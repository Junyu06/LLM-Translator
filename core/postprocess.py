import re
from dataclasses import dataclass


@dataclass
class PostProcessOptions:
    prefer_last_marker: bool = True  # 有多个“译文”时取最后一个
    strip_quotes: bool = True
    remove_leading_labels: bool = True


_MARKERS = [
    "译文：", "译文:", "译文",
    "Translation:", "Translation：", "translation:",
    "Output:", "输出：", "输出:",
]

_QUOTE_PAIRS = {
    '"': '"',
    "'": "'",
    "“": "”",
    "‘": "’",
}


def _strip_leading_marker(text: str) -> str:
    stripped = text.lstrip()
    for mk in sorted(_MARKERS, key=len, reverse=True):
        if stripped.startswith(mk):
            return stripped[len(mk):].strip()
    return text


def _strip_paired_wrapping_quotes(text: str) -> str:
    stripped = text.strip()
    if len(stripped) < 2:
        return stripped

    closing = _QUOTE_PAIRS.get(stripped[0])
    if closing is not None and stripped[-1] == closing:
        return stripped[1:-1].strip()
    return stripped


def extract_translation(raw: str, opt: PostProcessOptions = PostProcessOptions()) -> str:
    if raw is None:
        return ""
    text = raw.strip()
    if not text:
        return ""

    # 1) 只在输出开头识别 marker，避免截断正文里的 "Translation:" 等内容。
    if opt.remove_leading_labels:
        text = _strip_leading_marker(text)

    # 2) 如果模型把“原文：...”也吐出来了，尝试截断掉原文块（保守策略）
    # 仅当出现明显标签时截断，避免误删正文
    if opt.remove_leading_labels:
        # 去掉开头一些常见标签
        text = re.sub(r"^\s*(assistant|模型|翻译|译文)\s*[:：]\s*", "", text, flags=re.IGNORECASE).strip()

    # 3) 去掉成对引号包裹
    if opt.strip_quotes:
        text = _strip_paired_wrapping_quotes(text)

    # 4) 最后清理多余空白
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text
