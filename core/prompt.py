"""Translation prompts, one template set per model family.

Translation models follow the prompt they were trained with much better than
a hand-written one, so each family uses its model card's wording:

- Index-Translate (bilibili): "请将以下文本翻译为{目标语言}，直接输出翻译结果，不要进行任何解释。"
- Hy-MT / HY-MT / Hunyuan-MT (Tencent): "将以下文本翻译为{目标语言}，注意只需要输出翻译后的结果，不要额外解释："
- Any other model gets a plain English instruction.

Context is not put in the prompt. The pipeline sends several paragraphs in one
request instead, which both families handle as a normal translation input.
"""

from __future__ import annotations

from enum import Enum

from .lang import en_name, is_zh, normalize_lang, zh_name


class ModelFamily(str, Enum):
    INDEX = "index"
    HY = "hy"
    GENERIC = "generic"


def detect_family(model: str) -> ModelFamily:
    name = model.strip().lower().replace("_", "-")
    if "index-translate" in name or "indexteam" in name:
        return ModelFamily.INDEX
    if "hy-mt" in name or "hymt" in name or "hunyuan-mt" in name:
        return ModelFamily.HY
    return ModelFamily.GENERIC


def build_prompt(
    text: str,
    *,
    family: ModelFamily,
    target_lang: str,
    source_lang: str = "auto",
    detected_lang: str = "auto",
    markdown: bool = False,
) -> str:
    """`source_lang` is what the user picked; `detected_lang` only chooses the instruction language."""
    src = normalize_lang(source_lang)
    guessed = src if src != "auto" else normalize_lang(detected_lang)

    if family == ModelFamily.INDEX:
        source = "" if src == "auto" else zh_name(src)
        kind = "Markdown 文本" if markdown else f"{source}文本"
        keep = "保留 Markdown 格式，" if markdown else ""
        return f"请将以下{kind}翻译为{zh_name(target_lang)}，{keep}直接输出翻译结果，不要进行任何解释。\n\n{text}"

    if family == ModelFamily.HY and (is_zh(guessed) or is_zh(target_lang)):
        kind = "Markdown 文本" if markdown else "文本"
        keep = "保留 Markdown 格式，" if markdown else ""
        return f"将以下{kind}翻译为{zh_name(target_lang)}，{keep}注意只需要输出翻译后的结果，不要额外解释：\n\n{text}"

    if family == ModelFamily.HY:
        kind = "Markdown text" if markdown else "text"
        keep = " Keep the Markdown formatting." if markdown else ""
        return (
            f"Translate the following {kind} into {en_name(target_lang)}.{keep} "
            f"Note that you should only output the translated result without any additional explanation:\n\n{text}"
        )

    kind = "Markdown text" if markdown else "text"
    keep = "Keep the Markdown formatting. " if markdown else ""
    return (
        f"Translate the following {kind} into {en_name(target_lang)}. {keep}"
        f"Keep the paragraph breaks. Output only the translation, without any explanation.\n\n{text}"
    )
