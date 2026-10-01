"""Clean up what a translation model returns around the translation itself."""

import re

_LABELS = [
    "译文：", "译文:",
    "翻译：", "翻译:",
    "Translation:", "Translation：", "translation:",
    "Output:", "输出：", "输出:",
]

_QUOTE_PAIRS = {
    '"': '"',
    "'": "'",
    "“": "”",
    "‘": "’",
    "「": "」",
}

_THINK_RE = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL)


def strip_reasoning(text: str) -> str:
    """Drop a leading <think> block in case the server ignored think=false."""
    return _THINK_RE.sub("", text, count=1)


def _strip_leading_label(text: str) -> str:
    for label in sorted(_LABELS, key=len, reverse=True):
        if text.startswith(label):
            return text[len(label):].lstrip()
    return text


def _is_wrapped_in_quotes(text: str) -> bool:
    return len(text) >= 2 and _QUOTE_PAIRS.get(text[0]) == text[-1]


def extract_translation(raw: str, source: str = "", *, keep_format: bool = False) -> str:
    """Return the translation without labels, wrapping quotes, or stray blank lines.

    Wrapping quotes are removed only when the source was not quoted itself, so
    a translated quotation keeps its quotes. `keep_format` leaves Markdown
    output untouched apart from surrounding whitespace.
    """
    if not raw:
        return ""
    text = strip_reasoning(raw).strip()
    if keep_format or not text:
        return text

    text = _strip_leading_label(text)
    if _is_wrapped_in_quotes(text) and not _is_wrapped_in_quotes(source.strip()):
        text = text[1:-1].strip()

    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
