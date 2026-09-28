"""
Redis connection utilities for background jobs.

Phase 14: Background Processing
Phase 15: Production Hardening - Connection reliability, error handling, timeouts

Features:
- Connection pooling
- Timeout configuration
- Error handling
- Health checks
"""
import logging
import redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from rq import Queue
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Global connection pool
_redis_pool: Optional[redis.ConnectionPool] = None


def get_redis_connection_pool() -> redis.ConnectionPool:
    """
    Get or create Redis connection pool.
    
    Uses a singleton pattern to reuse the pool across requests.
    
    Returns:
        Redis connection pool
    """
    global _redis_pool
    
    if _redis_pool is None:
        logger.info("Creating Redis connection pool")
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=False,  # RQ requires bytes mode
            socket_connect_timeout=5,  # Connection timeout
            socket_timeout=5,  # Socket operation timeout
            socket_keepalive=True,  # Enable TCP keepalive
            max_connections=20,  # Maximum connections in pool
        )
    
    return _redis_pool


def get_redis_connection():
    """
    Get Redis connection from pool.
    
    Phase 15: Uses connection pool with proper timeouts and error handling.
    
    Returns:
        Redis connection instance
        
    Raises:
        RedisConnectionError: If connection fails
    """
    try:
        pool = get_redis_connection_pool()
        conn = redis.Redis(connection_pool=pool)
        
        # Test connection
        conn.ping()
        
        return conn
    
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error connecting to Redis: {e}")
        raise RedisConnectionError(f"Failed to connect to Redis: {e}") from e


def get_queue(name: str = "default") -> Queue:
    """
    Get RQ queue instance.
    
    Args:
        name: Queue name
        
    Returns:
        RQ Queue instance
        
    Raises:
        RedisConnectionError: If Redis is unavailable
    """
    try:
        conn = get_redis_connection()
        return Queue(name, connection=conn)
    except Exception as e:
        logger.error(f"Failed to create queue '{name}': {e}")
        raise


def get_analysis_queue() -> Queue:
    """
    Get the analysis queue.
    
    Returns:
        RQ Queue for repository analysis jobs
        
    Raises:
        RedisConnectionError: If Redis is unavailable
    """
    return get_queue("analysis")


def check_redis_health() -> bool:
    """
    Check if Redis is available.
    
    Returns:
        True if Redis is healthy, False otherwise
    """
    try:
        conn = get_redis_connection()
        conn.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False


def close_redis_connections():
    """
    Close Redis connection pool.
    
    Call this during application/worker shutdown.
    """
    global _redis_pool
    
    if _redis_pool is not None:
        try:
            _redis_pool.disconnect()
            _redis_pool = None
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.error(f"Error closing Redis pool: {e}")
