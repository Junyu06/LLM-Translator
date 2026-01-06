import os
import threading
from typing import Callable, Iterable, List
from urllib.parse import unquote, urlparse

try:
    from AppKit import (
        NSPasteboard,
        NSFilenamesPboardType,
        NSPasteboardTypeFileURL,
        NSPasteboardTypePNG,
        NSPasteboardTypeTIFF,
        NSImage,
    )
except Exception:  # noqa: BLE001 - optional dependency
    NSPasteboard = None
    NSFilenamesPboardType = None
    NSPasteboardTypeFileURL = None
    NSPasteboardTypePNG = None
    NSPasteboardTypeTIFF = None
    NSImage = None

try:
    from Foundation import NSURL, NSData
    from Quartz import (
        CGImageSourceCreateWithData,
        CGImageSourceCreateWithURL,
        CGImageSourceCreateImageAtIndex,
    )
    from Vision import (
        VNRecognizeTextRequest,
        VNImageRequestHandler,
        VNRequestTextRecognitionLevelAccurate,
    )
except Exception:  # noqa: BLE001 - optional dependency
    NSURL = None
    NSData = None
    CGImageSourceCreateWithData = None
    CGImageSourceCreateWithURL = None
    CGImageSourceCreateImageAtIndex = None
    VNRecognizeTextRequest = None
    VNImageRequestHandler = None
    VNRequestTextRecognitionLevelAccurate = None


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


def get_paste_images(debug: bool = False) -> List[bytes]:
    if NSPasteboard is None:
        if debug:
            print("OCR: NSPasteboard unavailable")
        return []

    pb = NSPasteboard.generalPasteboard()
    types = list(pb.types() or [])
    if debug:
        print(f"OCR: pasteboard types = {types}")

    candidates = []
    for ptype in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
        if ptype is not None:
            candidates.append(ptype)
    for ptype in ("public.png", "public.tiff", "public.jpeg"):
        candidates.append(ptype)

    for ptype in candidates:
        if ptype not in types:
            continue
        data = pb.dataForType_(ptype)
        if data is None:
            continue
        try:
            return [bytes(data)]
        except Exception:
            continue

    if NSImage is None:
        return []

    try:
        images = pb.readObjectsForClasses_options_([NSImage], None)
        if images:
            tiff = images[0].TIFFRepresentation()
            if tiff is not None:
                return [bytes(tiff)]
    except Exception:
        pass

    return []


def run_ocr(paths: Iterable[str]) -> str:
    _ensure_vision()
    texts = []
    for path in paths:
        cg_image = _cgimage_from_path(path)
        if cg_image is None:
            continue
        texts.append(_recognize_text(cg_image))
    return "\n".join(t.strip() for t in texts if t.strip())


def run_ocr_images(images: Iterable[bytes]) -> str:
    _ensure_vision()
    texts = []
    for data in images:
        cg_image = _cgimage_from_data(data)
        if cg_image is None:
            continue
        texts.append(_recognize_text(cg_image))
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
    images: Iterable[bytes],
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


def _is_image_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}


def _ensure_vision():
    if VNRecognizeTextRequest is None or VNImageRequestHandler is None:
        raise RuntimeError("Vision OCR is not available. Install pyobjc-framework-Vision.")


def _cgimage_from_path(path: str):
    if NSURL is None or CGImageSourceCreateWithURL is None:
        return None
    url = NSURL.fileURLWithPath_(path)
    source = CGImageSourceCreateWithURL(url, None)
    if source is None:
        return None
    return CGImageSourceCreateImageAtIndex(source, 0, None)


def _cgimage_from_data(data: bytes):
    if NSData is None or CGImageSourceCreateWithData is None:
        return None
    ns_data = NSData.dataWithBytes_length_(data, len(data))
    source = CGImageSourceCreateWithData(ns_data, None)
    if source is None:
        return None
    return CGImageSourceCreateImageAtIndex(source, 0, None)


def _recognize_text(cg_image) -> str:
    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(VNRequestTextRecognitionLevelAccurate)
    try:
        request.setRecognitionLanguages_(
            ["zh-Hans", "zh-Hant", "ja-JP", "ko-KR", "en-US"]
        )
        request.setUsesLanguageCorrection_(True)
    except Exception:
        pass
    handler = VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
    ok, err = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision OCR failed: {err}")

    results = request.results() or []
    lines = []
    for obs in results:
        candidates = obs.topCandidates_(1)
        if candidates and len(candidates) > 0:
            lines.append(candidates[0].string())
    return "\n".join(lines)
