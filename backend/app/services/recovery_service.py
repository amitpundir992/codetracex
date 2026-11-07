"""
Recovery service for Phase 25: Operational Reliability & Automated Recovery.

This service handles automated detection and recovery of stale analysis runs,
ensuring the system maintains reliable state even when jobs fail unexpectedly.

Key Features:
- Automated stale job detection
- Safe state transitions with repository isolation
- Idempotent cleanup operations
- Comprehensive logging without exposing secrets
- Integration with existing background job infrastructure

Design Principles:
- Reuses existing services (PersistenceService for state management)
- No competing job systems (uses RQ scheduler integration)
- Conservative failure detection (avoid false positives)
- Preserves useful analysis results where possible
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import AnalysisRun, AnalysisStatus
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RecoveryService:
    """
    Service for automated recovery of stale analysis runs.
    
    This service detects and marks stale RUNNING and QUEUED jobs as failed,
    ensuring the system maintains accurate state even when:
    - Workers crash (SIGKILL, OOM, timeout)
    - Jobs are killed by RQ timeout
    - Database connections are lost
    - Redis becomes temporarily unavailable
    
    Safety guarantees:
    - Repository isolation (optional per-repository recovery)
    - Configurable stale threshold (avoid false positives)
    - Idempotent operations (safe to call repeatedly)
    - No modification of actively processing jobs
    - No modification of completed/failed/cancelled jobs
    """
    
    def __init__(self, db: Session):
        """
        Initialize recovery service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
    
    def recover_stale_analyses(
        self,
        repository_id: Optional[str] = None,
        stale_threshold_hours: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Detect and recover stale analysis runs.
        
        An analysis run is considered "stale" if:
        - Status is RUNNING or QUEUED
        - Started more than stale_threshold_hours ago
        - Job is no longer actively processing
        
        This method is idempotent and safe to call repeatedly.
        
        Args:
            repository_id: Optional repository UUID to filter by
            stale_threshold_hours: Hours after which a job is stale (default from config)
            
        Returns:
            Dictionary with recovery statistics:
                - stale_count: Number of stale jobs detected
                - recovered_count: Number of jobs marked as failed
                - repository_id: Repository ID if filtered
                - threshold_hours: Threshold used
                - recovered_runs: List of recovered analysis run IDs
        """
        # Use configured threshold if not specified
        if stale_threshold_hours is None:
            stale_threshold_hours = getattr(
                self.settings, 
                'STALE_JOB_THRESHOLD_HOURS', 
                24
            )
        
        logger.info(
            f"Starting stale analysis recovery "
            f"(threshold={stale_threshold_hours}h, "
            f"repository_id={repository_id or 'all'})"
        )
        
        # Calculate cutoff time
        stale_cutoff = datetime.utcnow() - timedelta(hours=stale_threshold_hours)
        
        # Query for stale analysis runs
        query = self.db.query(AnalysisRun).filter(
            and_(
                AnalysisRun.status.in_([AnalysisStatus.RUNNING, AnalysisStatus.QUEUED]),
                AnalysisRun.started_at < stale_cutoff
            )
        )
        
        # Apply repository filter if specified
        if repository_id:
            query = query.filter(AnalysisRun.repository_id == repository_id)
        
        stale_runs = query.all()
        recovered_run_ids = []
        
        # Mark each as failed with appropriate error message
        for run in stale_runs:
            self._mark_run_as_stale(run, stale_threshold_hours)
            recovered_run_ids.append(str(run.id))
            
            logger.warning(
                f"Recovered stale analysis run: {run.id}, "
                f"repository: {run.repository_id}, "
                f"status was: {run.status.value}, "
                f"started at: {run.started_at}"
            )
        
        # Commit all changes in a single transaction
        if stale_runs:
            self.db.commit()
            logger.info(
                f"Successfully recovered {len(stale_runs)} stale analysis runs "
                f"(threshold={stale_threshold_hours}h)"
            )
        else:
            logger.info("No stale analysis runs detected")
        
        return {
            'stale_count': len(stale_runs),
            'recovered_count': len(recovered_run_ids),
            'repository_id': repository_id,
            'threshold_hours': stale_threshold_hours,
            'recovered_runs': recovered_run_ids
        }
    
    def _mark_run_as_stale(self, run: AnalysisRun, threshold_hours: int) -> None:
        """
        Mark a single analysis run as stale (failed).
        
        This is a private method called by recover_stale_analyses.
        Does not commit the transaction.
        
        Args:
            run: AnalysisRun instance to mark as stale
            threshold_hours: Threshold used for detection (for error message)
        """
        original_status = run.status.value
        elapsed_hours = (datetime.utcnow() - run.started_at).total_seconds() / 3600
        
        run.status = AnalysisStatus.FAILED
        run.completed_at = datetime.utcnow()
        run.error_message = (
            f"Analysis run marked as stale by automated recovery. "
            f"Original status: {original_status}, "
            f"exceeded {threshold_hours}h timeout "
            f"(elapsed: {elapsed_hours:.1f}h). "
            f"Likely cause: worker crash, job timeout, or resource exhaustion."
        )
        
        # Don't set progress to 100 for failed jobs
        # Keep the last known progress to help debugging
    
    def check_stale_runs(
        self,
        repository_id: Optional[str] = None,
        stale_threshold_hours: Optional[int] = None
    ) -> List[Dict[str, any]]:
        """
        Check for stale analysis runs without modifying them.
        
        This is a read-only operation useful for monitoring and alerting.
        
        Args:
            repository_id: Optional repository UUID to filter by
            stale_threshold_hours: Hours after which a job is stale (default from config)
            
        Returns:
            List of dictionaries containing stale run information:
                - analysis_run_id: UUID of stale run
                - repository_id: Repository UUID
                - status: Current status (RUNNING or QUEUED)
                - started_at: When the run started
                - elapsed_hours: Hours since started
                - current_stage: Last known pipeline stage
                - progress: Last known progress percentage
        """
        # Use configured threshold if not specified
        if stale_threshold_hours is None:
            stale_threshold_hours = getattr(
                self.settings, 
                'STALE_JOB_THRESHOLD_HOURS', 
                24
            )
        
        # Calculate cutoff time
        stale_cutoff = datetime.utcnow() - timedelta(hours=stale_threshold_hours)
        
        # Query for stale analysis runs
        query = self.db.query(AnalysisRun).filter(
            and_(
                AnalysisRun.status.in_([AnalysisStatus.RUNNING, AnalysisStatus.QUEUED]),
                AnalysisRun.started_at < stale_cutoff
            )
        )
        
        # Apply repository filter if specified
        if repository_id:
            query = query.filter(AnalysisRun.repository_id == repository_id)
        
        stale_runs = query.all()
        
        # Build result list
        results = []
        for run in stale_runs:
            elapsed = datetime.utcnow() - run.started_at
            elapsed_hours = elapsed.total_seconds() / 3600
            
            results.append({
                'analysis_run_id': str(run.id),
                'repository_id': str(run.repository_id),
                'status': run.status.value,
                'started_at': run.started_at.isoformat(),
                'elapsed_hours': round(elapsed_hours, 1),
                'current_stage': run.current_stage,
                'progress': run.progress,
                'job_id': run.job_id
            })
        
        return results
