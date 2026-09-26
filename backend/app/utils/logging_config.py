"""
Structured logging configuration for CodeTraceX.

Phase 15: Production Hardening

This module provides:
- Structured logging with JSON format option
- Request ID correlation
- Log sanitization to prevent secret leakage
- Context variables for job correlation
"""
import logging
import re
import sys
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variables for request and job correlation
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
job_id_var: ContextVar[Optional[str]] = ContextVar('job_id', default=None)
analysis_run_id_var: ContextVar[Optional[str]] = ContextVar('analysis_run_id', default=None)
repository_id_var: ContextVar[Optional[str]] = ContextVar('repository_id', default=None)

# Patterns for sensitive data that should never be logged
SENSITIVE_PATTERNS = [
    # API keys and tokens
    (re.compile(r'(api[_-]?key|token|bearer)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.IGNORECASE), r'\1=***REDACTED***'),
    # Redis URLs with credentials
    (re.compile(r'redis://([^:]+):([^@]+)@'), r'redis://***:***@'),
    # PostgreSQL URLs with credentials
    (re.compile(r'postgresql(\+\w+)?://([^:]+):([^@]+)@'), r'postgresql\1://***:***@'),
    # Authorization headers
    (re.compile(r'(authorization|auth)\s*:\s*["\']?([^"\']+)["\']?', re.IGNORECASE), r'\1: ***REDACTED***'),
    # Generic passwords
    (re.compile(r'(password|passwd|pwd)\s*[=:]\s*["\']?([^"\'&\s]+)["\']?', re.IGNORECASE), r'\1=***REDACTED***'),
    # LLM API keys (Gemini, OpenAI, etc.)
    (re.compile(r'(AIzaSy[a-zA-Z0-9_\-]{33})', re.IGNORECASE), r'***REDACTED_GEMINI_KEY***'),
    (re.compile(r'(sk-[a-zA-Z0-9]{48})', re.IGNORECASE), r'***REDACTED_OPENAI_KEY***'),
]


def sanitize_log_message(message: str) -> str:
    """
    Sanitize log messages to remove sensitive information.
    
    This prevents accidental logging of:
    - API keys
    - Database credentials
    - Redis URLs with passwords
    - Authorization headers
    - LLM provider keys
    
    Args:
        message: Original log message
        
    Returns:
        Sanitized message with secrets redacted
    """
    sanitized = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class SanitizingFormatter(logging.Formatter):
    """
    Logging formatter that sanitizes sensitive information.
    
    Automatically removes secrets from log messages before output.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with sanitization."""
        # Sanitize the message
        original_msg = record.getMessage()
        sanitized_msg = sanitize_log_message(original_msg)
        record.msg = sanitized_msg
        record.args = ()  # Clear args to prevent double formatting
        
        # Add correlation IDs from context
        record.request_id = request_id_var.get() or '-'
        record.job_id = job_id_var.get() or '-'
        record.analysis_run_id = analysis_run_id_var.get() or '-'
        record.repository_id = repository_id_var.get() or '-'
        
        return super().format(record)


class StructuredFormatter(SanitizingFormatter):
    """
    JSON structured logging formatter.
    
    Outputs logs in JSON format for easy parsing by log aggregation systems.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        import json
        from datetime import datetime
        
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_message(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add correlation IDs if present
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id
        
        job_id = job_id_var.get()
        if job_id:
            log_data["job_id"] = job_id
        
        analysis_run_id = analysis_run_id_var.get()
        if analysis_run_id:
            log_data["analysis_run_id"] = analysis_run_id
        
        repository_id = repository_id_var.get()
        if repository_id:
            log_data["repository_id"] = repository_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def configure_logging(
    level: str = "INFO",
    use_json: bool = False
) -> None:
    """
    Configure application logging.
    
    Sets up structured logging with sanitization.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        use_json: If True, use JSON structured format
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    if use_json:
        formatter = StructuredFormatter()
    else:
        # Human-readable format with correlation IDs
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[req_id=%(request_id)s job_id=%(job_id)s analysis=%(analysis_run_id)s repo=%(repository_id)s] - '
            '%(message)s'
        )
        formatter = SanitizingFormatter(format_string)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def set_request_context(
    request_id: Optional[str] = None,
    job_id: Optional[str] = None,
    analysis_run_id: Optional[str] = None,
    repository_id: Optional[str] = None
) -> None:
    """
    Set logging context for request/job correlation.
    
    This should be called at the beginning of request/job processing.
    
    Args:
        request_id: API request ID
        job_id: Background job ID
        analysis_run_id: Analysis run UUID
        repository_id: Repository UUID
    """
    if request_id:
        request_id_var.set(request_id)
    if job_id:
        job_id_var.set(job_id)
    if analysis_run_id:
        analysis_run_id_var.set(analysis_run_id)
    if repository_id:
        repository_id_var.set(repository_id)


def clear_request_context() -> None:
    """Clear logging context."""
    request_id_var.set(None)
    job_id_var.set(None)
    analysis_run_id_var.set(None)
    repository_id_var.set(None)


def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return request_id_var.get()
