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


def extract_translation(raw: str, opt: PostProcessOptions = PostProcessOptions()) -> str:
    if raw is None:
        return ""
    text = raw.strip()
    if not text:
        return ""

    # 1) 尝试按 marker 抽取（取最后一个 marker 后面的内容更安全）
    lowered = text  # 保持原样，不强制 lower（避免影响内容）
    positions = []
    for mk in _MARKERS:
        idx = lowered.rfind(mk) if opt.prefer_last_marker else lowered.find(mk)
        if idx != -1:
            positions.append((idx, mk))

    if positions:
        idx, mk = max(positions, key=lambda x: x[0])  # 取最靠后的 marker
        text = text[idx + len(mk):].strip()

    # 2) 如果模型把“原文：...”也吐出来了，尝试截断掉原文块（保守策略）
    # 仅当出现明显标签时截断，避免误删正文
    if opt.remove_leading_labels:
        # 去掉开头一些常见标签
        text = re.sub(r"^\s*(assistant|模型|翻译|译文)\s*[:：]\s*", "", text, flags=re.IGNORECASE).strip()

    # 3) 去掉成对引号包裹
    if opt.strip_quotes:
        text = text.strip()
        text = re.sub(r'^\s*[\"“”‘’\']\s*', "", text)
        text = re.sub(r'\s*[\"“”‘’\']\s*$', "", text)
        text = text.strip()

    # 4) 最后清理多余空白
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text