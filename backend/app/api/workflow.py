"""
Workflow API routes for Phase 8.

This module provides REST APIs for querying application workflows
built from static analysis data.

Endpoints:
    GET /api/repositories/{repo_id}/endpoints/{endpoint_id}/workflow
    GET /api/repositories/{repo_id}/symbols/{symbol_id}/workflow
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
import logging

from app.db.session import get_db
from app.db.models import Repository, ApiEndpoint, Symbol
from app.schemas.workflow import (
    WorkflowResponse,
    WorkflowNodeSchema,
    WorkflowEdgeSchema
)
from app.services.workflow_service import WorkflowService

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


def validate_symbol(db: Session, repo_id: UUID, symbol_id: UUID) -> Symbol:
    """
    Validate that symbol exists in repository and return it.
    
    Args:
        db: Database session
        repo_id: Repository UUID
        symbol_id: Symbol UUID
        
    Returns:
        Symbol model instance
        
    Raises:
        HTTPException: If symbol not found or belongs to different repository
    """
    symbol = (
        db.query(Symbol)
        .join(Symbol.analysis_run)
        .filter(Symbol.id == symbol_id)
        .first()
    )
    
    if not symbol:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol not found: {symbol_id}"
        )
    
    if symbol.analysis_run.repository_id != repo_id:
        raise HTTPException(
            status_code=400,
            detail=f"Symbol does not belong to repository {repo_id}"
        )
    
    return symbol


@router.get(
    "/repositories/{repo_id}/endpoints/{endpoint_id}/workflow",
    response_model=WorkflowResponse
)
async def get_endpoint_workflow(
    repo_id: UUID,
    endpoint_id: UUID,
    depth: int = Query(5, ge=1, le=10, description="Traversal depth (1-10)"),
    include_callers: bool = Query(False, description="Include upstream callers"),
    db: Session = Depends(get_db)
) -> WorkflowResponse:
    """
    Get application workflow for an API endpoint.
    
    Constructs the execution flow starting from the endpoint handler
    and traversing downstream function calls. This shows:
    
        API endpoint → handler → service → repository → model
    
    The workflow is derived from static analysis data and represents
    POSSIBLE execution paths, not guaranteed runtime behavior.
    
    Args:
        repo_id: Repository UUID
        endpoint_id: API endpoint UUID
        depth: Maximum traversal depth (default: 5, max: 10)
        include_callers: Include upstream callers (default: false)
        
    Returns:
        Workflow graph with nodes and edges
        
    Raises:
        404: If repository or endpoint not found
        400: If endpoint doesn't belong to repository
    
    Example Response:
        {
            "start_node": {
                "id": "endpoint:...",
                "type": "endpoint",
                "name": "POST /api/orders",
                "method": "POST",
                "path": "/api/orders"
            },
            "nodes": [
                {"id": "endpoint:...", "type": "endpoint", ...},
                {"id": "symbol:...", "type": "symbol", "name": "create_order", ...},
                {"id": "symbol:...", "type": "symbol", "name": "OrderService.create", ...}
            ],
            "edges": [
                {"source": "endpoint:...", "target": "symbol:...", "type": "handles"},
                {"source": "symbol:...", "target": "symbol:...", "type": "calls"}
            ],
            "node_count": 3,
            "edge_count": 2,
            "depth": 5,
            "truncated": false
        }
    """
    # Validate repository
    repository = validate_repository(db, repo_id)
    
    # Validate endpoint
    endpoint = validate_endpoint(db, repo_id, endpoint_id)
    
    # Build workflow
    workflow_service = WorkflowService(db)
    workflow = workflow_service.build_endpoint_workflow(
        endpoint_id=endpoint_id,
        depth=depth,
        include_callers=include_callers
    )
    
    # Convert to response schema
    workflow_dict = workflow.to_dict()
    
    return WorkflowResponse(
        start_node=WorkflowNodeSchema(**workflow_dict["start_node"]),
        nodes=[WorkflowNodeSchema(**node) for node in workflow_dict["nodes"]],
        edges=[WorkflowEdgeSchema(**edge) for edge in workflow_dict["edges"]],
        node_count=workflow_dict["node_count"],
        edge_count=workflow_dict["edge_count"],
        depth=workflow_dict["depth"],
        truncated=workflow_dict["truncated"],
        truncation_reason=workflow_dict.get("truncation_reason")
    )


@router.get(
    "/repositories/{repo_id}/symbols/{symbol_id}/workflow",
    response_model=WorkflowResponse
)
async def get_symbol_workflow(
    repo_id: UUID,
    symbol_id: UUID,
    depth: int = Query(5, ge=1, le=10, description="Traversal depth (1-10)"),
    direction: str = Query(
        "downstream",
        regex="^(downstream|upstream|both)$",
        description="Traversal direction: downstream, upstream, or both"
    ),
    db: Session = Depends(get_db)
) -> WorkflowResponse:
    """
    Get application workflow for a symbol (function/class/method).
    
    Constructs the execution flow starting from the symbol:
    
    - downstream: symbol → functions it calls
    - upstream: symbol → functions that call it
    - both: bidirectional traversal
    
    The workflow is derived from static analysis data and represents
    POSSIBLE execution paths based on syntactic evidence.
    
    Args:
        repo_id: Repository UUID
        symbol_id: Symbol UUID
        depth: Maximum traversal depth (default: 5, max: 10)
        direction: Traversal direction (downstream/upstream/both)
        
    Returns:
        Workflow graph with nodes and edges
        
    Raises:
        404: If repository or symbol not found
        400: If symbol doesn't belong to repository or invalid direction
    
    Example Response:
        {
            "start_node": {
                "id": "symbol:...",
                "type": "symbol",
                "name": "OrderService.create",
                "symbol_type": "method"
            },
            "nodes": [
                {"id": "symbol:...", "type": "symbol", "name": "OrderService.create", ...},
                {"id": "symbol:...", "type": "symbol", "name": "validate_order", ...},
                {"id": "symbol:...", "type": "symbol", "name": "OrderRepository.save", ...}
            ],
            "edges": [
                {"source": "symbol:...", "target": "symbol:...", "type": "calls", "line_number": 42}
            ],
            "node_count": 3,
            "edge_count": 2,
            "depth": 5,
            "truncated": false
        }
    """
    # Validate repository
    repository = validate_repository(db, repo_id)
    
    # Validate symbol
    symbol = validate_symbol(db, repo_id, symbol_id)
    
    # Validate direction
    if direction not in ("downstream", "upstream", "both"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid direction: {direction}. Must be 'downstream', 'upstream', or 'both'"
        )
    
    # Build workflow
    workflow_service = WorkflowService(db)
    workflow = workflow_service.build_symbol_workflow(
        symbol_id=symbol_id,
        depth=depth,
        direction=direction
    )
    
    # Convert to response schema
    workflow_dict = workflow.to_dict()
    
    return WorkflowResponse(
        start_node=WorkflowNodeSchema(**workflow_dict["start_node"]),
        nodes=[WorkflowNodeSchema(**node) for node in workflow_dict["nodes"]],
        edges=[WorkflowEdgeSchema(**edge) for edge in workflow_dict["edges"]],
        node_count=workflow_dict["node_count"],
        edge_count=workflow_dict["edge_count"],
        depth=workflow_dict["depth"],
        truncated=workflow_dict["truncated"],
        truncation_reason=workflow_dict.get("truncation_reason")
    )
