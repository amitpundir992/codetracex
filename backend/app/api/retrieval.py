"""
API endpoints for retrieving persisted repository analysis data.

Phase 4 endpoints for querying PostgreSQL database.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db import get_db
from app.db.models import Repository, AnalysisRun, Symbol, AnalysisStatus
from app.schemas.analysis import (
    RepositoryAnalysisResponse,
    AnalysisSummary,
    FileInfo,
    Symbol as SymbolSchema
)
from pydantic import BaseModel


router = APIRouter(prefix="/api/repositories", tags=["repositories"])


# Response schemas
class RepositoryListResponse(BaseModel):
    """Response schema for listing repositories."""
    id: str
    owner: str
    name: str
    full_name: str
    github_url: str
    description: Optional[str]
    language: Optional[str]
    stars: Optional[int]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class AnalysisRunResponse(BaseModel):
    """Response schema for analysis run details."""
    id: str
    repository_id: str
    status: str
    total_files: Optional[int]
    analyzed_files: Optional[int]
    total_symbols: Optional[int]
    total_imports: Optional[int]
    total_calls: Optional[int]
    started_at: str
    completed_at: Optional[str]
    error_message: Optional[str]
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[RepositoryListResponse])
def list_repositories(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List all repositories in the database.
    
    Returns paginated list of repositories with metadata.
    
    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum records to return (1-100)
        db: Database session
        
    Returns:
        List of repository records
    """
    repositories = db.query(Repository).order_by(
        desc(Repository.created_at)
    ).offset(skip).limit(limit).all()
    
    return [
        RepositoryListResponse(
            id=str(repo.id),
            owner=repo.owner,
            name=repo.name,
            full_name=repo.full_name,
            github_url=repo.github_url,
            description=repo.description,
            language=repo.language,
            stars=repo.stars,
            created_at=repo.created_at.isoformat(),
            updated_at=repo.updated_at.isoformat()
        )
        for repo in repositories
    ]


@router.get("/{repository_id}", response_model=RepositoryListResponse)
def get_repository(
    repository_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get repository details by ID.
    
    Args:
        repository_id: Repository UUID
        db: Database session
        
    Returns:
        Repository details
        
    Raises:
        404: Repository not found
    """
    repository = db.query(Repository).filter(
        Repository.id == repository_id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    return RepositoryListResponse(
        id=str(repository.id),
        owner=repository.owner,
        name=repository.name,
        full_name=repository.full_name,
        github_url=repository.github_url,
        description=repository.description,
        language=repository.language,
        stars=repository.stars,
        created_at=repository.created_at.isoformat(),
        updated_at=repository.updated_at.isoformat()
    )


@router.get("/{repository_id}/analysis/latest", response_model=AnalysisRunResponse)
def get_latest_analysis(
    repository_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get latest analysis run for a repository.
    
    Args:
        repository_id: Repository UUID
        db: Database session
        
    Returns:
        Latest analysis run details
        
    Raises:
        404: Repository or analysis not found
    """
    # Check repository exists
    repository = db.query(Repository).filter(
        Repository.id == repository_id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Get latest completed analysis
    analysis_run = db.query(AnalysisRun).filter(
        AnalysisRun.repository_id == repository_id,
        AnalysisRun.status == AnalysisStatus.completed
    ).order_by(desc(AnalysisRun.started_at)).first()
    
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed analysis found for repository {repository_id}"
        )
    
    return AnalysisRunResponse(
        id=str(analysis_run.id),
        repository_id=str(analysis_run.repository_id),
        status=analysis_run.status.value,
        total_files=analysis_run.total_files,
        analyzed_files=analysis_run.analyzed_files,
        total_symbols=analysis_run.total_symbols,
        total_imports=analysis_run.total_imports,
        total_calls=analysis_run.total_calls,
        started_at=analysis_run.started_at.isoformat(),
        completed_at=analysis_run.completed_at.isoformat() if analysis_run.completed_at else None,
        error_message=analysis_run.error_message
    )


@router.get("/{repository_id}/analysis", response_model=List[AnalysisRunResponse])
def list_analysis_runs(
    repository_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    List all analysis runs for a repository.
    
    Returns analysis runs in reverse chronological order (newest first).
    
    Args:
        repository_id: Repository UUID
        skip: Number of records to skip
        limit: Maximum records to return (1-50)
        db: Database session
        
    Returns:
        List of analysis runs
        
    Raises:
        404: Repository not found
    """
    # Check repository exists
    repository = db.query(Repository).filter(
        Repository.id == repository_id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Get analysis runs
    analysis_runs = db.query(AnalysisRun).filter(
        AnalysisRun.repository_id == repository_id
    ).order_by(desc(AnalysisRun.started_at)).offset(skip).limit(limit).all()
    
    return [
        AnalysisRunResponse(
            id=str(run.id),
            repository_id=str(run.repository_id),
            status=run.status.value,
            total_files=run.total_files,
            analyzed_files=run.analyzed_files,
            total_symbols=run.total_symbols,
            total_imports=run.total_imports,
            total_calls=run.total_calls,
            started_at=run.started_at.isoformat(),
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            error_message=run.error_message
        )
        for run in analysis_runs
    ]


@router.get("/{repository_id}/symbols", response_model=List[SymbolSchema])
def list_symbols(
    repository_id: UUID,
    name: Optional[str] = Query(None, description="Filter by symbol name"),
    symbol_type: Optional[str] = Query(None, description="Filter by symbol type"),
    language: Optional[str] = Query(None, description="Filter by language"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    List symbols from latest completed analysis.
    
    Supports filtering by name, type, and language.
    
    Args:
        repository_id: Repository UUID
        name: Optional symbol name filter (partial match)
        symbol_type: Optional symbol type filter (exact match)
        language: Optional language filter (exact match)
        skip: Number of records to skip
        limit: Maximum records to return (1-1000)
        db: Database session
        
    Returns:
        List of symbols matching filters
        
    Raises:
        404: Repository or analysis not found
    """
    # Get latest completed analysis
    analysis_run = db.query(AnalysisRun).filter(
        AnalysisRun.repository_id == repository_id,
        AnalysisRun.status == AnalysisStatus.completed
    ).order_by(desc(AnalysisRun.started_at)).first()
    
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed analysis found for repository {repository_id}"
        )
    
    # Build query with filters
    query = db.query(Symbol).filter(
        Symbol.analysis_run_id == analysis_run.id
    )
    
    if name:
        query = query.filter(Symbol.name.ilike(f"%{name}%"))
    
    if symbol_type:
        query = query.filter(Symbol.symbol_type == symbol_type)
    
    if language:
        query = query.filter(Symbol.language == language)
    
    symbols = query.order_by(Symbol.name).offset(skip).limit(limit).all()
    
    return [
        SymbolSchema(
            name=symbol.name,
            type=symbol.symbol_type.value,
            language=symbol.language,
            file=symbol.file.path,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            parent=symbol.parent.name if symbol.parent else None
        )
        for symbol in symbols
    ]
