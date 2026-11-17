"""Public domain errors, free of local file paths and private payloads."""


class SireError(Exception):
    """Carry an HTTP-compatible status and stable application error code."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
