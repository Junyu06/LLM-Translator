from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AppConfig:
    source_lang: str = "auto"
    target_lang: str = "en"
    use_context: bool = False
    collapse_newlines: bool = False
    output_mode: str = "translations_only"
    layout: str = "vertical"
    mode: str = "local"
    host: str = "http://127.0.0.1:11434"
    model: str = "demonbyron/HY-MT1.5-1.8B"
    font_size: int = 14
    hotkey_enabled: bool = True
    minimize_to_tray: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TranslationRequest:
    text: str
    source_lang: str = "auto"
    target_lang: str = "en"
    use_context: bool = False
    collapse_newlines: bool = False
    output_mode: str = "translations_only"
    model: str = "demonbyron/HY-MT1.5-1.8B"
    mode: str = "local"
    host: str = "http://127.0.0.1:11434"


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

