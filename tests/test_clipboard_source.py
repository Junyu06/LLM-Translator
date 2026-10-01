from __future__ import annotations

import sys
import unittest
from pathlib import Path

from python_backend.clipboard import choose_source, read_clipboard

SAMPLE_IMAGE = Path(__file__).resolve().parents[1] / "docs" / "images" / "main-window-markdown-mode.png"


class ClipboardSourceTests(unittest.TestCase):
    def test_text_only(self) -> None:
        self.assertEqual(choose_source("Hello world", has_image=False), "text")

    def test_image_only(self) -> None:
        self.assertEqual(choose_source("", has_image=True), "image")

    def test_whitespace_text_with_image_uses_image(self) -> None:
        self.assertEqual(choose_source("  \n", has_image=True), "image")

    def test_real_text_wins_over_selection_picture(self) -> None:
        # Office apps put a picture of the selection next to the copied text.
        self.assertEqual(choose_source("Quarterly results\nRevenue grew 12%.", has_image=True), "text")

    def test_image_file_name_next_to_image_uses_image(self) -> None:
        self.assertEqual(choose_source("Screenshot 2026-10-01 at 04.00.00.png", has_image=True), "image")

    def test_image_url_next_to_image_uses_image(self) -> None:
        self.assertEqual(choose_source("https://example.com/a/chart.jpeg?w=800", has_image=True), "image")

    def test_extensionless_or_fragment_url_next_to_image_uses_image(self) -> None:
        self.assertEqual(choose_source("https://example.com/image?id=7", has_image=True), "image")
        self.assertEqual(choose_source("https://cdn.example.com/a.png#preview", has_image=True), "image")

    def test_single_word_next_to_image_is_text(self) -> None:
        self.assertEqual(choose_source("Quarterly", has_image=True), "text")

    def test_file_name_without_image_is_text(self) -> None:
        self.assertEqual(choose_source("photo.png", has_image=False), "text")

    def test_nothing(self) -> None:
        self.assertEqual(choose_source("", has_image=False), "empty")


@unittest.skipUnless(sys.platform == "darwin", "macOS pasteboard and Vision OCR")
class MacClipboardCaptureTests(unittest.TestCase):
    """Uses a private pasteboard so the user's clipboard is never touched."""

    def setUp(self) -> None:
        from AppKit import NSPasteboard

        self.pb = NSPasteboard.pasteboardWithUniqueName()

    def tearDown(self) -> None:
        self.pb.releaseGlobally()

    def test_text(self) -> None:
        from AppKit import NSPasteboardTypeString

        self.pb.clearContents()
        self.pb.setString_forType_("Hello from the clipboard", NSPasteboardTypeString)
        self.assertEqual(read_clipboard(self.pb), {"source": "text", "text": "Hello from the clipboard"})

    def test_image_goes_through_ocr(self) -> None:
        from AppKit import NSPasteboardTypePNG
        from Foundation import NSData

        self.pb.clearContents()
        self.pb.setData_forType_(NSData.dataWithContentsOfFile_(str(SAMPLE_IMAGE)), NSPasteboardTypePNG)
        result = read_clipboard(self.pb)
        self.assertEqual(result["source"], "image")
        self.assertIn("local desktop translation tool", result["text"])

    def test_empty(self) -> None:
        self.pb.clearContents()
        self.assertEqual(read_clipboard(self.pb), {"source": "empty", "text": ""})


if __name__ == "__main__":
    unittest.main()
