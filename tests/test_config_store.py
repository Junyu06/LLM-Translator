from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from python_backend.config import ConfigStore
from python_backend.models import AppConfig


class ConfigStoreCorruptFileTests(unittest.TestCase):
    def test_load_backs_up_corrupt_file_and_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ui_config.json"
            corrupt_text = "{not valid json"
            config_path.write_text(corrupt_text, encoding="utf-8")

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                config = ConfigStore(config_path).load()

            self.assertEqual(config, AppConfig())
            self.assertIn("Translator config corrupt:", stderr.getvalue())
            self.assertIn(str(config_path), stderr.getvalue())

            corrupt_path = config_path.with_suffix(config_path.suffix + ".corrupt")
            self.assertTrue(corrupt_path.exists())
            self.assertEqual(corrupt_path.read_text(encoding="utf-8"), corrupt_text)


if __name__ == "__main__":
    unittest.main()
