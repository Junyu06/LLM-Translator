import asyncio
import io
import os
import threading
from typing import Callable, Iterable, List

try:
    from PIL import Image, ImageGrab
except Exception:  # noqa: BLE001 - optional dependency
    Image = None
    ImageGrab = None

try:
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
except Exception:  # noqa: BLE001 - optional dependency
    OcrEngine = None
    BitmapDecoder = None
    InMemoryRandomAccessStream = None
    DataWriter = None


def is_ocr_available() -> bool:
    return (
        OcrEngine is not None
        and BitmapDecoder is not None
        and InMemoryRandomAccessStream is not None
        and DataWriter is not None
        and Image is not None
        and ImageGrab is not None
    )


def get_paste_image_paths(root=None) -> List[str]:
    paths: List[str] = []
    if ImageGrab is not None:
        try:
            data = ImageGrab.grabclipboard()
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str) and _is_image_file(item):
                        paths.append(item)
        except Exception:
            pass
    if paths:
        return paths

    if root is None:
        return []
    try:
        text = root.clipboard_get()
    except Exception:
        return []
    text = text.strip()
    if text and os.path.exists(text) and _is_image_file(text):
        return [text]
    return []


def get_paste_images() -> List[bytes]:
    if ImageGrab is None or Image is None:
        return []
    try:
        data = ImageGrab.grabclipboard()
    except Exception:
        return []
    if isinstance(data, Image.Image):
        buf = io.BytesIO()
        data.save(buf, format="PNG")
        return [buf.getvalue()]
    return []


def run_ocr(paths: Iterable[str]) -> str:
    _ensure_ocr()
    images = []
    for path in paths:
        try:
            with open(path, "rb") as f:
                images.append(f.read())
        except Exception:
            continue
    return run_ocr_images(images)


def run_ocr_images(images: Iterable[bytes]) -> str:
    _ensure_ocr()
    return asyncio.run(_run_ocr_images_async(images))


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


def _ensure_ocr():
    if not is_ocr_available():
        raise RuntimeError("WinRT OCR is not available. Install winsdk and pillow.")


async def _run_ocr_images_async(images: Iterable[bytes]) -> str:
    texts: List[str] = []
    for data in images:
        text = await _ocr_from_bytes(data)
        if text:
            texts.append(text.strip())
    return "\n".join(t for t in texts if t)


async def _ocr_from_bytes(data: bytes) -> str:
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(data)
    await writer.store_async()
    await writer.flush_async()
    writer.detach_stream()
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("WinRT OCR engine is unavailable.")
    result = await engine.recognize_async(bitmap)
    return result.text or ""
