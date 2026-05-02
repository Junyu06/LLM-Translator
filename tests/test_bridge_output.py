from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from python_backend.bridge import write_json_line
from python_backend.config import ConfigStore


class BridgeOutputTests(unittest.TestCase):
    def test_json_line_is_safe_for_legacy_windows_codepage(self) -> None:
        buffer = io.BytesIO()
        stdout = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict", newline="")

        with patch.object(sys, "stdout", stdout):
            write_json_line({"text": "测试"})

        stdout.flush()
        self.assertEqual(buffer.getvalue(), b'{"text": "\\u6d4b\\u8bd5"}\n')

    def test_config_load_ignores_unknown_legacy_fields(self) -> None:
        workspace_temp = Path.cwd() / "tmp"
        workspace_temp.mkdir(exist_ok=True)
        config_path = workspace_temp / "test_bridge_output_config.json"
        try:
            config_path.write_text(
                '{"source_lang": "en", "window_geometry": "1280x820+0+0"}',
                encoding="utf-8",
            )

            config = ConfigStore(config_path).load()
        finally:
            config_path.unlink(missing_ok=True)

        self.assertEqual(config.source_lang, "en")


if __name__ == "__main__":
    unittest.main()
