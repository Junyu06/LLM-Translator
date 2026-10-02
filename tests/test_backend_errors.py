from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from backend.errors import BackendRequestError, BackendUnavailableError, ModelNotFoundError
from backend.ollama_backend import OllamaBackend, OllamaBackendOptions


class FakeResponse:
    def __init__(self, lines=None, body=b""):
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


def line(obj) -> bytes:
    return (json.dumps(obj) + "\n").encode()


def backend() -> OllamaBackend:
    return OllamaBackend(OllamaBackendOptions(model="m", host="http://127.0.0.1:11434"))


class OllamaStreamTests(unittest.TestCase):
    def test_streams_content_and_sends_think_false(self):
        lines = [line({"message": {"content": "你"}}), line({"message": {"content": "好"}, "done": True})]
        with patch("urllib.request.urlopen", return_value=FakeResponse(lines)) as urlopen:
            self.assertEqual("".join(backend().stream_chat([{"role": "user", "content": "hi"}])), "你好")
        payload = json.loads(urlopen.call_args[0][0].data)
        self.assertIs(payload["think"], False)
        self.assertEqual(payload["options"]["temperature"], 0.0)

    def test_error_inside_the_stream_raises(self):
        lines = [line({"message": {"content": "半"}}), line({"error": "model runner crashed"})]
        with patch("urllib.request.urlopen", return_value=FakeResponse(lines)):
            with self.assertRaises(BackendRequestError) as ctx:
                list(backend().stream_chat([]))
        self.assertEqual(ctx.exception.code, "backend_stream_error")
        self.assertIn("model runner crashed", str(ctx.exception))

    def test_stream_that_ends_without_done_raises(self):
        with patch("urllib.request.urlopen", return_value=FakeResponse([line({"message": {"content": "半截"}})])):
            with self.assertRaises(BackendRequestError) as ctx:
                list(backend().stream_chat([]))
        self.assertEqual(ctx.exception.code, "backend_stream_incomplete")

    def test_bad_json_has_stable_code(self):
        with patch("urllib.request.urlopen", return_value=FakeResponse([b"{bad json}\n"])):
            with self.assertRaises(BackendRequestError) as ctx:
                list(backend().stream_chat([]))
        self.assertEqual(ctx.exception.code, "invalid_backend_json")

    def test_timeout_has_stable_code(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(BackendRequestError) as ctx:
                list(backend().stream_chat([]))
        self.assertEqual(ctx.exception.code, "backend_timeout")

    def test_unreachable_server_maps_to_unavailable(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            with self.assertRaises(BackendUnavailableError) as ctx:
                list(backend().stream_chat([]))
        self.assertEqual(ctx.exception.code, "ollama_unavailable")

    def test_404_is_model_not_found_with_ollama_message(self):
        error = urllib.error.HTTPError(
            url="http://127.0.0.1:11434/api/chat",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"model \\"x\\" not found, try pulling it first"}'),
        )
        self.addCleanup(error.close)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ModelNotFoundError) as ctx:
                list(backend().stream_chat([]))
        self.assertEqual(ctx.exception.code, "model_not_found")
        self.assertIn("try pulling it first", str(ctx.exception))

    def test_list_models(self):
        body = json.dumps({"models": [{"name": "b:latest"}, {"name": "a:1b"}]}).encode()
        with patch("urllib.request.urlopen", return_value=FakeResponse(body=body)):
            self.assertEqual(backend().list_models(), ["a:1b", "b:latest"])


if __name__ == "__main__":
    unittest.main()
