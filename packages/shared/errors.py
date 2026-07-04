"""Domain errors that map to HTTP status codes.

These are raised in service/repository layers and caught by the API
exception handler middleware. Keeps HTTP concerns out of business logic.
"""


class CronwaveError(Exception):
    """Base for all domain errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An internal error occurred"):
        self.message = message
        super().__init__(message)


class NotFoundError(CronwaveError):
    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, resource: str, identifier: str):
        super().__init__(f"{resource} '{identifier}' not found")


class ConflictError(CronwaveError):
    status_code = 409
    error_code = "CONFLICT"


class ValidationError(CronwaveError):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class PermissionDeniedError(CronwaveError):
    status_code = 403
    error_code = "PERMISSION_DENIED"

    def __init__(self, message: str = "You don't have permission to perform this action"):
        super().__init__(message)


class AuthenticationError(CronwaveError):
    status_code = 401
    error_code = "AUTHENTICATION_REQUIRED"

    def __init__(self, message: str = "Invalid or expired credentials"):
        super().__init__(message)


class JobStateError(CronwaveError):
    """Raised when a job transition is invalid (e.g., completing a cancelled job)."""

    status_code = 409
    error_code = "INVALID_STATE_TRANSITION"
