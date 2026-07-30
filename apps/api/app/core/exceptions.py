"""Domain errors that services raise without knowing anything about HTTP.

`register_exception_handlers` is the single place where they become responses,
which keeps `services/` free of FastAPI imports and unit-testable in isolation.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "domain_error"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class PermissionDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class AuthenticationError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"


class ValidationError(DomainError):
    # Literal 422 rather than the Starlette constant, which was renamed between
    # versions (UNPROCESSABLE_ENTITY → UNPROCESSABLE_CONTENT).
    status_code = 422
    code = "validation_error"


class ServiceUnavailableError(DomainError):
    """An external dependency (e.g. the calendar assistant) is unreachable or
    unconfigured. Distinct from ConflictError: nothing about the request was
    wrong, retrying later may simply work."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )
