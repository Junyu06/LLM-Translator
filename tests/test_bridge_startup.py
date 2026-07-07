from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BRIDGE = ROOT_DIR / "python_backend" / "bridge.py"


class BridgeStartupImportTests(unittest.TestCase):
    def run_bridge(
        self,
        command: str,
        *,
        input_text: str | None = None,
        importtime: bool = False,
        extra_env: dict[str, str] | None = None,
        temp_dir: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        args = [sys.executable]
        if importtime:
            args.append("-X")
            args.append("importtime")
        args.extend([str(BRIDGE), command])

        def run_with_temp(home_dir: str) -> subprocess.CompletedProcess[str]:
            env = {
                **os.environ,
                "HOME": home_dir,
                "APPDATA": home_dir,
                "LOCALAPPDATA": home_dir,
                "PYTHONPATH": str(ROOT_DIR),
            }
            if extra_env:
                env.update(extra_env)
            return subprocess.run(
                args,
                input=input_text,
                text=True,
                capture_output=True,
                cwd=ROOT_DIR,
                env=env,
                check=False,
            )

        if temp_dir is not None:
            return run_with_temp(temp_dir)

        with tempfile.TemporaryDirectory() as generated_temp_dir:
            return run_with_temp(generated_temp_dir)

    def assert_translation_service_not_imported(self, command: str, *, input_text: str | None = None) -> None:
        result = self.run_bridge(command, input_text=input_text, importtime=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("translation_service", result.stdout + result.stderr)

    def test_health_does_not_import_translation_service(self) -> None:
        self.assert_translation_service_not_imported("health")

    def test_get_config_does_not_import_translation_service(self) -> None:
        self.assert_translation_service_not_imported("get-config")

    def test_save_config_does_not_import_translation_service(self) -> None:
        self.assert_translation_service_not_imported("save-config", input_text='{"source_lang": "en"}')

    def test_translate_imports_translation_service_for_request_path(self) -> None:
        result = self.run_bridge("translate", input_text='{"text": "hello"}', importtime=True)

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("translation_service", result.stdout + result.stderr)

    def test_startup_log_writes_to_stderr_when_enabled(self) -> None:
        result = self.run_bridge("health", extra_env={"TRANSLATOR_STARTUP_LOG": "1"})

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("stage=bridge_import_complete", result.stderr)
        self.assertIn("stage=command_dispatch_start details=health", result.stderr)

    def test_startup_log_appends_to_file_when_path_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "startup.log"
            result = self.run_bridge(
                "health",
                extra_env={"TRANSLATOR_STARTUP_LOG_FILE": str(log_path)},
                temp_dir=temp_dir,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")
            log_text = log_path.read_text(encoding="utf-8")

        self.assertIn("stage=bridge_import_complete", log_text)
        self.assertIn("stage=command_dispatch_start details=health", log_text)

    def test_invalid_startup_log_file_does_not_break_health(self) -> None:
        result = self.run_bridge(
            "health",
            extra_env={"TRANSLATOR_STARTUP_LOG_FILE": "/no/such/dir/translator.log"},
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"status": "ok"', result.stdout)


if __name__ == "__main__":
    unittest.main()
