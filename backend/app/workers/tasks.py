"""
Task handlers for background jobs.

Phase 14: Background Processing
Phase 15: Production Hardening - Job correlation, structured logging, resource cleanup

These functions are called by RQ workers to execute background jobs.
They are the bridge between Redis queue and business logic.
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import AnalysisRun
from app.services.job_orchestration_service import JobOrchestrationService
from app.utils.logging_config import set_request_context, clear_request_context
from app.middleware.error_handlers import get_safe_error_message

logger = logging.getLogger(__name__)


def analyze_repository_task(analysis_run_id: str, repository_url: str) -> Dict[str, Any]:
    """
    Background task for repository analysis.
    
    Phase 15 enhancements:
    - Job correlation in logs
    - Guaranteed session cleanup
    - Safe error messages
    - Resource cleanup on all exit paths
    
    This function is called by RQ worker to execute repository analysis.
    It creates a database session, retrieves the AnalysisRun, and executes
    the orchestration service.
    
    Design:
    - One task per repository analysis
    - Task owns database session lifecycle
    - Task handles cleanup on success and failure
    - Task does not expose secrets in return value
    
    Args:
        analysis_run_id: UUID of AnalysisRun
        repository_url: GitHub repository URL
        
    Returns:
        Dictionary with task results (safe for storage in Redis)
        
    Raises:
        Exception: Various exceptions based on failure mode
    """
    db: Session = None
    analysis_run = None
    
    try:
        # Set job correlation context for logging
        set_request_context(
            job_id=f"job-{analysis_run_id[:8]}",
            analysis_run_id=analysis_run_id
        )
        
        logger.info(f"Starting repository analysis task: {analysis_run_id}")
        logger.info(f"Repository URL: {repository_url}")
        
        # Create database session
        db = SessionLocal()
        
        # Retrieve AnalysisRun
        analysis_run = db.query(AnalysisRun).filter(
            AnalysisRun.id == analysis_run_id
        ).first()
        
        if not analysis_run:
            error_msg = f"AnalysisRun not found: {analysis_run_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Add repository ID to logging context
        set_request_context(repository_id=str(analysis_run.repository_id))
        
        # Create orchestration service
        orchestrator = JobOrchestrationService(db, analysis_run)
        
        # Execute analysis pipeline
        logger.info("Executing analysis pipeline")
        result = orchestrator.execute_analysis(repository_url)
        
        logger.info(f"Completed repository analysis task: {analysis_run_id}")
        
        return {
            "status": "completed",
            "analysis_run_id": analysis_run_id,
            "repository_url": repository_url,
            **result
        }
        
    except Exception as e:
        logger.error(f"Repository analysis task failed: {e}", exc_info=True)
        
        # Get safe error message (no secrets)
        safe_error = get_safe_error_message(e)
        
        # Ensure failure is recorded in database
        if db and analysis_run:
            try:
                orchestrator = JobOrchestrationService(db, analysis_run)
                orchestrator.mark_failed(safe_error)
                logger.info("Marked analysis as failed in database")
            except Exception as mark_error:
                logger.error(f"Failed to mark analysis as failed: {mark_error}")
        
        # Re-raise with safe message
        raise Exception(safe_error) from e
        
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


def cancel_analysis_task(analysis_run_id: str) -> Dict[str, Any]:
    """
    Cancel a running analysis task.
    
    Phase 15 enhancements:
    - Job correlation in logs
    - Guaranteed session cleanup
    
    This is a cooperative cancellation mechanism.
    The task checks a cancellation flag at pipeline boundaries.
    
    Note: RQ does not support forceful termination of running tasks.
    This function marks the analysis as cancelled in the database.
    The running task will detect this and exit gracefully.
    
    Args:
        analysis_run_id: UUID of AnalysisRun to cancel
        
    Returns:
        Dictionary with cancellation result
    """
    db: Session = None
    
    try:
        # Set job correlation context
        set_request_context(
            job_id=f"cancel-{analysis_run_id[:8]}",
            analysis_run_id=analysis_run_id
        )
        
        logger.info(f"Cancelling analysis task: {analysis_run_id}")
        
        # Create database session
        db = SessionLocal()
        
        # Retrieve AnalysisRun
        analysis_run = db.query(AnalysisRun).filter(
            AnalysisRun.id == analysis_run_id
        ).first()
        
        if not analysis_run:
            error_msg = f"AnalysisRun not found: {analysis_run_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Mark as cancelled
        from app.db.models import AnalysisStatus
        from datetime import datetime
        
        analysis_run.status = AnalysisStatus.CANCELLED
        analysis_run.completed_at = datetime.utcnow()
        analysis_run.current_stage = "Cancelled"
        db.commit()
        
        logger.info(f"Marked analysis as cancelled: {analysis_run_id}")
        
        return {
            "status": "cancelled",
            "analysis_run_id": analysis_run_id
        }
        
    except Exception as e:
        logger.error(f"Failed to cancel analysis task: {e}", exc_info=True)
        safe_error = get_safe_error_message(e)
        raise Exception(safe_error) from e
        
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
