"""
API endpoints for semantic search.

Phase 9: Embeddings + pgvector

These endpoints provide semantic similarity search over repository code.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db import get_db
from app.db.models import Repository
from app.services.semantic_search_service import SemanticSearchService

router = APIRouter(prefix="/api/repositories", tags=["semantic-search"])


# Request/Response schemas
class SemanticSearchRequest(BaseModel):
    """Request schema for semantic search."""
    query: str = Field(..., min_length=1, max_length=500, description="Natural language query")
    top_k: int = Field(10, ge=1, le=100, description="Number of results to return")
    chunk_type: Optional[str] = Field(None, description="Filter by chunk type (symbol, api_endpoint, etc.)")
    analysis_run_id: Optional[str] = Field(None, description="Optional analysis run UUID to filter by")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How does authentication work?",
                "top_k": 5,
                "chunk_type": None,
                "analysis_run_id": None
            }
        }


class SemanticSearchResultResponse(BaseModel):
    """Response schema for a single search result."""
    chunk_id: str
    similarity_score: float = Field(..., ge=0, le=1)
    content: str
    chunk_type: str
    file_path: str
    start_line: int
    end_line: int
    language: Optional[str] = None
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None
    api_endpoint_method: Optional[str] = None
    api_endpoint_path: Optional[str] = None
    
    class Config:
        from_attributes = True


class SemanticSearchResponse(BaseModel):
    """Response schema for semantic search."""
    query: str
    repository_id: str
    total_results: int
    results: List[SemanticSearchResultResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How does authentication work?",
                "repository_id": "123e4567-e89b-12d3-a456-426614174000",
                "total_results": 5,
                "results": [
                    {
                        "chunk_id": "123e4567-e89b-12d3-a456-426614174001",
                        "similarity_score": 0.89,
                        "content": "def authenticate_user(username, password): ...",
                        "chunk_type": "symbol",
                        "file_path": "app/auth/service.py",
                        "start_line": 42,
                        "end_line": 78,
                        "language": "Python",
                        "symbol_name": "authenticate_user",
                        "symbol_type": "function",
                        "api_endpoint_method": None,
                        "api_endpoint_path": None
                    }
                ]
            }
        }


@router.post("/{repository_id}/semantic-search", response_model=SemanticSearchResponse)
def semantic_search(
    repository_id: UUID,
    request: SemanticSearchRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Perform semantic similarity search over repository code.
    
    This endpoint:
    1. Validates the repository exists
    2. Generates embedding for the query
    3. Searches for similar code chunks using pgvector
    4. Returns ranked results with source traceability
    
    **Important**: This endpoint returns retrieval results only.
    No LLM-generated answers or explanations are provided.
    
    Args:
        repository_id: UUID of the repository to search
        request: Search request with query and parameters
        db: Database session (injected)
        
    Returns:
        SemanticSearchResponse with ranked chunks
        
    Raises:
        404: Repository not found
        400: Invalid request parameters
        500: Search failed
        
    Example:
        POST /api/repositories/{repo_id}/semantic-search
        {
            "query": "How does user authentication work?",
            "top_k": 5
        }
    """
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Parse optional analysis_run_id
    analysis_run_id_uuid = None
    if request.analysis_run_id:
        try:
            analysis_run_id_uuid = UUID(request.analysis_run_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid analysis_run_id format"
            )
    
    # Initialize search service
    search_service = SemanticSearchService(db)
    
    try:
        # Perform search (with or without chunk_type filter)
        if request.chunk_type:
            results = search_service.search_by_chunk_type(
                repository_id=repository_id,
                query=request.query,
                chunk_type=request.chunk_type,
                top_k=request.top_k,
                analysis_run_id=analysis_run_id_uuid
            )
        else:
            results = search_service.search(
                repository_id=repository_id,
                query=request.query,
                top_k=request.top_k,
                analysis_run_id=analysis_run_id_uuid
            )
        
        # Convert to response format
        result_responses = [
            SemanticSearchResultResponse(**result.to_dict())
            for result in results
        ]
        
        return SemanticSearchResponse(
            query=request.query,
            repository_id=str(repository_id),
            total_results=len(result_responses),
            results=result_responses
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(e)}"
        )


@router.get("/{repository_id}/semantic-search", response_model=SemanticSearchResponse)
def semantic_search_get(
    repository_id: UUID,
    query: str = Query(..., min_length=1, max_length=500, description="Natural language query"),
    top_k: int = Query(10, ge=1, le=100, description="Number of results"),
    chunk_type: Optional[str] = Query(None, description="Filter by chunk type"),
    analysis_run_id: Optional[str] = Query(None, description="Filter by analysis run UUID"),
    db: Session = Depends(get_db)
):
    """
    Perform semantic search using GET method (convenience endpoint).
    
    This is a convenience wrapper around the POST endpoint for simple queries.
    For more complex requests, use the POST endpoint.
    
    Args:
        repository_id: UUID of repository
        query: Natural language query
        top_k: Number of results to return
        chunk_type: Optional chunk type filter
        analysis_run_id: Optional analysis run filter
        db: Database session (injected)
        
    Returns:
        SemanticSearchResponse with ranked chunks
        
    Example:
        GET /api/repositories/{repo_id}/semantic-search?query=authentication&top_k=5
    """
    # Reuse POST endpoint logic
    request = SemanticSearchRequest(
        query=query,
        top_k=top_k,
        chunk_type=chunk_type,
        analysis_run_id=analysis_run_id
    )
    
    return semantic_search(repository_id, request, db)
