"""
Centralized error handling for FastAPI application.

Phase 15: Production Hardening

This module provides:
- Safe error responses (no secret leakage)
- Structured error format
- Request ID inclusion in errors
- Appropriate HTTP status codes
- Internal logging with full details
"""
import logging
from typing import Any, Dict, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.logging_config import get_request_id, sanitize_log_message

logger = logging.getLogger(__name__)


class SafeAPIError(Exception):
    """
    Base exception for safe API errors.
    
    These errors contain only safe information that can be returned to clients.
    Internal details should be logged separately.
    """
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize safe API error.
        
        Args:
            message: Safe error message for client
            status_code: HTTP status code
            error_code: Machine-readable error code
            details: Optional additional safe details
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


def create_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """
    Create standardized error response.
    
    Response format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable message",
            "request_id": "abc123",
            "details": {}  // optional
        }
    }
    
    Args:
        request: FastAPI request
        status_code: HTTP status code
        error_code: Machine-readable error code
        message: Human-readable error message
        details: Optional additional details
        
    Returns:
        JSONResponse with standardized error format
    """
    request_id = get_request_id()
    if not request_id:
        # Fallback if middleware hasn't set it
        request_id = getattr(request.state, "request_id", "unknown")
    
    error_body = {
        "error": {
            "code": error_code,
            "message": message,
            "request_id": request_id
        }
    }
    
    if details:
        error_body["error"]["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=error_body
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle FastAPI validation errors.
    
    These occur when request data doesn't match Pydantic schemas.
    
    Args:
        request: FastAPI request
        exc: Validation error
        
    Returns:
        Structured error response
    """
    logger.warning(f"Validation error: {exc.errors()}")
    
    # Sanitize validation errors (might contain sensitive input)
    safe_errors = []
    for error in exc.errors():
        safe_error = {
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        }
        safe_errors.append(safe_error)
    
    return create_error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"validation_errors": safe_errors}
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle Starlette/FastAPI HTTP exceptions.
    
    Args:
        request: FastAPI request
        exc: HTTP exception
        
    Returns:
        Structured error response
    """
    # Map status code to error code
    error_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT"
    }
    
    error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")
    
    # Log internal errors
    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    else:
        logger.info(f"HTTP {exc.status_code}: {exc.detail}")
    
    return create_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=error_code,
        message=str(exc.detail)
    )


async def safe_api_error_handler(
    request: Request,
    exc: SafeAPIError
) -> JSONResponse:
    """
    Handle SafeAPIError exceptions.
    
    Args:
        request: FastAPI request
        exc: Safe API error
        
    Returns:
        Structured error response
    """
    logger.error(f"Safe API error: {exc.error_code} - {exc.message}")
    
    return create_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle unexpected exceptions.
    
    This is the catch-all handler for any exception not handled elsewhere.
    It logs full details internally but returns only safe information to client.
    
    Args:
        request: FastAPI request
        exc: Any unhandled exception
        
    Returns:
        Generic error response
    """
    # Log full exception with stack trace
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Return generic safe message
    return create_error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred. Please try again later."
    )


def get_safe_error_message(exc: Exception) -> str:
    """
    Convert exception to safe error message.
    
    This removes sensitive information like file paths, connection strings, etc.
    while preserving useful diagnostic information.
    
    Args:
        exc: Exception
        
    Returns:
        Safe error message suitable for logging and display
    """
    error_message = str(exc)
    
    # Use sanitize function from logging_config
    safe_message = sanitize_log_message(error_message)
    
    # Map known exception types to safe messages
    exc_type = type(exc).__name__
    
    if "Connection" in exc_type or "ConnectionError" in error_message:
        return "Database or external service connection failed"
    
    if "Redis" in exc_type or "Redis" in error_message:
        return "Cache service temporarily unavailable"
    
    if "Timeout" in exc_type or "timeout" in error_message.lower():
        return "Operation timed out"
    
    if "PermissionError" in exc_type:
        return "File system permission denied"
    
    # Truncate very long messages
    if len(safe_message) > 500:
        safe_message = safe_message[:500] + "... (truncated)"
    
    return safe_message
