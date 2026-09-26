"""
Configuration validation for CodeTraceX.

Phase 15: Production Hardening

Validates environment configuration at startup to fail fast with clear errors.
"""
import logging
import re
from typing import List, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Configuration validation error."""
    pass


def validate_database_url(url: str) -> Tuple[bool, str]:
    """
    Validate DATABASE_URL format.
    
    Args:
        url: Database URL
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "DATABASE_URL is required"
    
    # PostgreSQL URL pattern
    if not url.startswith("postgresql"):
        return False, "DATABASE_URL must start with 'postgresql' or 'postgresql+psycopg'"
    
    try:
        parsed = urlparse(url)
        
        if not parsed.hostname:
            return False, "DATABASE_URL missing hostname"
        
        if not parsed.path or parsed.path == "/":
            return False, "DATABASE_URL missing database name"
        
        return True, ""
    
    except Exception as e:
        return False, f"Invalid DATABASE_URL format: {e}"


def validate_redis_url(url: str) -> Tuple[bool, str]:
    """
    Validate REDIS_URL format.
    
    Args:
        url: Redis URL
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "REDIS_URL is required"
    
    if not url.startswith("redis://"):
        return False, "REDIS_URL must start with 'redis://'"
    
    try:
        parsed = urlparse(url)
        
        if not parsed.hostname:
            return False, "REDIS_URL missing hostname"
        
        return True, ""
    
    except Exception as e:
        return False, f"Invalid REDIS_URL format: {e}"


def validate_positive_integer(value: int, name: str, min_value: int = 1) -> Tuple[bool, str]:
    """
    Validate positive integer configuration.
    
    Args:
        value: Value to validate
        name: Configuration name
        min_value: Minimum allowed value
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(value, int):
        return False, f"{name} must be an integer"
    
    if value < min_value:
        return False, f"{name} must be >= {min_value}"
    
    return True, ""


def validate_port(port: int) -> Tuple[bool, str]:
    """
    Validate port number.
    
    Args:
        port: Port number
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(port, int):
        return False, "APP_PORT must be an integer"
    
    if port < 1 or port > 65535:
        return False, "APP_PORT must be between 1 and 65535"
    
    return True, ""


def validate_configuration() -> None:
    """
    Validate application configuration at startup.
    
    Raises:
        ConfigurationError: If configuration is invalid
    """
    from app.core.config import get_settings
    
    errors: List[str] = []
    settings = get_settings()
    
    logger.info("Validating configuration...")
    
    # Validate DATABASE_URL
    valid, error = validate_database_url(settings.DATABASE_URL)
    if not valid:
        errors.append(error)
    
    # Validate REDIS_URL
    valid, error = validate_redis_url(settings.REDIS_URL)
    if not valid:
        errors.append(error)
    
    # Validate APP_PORT
    valid, error = validate_port(settings.APP_PORT)
    if not valid:
        errors.append(error)
    
    # Validate pool sizes
    valid, error = validate_positive_integer(settings.DB_POOL_SIZE, "DB_POOL_SIZE")
    if not valid:
        errors.append(error)
    
    valid, error = validate_positive_integer(settings.DB_MAX_OVERFLOW, "DB_MAX_OVERFLOW")
    if not valid:
        errors.append(error)
    
    # Validate repository limits
    valid, error = validate_positive_integer(settings.MAX_REPOSITORY_SIZE_MB, "MAX_REPOSITORY_SIZE_MB")
    if not valid:
        errors.append(error)
    
    valid, error = validate_positive_integer(settings.MAX_REPOSITORY_FILES, "MAX_REPOSITORY_FILES")
    if not valid:
        errors.append(error)
    
    # Validate embedding configuration
    valid, error = validate_positive_integer(settings.EMBEDDING_DIMENSION, "EMBEDDING_DIMENSION")
    if not valid:
        errors.append(error)
    
    valid, error = validate_positive_integer(settings.EMBEDDING_BATCH_SIZE, "EMBEDDING_BATCH_SIZE")
    if not valid:
        errors.append(error)
    
    valid, error = validate_positive_integer(
        settings.MAX_EMBEDDING_CONTENT_LENGTH, 
        "MAX_EMBEDDING_CONTENT_LENGTH",
        min_value=100
    )
    if not valid:
        errors.append(error)
    
    # Validate worker configuration
    valid, error = validate_positive_integer(settings.WORKER_CONCURRENCY, "WORKER_CONCURRENCY")
    if not valid:
        errors.append(error)
    
    valid, error = validate_positive_integer(
        settings.MAX_CONCURRENT_ANALYSIS_JOBS,
        "MAX_CONCURRENT_ANALYSIS_JOBS"
    )
    if not valid:
        errors.append(error)
    
    valid, error = validate_positive_integer(settings.JOB_TIMEOUT, "JOB_TIMEOUT", min_value=60)
    if not valid:
        errors.append(error)
    
    valid, error = validate_positive_integer(settings.JOB_RESULT_TTL, "JOB_RESULT_TTL", min_value=60)
    if not valid:
        errors.append(error)
    
    # Validate LLM timeout
    valid, error = validate_positive_integer(settings.LLM_TIMEOUT, "LLM_TIMEOUT", min_value=5)
    if not valid:
        errors.append(error)
    
    # Validate LLM max tokens
    valid, error = validate_positive_integer(settings.LLM_MAX_TOKENS, "LLM_MAX_TOKENS", min_value=100)
    if not valid:
        errors.append(error)
    
    # Check environment
    if settings.APP_ENV not in ["development", "production", "test"]:
        errors.append("APP_ENV must be one of: development, production, test")
    
    # Warn if LLM API key is missing (not required but useful)
    if not settings.LLM_API_KEY:
        logger.warning("LLM_API_KEY not set - LLM features will not work")
    
    # Report errors
    if errors:
        error_message = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        logger.error(error_message)
        raise ConfigurationError(error_message)
    
    logger.info("Configuration validation passed")
    
    # Log non-sensitive configuration
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Port: {settings.APP_PORT}")
    logger.info(f"Database pool size: {settings.DB_POOL_SIZE}")
    logger.info(f"Max repository size: {settings.MAX_REPOSITORY_SIZE_MB}MB")
    logger.info(f"Max repository files: {settings.MAX_REPOSITORY_FILES}")
    logger.info(f"Worker concurrency: {settings.WORKER_CONCURRENCY}")
    logger.info(f"Job timeout: {settings.JOB_TIMEOUT}s")
