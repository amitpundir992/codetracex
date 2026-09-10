"""
API endpoint management API routes.

Phase 7: API & Application Structure Intelligence

This module provides REST APIs for querying detected API endpoints.

Endpoints:
    GET /api/repositories/{repo_id}/endpoints - List endpoints
    GET /api/repositories/{repo_id}/endpoints/{endpoint_id} - Endpoint details
    GET /api/repositories/{repo_id}/endpoints/{endpoint_id}/dependencies - Dependencies
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from uuid import UUID
from typing import Optional
import logging
import math

from app.db.session import get_db
from app.db.models import Repository, ApiEndpoint, File, Symbol, Call
from app.schemas.api_endpoints import (
    ApiEndpointListResponse,
    ApiEndpointSummary,
    ApiEndpointDetail,
    ApiEndpointDependenciesResponse,
    SymbolInfo,
    DependencyNode
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


def validate_endpoint(db: Session, repo_id: UUID, endpoint_id: UUID) -> ApiEndpoint:
    """
    Validate that endpoint exists in repository and return it.
    
    Args:
        db: Database session
        repo_id: Repository UUID
        endpoint_id: Endpoint UUID
        
    Returns:
        ApiEndpoint model instance
        
    Raises:
        HTTPException: If endpoint not found or belongs to different repository
    """
    endpoint = (
        db.query(ApiEndpoint)
        .filter(ApiEndpoint.id == endpoint_id)
        .first()
    )
    
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail=f"Endpoint not found: {endpoint_id}"
        )
    
    if endpoint.repository_id != repo_id:
        raise HTTPException(
            status_code=400,
            detail=f"Endpoint does not belong to repository {repo_id}"
        )
    
    return endpoint


@router.get("/repositories/{repo_id}/endpoints", response_model=ApiEndpointListResponse)
async def list_endpoints(
    repo_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    method: Optional[str] = Query(None, description="Filter by HTTP method (GET, POST, etc.)"),
    framework: Optional[str] = Query(None, description="Filter by framework (fastapi, flask, express)"),
    db: Session = Depends(get_db)
) -> ApiEndpointListResponse:
    """
    List API endpoints for a repository.
    
    Returns paginated list of endpoints with optional filtering by
    HTTP method and framework.
    
    Query Parameters:
        page: Page number (default: 1)
        page_size: Items per page (default: 20, max: 100)
        method: Filter by HTTP method (optional)
        framework: Filter by framework (optional)
        
    Returns:
        Paginated list of endpoint summaries
        
    Raises:
        404: If repository not found
    """
    # Validate repository
    repository = validate_repository(db, repo_id)
    
    # Get latest analysis run for this repository
    from app.db.models import AnalysisRun, AnalysisStatus
    latest_analysis = (
        db.query(AnalysisRun)
        .filter(
            AnalysisRun.repository_id == repo_id,
            AnalysisRun.status == AnalysisStatus.COMPLETED
        )
        .order_by(AnalysisRun.completed_at.desc())
        .first()
    )
    
    if not latest_analysis:
        # No completed analysis runs
        return ApiEndpointListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0
        )
    
    # Build query
    query = (
        db.query(ApiEndpoint)
        .join(File, ApiEndpoint.file_id == File.id)
        .filter(ApiEndpoint.analysis_run_id == latest_analysis.id)
    )
    
    # Apply filters
    if method:
        from app.db.models import HttpMethod
        try:
            http_method = HttpMethod[method.upper()]
            query = query.filter(ApiEndpoint.method == http_method)
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid HTTP method: {method}"
            )
    
    if framework:
        query = query.filter(ApiEndpoint.framework == framework.lower())
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size
    
    # Get paginated results
    endpoints = query.offset(offset).limit(page_size).all()
    
    # Build response
    items = []
    for endpoint in endpoints:
        items.append(ApiEndpointSummary(
            id=endpoint.id,
            method=endpoint.method.value,
            path=endpoint.path,
            framework=endpoint.framework,
            handler_name=endpoint.handler_name,
            start_line=endpoint.start_line,
            end_line=endpoint.end_line,
            file_path=endpoint.file.path
        ))
    
    return ApiEndpointListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/repositories/{repo_id}/endpoints/{endpoint_id}", response_model=ApiEndpointDetail)
async def get_endpoint_detail(
    repo_id: UUID,
    endpoint_id: UUID,
    db: Session = Depends(get_db)
) -> ApiEndpointDetail:
    """
    Get detailed information about a specific endpoint.
    
    Returns complete endpoint information including file details
    and resolved handler symbol if available.
    
    Args:
        repo_id: Repository UUID
        endpoint_id: Endpoint UUID
        
    Returns:
        Detailed endpoint information
        
    Raises:
        404: If repository or endpoint not found
        400: If endpoint doesn't belong to repository
    """
    # Validate repository
    repository = validate_repository(db, repo_id)
    
    # Validate endpoint
    endpoint = validate_endpoint(db, repo_id, endpoint_id)
    
    # Load relationships
    endpoint = (
        db.query(ApiEndpoint)
        .options(joinedload(ApiEndpoint.file))
        .options(joinedload(ApiEndpoint.symbol))
        .filter(ApiEndpoint.id == endpoint_id)
        .first()
    )
    
    # Build response
    handler_symbol = None
    if endpoint.symbol:
        handler_symbol = SymbolInfo(
            id=endpoint.symbol.id,
            name=endpoint.symbol.name,
            type=endpoint.symbol.symbol_type.value,
            file_path=endpoint.symbol.file.path,
            start_line=endpoint.symbol.start_line,
            end_line=endpoint.symbol.end_line
        )
    
    return ApiEndpointDetail(
        id=endpoint.id,
        method=endpoint.method.value,
        path=endpoint.path,
        framework=endpoint.framework,
        handler_name=endpoint.handler_name,
        start_line=endpoint.start_line,
        end_line=endpoint.end_line,
        repository_id=endpoint.repository_id,
        analysis_run_id=endpoint.analysis_run_id,
        file_id=endpoint.file_id,
        file_path=endpoint.file.path,
        symbol_id=endpoint.symbol_id,
        handler_symbol=handler_symbol,
        created_at=endpoint.created_at
    )


@router.get(
    "/repositories/{repo_id}/endpoints/{endpoint_id}/dependencies",
    response_model=ApiEndpointDependenciesResponse
)
async def get_endpoint_dependencies(
    repo_id: UUID,
    endpoint_id: UUID,
    depth: int = Query(3, ge=1, le=5, description="Traversal depth"),
    db: Session = Depends(get_db)
) -> ApiEndpointDependenciesResponse:
    """
    Get dependency information for an endpoint.
    
    Returns downstream dependencies (functions/services called by this endpoint)
    and upstream callers (functions/endpoints that call this handler).
    
    Uses the existing Call relationships from Phase 3 to build the graph.
    
    Args:
        repo_id: Repository UUID
        endpoint_id: Endpoint UUID
        depth: Traversal depth (default: 3, max: 5)
        
    Returns:
        Dependency graph information
        
    Raises:
        404: If repository or endpoint not found
        400: If endpoint doesn't belong to repository
    """
    # Validate repository
    repository = validate_repository(db, repo_id)
    
    # Validate endpoint
    endpoint = validate_endpoint(db, repo_id, endpoint_id)
    
    # Load endpoint with symbol
    endpoint = (
        db.query(ApiEndpoint)
        .options(joinedload(ApiEndpoint.symbol))
        .filter(ApiEndpoint.id == endpoint_id)
        .first()
    )
    
    dependencies = []
    callers = []
    
    if endpoint.symbol:
        # Get downstream dependencies (what this handler calls)
        # Use Call table to find functions called by this handler
        calls_query = (
            db.query(Call)
            .filter(
                Call.analysis_run_id == endpoint.analysis_run_id,
                Call.caller_name == endpoint.handler_name
            )
            .limit(20)  # Limit to prevent huge result sets
        )
        
        for call in calls_query:
            # Try to find the called symbol
            called_symbol = (
                db.query(Symbol)
                .join(File)
                .filter(
                    Symbol.analysis_run_id == endpoint.analysis_run_id,
                    Symbol.name == call.callee_name
                )
                .first()
            )
            
            if called_symbol:
                dependencies.append(DependencyNode(
                    id=called_symbol.id,
                    name=called_symbol.name,
                    type="symbol",
                    file_path=called_symbol.file.path
                ))
        
        # Get upstream callers (what calls this handler)
        callers_query = (
            db.query(Call)
            .filter(
                Call.analysis_run_id == endpoint.analysis_run_id,
                Call.callee_name == endpoint.handler_name
            )
            .limit(20)
        )
        
        for call in callers_query:
            # Try to find the caller symbol
            caller_symbol = (
                db.query(Symbol)
                .join(File)
                .filter(
                    Symbol.analysis_run_id == endpoint.analysis_run_id,
                    Symbol.name == call.caller_name
                )
                .first()
            )
            
            if caller_symbol:
                callers.append(DependencyNode(
                    id=caller_symbol.id,
                    name=caller_symbol.name,
                    type="symbol",
                    file_path=caller_symbol.file.path
                ))
    
    return ApiEndpointDependenciesResponse(
        endpoint_id=endpoint.id,
        method=endpoint.method.value,
        path=endpoint.path,
        handler_name=endpoint.handler_name,
        dependencies=dependencies,
        callers=callers
    )
