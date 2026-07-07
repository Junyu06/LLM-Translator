from __future__ import annotations

import io
import sys
import types
import unittest
import urllib.error
from unittest.mock import patch

from backend.errors import BackendRequestError, BackendUnavailableError, ModelNotFoundError
from backend.ollama_backend import OllamaBackend, OllamaBackendOptions, OllamaMode


class FakeResponse:
    def __init__(self, lines: list[bytes] | None = None, body: bytes = b""):
        self._lines = lines or []
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._lines)

    def read(self):
        return self._body


class BackendErrorCodeTests(unittest.TestCase):
    def test_http_stream_json_decode_error_has_stable_code(self):
        backend = OllamaBackend(OllamaBackendOptions(mode=OllamaMode.HTTP))

        with patch("urllib.request.urlopen", return_value=FakeResponse([b"{bad json}\n"])):
            with self.assertRaises(BackendRequestError) as ctx:
                list(backend.stream_generate("hello"))

        self.assertEqual(ctx.exception.code, "invalid_backend_json")

    def test_http_stream_timeout_has_stable_code(self):
        backend = OllamaBackend(OllamaBackendOptions(mode=OllamaMode.HTTP))

        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(BackendRequestError) as ctx:
                list(backend.stream_generate("hello"))

        self.assertEqual(ctx.exception.code, "backend_timeout")

    def test_http_url_error_maps_to_unavailable_code(self):
        backend = OllamaBackend(OllamaBackendOptions(mode=OllamaMode.HTTP))

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with self.assertRaises(BackendUnavailableError) as ctx:
                backend.generate("hello")

        self.assertEqual(ctx.exception.code, "ollama_unavailable")

    def test_http_os_error_maps_to_unavailable_code(self):
        backend = OllamaBackend(OllamaBackendOptions(mode=OllamaMode.HTTP))

        with patch("urllib.request.urlopen", side_effect=OSError("socket closed")):
            with self.assertRaises(BackendUnavailableError) as ctx:
                list(backend.stream_generate("hello"))

        self.assertEqual(ctx.exception.code, "ollama_unavailable")

    def test_missing_local_dependency_has_dependency_missing_code(self):
        backend = OllamaBackend(OllamaBackendOptions(mode=OllamaMode.LOCAL))
        original_platform = sys.platform

        def fake_import(name, *args, **kwargs):
            if name == "ollama":
                raise ModuleNotFoundError("No module named 'ollama'")
            return original_import(name, *args, **kwargs)

        original_import = __import__

        with patch.object(sys, "platform", "darwin"):
            with patch("builtins.__import__", side_effect=fake_import):
                with self.assertRaises(BackendUnavailableError) as ctx:
                    backend.generate("hello")

        self.assertEqual(ctx.exception.code, "dependency_missing")

    def test_http_404_has_model_not_found_code(self):
        backend = OllamaBackend(OllamaBackendOptions(mode=OllamaMode.HTTP))
        error = urllib.error.HTTPError(
            url="http://127.0.0.1:11434/api/chat",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"model missing"}'),
        )
        self.addCleanup(error.close)

        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ModelNotFoundError) as ctx:
                backend.generate("hello")

        self.assertEqual(ctx.exception.code, "model_not_found")

    def test_local_missing_response_content_has_unexpected_response_code(self):
        backend = OllamaBackend(OllamaBackendOptions(mode=OllamaMode.LOCAL))
        fake_ollama = types.SimpleNamespace(chat=lambda **kwargs: {"message": {}})

        with patch.object(sys, "platform", "darwin"):
            with patch.dict(sys.modules, {"ollama": fake_ollama}):
                with self.assertRaises(BackendRequestError) as ctx:
                    backend.generate("hello")

        self.assertEqual(ctx.exception.code, "unexpected_backend_response")


if __name__ == "__main__":
    unittest.main()
