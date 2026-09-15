"""
API endpoints for hybrid search (semantic + keyword).

Phase 10: Hybrid Retrieval

These endpoints provide hybrid search combining semantic similarity and keyword matching.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db import get_db
from app.db.models import Repository
from app.services.hybrid_search_service import HybridSearchService

router = APIRouter(prefix="/api/repositories", tags=["hybrid-search"])


# Request/Response schemas
class HybridSearchRequest(BaseModel):
    """Request schema for hybrid search."""
    query: str = Field(..., min_length=1, max_length=500, description="Natural language or keyword query")
    top_k: int = Field(10, ge=1, le=100, description="Number of results to return")
    semantic_weight: float = Field(0.5, ge=0, le=1, description="Weight for semantic similarity (0-1)")
    keyword_weight: float = Field(0.5, ge=0, le=1, description="Weight for keyword relevance (0-1)")
    chunk_type: Optional[str] = Field(None, description="Filter by chunk type (symbol, api_endpoint, etc.)")
    analysis_run_id: Optional[str] = Field(None, description="Optional analysis run UUID to filter by")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How does OrderService authenticate users?",
                "top_k": 10,
                "semantic_weight": 0.6,
                "keyword_weight": 0.4,
                "chunk_type": None,
                "analysis_run_id": None
            }
        }


class HybridSearchResultResponse(BaseModel):
    """Response schema for a single hybrid search result."""
    chunk_id: str
    final_score: float = Field(..., ge=0, le=1, description="Combined weighted score")
    semantic_score: Optional[float] = Field(None, ge=0, le=1, description="Semantic similarity score (if available)")
    keyword_score: Optional[float] = Field(None, ge=0, le=1, description="Keyword relevance score (if available)")
    retrieval_source: str = Field(..., description="Source: 'semantic', 'keyword', or 'hybrid'")
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


class HybridSearchResponse(BaseModel):
    """Response schema for hybrid search."""
    query: str
    repository_id: str
    total_results: int
    semantic_weight: float
    keyword_weight: float
    results: List[HybridSearchResultResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How does OrderService authenticate users?",
                "repository_id": "123e4567-e89b-12d3-a456-426614174000",
                "total_results": 10,
                "semantic_weight": 0.6,
                "keyword_weight": 0.4,
                "results": [
                    {
                        "chunk_id": "123e4567-e89b-12d3-a456-426614174001",
                        "final_score": 0.87,
                        "semantic_score": 0.92,
                        "keyword_score": 0.75,
                        "retrieval_source": "hybrid",
                        "content": "class OrderService:\\n    def authenticate_user(...):",
                        "chunk_type": "symbol",
                        "file_path": "services/order_service.py",
                        "start_line": 42,
                        "end_line": 78,
                        "language": "Python",
                        "symbol_name": "OrderService.authenticate_user",
                        "symbol_type": "method",
                        "api_endpoint_method": None,
                        "api_endpoint_path": None
                    }
                ]
            }
        }


@router.post("/{repository_id}/hybrid-search", response_model=HybridSearchResponse)
def hybrid_search(
    repository_id: UUID,
    request: HybridSearchRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Perform hybrid search combining semantic and keyword retrieval.
    
    This endpoint:
    1. Validates the repository exists
    2. Executes semantic search (vector similarity via pgvector)
    3. Executes keyword search (full-text search via PostgreSQL tsvector)
    4. Normalizes scores from both sources
    5. Applies configurable weights
    6. Fuses and deduplicates results
    7. Returns ranked results with source traceability
    
    **Hybrid Retrieval Benefits:**
    - Natural language queries: Semantic search excels
    - Exact identifiers (e.g., "OrderService"): Keyword search excels
    - Mixed queries: Hybrid fusion provides best of both
    
    **Score Interpretation:**
    - semantic_score: Cosine similarity (0-1, higher = more similar)
    - keyword_score: PostgreSQL ts_rank (normalized to 0-1)
    - final_score: Weighted combination (0-1, higher = better match)
    
    **Retrieval Source:**
    - 'semantic': Only found via semantic search
    - 'keyword': Only found via keyword search
    - 'hybrid': Found via both searches
    
    **Important**: This endpoint returns retrieval results only.
    No LLM-generated answers or explanations are provided.
    
    Args:
        repository_id: UUID of the repository to search
        request: Search request with query, weights, and parameters
        db: Database session (injected)
        
    Returns:
        HybridSearchResponse with ranked chunks
        
    Raises:
        404: Repository not found
        400: Invalid request parameters
        500: Search failed
        
    Example:
        POST /api/repositories/{repo_id}/hybrid-search
        {
            "query": "How does OrderService authenticate users?",
            "top_k": 10,
            "semantic_weight": 0.6,
            "keyword_weight": 0.4
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
    search_service = HybridSearchService(db)
    
    try:
        # Perform hybrid search
        if request.chunk_type:
            results = search_service.search_by_chunk_type(
                repository_id=repository_id,
                query=request.query,
                chunk_type=request.chunk_type,
                top_k=request.top_k,
                semantic_weight=request.semantic_weight,
                keyword_weight=request.keyword_weight,
                analysis_run_id=analysis_run_id_uuid
            )
        else:
            results = search_service.search(
                repository_id=repository_id,
                query=request.query,
                top_k=request.top_k,
                semantic_weight=request.semantic_weight,
                keyword_weight=request.keyword_weight,
                analysis_run_id=analysis_run_id_uuid
            )
        
        # Convert to response format
        result_responses = [
            HybridSearchResultResponse(**result.to_dict())
            for result in results
        ]
        
        return HybridSearchResponse(
            query=request.query,
            repository_id=str(repository_id),
            total_results=len(result_responses),
            semantic_weight=request.semantic_weight,
            keyword_weight=request.keyword_weight,
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
            detail=f"Hybrid search failed: {str(e)}"
        )


@router.get("/{repository_id}/hybrid-search", response_model=HybridSearchResponse)
def hybrid_search_get(
    repository_id: UUID,
    query: str = Query(..., min_length=1, max_length=500, description="Natural language or keyword query"),
    top_k: int = Query(10, ge=1, le=100, description="Number of results"),
    semantic_weight: float = Query(0.5, ge=0, le=1, description="Semantic weight"),
    keyword_weight: float = Query(0.5, ge=0, le=1, description="Keyword weight"),
    chunk_type: Optional[str] = Query(None, description="Filter by chunk type"),
    analysis_run_id: Optional[str] = Query(None, description="Filter by analysis run UUID"),
    db: Session = Depends(get_db)
):
    """
    Perform hybrid search using GET method (convenience endpoint).
    
    This is a convenience wrapper around the POST endpoint for simple queries.
    For more complex requests, use the POST endpoint.
    
    Args:
        repository_id: UUID of repository
        query: Natural language or keyword query
        top_k: Number of results to return
        semantic_weight: Weight for semantic scores
        keyword_weight: Weight for keyword scores
        chunk_type: Optional chunk type filter
        analysis_run_id: Optional analysis run filter
        db: Database session (injected)
        
    Returns:
        HybridSearchResponse with ranked chunks
        
    Example:
        GET /api/repositories/{repo_id}/hybrid-search?query=OrderService&top_k=10
    """
    # Reuse POST endpoint logic
    request = HybridSearchRequest(
        query=query,
        top_k=top_k,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
        chunk_type=chunk_type,
        analysis_run_id=analysis_run_id
    )
    
    return hybrid_search(repository_id, request, db)
