"""
Custom exception classes for Kanwar Sahayata.

Provides consistent error handling with HTTP status codes
and structured error responses across all API endpoints.
"""

from typing import Optional, Any, Dict


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found (404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        error_code: str = "NOT_FOUND",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=404,
            error_code=error_code,
            details=details,
        )


class ValidationError(AppException):
    """Request validation failed (422)."""

    def __init__(
        self,
        message: str = "Validation failed",
        error_code: str = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=422,
            error_code=error_code,
            details=details,
        )


class DuplicateError(AppException):
    """Resource already exists (409)."""

    def __init__(
        self,
        message: str = "Resource already exists",
        error_code: str = "DUPLICATE",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=409,
            error_code=error_code,
            details=details,
        )


class ConflictError(AppException):
    """Resource state conflict (409)."""

    def __init__(
        self,
        message: str = "Resource state conflict",
        error_code: str = "CONFLICT",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=409,
            error_code=error_code,
            details=details,
        )


class UnauthorizedError(AppException):
    """Authentication required (401)."""

    def __init__(
        self,
        message: str = "Authentication required",
        error_code: str = "UNAUTHORIZED",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=401,
            error_code=error_code,
            details=details,
        )


class ForbiddenError(AppException):
    """Permission denied (403)."""

    def __init__(
        self,
        message: str = "Permission denied",
        error_code: str = "FORBIDDEN",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=403,
            error_code=error_code,
            details=details,
        )


class SeasonNotActiveError(AppException):
    """Operation requires an active season (400)."""

    def __init__(
        self,
        message: str = "No active season found",
        error_code: str = "SEASON_NOT_ACTIVE",
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code,
        )


class ServiceUnavailableError(AppException):
    """External service unavailable (503)."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        error_code: str = "SERVICE_UNAVAILABLE",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=503,
            error_code=error_code,
            details=details,
        )


class RateLimitError(AppException):
    """Too many requests (429)."""

    def __init__(
        self,
        message: str = "Too many requests. Please try again later.",
        error_code: str = "RATE_LIMIT_EXCEEDED",
        retry_after_seconds: int = 60,
    ):
        super().__init__(
            message=message,
            status_code=429,
            error_code=error_code,
            details={"retry_after_seconds": retry_after_seconds},
        )