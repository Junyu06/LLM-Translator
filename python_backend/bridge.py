from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from python_backend.config import ConfigStore
from python_backend.models import AppConfig, TranslationRequest
from python_backend.services.translation_service import TranslationService


def read_stdin_json() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def write_json(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


def write_json_line(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def cmd_health() -> int:
    write_json({"status": "ok", "python": sys.executable})
    return 0


def cmd_get_config() -> int:
    write_json(ConfigStore().load().to_dict())
    return 0


def cmd_save_config() -> int:
    payload = read_stdin_json()
    merged = {**ConfigStore().load().to_dict(), **payload}
    config = AppConfig(**merged)
    write_json(ConfigStore().save(config).to_dict())
    return 0


def cmd_translate() -> int:
    payload = read_stdin_json()
    request = TranslationRequest(**payload)
    response = TranslationService().translate(request)
    write_json(response.to_dict())
    return 0


def cmd_translate_stream() -> int:
    payload = read_stdin_json()
    request = TranslationRequest(**payload)
    for event in TranslationService().stream_translate(request):
        write_json_line(event)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Python services into Tauri commands")
    parser.add_argument("command", choices=["health", "get-config", "save-config", "translate", "translate-stream"])
    args = parser.parse_args()

    try:
        if args.command == "health":
            return cmd_health()
        if args.command == "get-config":
            return cmd_get_config()
        if args.command == "save-config":
            return cmd_save_config()
        if args.command == "translate":
            return cmd_translate()
        if args.command == "translate-stream":
            return cmd_translate_stream()
    except Exception as exc:
        error_payload = {
            "error": str(exc),
            "command": args.command,
            "python": sys.executable,
            "python3_in_path": shutil.which("python3"),
        }
        if args.command == "translate-stream":
            write_json_line(
                {
                    "event": "error",
                    "message": str(exc),
                    **error_payload,
                }
            )
        else:
            write_json(error_payload)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
