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
from app.db.models import Repository, AnalysisRun, Symbol, File, AnalysisStatus
from app.schemas.analysis import (
    RepositoryAnalysisResponse,
    AnalysisSummary,
    FileInfo,
    Symbol as SymbolSchema,
    SymbolCallersResponse,
    SymbolCalleesResponse,
    SymbolDependenciesResponse,
    SymbolDependentsResponse,
    FileDependenciesResponse,
    FileDependentsResponse,
    ImpactAnalysisResponse,
    GraphEdge as GraphEdgeSchema
)
from app.services.graph_service import GraphService
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


# ============================================================================
# Phase 5: Graph Query Endpoints
# ============================================================================


@router.get("/{repository_id}/symbols/{symbol_id}/callers", response_model=SymbolCallersResponse)
def get_symbol_callers(
    repository_id: UUID,
    symbol_id: UUID,
    depth: int = Query(1, ge=1, le=10, description="Traversal depth (1-10)"),
    db: Session = Depends(get_db)
):
    """
    Get symbols that call the specified symbol.
    
    Returns the reverse call graph (who calls this symbol).
    
    Args:
        repository_id: Repository UUID
        symbol_id: Symbol UUID
        depth: Traversal depth (default: 1 for direct callers, max: 10)
        db: Database session
        
    Returns:
        List of caller relationships
        
    Raises:
        404: Symbol not found
    """
    # Verify symbol exists and belongs to repository
    symbol = db.query(Symbol).filter(Symbol.id == symbol_id).first()
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} not found"
        )
    
    # Verify symbol belongs to this repository
    analysis_run = db.query(AnalysisRun).filter(
        AnalysisRun.id == symbol.analysis_run_id,
        AnalysisRun.repository_id == repository_id
    ).first()
    
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} does not belong to repository {repository_id}"
        )
    
    # Get callers using graph service
    graph_service = GraphService(db)
    caller_edges = graph_service.get_symbol_callers(symbol_id, depth)
    
    # Convert to response schema
    callers = [
        GraphEdgeSchema(
            type=edge.relationship_type,
            source=edge.source.to_dict(),
            target=edge.target.to_dict(),
            line_number=edge.line_number
        )
        for edge in caller_edges
    ]
    
    # Count unique caller symbols
    unique_callers = set(edge.source.id for edge in caller_edges)
    
    return SymbolCallersResponse(
        symbol_id=str(symbol_id),
        symbol_name=symbol.name,
        depth=depth,
        callers=callers,
        total_callers=len(unique_callers)
    )


@router.get("/{repository_id}/symbols/{symbol_id}/callees", response_model=SymbolCalleesResponse)
def get_symbol_callees(
    repository_id: UUID,
    symbol_id: UUID,
    depth: int = Query(1, ge=1, le=10, description="Traversal depth (1-10)"),
    db: Session = Depends(get_db)
):
    """
    Get symbols that the specified symbol calls.
    
    Returns the forward call graph (what this symbol calls).
    
    Args:
        repository_id: Repository UUID
        symbol_id: Symbol UUID
        depth: Traversal depth (default: 1 for direct callees, max: 10)
        db: Database session
        
    Returns:
        List of callee relationships
        
    Raises:
        404: Symbol not found
    """
    # Verify symbol exists and belongs to repository
    symbol = db.query(Symbol).filter(Symbol.id == symbol_id).first()
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} not found"
        )
    
    # Verify symbol belongs to this repository
    analysis_run = db.query(AnalysisRun).filter(
        AnalysisRun.id == symbol.analysis_run_id,
        AnalysisRun.repository_id == repository_id
    ).first()
    
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} does not belong to repository {repository_id}"
        )
    
    # Get callees using graph service
    graph_service = GraphService(db)
    callee_edges = graph_service.get_symbol_callees(symbol_id, depth)
    
    # Convert to response schema
    callees = [
        GraphEdgeSchema(
            type=edge.relationship_type,
            source=edge.source.to_dict(),
            target=edge.target.to_dict(),
            line_number=edge.line_number
        )
        for edge in callee_edges
    ]
    
    # Count unique callee symbols
    unique_callees = set(edge.target.id for edge in callee_edges)
    
    return SymbolCalleesResponse(
        symbol_id=str(symbol_id),
        symbol_name=symbol.name,
        depth=depth,
        callees=callees,
        total_callees=len(unique_callees)
    )


@router.get("/{repository_id}/symbols/{symbol_id}/dependencies", response_model=SymbolDependenciesResponse)
def get_symbol_dependencies(
    repository_id: UUID,
    symbol_id: UUID,
    depth: int = Query(1, ge=1, le=10, description="Traversal depth (1-10)"),
    db: Session = Depends(get_db)
):
    """
    Get all dependencies of a symbol.
    
    Dependencies include:
    - Functions/methods this symbol calls
    - Modules this symbol's file imports
    
    Args:
        repository_id: Repository UUID
        symbol_id: Symbol UUID
        depth: Traversal depth
        db: Database session
        
    Returns:
        Symbol dependencies grouped by type
        
    Raises:
        404: Symbol not found
    """
    # Verify symbol exists and belongs to repository
    symbol = db.query(Symbol).filter(Symbol.id == symbol_id).first()
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} not found"
        )
    
    # Verify symbol belongs to this repository
    analysis_run = db.query(AnalysisRun).filter(
        AnalysisRun.id == symbol.analysis_run_id,
        AnalysisRun.repository_id == repository_id
    ).first()
    
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} does not belong to repository {repository_id}"
        )
    
    # Get dependencies using graph service
    graph_service = GraphService(db)
    dependencies = graph_service.get_symbol_dependencies(symbol_id, depth)
    
    # Convert to response schema
    call_edges = [
        GraphEdgeSchema(
            type=edge.relationship_type,
            source=edge.source.to_dict(),
            target=edge.target.to_dict(),
            line_number=edge.line_number
        )
        for edge in dependencies["calls"]
    ]
    
    import_edges = [
        GraphEdgeSchema(
            type=edge.relationship_type,
            source=edge.source.to_dict(),
            target=edge.target.to_dict(),
            line_number=edge.line_number
        )
        for edge in dependencies["imports"]
    ]
    
    total = len(call_edges) + len(import_edges)
    
    return SymbolDependenciesResponse(
        symbol_id=str(symbol_id),
        symbol_name=symbol.name,
        depth=depth,
        calls=call_edges,
        imports=import_edges,
        total_dependencies=total
    )


@router.get("/{repository_id}/symbols/{symbol_id}/dependents", response_model=SymbolDependentsResponse)
def get_symbol_dependents(
    repository_id: UUID,
    symbol_id: UUID,
    depth: int = Query(1, ge=1, le=10, description="Traversal depth (1-10)"),
    db: Session = Depends(get_db)
):
    """
    Get all dependents of a symbol.
    
    Dependents include:
    - Symbols that call this symbol
    - Files that import this symbol's file
    
    Args:
        repository_id: Repository UUID
        symbol_id: Symbol UUID
        depth: Traversal depth
        db: Database session
        
    Returns:
        Symbol dependents grouped by type
        
    Raises:
        404: Symbol not found
    """
    # Verify symbol exists and belongs to repository
    symbol = db.query(Symbol).filter(Symbol.id == symbol_id).first()
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} not found"
        )
    
    # Verify symbol belongs to this repository
    analysis_run = db.query(AnalysisRun).filter(
        AnalysisRun.id == symbol.analysis_run_id,
        AnalysisRun.repository_id == repository_id
    ).first()
    
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} does not belong to repository {repository_id}"
        )
    
    # Get dependents using graph service
    graph_service = GraphService(db)
    dependents = graph_service.get_symbol_dependents(symbol_id, depth)
    
    # Convert to response schema
    caller_edges = [
        GraphEdgeSchema(
            type=edge.relationship_type,
            source=edge.source.to_dict(),
            target=edge.target.to_dict(),
            line_number=edge.line_number
        )
        for edge in dependents["callers"]
    ]
    
    imported_by_edges = [
        GraphEdgeSchema(
            type=edge.relationship_type,
            source=edge.source.to_dict(),
            target=edge.target.to_dict(),
            line_number=edge.line_number
        )
        for edge in dependents["imported_by"]
    ]
    
    total = len(caller_edges) + len(imported_by_edges)
    
    return SymbolDependentsResponse(
        symbol_id=str(symbol_id),
        symbol_name=symbol.name,
        depth=depth,
        callers=caller_edges,
        imported_by=imported_by_edges,
        total_dependents=total
    )


@router.get("/{repository_id}/files/{file_id}/dependencies", response_model=FileDependenciesResponse)
def get_file_dependencies(
    repository_id: UUID,
    file_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get files that the specified file imports.
    
    Args:
        repository_id: Repository UUID
        file_id: File UUID
        db: Database session
        
    Returns:
        List of import relationships
        
    Raises:
        404: File not found
    """
    # Verify file exists and belongs to repository
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found"
        )
    
    if file.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} does not belong to repository {repository_id}"
        )
    
    # Get dependencies using graph service
    graph_service = GraphService(db)
    dependency_edges = graph_service.get_file_dependencies(file_id)
    
    # Convert to response schema
    imports = [
        GraphEdgeSchema(
            type=edge.relationship_type,
            source=edge.source.to_dict(),
            target=edge.target.to_dict(),
            line_number=edge.line_number
        )
        for edge in dependency_edges
    ]
    
    return FileDependenciesResponse(
        file_id=str(file_id),
        file_path=file.path,
        imports=imports,
        total_dependencies=len(imports)
    )


@router.get("/{repository_id}/files/{file_id}/dependents", response_model=FileDependentsResponse)
def get_file_dependents(
    repository_id: UUID,
    file_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get files that import the specified file.
    
    Args:
        repository_id: Repository UUID
        file_id: File UUID
        db: Database session
        
    Returns:
        List of import relationships
        
    Raises:
        404: File not found
    """
    # Verify file exists and belongs to repository
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found"
        )
    
    if file.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} does not belong to repository {repository_id}"
        )
    
    # Get dependents using graph service
    graph_service = GraphService(db)
    dependent_edges = graph_service.get_file_dependents(file_id)
    
    # Convert to response schema
    imported_by = [
        GraphEdgeSchema(
            type=edge.relationship_type,
            source=edge.source.to_dict(),
            target=edge.target.to_dict(),
            line_number=edge.line_number
        )
        for edge in dependent_edges
    ]
    
    return FileDependentsResponse(
        file_id=str(file_id),
        file_path=file.path,
        imported_by=imported_by,
        total_dependents=len(imported_by)
    )


@router.get("/{repository_id}/symbols/{symbol_id}/impact", response_model=ImpactAnalysisResponse)
def analyze_symbol_impact(
    repository_id: UUID,
    symbol_id: UUID,
    max_depth: int = Query(5, ge=1, le=10, description="Maximum traversal depth (1-10)"),
    db: Session = Depends(get_db)
):
    """
    Analyze the blast radius of changes to a symbol.
    
    This performs multi-level traversal to find all symbols that
    transitively depend on the target symbol.
    
    Use this to understand the impact of modifying a function:
    - What would break if this function's signature changed?
    - Which parts of the codebase depend on this function?
    - How far does the dependency chain extend?
    
    Args:
        repository_id: Repository UUID
        symbol_id: Symbol UUID
        max_depth: Maximum traversal depth (default: 5, max: 10)
        db: Database session
        
    Returns:
        Impact analysis with direct and indirect dependents
        
    Raises:
        404: Symbol not found
    """
    # Verify symbol exists and belongs to repository
    symbol = db.query(Symbol).filter(Symbol.id == symbol_id).first()
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} not found"
        )
    
    # Verify symbol belongs to this repository
    analysis_run = db.query(AnalysisRun).filter(
        AnalysisRun.id == symbol.analysis_run_id,
        AnalysisRun.repository_id == repository_id
    ).first()
    
    if not analysis_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol_id} does not belong to repository {repository_id}"
        )
    
    # Perform impact analysis
    graph_service = GraphService(db)
    impact = graph_service.analyze_symbol_impact(symbol_id, max_depth)
    
    return ImpactAnalysisResponse(
        target=impact["target"],
        direct_callers=impact["direct_callers"],
        indirect_dependents=impact["indirect_dependents"],
        total_dependents=impact["total_dependents"],
        depth_map=impact["depth_map"],
        max_depth=max_depth
    )
