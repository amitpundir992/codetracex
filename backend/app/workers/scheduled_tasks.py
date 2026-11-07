"""
Scheduled tasks for CodeTraceX background processing.

Phase 25: Operational Reliability & Automated Recovery

This module defines periodic tasks that run via RQ scheduler.
Tasks are registered with the worker when it starts.

Architecture:
- Uses RQ's built-in scheduler (no separate system required)
- Worker runs with with_scheduler=True
- Tasks are scheduled using cron-like intervals
- Each task runs as a regular RQ job

Scheduled Tasks:
1. Stale analysis recovery - Detects and marks stale jobs as failed
2. Additional maintenance tasks (future enhancement)
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.recovery_service import RecoveryService
from app.utils.logging_config import set_request_context, clear_request_context
from app.middleware.error_handlers import get_safe_error_message

logger = logging.getLogger(__name__)


def recover_stale_analyses_task(
    stale_threshold_hours: int = 24,
    repository_id: str = None
) -> Dict[str, Any]:
    """
    Scheduled task to recover stale analysis runs.
    
    This task runs periodically to detect and mark stale jobs as failed.
    It ensures the system maintains accurate state even when workers crash
    or jobs are killed unexpectedly.
    
    Safety features:
    - Read-only until recovery decision is made
    - Idempotent (safe to run multiple times)
    - Repository isolation support
    - Comprehensive logging
    - Automatic session cleanup
    
    Args:
        stale_threshold_hours: Hours after which a job is considered stale
        repository_id: Optional repository UUID to filter by
        
    Returns:
        Dictionary with recovery statistics
        
    Raises:
        Exception: On critical failure (prevents silent failures)
    """
    db: Session = None
    
    try:
        # Set logging context
        set_request_context(
            job_id="scheduled-recovery",
            task="stale_analysis_recovery"
        )
        
        logger.info(
            f"Starting scheduled stale analysis recovery "
            f"(threshold={stale_threshold_hours}h)"
        )
        
        # Create database session
        db = SessionLocal()
        
        # Create recovery service
        recovery_service = RecoveryService(db)
        
        # Perform recovery
        result = recovery_service.recover_stale_analyses(
            repository_id=repository_id,
            stale_threshold_hours=stale_threshold_hours
        )
        
        # Log summary
        if result['recovered_count'] > 0:
            logger.warning(
                f"Stale analysis recovery completed: "
                f"{result['recovered_count']} runs marked as failed"
            )
        else:
            logger.info("Stale analysis recovery completed: no stale runs detected")
        
        return {
            "status": "completed",
            "task": "recover_stale_analyses",
            **result
        }
        
    except Exception as e:
        logger.error(
            f"Stale analysis recovery task failed: {e}",
            exc_info=True
        )
        
        # Get safe error message (no secrets)
        safe_error = get_safe_error_message(e)
        
        # Re-raise to mark task as failed in RQ
        raise Exception(f"Recovery task failed: {safe_error}") from e
        
    finally:
        # Always close database session
        if db:
            try:
                db.close()
                logger.debug("Database session closed")
            except Exception as close_error:
                logger.error(f"Failed to close database session: {close_error}")
        
        # Clear logging context
        clear_request_context()


def check_stale_analyses_task(
    stale_threshold_hours: int = 24
) -> Dict[str, Any]:
    """
    Scheduled task to check for stale analyses without recovering them.
    
    This is a monitoring task that reports stale runs without modifying state.
    Useful for alerting and observability.
    
    Args:
        stale_threshold_hours: Hours after which a job is considered stale
        
    Returns:
        Dictionary with stale run information
    """
    db: Session = None
    
    try:
        # Set logging context
        set_request_context(
            job_id="scheduled-check",
            task="stale_analysis_check"
        )
        
        logger.info(
            f"Starting scheduled stale analysis check "
            f"(threshold={stale_threshold_hours}h)"
        )
        
        # Create database session
        db = SessionLocal()
        
        # Create recovery service
        recovery_service = RecoveryService(db)
        
        # Check for stale runs (read-only)
        stale_runs = recovery_service.check_stale_runs(
            stale_threshold_hours=stale_threshold_hours
        )
        
        # Log results
        if stale_runs:
            logger.warning(
                f"Found {len(stale_runs)} stale analysis runs: "
                f"{[run['analysis_run_id'][:8] for run in stale_runs]}"
            )
            for run in stale_runs:
                logger.warning(
                    f"Stale run detected: {run['analysis_run_id'][:8]}, "
                    f"status={run['status']}, "
                    f"elapsed={run['elapsed_hours']}h, "
                    f"stage={run['current_stage']}"
                )
        else:
            logger.info("No stale analysis runs detected")
        
        return {
            "status": "completed",
            "task": "check_stale_analyses",
            "stale_count": len(stale_runs),
            "stale_runs": stale_runs
        }
        
    except Exception as e:
        logger.error(
            f"Stale analysis check task failed: {e}",
            exc_info=True
        )
        
        # Get safe error message
        safe_error = get_safe_error_message(e)
        
        # Re-raise to mark task as failed in RQ
        raise Exception(f"Check task failed: {safe_error}") from e
        
    finally:
        # Always close database session
        if db:
            try:
                db.close()
                logger.debug("Database session closed")
            except Exception as close_error:
                logger.error(f"Failed to close database session: {close_error}")
        
        # Clear logging context
        clear_request_context()
