from dataclasses import dataclass

# 你可以按需扩充
_LANG_ALIASES = {
    "zh-cn": "zh",
    "zh-hans": "zh",
    "zh-hant": "zh",
    "cn": "zh",
    "chinese": "zh",
    "中文": "zh",

    "eng": "en",
    "english": "en",

    "jp": "ja",
    "jpn": "ja",
    "japanese": "ja",
}

# 给 prompt 里显示的名字（你也可以全部用英文）
_LANG_DISPLAY = {
    "zh": "中文",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
}


def normalize_lang(lang: str) -> str:
    """
    Normalize language code to short form like 'zh', 'en', 'ja', or 'auto'.
    """
    if not lang:
        return "auto"
    x = lang.strip().lower()
    if x == "auto":
        return "auto"
    return _LANG_ALIASES.get(x, x)


def is_zh(lang: str) -> bool:
    return normalize_lang(lang) == "zh"


def display_lang(lang: str) -> str:
    """
    Convert lang code to a nicer display name for prompts.
    """
    x = normalize_lang(lang)
    if x == "auto":
        return "auto"
    return _LANG_DISPLAY.get(x, x)