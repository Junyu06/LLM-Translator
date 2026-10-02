"""Read whatever the user copied: text as-is, or an image through system OCR.

Every capture path (toolbar button, double-copy hotkey, tray menu, paste into
the source box) goes through `read_clipboard()` so an image clipboard is
handled the same way everywhere.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".heic"}


def _looks_like_image_reference(text: str) -> bool:
    """Finder and browsers put the file name or URL next to a copied image.

    Any single URL counts (CDN and proxy URLs often have no extension); a
    plain word or a sentence does not.
    """
    stripped = text.strip()
    if not stripped or "\n" in stripped:
        return False
    if re.match(r"^(?:[A-Za-z][A-Za-z0-9+.-]*://|data:image/)\S*$", stripped):
        return True
    path = re.split(r"[?#]", stripped, maxsplit=1)[0]
    return os.path.splitext(path)[1].lower() in _IMAGE_EXTENSIONS


def choose_source(text: str, has_image: bool) -> str:
    """Decide what to translate: "text", "image", or "empty".

    Real text wins over an image, because Office and some editors put a
    picture of the selection next to the text. An image wins when the only
    text is the image's own file name or URL.
    """
    if text.strip() and not (has_image and _looks_like_image_reference(text)):
        return "text"
    if has_image:
        return "image"
    return "empty"


def _read_macos(pasteboard=None) -> dict[str, Any]:
    from AppKit import NSPasteboard, NSPasteboardTypeString

    from ui_mac.ocr import get_paste_image_paths, get_paste_images, run_ocr, run_ocr_images

    pb = pasteboard or NSPasteboard.generalPasteboard()
    text = pb.stringForType_(NSPasteboardTypeString) or ""
    paths = get_paste_image_paths(pasteboard=pb)
    images = [] if paths else get_paste_images(pasteboard=pb)
    source = choose_source(str(text), bool(paths or images))
    if source == "image":
        text = run_ocr(paths) if paths else run_ocr_images(images)
    return {"source": source, "text": str(text)}


def _read_windows() -> dict[str, Any]:
    from ui_windows.ocr import (
        get_paste_image_paths,
        get_paste_images,
        is_ocr_available,
        run_ocr,
        run_ocr_images,
    )

    try:
        import pyperclip

        text = pyperclip.paste() or ""
    except Exception:
        text = ""
    paths = get_paste_image_paths()
    images = [] if paths else get_paste_images()
    source = choose_source(text, bool(paths or images))
    if source == "image":
        if not is_ocr_available():
            raise RuntimeError("WinRT OCR is not available. Install winsdk and pillow.")
        text = run_ocr(paths) if paths else run_ocr_images(images)
    return {"source": source, "text": text}


def read_clipboard(pasteboard=None) -> dict[str, Any]:
    """`pasteboard` lets tests use a private macOS pasteboard instead of the user's."""
    if sys.platform == "darwin":
        return _read_macos(pasteboard)
    if sys.platform.startswith("win"):
        return _read_windows()
    raise RuntimeError("Clipboard capture is implemented only for macOS and Windows.")
