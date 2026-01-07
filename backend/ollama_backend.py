# hy_translator/backend/ollama_backend.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import sys
from typing import Any, Dict

from .errors import BackendUnavailableError, BackendRequestError, ModelNotFoundError


class OllamaMode(str, Enum):
    LOCAL = "local"  # python package: ollama.chat(...)
    HTTP = "http"    # remote or custom host via HTTP API


@dataclass
class OllamaBackendOptions:
    mode: OllamaMode = OllamaMode.LOCAL
    model: str = "demonbyron/HY-MT1.5-1.8B"

    # chat options (temperature, top_p, num_ctx, repeat_penalty, ...)
    options: Dict[str, Any] = field(default_factory=lambda: {"temperature": 0.0})

    # only for HTTP mode
    host: str = "http://127.0.0.1:11434"
    timeout_sec: int = 60


class OllamaBackend:
    """
    Backend that exposes a simple generate(prompt)->raw_text API for the pipeline.

    - LOCAL mode uses `ollama` python package.
    - HTTP mode uses Ollama REST API (supports remote host).
    """

    def __init__(self, cfg: OllamaBackendOptions = OllamaBackendOptions()):
        self.cfg = cfg

    def generate(self, prompt: str) -> str:
        """
        For your pipeline: generate(prompt) -> raw model output text.
        """
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages)

    def stream_generate(self, prompt: str):
        """
        Streaming generator: yields raw text chunks.
        """
        messages = [{"role": "user", "content": prompt}]
        return self.stream_chat(messages)

    def chat(self, messages: list[dict]) -> str:
        if self.cfg.mode == OllamaMode.LOCAL:
            return self._chat_local(messages)
        return self._chat_http(messages)

    def stream_chat(self, messages: list[dict]):
        if self.cfg.mode == OllamaMode.LOCAL:
            return self._chat_local_stream(messages)
        return self._chat_http_stream(messages)

    # ---------- LOCAL (python package) ----------

    def _chat_local(self, messages: list[dict]) -> str:
        if sys.platform.startswith("win"):
            return self._chat_http(messages)
        try:
            import ollama  # type: ignore
        except Exception as e:
            raise BackendUnavailableError(
                "Local mode requires `pip install ollama`."
            ) from e

        try:
            resp = ollama.chat(
                model=self.cfg.model,
                messages=messages,
                options=dict(self.cfg.options) if self.cfg.options else None,
            )
            # resp["message"]["content"]
            msg = resp.get("message", {})
            content = msg.get("content")
            if content is None:
                raise BackendRequestError(f"Unexpected ollama.chat response: {resp}")
            return content

        except Exception as e:
            # ollama python client errors are not super standardized; keep message
            raise BackendRequestError(f"ollama.chat failed: {e}") from e

    def _chat_local_stream(self, messages: list[dict]):
        if sys.platform.startswith("win"):
            return self._chat_http_stream(messages)
        try:
            import ollama  # type: ignore
        except Exception as e:
            raise BackendUnavailableError(
                "Local mode requires `pip install ollama`."
            ) from e

        try:
            resp = ollama.chat(
                model=self.cfg.model,
                messages=messages,
                options=dict(self.cfg.options) if self.cfg.options else None,
                stream=True,
            )
            for chunk in resp:
                msg = chunk.get("message", {})
                content = msg.get("content")
                if content:
                    yield content
        except Exception as e:
            raise BackendRequestError(f"ollama.chat(stream) failed: {e}") from e

    # ---------- HTTP (remote host) ----------

    def _chat_http(self, messages: list[dict]) -> str:
        import json
        import urllib.request
        import urllib.error

        base = self.cfg.host.rstrip("/")
        url = f"{base}/api/chat"

        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "stream": False,
            "options": dict(self.cfg.options),
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout_sec) as resp:
                data = resp.read().decode("utf-8")
                obj = json.loads(data) if data else {}
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 404:
                raise ModelNotFoundError(msg) from e
            raise BackendRequestError(f"Ollama HTTP {e.code}: {msg}") from e
        except urllib.error.URLError as e:
            raise BackendUnavailableError(f"Ollama not reachable: {base}") from e

        # Ollama /api/chat returns {"message": {"role": "...", "content": "..."}, ...}
        msg = obj.get("message", {})
        content = msg.get("content")
        if content is None:
            raise BackendRequestError(f"Unexpected /api/chat response: {obj}")
        return content

    def _chat_http_stream(self, messages: list[dict]):
        import json
        import urllib.request
        import urllib.error

        base = self.cfg.host.rstrip("/")
        url = f"{base}/api/chat"

        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "stream": True,
            "options": dict(self.cfg.options),
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout_sec) as resp:
                for raw_line in resp:
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if obj.get("done"):
                        break
                    msg = obj.get("message", {})
                    content = msg.get("content")
                    if content:
                        yield content
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")
            if e.code == 404:
                raise ModelNotFoundError(msg) from e
            raise BackendRequestError(f"Ollama HTTP {e.code}: {msg}") from e
        except urllib.error.URLError as e:
            raise BackendUnavailableError(f"Ollama not reachable: {base}") from e

    # Optional helpers (nice for UI)
    def is_available(self) -> bool:
        if self.cfg.mode == OllamaMode.LOCAL:
            # Local mode still needs the daemon; simplest is try a tiny call
            try:
                _ = self._chat_local([{"role": "user", "content": "ping"}])
                return True
            except Exception:
                return False

        # HTTP mode: call /api/version
        import json
        import urllib.request
        import urllib.error

        base = self.cfg.host.rstrip("/")
        url = f"{base}/api/version"
        body = json.dumps({}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                _ = resp.read()
            return True
        except Exception:
            return False
