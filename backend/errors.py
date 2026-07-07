class BackendError(Exception):
    """Base backend error."""

    default_code = "backend_error"

    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message)
        self.code = code or self.default_code


class BackendUnavailableError(BackendError):
    """Backend service not reachable (e.g., Ollama not running)."""

    default_code = "ollama_unavailable"


class BackendRequestError(BackendError):
    """Backend returned an error response or invalid payload."""

    default_code = "backend_request_failed"


class ModelNotFoundError(BackendError):
    """Model not found in backend."""

    default_code = "model_not_found"
