from __future__ import annotations

from dataclasses import fields
import json
import os
import sys
from pathlib import Path

from .models import AppConfig

APP_CONFIG_FIELDS = {field.name for field in fields(AppConfig)}


def get_config_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Translator" / "ui_config.json"
    base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "Translator" / "ui_config.json"


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or get_config_path()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return AppConfig()
        known_values = {key: value for key, value in data.items() if key in APP_CONFIG_FIELDS}
        return AppConfig(**{**AppConfig().to_dict(), **known_values})

    def save(self, config: AppConfig) -> AppConfig:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return config

