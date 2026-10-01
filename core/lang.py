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

# Translation models are trained with full language names: Chinese names in
# Chinese prompts, English names in English prompts.
_ZH_NAMES = {
    "zh": "中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "de": "德语",
    "es": "西班牙语",
    "ru": "俄语",
}

_EN_NAMES = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
}


def normalize_lang(lang: str) -> str:
    """Normalize a language code to a short form like 'zh', 'en', 'ja', or 'auto'."""
    if not lang:
        return "auto"
    x = lang.strip().lower()
    if x == "auto":
        return "auto"
    return _LANG_ALIASES.get(x, x)


def is_zh(lang: str) -> bool:
    return normalize_lang(lang) == "zh"


def zh_name(lang: str) -> str:
    x = normalize_lang(lang)
    return _ZH_NAMES.get(x, x)


def en_name(lang: str) -> str:
    x = normalize_lang(lang)
    return _EN_NAMES.get(x, x)
