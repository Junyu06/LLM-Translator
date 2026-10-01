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
# The label part of a Markdown reference link: [text][label]
_REFERENCE_LABEL_RE = re.compile(r"(?<=\]\[)([^\]]*)(?=\])")


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


def restore_reference_labels(source: str, translation: str) -> str:
    """Put back reference-link labels the model translated ([文档][网站] -> [文档][site]).

    Labels are matched by order, and only when both texts have the same number.
    """
    labels = _REFERENCE_LABEL_RE.findall(source)
    if not labels or len(_REFERENCE_LABEL_RE.findall(translation)) != len(labels):
        return translation
    remaining = iter(labels)
    return _REFERENCE_LABEL_RE.sub(lambda _: next(remaining), translation)


def extract_translation(raw: str, source: str = "", *, keep_format: bool = False) -> str:
    """Return the translation without labels, wrapping quotes, or stray blank lines.

    Wrapping quotes are removed only when the source was not quoted itself, so
    a translated quotation keeps its quotes. `keep_format` leaves Markdown
    output untouched apart from surrounding whitespace and reference-link labels.
    """
    if not raw:
        return ""
    text = strip_reasoning(raw).strip()
    if keep_format:
        return restore_reference_labels(source, text)
    if not text:
        return text

    text = _strip_leading_label(text)
    if _is_wrapped_in_quotes(text) and not _is_wrapped_in_quotes(source.strip()):
        text = text[1:-1].strip()

    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
