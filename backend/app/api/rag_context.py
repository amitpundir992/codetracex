"""
API endpoints for Phase 11: RAG Context Pipeline.

These endpoints expose the RAG context assembly functionality for building
structured evidence packages from repository intelligence.

IMPORTANT: These endpoints return EVIDENCE ONLY.
No LLM-generated answers or explanations are provided.

Phase 12 will consume this evidence to generate answers.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Body
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Repository
from app.services.rag_context_service import RAGContextService
from app.schemas.rag_context import (
    RAGContextRequest,
    RAGContextResponse,
    RAGContext
)

router = APIRouter(prefix="/api/repositories", tags=["rag-context"])


@router.post("/{repository_id}/rag/context", response_model=RAGContextResponse)
def build_rag_context(
    repository_id: UUID,
    request: RAGContextRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Build a RAG context package for a user question.
    
    This endpoint orchestrates the complete Phase 11 evidence assembly pipeline:
    
    1. **Hybrid Retrieval**: Combines semantic (vector) and keyword (full-text) search
    2. **Deduplication**: Removes duplicate chunks by chunk_id
    3. **Ranking**: Sorts by combined retrieval score (deterministic tie-breaking)
    4. **Graph Enrichment**: Adds structured relationship evidence (optional)
    5. **Context Budgeting**: Enforces configurable character and item limits
    6. **Packaging**: Returns structured, bounded evidence package
    
    **What This Endpoint Returns:**
    - Retrieved code chunks with source traceability
    - Retrieval scores (semantic, keyword, combined)
    - Graph relationships (callers, callees, dependencies)
    - Retrieval metadata (transparency)
    - Truncation information (if context budget exceeded)
    
    **What This Endpoint Does NOT Return:**
    - LLM-generated answers
    - Natural language explanations
    - Code summaries
    - Recommendations
    
    **Evidence Assembly (No Generation):**
    All content is deterministically retrieved from repository analysis.
    No LLM or ML models are used to generate, rewrite, or transform content.
    
    **Repository Isolation:**
    Results are strictly isolated to the specified repository.
    No cross-repository contamination occurs.
    
    **Analysis Run Behavior:**
    - If `analysis_run_id` is provided: Uses only that analysis run
    - If not provided: Uses the latest successful analysis run for the repository
    - If no successful runs exist: Returns empty evidence
    
    **Context Budgeting:**
    The context budget prevents unbounded evidence from overwhelming future LLM context:
    - `max_evidence_items`: Maximum number of chunks (default: 20)
    - `max_characters`: Maximum total characters (default: 15000)
    - `max_chunk_characters`: Maximum characters per chunk (default: 2000)
    
    When limits are reached, the `truncated` flag is set to `true`.
    
    **Graph Evidence:**
    When `include_graph_evidence` is true, structured relationships are added:
    - Callers: Symbols that call the retrieved symbol
    - Callees: Symbols the retrieved symbol calls
    - Dependencies: Imported modules/files
    - Dependents: Files that import this symbol's file
    
    Graph evidence is limited by `max_graph_nodes` per relationship type.
    
    **Determinism:**
    Same repository + question + parameters = same evidence (when repository unchanged).
    Tie-breaking uses chunk_id (UUID) for deterministic ordering.
    
    Args:
        repository_id: UUID of the repository to query
        request: RAG context request with question and parameters
        db: Database session (injected)
        
    Returns:
        RAGContextResponse containing the complete context package
        
    Raises:
        404: Repository not found
        400: Invalid request parameters
        500: Context building failed
        
    Example:
        POST /api/repositories/{repo_id}/rag/context
        {
            "question": "How does the OrderService authenticate users?",
            "top_k": 10,
            "semantic_weight": 0.6,
            "keyword_weight": 0.4,
            "max_evidence_items": 15,
            "max_characters": 10000,
            "include_graph_evidence": true,
            "graph_depth": 1,
            "max_graph_nodes": 10
        }
        
        Response:
        {
            "context": {
                "question": "How does the OrderService authenticate users?",
                "repository_id": "...",
                "evidence": [...],  # Retrieved chunks
                "graph_evidence": [...],  # Relationship data
                "total_evidence_items": 12,
                "total_characters": 8542,
                "context_limit_reached": false,
                "truncated": false,
                "retrieval_metadata": {...}
            }
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
    
    # Initialize RAG context service
    rag_service = RAGContextService(db)
    
    try:
        # Build RAG context
        context = rag_service.build_context(
            repository_id=repository_id,
            question=request.question,
            top_k=request.top_k,
            semantic_weight=request.semantic_weight,
            keyword_weight=request.keyword_weight,
            max_evidence_items=request.max_evidence_items,
            max_characters=request.max_characters,
            max_chunk_characters=request.max_chunk_characters,
            include_graph_evidence=request.include_graph_evidence,
            graph_depth=request.graph_depth,
            max_graph_nodes=request.max_graph_nodes,
            analysis_run_id=analysis_run_id_uuid,
            chunk_type=request.chunk_type
        )
        
        return RAGContextResponse(context=context)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG context building failed: {str(e)}"
        )
