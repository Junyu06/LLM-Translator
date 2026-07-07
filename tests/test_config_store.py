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

    def test_repeated_corrupt_loads_do_not_overwrite_existing_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ui_config.json"
            config_path.write_text("{first", encoding="utf-8")

            with redirect_stderr(io.StringIO()):
                ConfigStore(config_path).load()

            config_path.write_text("{second", encoding="utf-8")

            with redirect_stderr(io.StringIO()):
                ConfigStore(config_path).load()

            first_backup = config_path.with_suffix(config_path.suffix + ".corrupt")
            second_backup = config_path.with_suffix(config_path.suffix + ".corrupt.1")
            self.assertEqual(first_backup.read_text(encoding="utf-8"), "{first")
            self.assertEqual(second_backup.read_text(encoding="utf-8"), "{second")


if __name__ == "__main__":
    unittest.main()
