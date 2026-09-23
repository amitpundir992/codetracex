"""
API endpoints for background job management.

Phase 14: Background Processing
"""
import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from rq.job import Job

from app.schemas.jobs import JobCreateResponse, JobStatusResponse, JobCancelResponse
from app.schemas.repository import RepositoryRequest
from app.db import get_db
from app.db.models import Repository, AnalysisRun, AnalysisStatus
from app.services.repository_service import RepositoryService, InvalidRepositoryURLError
from app.services.github_service import GitHubAPIError, RepositoryNotFoundError
from app.workers.redis_connection import get_analysis_queue
from app.workers.tasks import analyze_repository_task, cancel_analysis_task
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["jobs"])


@router.post("/repositories/analyze-async", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_repository_analysis(
    request: RepositoryRequest,
    db: Session = Depends(get_db)
):
    """
    Start asynchronous repository analysis.
    
    This endpoint enqueues a repository analysis job and returns immediately.
    The actual analysis runs in a background worker.
    
    Phase 14: Background Processing
    
    Workflow:
    1. Validate repository URL
    2. Get repository metadata from GitHub
    3. Create or retrieve repository record
    4. Check for duplicate active jobs
    5. Create AnalysisRun with status=queued
    6. Enqueue job in Redis
    7. Return job information
    
    The client should poll GET /api/jobs/{analysis_run_id} to check status.
    
    Args:
        request: Repository request with GitHub URL
        db: Database session
        
    Returns:
        Job creation response with job_id and analysis_run_id
        
    Raises:
        400: Invalid repository URL
        404: Repository not found on GitHub
        409: Active analysis already running for this repository
        500: Internal server error
    """
    logger.info(f"Starting async analysis for: {request.url}")
    
    # Validate URL and get metadata
    repository_service = RepositoryService()
    
    try:
        metadata = await repository_service.get_repository_metadata(request.url)
    except InvalidRepositoryURLError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RepositoryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub repository not found"
        )
    except GitHubAPIError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error communicating with GitHub"
        )
    
    owner = metadata["owner"]
    name = metadata["name"]
    full_name = f"{owner}/{name}"
    
    # Create or get repository
    repository = db.query(Repository).filter(
        Repository.full_name == full_name
    ).first()
    
    if not repository:
        repository = Repository(
            owner=owner,
            name=name,
            full_name=full_name,
            github_url=metadata["url"],
            default_branch=metadata["default_branch"],
            description=metadata.get("description"),
            language=metadata.get("language"),
            stars=metadata.get("stars")
        )
        db.add(repository)
        db.commit()
        db.refresh(repository)
        logger.info(f"Created repository record: {repository.id}")
    
    # Check for duplicate active jobs
    active_statuses = [AnalysisStatus.QUEUED, AnalysisStatus.PENDING, AnalysisStatus.RUNNING]
    active_analysis = db.query(AnalysisRun).filter(
        AnalysisRun.repository_id == repository.id,
        AnalysisRun.status.in_(active_statuses)
    ).first()
    
    if active_analysis:
        logger.warning(f"Active analysis already exists: {active_analysis.id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Analysis already in progress for this repository. Job ID: {active_analysis.id}"
        )
    
    # Create analysis run
    analysis_run = AnalysisRun(
        repository_id=repository.id,
        status=AnalysisStatus.QUEUED,
        progress=0,
        current_stage="Queued"
    )
    db.add(analysis_run)
    db.commit()
    db.refresh(analysis_run)
    
    logger.info(f"Created analysis run: {analysis_run.id}")
    
    # Enqueue job
    try:
        queue = get_analysis_queue()
        settings = get_settings()
        
        job = queue.enqueue(
            analyze_repository_task,
            args=(str(analysis_run.id), request.url),
            job_timeout=settings.JOB_TIMEOUT,
            result_ttl=settings.JOB_RESULT_TTL,
            failure_ttl=settings.JOB_RESULT_TTL
        )
        
        # Store job ID in analysis run
        analysis_run.job_id = job.id
        db.commit()
        
        logger.info(f"Enqueued job: {job.id} for analysis run: {analysis_run.id}")
        
        return JobCreateResponse(
            job_id=job.id,
            analysis_run_id=analysis_run.id,
            repository_id=repository.id,
            status="queued"
        )
        
    except Exception as e:
        logger.error(f"Failed to enqueue job: {e}", exc_info=True)
        
        # Mark analysis as failed
        analysis_run.status = AnalysisStatus.FAILED
        analysis_run.error_message = "Failed to enqueue job"
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start analysis job"
        )


@router.get("/jobs/{analysis_run_id}", response_model=JobStatusResponse)
def get_job_status(
    analysis_run_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get status of an analysis job.
    
    Phase 14: Background Processing
    
    Returns the current status, progress, and stage of an analysis job.
    
    Args:
        analysis_run_id: UUID of the analysis run
        db: Database session
        
    Returns:
        Job status information
        
    Raises:
        404: Analysis run not found
    """
    analysis_run = db.query(AnalysisRun).filter(
        AnalysisRun.id == analysis_run_id
    ).first()
    
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run not found: {analysis_run_id}"
        )
    
    # Get repository info
    repository = analysis_run.repository
    
    return JobStatusResponse(
        job_id=analysis_run.job_id,
        analysis_run_id=analysis_run.id,
        repository_id=repository.id,
        repository_name=repository.full_name,
        status=analysis_run.status.value,
        progress=analysis_run.progress,
        current_stage=analysis_run.current_stage,
        total_files=analysis_run.total_files or 0,
        analyzed_files=analysis_run.analyzed_files or 0,
        total_symbols=analysis_run.total_symbols or 0,
        created_at=analysis_run.started_at,
        started_at=analysis_run.started_at if analysis_run.status != AnalysisStatus.QUEUED else None,
        completed_at=analysis_run.completed_at,
        error_message=analysis_run.error_message
    )


@router.post("/jobs/{analysis_run_id}/cancel", response_model=JobCancelResponse)
def cancel_job(
    analysis_run_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Cancel a running analysis job.
    
    Phase 14: Background Processing
    
    This is a cooperative cancellation. The worker will detect the
    cancellation and exit gracefully at the next pipeline boundary.
    
    Note: Jobs cannot be forcefully terminated. If a job is in the middle
    of a long-running operation, it may take time to detect cancellation.
    
    Args:
        analysis_run_id: UUID of the analysis run to cancel
        db: Database session
        
    Returns:
        Cancellation confirmation
        
    Raises:
        404: Analysis run not found
        409: Job is not in a cancellable state
    """
    analysis_run = db.query(AnalysisRun).filter(
        AnalysisRun.id == analysis_run_id
    ).first()
    
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run not found: {analysis_run_id}"
        )
    
    # Check if job can be cancelled
    cancellable_statuses = [AnalysisStatus.QUEUED, AnalysisStatus.PENDING, AnalysisStatus.RUNNING]
    if analysis_run.status not in cancellable_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job cannot be cancelled. Current status: {analysis_run.status.value}"
        )
    
    # Mark as cancelled
    from datetime import datetime
    
    analysis_run.status = AnalysisStatus.CANCELLED
    analysis_run.completed_at = datetime.utcnow()
    analysis_run.current_stage = "Cancelled"
    db.commit()
    
    logger.info(f"Cancelled analysis run: {analysis_run_id}")
    
    # Try to cancel RQ job if it exists
    if analysis_run.job_id:
        try:
            queue = get_analysis_queue()
            job = Job.fetch(analysis_run.job_id, connection=queue.connection)
            job.cancel()
            logger.info(f"Cancelled RQ job: {analysis_run.job_id}")
        except Exception as e:
            logger.warning(f"Failed to cancel RQ job: {e}")
            # Continue anyway - database status is marked as cancelled
    
    return JobCancelResponse(
        job_id=analysis_run.job_id,
        analysis_run_id=analysis_run.id,
        status="cancelled",
        message="Analysis job cancelled successfully"
    )


@router.get("/repositories/{repository_id}/latest-job", response_model=JobStatusResponse)
def get_latest_job_for_repository(
    repository_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get the latest analysis job for a repository.
    
    Phase 14: Background Processing
    
    Returns the most recent analysis job (active or completed).
    
    Args:
        repository_id: UUID of the repository
        db: Database session
        
    Returns:
        Latest job status
        
    Raises:
        404: Repository or analysis run not found
    """
    repository = db.query(Repository).filter(
        Repository.id == repository_id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repository_id}"
        )
    
    # Get latest analysis run
    latest_analysis = db.query(AnalysisRun).filter(
        AnalysisRun.repository_id == repository_id
    ).order_by(AnalysisRun.started_at.desc()).first()
    
    if not latest_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis runs found for repository: {repository_id}"
        )
    
    return JobStatusResponse(
        job_id=latest_analysis.job_id,
        analysis_run_id=latest_analysis.id,
        repository_id=repository.id,
        repository_name=repository.full_name,
        status=latest_analysis.status.value,
        progress=latest_analysis.progress,
        current_stage=latest_analysis.current_stage,
        total_files=latest_analysis.total_files or 0,
        analyzed_files=latest_analysis.analyzed_files or 0,
        total_symbols=latest_analysis.total_symbols or 0,
        created_at=latest_analysis.started_at,
        started_at=latest_analysis.started_at if latest_analysis.status != AnalysisStatus.QUEUED else None,
        completed_at=latest_analysis.completed_at,
        error_message=latest_analysis.error_message
    )
