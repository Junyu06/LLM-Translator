from __future__ import annotations

import json
import threading
import unittest
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib import error, request

from python_backend.api_server import TranslatorAPIHandler, build_server
from python_backend.config import ConfigStore
from python_backend.models import AppConfig


class _StubConfigStore:
    def load(self) -> AppConfig:
        return AppConfig()

    def save(self, config: AppConfig) -> AppConfig:
        return config


class APIServerMalformedPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = TemporaryDirectory()
        cls._old_config_store = TranslatorAPIHandler.config_store
        cls._old_translation_service = TranslatorAPIHandler.translation_service
        TranslatorAPIHandler.config_store = _StubConfigStore()
        TranslatorAPIHandler.translation_service = cls._old_translation_service
        cls._server = build_server(host="127.0.0.1", port=0)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls._base_url = f"http://127.0.0.1:{cls._server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=5)
        TranslatorAPIHandler.config_store = cls._old_config_store
        TranslatorAPIHandler.translation_service = cls._old_translation_service
        cls._temp_dir.cleanup()

    def _request_json(self, method: str, path: str, payload: dict) -> error.HTTPError | request.addinfourl:
        req = request.Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            return request.urlopen(req, timeout=5)
        except error.HTTPError as exc:
            return exc

    def test_translate_malformed_payload_returns_json_400(self) -> None:
        response = self._request_json("POST", "/translate", {})

        self.assertEqual(response.status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.headers.get_content_type(), "application/json")
        try:
            body = json.loads(response.read().decode("utf-8"))
        finally:
            response.close()
        self.assertIn("error", body)

    def test_config_malformed_payload_returns_json_400(self) -> None:
        response = self._request_json("PUT", "/config", {"unexpected": True})

        self.assertEqual(response.status, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.headers.get_content_type(), "application/json")
        try:
            body = json.loads(response.read().decode("utf-8"))
        finally:
            response.close()
        self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main()
