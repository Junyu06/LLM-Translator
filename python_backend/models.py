from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


LANGUAGES = {"auto", "zh", "en", "ja", "ko", "fr", "de", "es", "ru"}
TARGET_LANGUAGES = LANGUAGES - {"auto"}
OUTPUT_MODES = {"translations_only", "interleaved"}
TRANSLATION_MODES = {"normal", "markdown"}
LAYOUTS = {"vertical", "horizontal"}
MODES = {"local", "http"}
THEMES = {"light", "dark", "system"}
UI_LANGUAGES = {"en", "zh"}


def _require_string_choice(field: str, value: Any, choices: set[str]) -> None:
    if not isinstance(value, str) or value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"Invalid {field}: expected one of {allowed}.")


def _require_bool(field: str, value: Any) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"Invalid {field}: expected boolean.")


def _require_int(field: str, value: Any, *, minimum: int | None = None) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Invalid {field}: expected integer.")
    if minimum is not None and value < minimum:
        raise ValueError(f"Invalid {field}: expected integer >= {minimum}.")


@dataclass
class AppConfig:
    source_lang: str = "auto"
    target_lang: str = "zh"
    collapse_newlines: bool = False
    output_mode: str = "translations_only"
    translation_mode: str = "normal"
    layout: str = "vertical"
    mode: str = "local"
    host: str = "http://127.0.0.1:11434"
    model: str = "demonbyron/HY-MT1.5-1.8B"
    font_size: int = 14
    hotkey_enabled: bool = True
    minimize_to_tray: bool = True
    theme: str = "system"
    ui_lang: str = "en"

    def __post_init__(self) -> None:
        _require_string_choice("source_lang", self.source_lang, LANGUAGES)
        _require_string_choice("target_lang", self.target_lang, TARGET_LANGUAGES)
        _require_bool("collapse_newlines", self.collapse_newlines)
        _require_string_choice("output_mode", self.output_mode, OUTPUT_MODES)
        _require_string_choice("translation_mode", self.translation_mode, TRANSLATION_MODES)
        _require_string_choice("layout", self.layout, LAYOUTS)
        _require_string_choice("mode", self.mode, MODES)
        if not isinstance(self.host, str):
            raise ValueError("Invalid host: expected string.")
        if not isinstance(self.model, str):
            raise ValueError("Invalid model: expected string.")
        _require_int("font_size", self.font_size, minimum=1)
        _require_bool("hotkey_enabled", self.hotkey_enabled)
        _require_bool("minimize_to_tray", self.minimize_to_tray)
        _require_string_choice("theme", self.theme, THEMES)
        _require_string_choice("ui_lang", self.ui_lang, UI_LANGUAGES)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TranslationRequest:
    text: str
    source_lang: str = "auto"
    target_lang: str = "zh"
    collapse_newlines: bool = False
    output_mode: str = "translations_only"
    translation_mode: str = "normal"
    model: str = "demonbyron/HY-MT1.5-1.8B"
    mode: str = "local"
    host: str = "http://127.0.0.1:11434"
    max_chars: int = 50000
    max_segments: int = 200
    max_segment_chars: int = 8000

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise ValueError("Invalid text: expected string.")
        _require_string_choice("source_lang", self.source_lang, LANGUAGES)
        _require_string_choice("target_lang", self.target_lang, TARGET_LANGUAGES)
        _require_bool("collapse_newlines", self.collapse_newlines)
        _require_string_choice("output_mode", self.output_mode, OUTPUT_MODES)
        _require_string_choice("translation_mode", self.translation_mode, TRANSLATION_MODES)
        if not isinstance(self.model, str):
            raise ValueError("Invalid model: expected string.")
        _require_string_choice("mode", self.mode, MODES)
        if not isinstance(self.host, str):
            raise ValueError("Invalid host: expected string.")
        _require_int("max_chars", self.max_chars, minimum=0)
        _require_int("max_segments", self.max_segments, minimum=0)
        _require_int("max_segment_chars", self.max_segment_chars, minimum=0)


@dataclass
class SegmentResult:
    source: str
    target: str


@dataclass
class TranslationResponse:
    output_text: str
    segments: list[SegmentResult] = field(default_factory=list)
    detected_source_lang: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data
