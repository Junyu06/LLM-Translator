"""Translation prompts, one template set per model family.

Translation models follow the prompt they were trained with much better than
a hand-written one, so each family uses its model card's wording:

- Index-Translate (bilibili): "请将以下文本翻译为{目标语言}，直接输出翻译结果，不要进行任何解释。"
- Hy-MT / HY-MT / Hunyuan-MT (Tencent): "将以下文本翻译为{目标语言}，注意只需要输出翻译后的结果，不要额外解释："
- Any other model gets a plain English instruction.

Glossary terms use each family's documented terminology wording: Index's
"要求：术语…固定译法" and Hy-MT's "参考下面的翻译：{原文} 翻译成 {译文}".
Only terms that occur in the text are sent.

Context is not put in the prompt. The pipeline sends several paragraphs in one
request instead, which both families handle as a normal translation input.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum
from typing import List, Sequence, Tuple

from .lang import en_name, is_zh, normalize_lang, zh_name

Term = Tuple[str, str]


class ModelFamily(str, Enum):
    INDEX = "index"
    HY = "hy"
    GENERIC = "generic"


# What the user can pick in settings: "auto" detects the family from the model
# name, "custom" uses the user's own template.
PROMPT_STYLES = {"auto", "index", "hy", "generic", "custom"}


def detect_family(model: str) -> ModelFamily:
    name = model.strip().lower().replace("_", "-")
    if "index-translate" in name or "indexteam" in name:
        return ModelFamily.INDEX
    if "hy-mt" in name or "hymt" in name or "hunyuan-mt" in name:
        return ModelFamily.HY
    return ModelFamily.GENERIC


def resolve_family(model: str, style: str) -> ModelFamily:
    if style in {"index", "hy", "generic"}:
        return ModelFamily(style)
    return detect_family(model)


_GLOSSARY_SEPARATORS = ("=>", "->", "→", "\t", "=")


def parse_glossary(text: str) -> List[Term]:
    """One term per line: `source = target` (also `=>`, `->`, `→` or a tab). `#` starts a comment line."""
    terms: List[Term] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for separator in _GLOSSARY_SEPARATORS:
            if separator in line:
                source, target = (part.strip() for part in line.split(separator, 1))
                if source and target:
                    terms.append((source, target))
                break
    return terms


def _is_wide(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in "WF"


def _continues_word(ch: str) -> bool:
    """A letter or digit that would make a match part of a longer word. CJK
    characters do not: `API` stands on its own in `使用API接口`."""
    return ch.isalnum() and not _is_wide(ch)


def _occurs_as_word(term: str, text: str) -> bool:
    for match in re.finditer(re.escape(term), text, re.IGNORECASE):
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end()] if match.end() < len(text) else ""
        if not (before and _continues_word(before)) and not (after and _continues_word(after)):
            return True
    return False


def terms_in(text: str, glossary: Sequence[Term]) -> List[Term]:
    """Glossary terms that occur in `text`.

    Chinese, Japanese and Korean terms match anywhere (there are no spaces
    between words); other terms match whole words, ignoring case, so `café`
    finds `CAFÉ` but not `decaféination`, and `API` finds `使用API接口`.
    """
    found: List[Term] = []
    for source, target in glossary:
        matched = source in text if any(_is_wide(ch) for ch in source) else _occurs_as_word(source, text)
        if matched:
            found.append((source, target))
    return found


def build_prompt(
    text: str,
    *,
    family: ModelFamily,
    target_lang: str,
    source_lang: str = "auto",
    detected_lang: str = "auto",
    markdown: bool = False,
    glossary: Sequence[Term] = (),
) -> str:
    """`source_lang` is what the user picked; `detected_lang` only chooses the instruction language."""
    src = normalize_lang(source_lang)
    guessed = src if src != "auto" else normalize_lang(detected_lang)
    terms = terms_in(text, glossary)

    if family == ModelFamily.INDEX:
        source = "" if src == "auto" else zh_name(src)
        kind = "Markdown 文本" if markdown else f"{source}文本"
        keep = "保留 Markdown 格式，" if markdown else ""
        if terms:
            fixed = "；".join(f"{s} 固定译为“{t}”" for s, t in terms)
            keep = keep or "保留原文结构，"
            return (
                f"请将以下{kind}翻译为{zh_name(target_lang)}。要求：术语使用固定译法（{fixed}），"
                f"{keep}直接输出翻译结果，不要进行任何解释：\n\n{text}"
            )
        return f"请将以下{kind}翻译为{zh_name(target_lang)}，{keep}直接输出翻译结果，不要进行任何解释。\n\n{text}"

    if family == ModelFamily.HY and (is_zh(guessed) or is_zh(target_lang)):
        kind = "Markdown 文本" if markdown else "文本"
        keep = "保留 Markdown 格式，" if markdown else ""
        reference = "".join(f"{s} 翻译成 {t}\n" for s, t in terms)
        reference = f"参考下面的翻译：\n{reference}\n" if terms else ""
        return f"{reference}将以下{kind}翻译为{zh_name(target_lang)}，{keep}注意只需要输出翻译后的结果，不要额外解释：\n\n{text}"

    reference = "".join(f"{s} is translated as {t}\n" for s, t in terms)
    reference = f"Refer to the following translations:\n{reference}\n" if terms else ""

    if family == ModelFamily.HY:
        kind = "Markdown text" if markdown else "text"
        keep = " Keep the Markdown formatting." if markdown else ""
        return (
            f"{reference}Translate the following {kind} into {en_name(target_lang)}.{keep} "
            f"Note that you should only output the translated result without any additional explanation:\n\n{text}"
        )

    kind = "Markdown text" if markdown else "text"
    keep = "Keep the Markdown formatting. " if markdown else ""
    return (
        f"{reference}Translate the following {kind} into {en_name(target_lang)}. {keep}"
        f"Keep the paragraph breaks. Output only the translation, without any explanation.\n\n{text}"
    )


def build_custom_prompt(
    template: str,
    text: str,
    *,
    target_lang: str,
    source_lang: str = "auto",
    glossary: Sequence[Term] = (),
) -> str:
    """Fill a user template.

    Placeholders: {text}, {target_lang} (English name), {target_lang_zh}
    (Chinese name), {source_lang} and {glossary} (one `source = target` per
    line). Without {text} the text goes after a blank line; without
    {glossary}, terms found in the text go before the template.
    """
    terms = terms_in(text, glossary)
    glossary_lines = "\n".join(f"{s} = {t}" for s, t in terms)
    src = normalize_lang(source_lang)
    values = {
        "{target_lang_zh}": zh_name(target_lang),
        "{target_lang}": en_name(target_lang),
        "{source_lang}": "" if src == "auto" else en_name(src),
        "{glossary}": glossary_lines,
    }
    prompt = template.strip()
    has_text = "{text}" in prompt
    # Fill the text last, so placeholders inside the text are left alone.
    prompt = prompt.replace("{text}", "\0")
    for placeholder, value in values.items():
        prompt = prompt.replace(placeholder, value)
    if terms and "{glossary}" not in template:
        prompt = f"Refer to the following translations:\n{glossary_lines}\n\n{prompt}"
    return prompt.replace("\0", text) if has_text else f"{prompt}\n\n{text}"
