class BackendError(Exception):
    """Base backend error."""


class BackendUnavailableError(BackendError):
    """Backend service not reachable (e.g., Ollama not running)."""


class BackendRequestError(BackendError):
    """Backend returned an error response or invalid payload."""


class ModelNotFoundError(BackendError):
    """Model not found in backend."""