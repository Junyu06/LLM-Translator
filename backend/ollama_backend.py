"""Talk to an Ollama server over its HTTP API.

"Local" mode is the same API on this machine, so there is one code path.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List

from .errors import BackendRequestError, BackendUnavailableError, ModelNotFoundError

LOCAL_HOST = "http://127.0.0.1:11434"


@dataclass
class OllamaBackendOptions:
    model: str
    host: str = LOCAL_HOST
    # Greedy decoding: the model cards of Index-Translate and Hy-MT2 evaluate with it.
    options: Dict[str, Any] = field(default_factory=lambda: {"temperature": 0.0})
    timeout_sec: int = 60


class OllamaBackend:
    def __init__(self, cfg: OllamaBackendOptions):
        self.cfg = cfg

    @property
    def base_url(self) -> str:
        return self.cfg.host.strip().rstrip("/") or LOCAL_HOST

    def stream_chat(self, messages: List[dict]) -> Iterator[str]:
        """Yield reply text as it arrives.

        `think: false` matters for Index-Translate: Ollama treats it as a
        reasoning model, and without the flag the rendered prompt differs
        from the format the model was trained on. Models without a thinking
        mode ignore the flag.
        """
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "stream": True,
            "think": False,
            "options": dict(self.cfg.options),
        }
        finished = False
        with self._open("/api/chat", payload) as resp:
            try:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if obj.get("error"):
                        raise BackendRequestError(f"Ollama: {obj['error']}", code="backend_stream_error")
                    content = obj.get("message", {}).get("content")
                    if content:
                        yield content
                    if obj.get("done"):
                        finished = True
                        break
            except json.JSONDecodeError as e:
                raise BackendRequestError(
                    f"Invalid JSON from Ollama stream: {e}",
                    code="invalid_backend_json",
                ) from e
            except TimeoutError as e:
                raise BackendRequestError(f"Ollama timed out: {e}", code="backend_timeout") from e
            except OSError as e:
                raise BackendUnavailableError(f"Ollama connection lost: {self.base_url}") from e
        if not finished:
            raise BackendRequestError(
                "Ollama stopped before the reply finished.",
                code="backend_stream_incomplete",
            )

    def list_models(self) -> List[str]:
        with self._open("/api/tags", None, timeout=5) as resp:
            try:
                obj = json.loads(resp.read().decode("utf-8") or "{}")
            except json.JSONDecodeError as e:
                raise BackendRequestError(f"Invalid JSON from Ollama: {e}", code="invalid_backend_json") from e
        return sorted(m["name"] for m in obj.get("models", []) if isinstance(m, dict) and m.get("name"))

    def _open(self, path: str, payload: dict | None, timeout: int | None = None):
        url = f"{self.base_url}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.cfg.timeout_sec)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            message = _error_message(body) or f"HTTP {e.code}"
            if e.code == 404:
                raise ModelNotFoundError(message) from e
            raise BackendRequestError(f"Ollama HTTP {e.code}: {message}") from e
        except TimeoutError as e:
            raise BackendRequestError(f"Ollama timed out: {e}", code="backend_timeout") from e
        except (urllib.error.URLError, OSError) as e:
            raise BackendUnavailableError(f"Ollama not reachable: {self.base_url}") from e


def _error_message(body: str) -> str:
    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        return body.strip()
    return str(obj.get("error", "")).strip() if isinstance(obj, dict) else body.strip()
