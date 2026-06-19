class BackendConnectionError(RuntimeError):
    """Raised when the LuxCode backend cannot be reached."""


class BackendResponseError(RuntimeError):
    """Raised when the backend response is not usable JSON."""
