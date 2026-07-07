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


def corrupt_backup_path(path: Path) -> Path:
    base = path.with_suffix(path.suffix + ".corrupt")
    if not base.exists():
        return base

    index = 1
    while True:
        candidate = path.with_suffix(path.suffix + f".corrupt.{index}")
        if not candidate.exists():
            return candidate
        index += 1


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or get_config_path()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            raw_bytes = self.path.read_bytes()
            data = json.loads(raw_bytes.decode("utf-8"))
            if not isinstance(data, dict):
                raise TypeError("Config file must contain a JSON object.")
        except Exception:
            corrupt_path = corrupt_backup_path(self.path)
            try:
                if "raw_bytes" in locals():
                    corrupt_path.write_bytes(raw_bytes)
                    print(f"Translator config corrupt: {self.path} -> {corrupt_path}", file=sys.stderr)
                else:
                    print(
                        f"Translator config corrupt: {self.path} (backup unavailable)",
                        file=sys.stderr,
                    )
            except Exception as backup_exc:
                print(
                    f"Translator config corrupt: {self.path} (backup failed: {backup_exc})",
                    file=sys.stderr,
                )
            return AppConfig()
        known_values = {key: value for key, value in data.items() if key in APP_CONFIG_FIELDS}
        return AppConfig(**{**AppConfig().to_dict(), **known_values})

    def save(self, config: AppConfig) -> AppConfig:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return config
