"""Shared application exceptions.

These exceptions are framework-agnostic: they carry a stable machine-readable
``code`` and a human-readable ``message``. The presentation layer is responsible
for translating them into HTTP responses.
"""


class AppError(Exception):
    """Base class for expected application errors."""

    code: str = "application_error"
    message: str = "Application error"
    status_code: int = 400

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class NotFoundError(AppError):
    """Base class for a resource that could not be found."""

    code = "not_found"
    message = "Resource not found"
    status_code = 404


class ConflictError(AppError):
    """Base class for a state conflict."""

    code = "conflict"
    message = "Resource conflict"
    status_code = 409
