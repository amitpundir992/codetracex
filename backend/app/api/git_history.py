"""
Git history API endpoints.

Phase 6: Git History Intelligence

This module provides REST APIs for querying Git commit history.

Endpoints:
    GET /api/repositories/{repo_id}/commits - List commits
    GET /api/repositories/{repo_id}/commits/{commit_id} - Commit details
    GET /api/repositories/{repo_id}/files/{file_id}/history - File history
    GET /api/repositories/{repo_id}/files/{file_id}/co-changes - Co-change analysis
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, desc
from uuid import UUID
from typing import Optional
import logging

from app.db.session import get_db
from app.db.models import Repository, Commit, CommitFileChange, File
from app.schemas.git_history import (
    CommitListResponse,
    CommitSummarySchema,
    CommitDetailSchema,
    FileHistoryResponse,
    FileHistorySchema,
    CoChangeResponse,
    CoChangeFileSchema
)

logger = logging.getLogger(__name__)

router = APIRouter()


def validate_repository(db: Session, repo_id: UUID) -> Repository:
    """
    Validate that repository exists and return it.
    
    Args:
        db: Database session
        repo_id: Repository UUID
        
    Returns:
        Repository model instance
        
    Raises:
        HTTPException: If repository not found
    """
    repository = db.query(Repository).filter(Repository.id == repo_id).first()
    
    if not repository:
        raise HTTPException(
            status_code=404,
            detail=f"Repository not found: {repo_id}"
        )
    
    return repository


def validate_commit(db: Session, repo_id: UUID, commit_id: UUID) -> Commit:
    """
    Validate that commit exists in repository and return it.
    
    Args:
        db: Database session
        repo_id: Repository UUID
        commit_id: Commit UUID
        
    Returns:
        Commit model instance
        
    Raises:
        HTTPException: If commit not found or belongs to different repository
    """
    commit = (
        db.query(Commit)
        .filter(Commit.id == commit_id)
        .first()
    )
    
    if not commit:
        raise HTTPException(
            status_code=404,
            detail=f"Commit not found: {commit_id}"
        )
    
    if commit.repository_id != repo_id:
        raise HTTPException(
            status_code=400,
            detail=f"Commit does not belong to repository {repo_id}"
        )
    
    return commit


def validate_file(db: Session, repo_id: UUID, file_id: UUID) -> File:
    """
    Validate that file exists in repository and return it.
    
    Args:
        db: Database session
        repo_id: Repository UUID
        file_id: File UUID
        
    Returns:
        File model instance
        
    Raises:
        HTTPException: If file not found or belongs to different repository
    """
    file = db.query(File).filter(File.id == file_id).first()
    
    if not file:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {file_id}"
        )
    
    if file.repository_id != repo_id:
        raise HTTPException(
            status_code=400,
            detail=f"File does not belong to repository {repo_id}"
        )
    
    return file


@router.get(
    "/repositories/{repo_id}/commits",
    response_model=CommitListResponse,
    summary="List repository commits"
)
def list_commits(
    repo_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    List commits for a repository with pagination.
    
    Returns commits in reverse chronological order (newest first).
    
    Args:
        repo_id: Repository UUID
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        db: Database session
        
    Returns:
        CommitListResponse with paginated commits
        
    Raises:
        404: Repository not found
    """
    # Validate repository exists
    repository = validate_repository(db, repo_id)
    
    # Count total commits
    total = (
        db.query(func.count(Commit.id))
        .filter(Commit.repository_id == repo_id)
        .scalar()
    )
    
    # Calculate pagination
    offset = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size
    
    # Query commits
    commits = (
        db.query(Commit)
        .filter(Commit.repository_id == repo_id)
        .order_by(desc(Commit.committed_at))
        .limit(page_size)
        .offset(offset)
        .all()
    )
    
    # Convert to schemas
    items = [CommitSummarySchema.from_commit(c) for c in commits]
    
    return CommitListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get(
    "/repositories/{repo_id}/commits/{commit_id}",
    response_model=CommitDetailSchema,
    summary="Get commit details"
)
def get_commit_detail(
    repo_id: UUID,
    commit_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific commit.
    
    Includes:
    - Commit metadata (author, message, timestamp)
    - Parent commits
    - File changes (additions, deletions, change type)
    - Statistics (total lines changed, files changed)
    
    Args:
        repo_id: Repository UUID
        commit_id: Commit UUID
        db: Database session
        
    Returns:
        CommitDetailSchema with full commit information
        
    Raises:
        404: Repository or commit not found
        400: Commit does not belong to repository
    """
    # Validate repository exists
    validate_repository(db, repo_id)
    
    # Validate commit and load file changes
    commit = (
        db.query(Commit)
        .options(joinedload(Commit.file_changes))
        .filter(Commit.id == commit_id)
        .first()
    )
    
    if not commit:
        raise HTTPException(
            status_code=404,
            detail=f"Commit not found: {commit_id}"
        )
    
    if commit.repository_id != repo_id:
        raise HTTPException(
            status_code=400,
            detail=f"Commit does not belong to repository {repo_id}"
        )
    
    return CommitDetailSchema.from_commit(commit)


@router.get(
    "/repositories/{repo_id}/files/{file_id}/history",
    response_model=FileHistoryResponse,
    summary="Get file commit history"
)
def get_file_history(
    repo_id: UUID,
    file_id: UUID,
    limit: int = Query(50, ge=1, le=200, description="Maximum commits to return"),
    db: Session = Depends(get_db)
):
    """
    Get commit history for a specific file.
    
    Returns all commits that modified the file, ordered by date (newest first).
    
    Note:
        File history is tracked by path. If a file was renamed,
        only commits after the rename will be shown unless
        the old path was explicitly linked.
    
    Args:
        repo_id: Repository UUID
        file_id: File UUID
        limit: Maximum number of commits to return
        db: Database session
        
    Returns:
        FileHistoryResponse with commit history
        
    Raises:
        404: Repository or file not found
        400: File does not belong to repository
    """
    # Validate repository and file
    validate_repository(db, repo_id)
    file = validate_file(db, repo_id, file_id)
    
    # Query commits that changed this file
    # Join: CommitFileChange -> Commit
    # Filter by file_id OR path (to catch renamed files)
    results = (
        db.query(Commit, CommitFileChange)
        .join(CommitFileChange, CommitFileChange.commit_id == Commit.id)
        .filter(
            and_(
                Commit.repository_id == repo_id,
                (
                    (CommitFileChange.file_id == file_id) |
                    (CommitFileChange.path == file.path)
                )
            )
        )
        .order_by(desc(Commit.committed_at))
        .limit(limit)
        .all()
    )
    
    # Convert to schemas
    commits = []
    for commit, file_change in results:
        subject = commit.commit_message.split('\n')[0] if commit.commit_message else ''
        
        commits.append(FileHistorySchema(
            commit_id=commit.id,
            commit_hash=commit.commit_hash,
            short_hash=commit.commit_hash[:8],
            author_name=commit.author_name,
            author_email=commit.author_email,
            subject=subject,
            committed_at=commit.committed_at,
            change_type=file_change.change_type.value,
            additions=file_change.additions or 0,
            deletions=file_change.deletions or 0
        ))
    
    return FileHistoryResponse(
        file_id=file.id,
        file_path=file.path,
        commits=commits,
        total_commits=len(commits)
    )


@router.get(
    "/repositories/{repo_id}/files/{file_id}/co-changes",
    response_model=CoChangeResponse,
    summary="Get files that frequently change together"
)
def get_file_co_changes(
    repo_id: UUID,
    file_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="Maximum files to return"),
    db: Session = Depends(get_db)
):
    """
    Get files that frequently change together with the target file.
    
    Co-change analysis identifies files that are often modified
    in the same commits as the target file. This indicates:
    - Related functionality
    - Coupling between modules
    - Potential refactoring opportunities
    
    The query:
    1. Finds all commits that modified the target file
    2. Finds other files changed in those same commits
    3. Counts how many times each file co-changed
    4. Returns top N files by co-change frequency
    
    Args:
        repo_id: Repository UUID
        file_id: File UUID
        limit: Maximum number of co-changed files to return
        db: Database session
        
    Returns:
        CoChangeResponse with co-changed files
        
    Raises:
        404: Repository or file not found
        400: File does not belong to repository
    """
    # Validate repository and file
    validate_repository(db, repo_id)
    file = validate_file(db, repo_id, file_id)
    
    # Subquery: Get commit IDs that changed the target file
    target_commits = (
        db.query(CommitFileChange.commit_id)
        .filter(
            (CommitFileChange.file_id == file_id) |
            (CommitFileChange.path == file.path)
        )
        .subquery()
    )
    
    # Query: Find files changed in those same commits
    # Exclude the target file itself
    # Group by file and count shared commits
    co_changes = (
        db.query(
            CommitFileChange.path,
            CommitFileChange.file_id,
            func.count(CommitFileChange.commit_id).label('shared_commits'),
            func.max(Commit.committed_at).label('last_shared_commit')
        )
        .join(Commit, Commit.id == CommitFileChange.commit_id)
        .filter(
            and_(
                CommitFileChange.commit_id.in_(target_commits),
                CommitFileChange.path != file.path,  # Exclude target file
                Commit.repository_id == repo_id
            )
        )
        .group_by(CommitFileChange.path, CommitFileChange.file_id)
        .order_by(desc('shared_commits'))
        .limit(limit)
        .all()
    )
    
    # Convert to schemas
    co_changed_files = [
        CoChangeFileSchema(
            file_id=row.file_id,
            file_path=row.path,
            shared_commits=row.shared_commits,
            last_shared_commit=row.last_shared_commit
        )
        for row in co_changes
    ]
    
    return CoChangeResponse(
        file_id=file.id,
        file_path=file.path,
        co_changed_files=co_changed_files,
        total_files=len(co_changed_files)
    )
