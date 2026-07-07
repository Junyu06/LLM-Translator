from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import shutil
import sys
from typing import Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from python_backend.config import ConfigStore
from python_backend.models import AppConfig


def startup_log(stage: str, details: str | None = None) -> None:
    if os.getenv("TRANSLATOR_STARTUP_LOG") != "1" and not os.getenv("TRANSLATOR_STARTUP_LOG_FILE"):
        return

    timestamp = datetime.now(timezone.utc).isoformat()
    line = f"{timestamp} stage={stage}"
    if details:
        line += f" details={details}"
    line += "\n"

    if os.getenv("TRANSLATOR_STARTUP_LOG") == "1":
        sys.stderr.write(line)
        sys.stderr.flush()

    log_file = os.getenv("TRANSLATOR_STARTUP_LOG_FILE")
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError as exc:
            if os.getenv("TRANSLATOR_STARTUP_LOG") == "1":
                sys.stderr.write(f"startup_log_file_error path={log_file} error={exc}\n")
                sys.stderr.flush()


def get_translation_types() -> tuple[type, type]:
    from python_backend.models import TranslationRequest
    from python_backend.services.translation_service import TranslationService

    return TranslationRequest, TranslationService


def get_translation_service() -> Any:
    _, TranslationService = get_translation_types()

    return TranslationService()


startup_log("bridge_import_complete")


def read_stdin_json() -> dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def encode_json(payload: dict) -> str:
    # Keep bridge stdout ASCII-safe. Windows packaged apps may inherit a legacy
    # code page, and non-ASCII translation output can otherwise fail to encode.
    return json.dumps(payload, ensure_ascii=True)


def write_json(payload: dict) -> None:
    sys.stdout.write(encode_json(payload))


def write_json_line(payload: dict) -> None:
    sys.stdout.write(encode_json(payload) + "\n")
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
    TranslationRequest, _ = get_translation_types()
    request = TranslationRequest(**payload)
    response = get_translation_service().translate(request)
    write_json(response.to_dict())
    return 0


def cmd_translate_stream() -> int:
    payload = read_stdin_json()
    TranslationRequest, _ = get_translation_types()
    request = TranslationRequest(**payload)
    for event in get_translation_service().stream_translate(request):
        write_json_line(event)
    return 0


def cmd_ocr_clipboard() -> int:
    if sys.platform == "darwin":
        from ui_mac.ocr import get_paste_image_paths, get_paste_images, run_ocr, run_ocr_images

        paths = get_paste_image_paths()
        if paths:
            write_json({"text": run_ocr(paths)})
            return 0

        images = get_paste_images()
        if images:
            write_json({"text": run_ocr_images(images)})
            return 0

        raise RuntimeError("No image found in clipboard.")

    if sys.platform.startswith("win"):
        from ui_windows.ocr import (
            get_paste_image_paths,
            get_paste_images,
            is_ocr_available,
            run_ocr,
            run_ocr_images,
        )

        if not is_ocr_available():
            raise RuntimeError("WinRT OCR is not available. Install winsdk and pillow.")

        paths = get_paste_image_paths()
        if paths:
            write_json({"text": run_ocr(paths)})
            return 0

        images = get_paste_images()
        if images:
            write_json({"text": run_ocr_images(images)})
            return 0

        raise RuntimeError("No image found in clipboard.")

    raise RuntimeError("Clipboard OCR is implemented only for macOS and Windows.")


def cmd_hotkey_listener() -> int:
    if not sys.platform.startswith("win"):
        raise RuntimeError("The bridge hotkey listener is implemented only for Windows.")

    from ui_windows.hotkey_windows import DoubleCtrlCListener

    listener = DoubleCtrlCListener(
        on_trigger=lambda: write_json_line({"event": "trigger", "hotkey": "ctrl+c ctrl+c"})
    )
    listener.run()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Python services into Tauri commands")
    parser.add_argument(
        "command",
        choices=[
            "health",
            "get-config",
            "save-config",
            "translate",
            "translate-stream",
            "ocr-clipboard",
            "hotkey-listener",
        ],
    )
    args = parser.parse_args()
    startup_log("command_dispatch_start", args.command)

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
        if args.command == "ocr-clipboard":
            return cmd_ocr_clipboard()
        if args.command == "hotkey-listener":
            return cmd_hotkey_listener()
    except Exception as exc:
        error_payload = {
            "error": str(exc),
            "command": args.command,
            "python": sys.executable,
            "python3_in_path": shutil.which("python3"),
        }
        if args.command in {"translate-stream", "hotkey-listener"}:
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
