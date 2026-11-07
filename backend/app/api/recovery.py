"""
API endpoints for operational recovery and maintenance.

Phase 25: Operational Reliability & Automated Recovery

These endpoints provide manual triggers for recovery operations.
They are designed for:
- Manual recovery after incidents
- Integration with external monitoring/alerting
- Cron job/scheduled task integration
- Administrative operations
"""
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_db
from app.services.recovery_service import RecoveryService
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recovery", tags=["recovery"])
settings = get_settings()


class RecoveryRequest(BaseModel):
    """Request to recover stale analysis runs."""
    repository_id: Optional[UUID] = None
    stale_threshold_hours: Optional[int] = None


class RecoveryResponse(BaseModel):
    """Response from recovery operation."""
    stale_count: int
    recovered_count: int
    repository_id: Optional[str] = None
    threshold_hours: int
    recovered_runs: List[str]
    message: str


class StaleRunInfo(BaseModel):
    """Information about a stale analysis run."""
    analysis_run_id: str
    repository_id: str
    status: str
    started_at: str
    elapsed_hours: float
    current_stage: Optional[str] = None
    progress: Optional[int] = None
    job_id: Optional[str] = None


class StaleRunsResponse(BaseModel):
    """Response with list of stale runs."""
    stale_count: int
    threshold_hours: int
    stale_runs: List[StaleRunInfo]


@router.post("/recover-stale-analyses", response_model=RecoveryResponse)
def recover_stale_analyses(
    request: RecoveryRequest = RecoveryRequest(),
    db: Session = Depends(get_db)
):
    """
    Recover stale analysis runs by marking them as failed.
    
    Phase 25: Automated recovery
    
    This endpoint detects and marks stale RUNNING and QUEUED analysis runs as failed.
    A run is considered stale if it has been running longer than the threshold
    without completing.
    
    Safety guarantees:
    - Only affects RUNNING and QUEUED runs
    - Does not modify completed, failed, or cancelled runs
    - Respects repository isolation if repository_id is provided
    - Idempotent (safe to call multiple times)
    
    Use cases:
    - Manual recovery after worker crash
    - Scheduled cleanup via cron/systemd timer
    - Integration with monitoring/alerting systems
    
    Args:
        request: Recovery parameters (optional)
        db: Database session
        
    Returns:
        Recovery statistics
        
    Raises:
        500: Internal server error
    """
    logger.info(
        f"Starting stale analysis recovery "
        f"(repository_id={request.repository_id}, "
        f"threshold={request.stale_threshold_hours})"
    )
    
    try:
        # Create recovery service
        recovery_service = RecoveryService(db)
        
        # Perform recovery
        result = recovery_service.recover_stale_analyses(
            repository_id=str(request.repository_id) if request.repository_id else None,
            stale_threshold_hours=request.stale_threshold_hours
        )
        
        # Build response
        message = (
            f"Recovery completed: {result['recovered_count']} stale runs marked as failed"
            if result['recovered_count'] > 0
            else "No stale runs detected"
        )
        
        return RecoveryResponse(
            stale_count=result['stale_count'],
            recovered_count=result['recovered_count'],
            repository_id=result['repository_id'],
            threshold_hours=result['threshold_hours'],
            recovered_runs=result['recovered_runs'],
            message=message
        )
        
    except Exception as e:
        logger.error(f"Stale analysis recovery failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recovery operation failed: {str(e)}"
        )


@router.get("/check-stale-analyses", response_model=StaleRunsResponse)
def check_stale_analyses(
    repository_id: Optional[UUID] = Query(None, description="Optional repository ID to filter by"),
    stale_threshold_hours: Optional[int] = Query(None, description="Hours after which a job is stale"),
    db: Session = Depends(get_db)
):
    """
    Check for stale analysis runs without modifying them.
    
    Phase 25: Automated recovery
    
    This is a read-only operation that reports stale runs without changing state.
    Useful for monitoring, alerting, and dashboards.
    
    Args:
        repository_id: Optional repository UUID to filter by
        stale_threshold_hours: Hours after which a job is stale
        db: Database session
        
    Returns:
        List of stale analysis runs with details
        
    Raises:
        500: Internal server error
    """
    try:
        # Create recovery service
        recovery_service = RecoveryService(db)
        
        # Check for stale runs (read-only)
        stale_runs = recovery_service.check_stale_runs(
            repository_id=str(repository_id) if repository_id else None,
            stale_threshold_hours=stale_threshold_hours
        )
        
        # Determine threshold used
        threshold = stale_threshold_hours or getattr(settings, 'STALE_JOB_THRESHOLD_HOURS', 24)
        
        # Build response
        stale_info_list = [
            StaleRunInfo(**run) for run in stale_runs
        ]
        
        return StaleRunsResponse(
            stale_count=len(stale_info_list),
            threshold_hours=threshold,
            stale_runs=stale_info_list
        )
        
    except Exception as e:
        logger.error(f"Stale analysis check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Check operation failed: {str(e)}"
        )
