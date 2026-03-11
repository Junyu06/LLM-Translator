from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .models import AppConfig


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
        return AppConfig(**{**AppConfig().to_dict(), **data})

    def save(self, config: AppConfig) -> AppConfig:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return config

