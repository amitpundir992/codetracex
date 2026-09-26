"""
Health and readiness check endpoints.

Phase 15: Production Hardening

Health checks:
- /health: Lightweight liveness check (is process alive?)
- /ready: Readiness check (can serve traffic? are dependencies available?)

These endpoints are used by:
- Kubernetes/Docker health probes
- Load balancers
- Monitoring systems
"""
import logging
from typing import Dict, Any
from enum import Enum

from fastapi import APIRouter, status, Response
from sqlalchemy import text
import redis

from app.db.session import engine
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

settings = get_settings()


class HealthStatus(str, Enum):
    """Health check status values."""
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@router.get("/health")
async def health_check():
    """
    Liveness health check.
    
    This is a lightweight check that only verifies the application process is alive.
    It does NOT check external dependencies.
    
    Use this for:
    - Kubernetes liveness probes
    - Basic monitoring
    - Load balancer health checks (if you want fast checks)
    
    Returns:
        200: Service is alive
    """
    return {
        "status": HealthStatus.OK,
        "service": "codetracex-backend"
    }


def check_database() -> Dict[str, Any]:
    """
    Check database connectivity.
    
    Performs a simple query to verify database is reachable.
    Uses a short timeout to avoid blocking.
    
    Returns:
        Dictionary with status and optional error
    """
    try:
        # Use connection from pool with timeout
        with engine.connect() as conn:
            # Simple query with short timeout
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        return {
            "status": HealthStatus.OK,
            "message": "Database connection successful"
        }
    
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": HealthStatus.UNAVAILABLE,
            "message": "Database unavailable",
            "error": type(e).__name__  # Don't expose details
        }


def check_redis() -> Dict[str, Any]:
    """
    Check Redis connectivity.
    
    Performs a simple PING to verify Redis is reachable.
    Uses a short timeout.
    
    Returns:
        Dictionary with status and optional error
    """
    try:
        # Create Redis connection with timeout
        redis_client = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True
        )
        
        # Simple ping
        redis_client.ping()
        redis_client.close()
        
        return {
            "status": HealthStatus.OK,
            "message": "Redis connection successful"
        }
    
    except redis.ConnectionError as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": HealthStatus.UNAVAILABLE,
            "message": "Redis unavailable",
            "error": "ConnectionError"
        }
    
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": HealthStatus.UNAVAILABLE,
            "message": "Redis unavailable",
            "error": type(e).__name__
        }


@router.get("/ready")
async def readiness_check(response: Response):
    """
    Readiness health check.
    
    This checks if the application is ready to serve traffic.
    Verifies that required dependencies are available:
    - PostgreSQL database
    - Redis cache/queue
    
    Use this for:
    - Kubernetes readiness probes
    - Load balancer routing decisions
    - Deployment verification
    
    Returns:
        200: Service is ready
        503: Service is not ready (dependencies unavailable)
    """
    checks = {}
    overall_status = HealthStatus.OK
    
    # Check database
    db_check = check_database()
    checks["database"] = db_check
    if db_check["status"] != HealthStatus.OK:
        overall_status = HealthStatus.UNAVAILABLE
    
    # Check Redis
    redis_check = check_redis()
    checks["redis"] = redis_check
    if redis_check["status"] != HealthStatus.OK:
        overall_status = HealthStatus.UNAVAILABLE
    
    # Determine HTTP status code
    if overall_status == HealthStatus.OK:
        response.status_code = status.HTTP_200_OK
        status_message = "ready"
    else:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        status_message = "not_ready"
    
    return {
        "status": status_message,
        "checks": {
            "database": {
                "status": checks["database"]["status"],
                "message": checks["database"].get("message", "")
            },
            "redis": {
                "status": checks["redis"]["status"],
                "message": checks["redis"].get("message", "")
            }
        }
    }
