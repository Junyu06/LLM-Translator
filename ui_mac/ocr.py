import os
import threading
from io import BytesIO
from typing import Callable, Iterable, List
from urllib.parse import unquote, urlparse

try:
    from AppKit import (
        NSPasteboard,
        NSFilenamesPboardType,
        NSPasteboardTypeFileURL,
        NSPasteboardTypePNG,
        NSPasteboardTypeTIFF,
    )
except Exception:  # noqa: BLE001 - optional dependency
    NSPasteboard = None
    NSFilenamesPboardType = None
    NSPasteboardTypeFileURL = None
    NSPasteboardTypePNG = None
    NSPasteboardTypeTIFF = None


def get_paste_image_paths(root=None) -> List[str]:
    paths: List[str] = []
    if NSPasteboard is not None:
        try:
            pb = NSPasteboard.generalPasteboard()
            items = pb.propertyListForType_(NSFilenamesPboardType)
            if items:
                paths.extend([p for p in items if _is_image_file(p)])
        except Exception:
            pass

        try:
            pb = NSPasteboard.generalPasteboard()
            url_str = pb.stringForType_(NSPasteboardTypeFileURL)
            if url_str:
                parsed = urlparse(url_str)
                if parsed.scheme == "file":
                    path = unquote(parsed.path)
                    if _is_image_file(path):
                        paths.append(path)
        except Exception:
            pass

    if not paths and root is not None:
        try:
            text = root.clipboard_get()
        except Exception:
            text = ""
        text = text.strip()
        if text and os.path.exists(text) and _is_image_file(text):
            paths.append(text)

    return paths


def run_ocr(paths: Iterable[str]) -> str:
    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore
    except Exception as exc:
        raise RuntimeError("OCR needs Pillow + pytesseract (and tesseract).") from exc

    texts = []
    for path in paths:
        try:
            img = Image.open(path)
            texts.append(pytesseract.image_to_string(img))
        except Exception:
            continue
    return "\n".join(t.strip() for t in texts if t.strip())


def run_ocr_images(images: Iterable["Image.Image"]) -> str:
    try:
        import pytesseract  # type: ignore
    except Exception as exc:
        raise RuntimeError("OCR needs pytesseract (and tesseract).") from exc

    texts = []
    for img in images:
        try:
            texts.append(pytesseract.image_to_string(img))
        except Exception:
            continue
    return "\n".join(t.strip() for t in texts if t.strip())


def run_ocr_async(
    paths: Iterable[str],
    on_done: Callable[[str], None],
    on_error: Callable[[Exception], None] | None = None,
):
    def worker():
        try:
            result = run_ocr(paths)
            on_done(result)
        except Exception as exc:
            if on_error is not None:
                on_error(exc)

    threading.Thread(target=worker, daemon=True).start()


def run_ocr_async_images(
    images: Iterable["Image.Image"],
    on_done: Callable[[str], None],
    on_error: Callable[[Exception], None] | None = None,
):
    def worker():
        try:
            result = run_ocr_images(images)
            on_done(result)
        except Exception as exc:
            if on_error is not None:
                on_error(exc)

    threading.Thread(target=worker, daemon=True).start()


def get_paste_images() -> List["Image.Image"]:
    if NSPasteboard is None:
        return []

    try:
        from PIL import Image  # type: ignore
    except Exception:
        return []

    pb = NSPasteboard.generalPasteboard()
    for ptype in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
        if ptype is None:
            continue
        data = pb.dataForType_(ptype)
        if data is None:
            continue
        try:
            raw = bytes(data)
            img = Image.open(BytesIO(raw))
            return [img]
        except Exception:
            continue
    return []


def _is_image_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
