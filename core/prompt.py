from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .lang import normalize_lang, is_zh, display_lang


class PromptPreset(str, Enum):
    AUTO = "auto"
    ZH_XX = "zh_xx"
    XX_XX = "xx_xx"
    TERMINOLOGY = "terminology"
    CONTEXTUAL = "contextual"
    FORMATTED_ZH = "formatted_zh"


@dataclass
class TerminologyHint:
    source_term: str
    target_term: str


@dataclass
class PromptOptions:
    source_lang: str = "auto"     # 'zh'/'en'/'ja'/'auto'
    target_lang: str = "en"       # 'en'/'ja'/'zh'...
    preset: PromptPreset = PromptPreset.AUTO

    terminology: Optional[TerminologyHint] = None
    context: str = ""
    src_text_with_format: str = ""


def _auto_preset(opt: PromptOptions, source_text: str) -> PromptPreset:
    if opt.src_text_with_format:
        return PromptPreset.FORMATTED_ZH
    if opt.context.strip():
        return PromptPreset.CONTEXTUAL
    if opt.terminology is not None:
        return PromptPreset.TERMINOLOGY

    src = normalize_lang(opt.source_lang)
    tgt = normalize_lang(opt.target_lang)

    if is_zh(src) or is_zh(tgt):
        return PromptPreset.ZH_XX
    return PromptPreset.XX_XX


def build_prompt(source_text: str, opt: PromptOptions) -> str:
    preset = opt.preset
    if preset == PromptPreset.AUTO:
        preset = _auto_preset(opt, source_text)

    tgt_disp = display_lang(opt.target_lang)

    # 官方模板：ZH<=>XX
    if preset == PromptPreset.ZH_XX:
        return (
            f"将以下文本翻译为{tgt_disp}，注意只需要输出翻译后的结果，不要额外解释：\n\n"
            f"{source_text}\n"
        )

    # 官方模板：XX<=>XX（不含中文）
    if preset == PromptPreset.XX_XX:
        return (
            f"Translate the following segment into {tgt_disp}, without additional explanation.\n\n"
            f"{source_text}\n"
        )

    # 官方模板：术语干预
    if preset == PromptPreset.TERMINOLOGY:
        if opt.terminology is None:
            # 兜底
            return build_prompt(source_text, PromptOptions(
                source_lang=opt.source_lang,
                target_lang=opt.target_lang,
                preset=PromptPreset.AUTO,
            ))
        return (
            "参考下面的翻译：\n"
            f"{opt.terminology.source_term} 翻译成 {opt.terminology.target_term}\n\n"
            f"将以下文本翻译为{tgt_disp}，注意只需要输出翻译后的结果，不要额外解释：\n"
            f"{source_text}\n"
        )

    # 官方模板：上下文翻译
    if preset == PromptPreset.CONTEXTUAL:
        ctx = opt.context.rstrip()
        return (
            f"{ctx}\n"
            f"参考上面的信息，把下面的文本翻译成{tgt_disp}，注意不需要翻译上文，也不要额外解释：\n"
            f"{source_text}\n"
        )

    # 官方模板：格式翻译（固定翻译为中文）
    if preset == PromptPreset.FORMATTED_ZH:
        src = opt.src_text_with_format if opt.src_text_with_format else source_text
        return (
            "将以下<source></source>之间的文本翻译为中文，注意只需要输出翻译后的结果，不要额外解释，"
            "原文中的<sn></sn>标签表示标签内文本包含格式信息，需要在译文中相应的位置尽量保留该标签。输出格式为：<target>str</target>\n\n"
            f"<source>{src}</source>\n"
        )

    # fallback
    return (
        f"Translate the following segment into {tgt_disp}, without additional explanation.\n\n"
        f"{source_text}\n"
    )