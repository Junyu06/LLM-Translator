from __future__ import annotations

import argparse
import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from .config import ConfigStore
    from .models import AppConfig, TranslationRequest
    from .services.translation_service import TranslationService
except ImportError:
    from python_backend.config import ConfigStore
    from python_backend.models import AppConfig, TranslationRequest
    from python_backend.services.translation_service import TranslationService


class TranslatorAPIHandler(BaseHTTPRequestHandler):
    config_store = ConfigStore()
    translation_service = TranslationService()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._write_json(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/config":
            self._write_json(HTTPStatus.OK, self.config_store.load().to_dict())
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/translate":
            try:
                payload = self._read_json()
                request = TranslationRequest(**payload)
                response = self.translation_service.translate(request)
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._write_json(HTTPStatus.OK, response.to_dict())
            return
        if self.path == "/ocr":
            self._write_json(
                HTTPStatus.NOT_IMPLEMENTED,
                {"error": "OCR endpoint is reserved for Phase 3 native parity work."},
            )
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_PUT(self) -> None:  # noqa: N802
        if self.path == "/config":
            try:
                payload = self._read_json()
                merged = {**self.config_store.load().to_dict(), **payload}
                config = AppConfig(**merged)
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self.config_store.save(config)
            self._write_json(HTTPStatus.OK, config.to_dict())
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON") from exc

    def _write_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def build_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), TranslatorAPIHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Translator local API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = build_server(host=args.host, port=args.port)
    print(f"Translator API listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
