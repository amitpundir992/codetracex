"""
Redis connection utilities for background jobs.

Phase 14: Background Processing
"""
import redis
from rq import Queue
from app.core.config import get_settings

settings = get_settings()


def get_redis_connection():
    """
    Get Redis connection.
    
    Returns:
        Redis connection instance
    """
    return redis.from_url(
        settings.REDIS_URL,
        decode_responses=False  # RQ requires bytes mode
    )


def get_queue(name: str = "default") -> Queue:
    """
    Get RQ queue instance.
    
    Args:
        name: Queue name
        
    Returns:
        RQ Queue instance
    """
    conn = get_redis_connection()
    return Queue(name, connection=conn)


def get_analysis_queue() -> Queue:
    """
    Get the analysis queue.
    
    Returns:
        RQ Queue for repository analysis jobs
    """
    return get_queue("analysis")
