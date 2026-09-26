"""
Request ID middleware for request correlation.

Phase 15: Production Hardening

This middleware:
- Generates unique request IDs for tracing
- Accepts client-provided request IDs (with validation)
- Adds request ID to response headers
- Sets request ID in logging context
"""
import uuid
import re
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.logging_config import set_request_context, clear_request_context

logger = logging.getLogger(__name__)

# Valid request ID pattern (UUID or alphanumeric up to 64 chars)
REQUEST_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-_]{8,64}$')

# Header names
REQUEST_ID_HEADER = "X-Request-ID"


def generate_request_id() -> str:
    """
    Generate a new request ID.
    
    Returns:
        UUID string without hyphens for compactness
    """
    return uuid.uuid4().hex


def validate_request_id(request_id: str) -> bool:
    """
    Validate client-provided request ID.
    
    Prevents log injection and ensures reasonable format.
    
    Args:
        request_id: Client-provided request ID
        
    Returns:
        True if valid, False otherwise
    """
    if not request_id:
        return False
    
    # Check length and pattern
    if len(request_id) < 8 or len(request_id) > 64:
        return False
    
    return bool(REQUEST_ID_PATTERN.match(request_id))


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request ID correlation.
    
    Flow:
    1. Check for existing X-Request-ID header
    2. Validate or generate request ID
    3. Set request ID in logging context
    4. Process request
    5. Add X-Request-ID to response headers
    6. Clear logging context
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with request ID correlation.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/route handler
            
        Returns:
            Response with X-Request-ID header
        """
        # Get or generate request ID
        client_request_id = request.headers.get(REQUEST_ID_HEADER)
        
        if client_request_id and validate_request_id(client_request_id):
            request_id = client_request_id
            logger.debug(f"Using client request ID: {request_id}")
        else:
            request_id = generate_request_id()
            if client_request_id:
                logger.debug(f"Invalid client request ID '{client_request_id}', generated new: {request_id}")
        
        # Set request ID in logging context
        set_request_context(request_id=request_id)
        
        try:
            # Store request ID in request state for access in routes
            request.state.request_id = request_id
            
            # Process request
            response = await call_next(request)
            
            # Add request ID to response headers
            response.headers[REQUEST_ID_HEADER] = request_id
            
            return response
        
        finally:
            # Always clear context after request
            clear_request_context()
