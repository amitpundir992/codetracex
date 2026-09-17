"""
Pydantic schemas for Phase 11: RAG Context Pipeline.

These schemas define the structured evidence package that will be consumed
by future LLM integration (Phase 12).

Phase 11 is ONLY about evidence assembly, not answer generation.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class EvidenceItem(BaseModel):
    """
    A single piece of repository evidence retrieved for a question.
    
    Each evidence item preserves complete source traceability for citation
    and verification purposes.
    """
    # Retrieval metadata
    chunk_id: UUID = Field(..., description="Unique identifier of the chunk")
    retrieval_score: float = Field(..., ge=0, le=1, description="Combined retrieval score")
    semantic_score: Optional[float] = Field(None, ge=0, le=1, description="Semantic similarity score")
    keyword_score: Optional[float] = Field(None, ge=0, le=1, description="Keyword relevance score")
    retrieval_source: str = Field(..., description="Source: semantic, keyword, hybrid, or graph")
    
    # Content
    content: str = Field(..., description="Source code or text content")
    chunk_type: str = Field(..., description="Type: symbol, api_endpoint, etc.")
    
    # Source traceability
    file_path: str = Field(..., description="File path in repository")
    start_line: int = Field(..., ge=1, description="Starting line number")
    end_line: int = Field(..., ge=1, description="Ending line number")
    language: Optional[str] = Field(None, description="Programming language")
    
    # Symbol information (if applicable)
    symbol_name: Optional[str] = Field(None, description="Symbol name")
    symbol_type: Optional[str] = Field(None, description="Symbol type: function, class, method, etc.")
    
    # API information (if applicable)
    api_endpoint_method: Optional[str] = Field(None, description="HTTP method: GET, POST, etc.")
    api_endpoint_path: Optional[str] = Field(None, description="API endpoint path")
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional context-specific metadata")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                "retrieval_score": 0.87,
                "semantic_score": 0.92,
                "keyword_score": 0.75,
                "retrieval_source": "hybrid",
                "content": "class OrderService:\n    def authenticate_user(self, token):\n        ...",
                "chunk_type": "symbol",
                "file_path": "backend/services/order_service.py",
                "start_line": 42,
                "end_line": 78,
                "language": "Python",
                "symbol_name": "OrderService.authenticate_user",
                "symbol_type": "method",
                "api_endpoint_method": None,
                "api_endpoint_path": None,
                "metadata": None
            }
        }


class GraphEvidence(BaseModel):
    """
    Structured graph evidence enrichment for a symbol or API.
    
    Provides deterministic repository relationships derived from static analysis.
    This is NOT a complete graph dump - only relevant connected nodes.
    """
    # Source node
    node_id: str = Field(..., description="UUID of the source node")
    node_type: str = Field(..., description="Type: symbol, file, endpoint")
    node_name: str = Field(..., description="Display name")
    
    # Relationship evidence
    callers: List[Dict[str, Any]] = Field(default_factory=list, description="Symbols that call this node")
    callees: List[Dict[str, Any]] = Field(default_factory=list, description="Symbols this node calls")
    dependencies: List[Dict[str, Any]] = Field(default_factory=list, description="Dependencies")
    dependents: List[Dict[str, Any]] = Field(default_factory=list, description="Dependents")
    
    # Limits
    truncated: bool = Field(False, description="Whether graph evidence was truncated")
    truncation_reason: Optional[str] = Field(None, description="Why truncation occurred")
    
    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "123e4567-e89b-12d3-a456-426614174000",
                "node_type": "symbol",
                "node_name": "OrderService.process_payment",
                "callers": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174001",
                        "name": "OrderController.create_order",
                        "type": "method",
                        "file": "controllers/order_controller.py"
                    }
                ],
                "callees": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174002",
                        "name": "PaymentGateway.charge",
                        "type": "method",
                        "file": "services/payment_gateway.py"
                    }
                ],
                "dependencies": [],
                "dependents": [],
                "truncated": False,
                "truncation_reason": None
            }
        }


class RetrievalMetadata(BaseModel):
    """
    Metadata about the retrieval process.
    
    Provides transparency into how evidence was selected.
    """
    total_candidates: int = Field(..., ge=0, description="Total chunks retrieved before filtering")
    selected_evidence: int = Field(..., ge=0, description="Number of evidence items after deduplication/selection")
    semantic_candidates: int = Field(0, ge=0, description="Candidates from semantic search")
    keyword_candidates: int = Field(0, ge=0, description="Candidates from keyword search")
    deduplicated_count: int = Field(0, ge=0, description="Number of duplicates removed")
    graph_enrichments: int = Field(0, ge=0, description="Number of graph evidence items added")
    
    # Weights used
    semantic_weight: float = Field(0.5, ge=0, le=1, description="Weight applied to semantic scores")
    keyword_weight: float = Field(0.5, ge=0, le=1, description="Weight applied to keyword scores")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_candidates": 50,
                "selected_evidence": 12,
                "semantic_candidates": 30,
                "keyword_candidates": 25,
                "deduplicated_count": 5,
                "graph_enrichments": 2,
                "semantic_weight": 0.6,
                "keyword_weight": 0.4
            }
        }


class RAGContext(BaseModel):
    """
    Complete RAG context package for a user question.
    
    This is the final output of Phase 11: a structured, bounded, deduplicated
    collection of repository evidence ready for LLM consumption.
    
    IMPORTANT: This schema contains NO LLM-generated content.
    All content is retrieved/derived from deterministic repository analysis.
    """
    # Query context
    question: str = Field(..., min_length=1, max_length=1000, description="User's question")
    repository_id: UUID = Field(..., description="Repository being queried")
    analysis_run_id: Optional[UUID] = Field(None, description="Specific analysis run (if filtered)")
    
    # Evidence
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Retrieved evidence items")
    graph_evidence: List[GraphEvidence] = Field(default_factory=list, description="Structured graph enrichment")
    
    # Context budgeting
    total_evidence_items: int = Field(..., ge=0, description="Total number of evidence items")
    total_characters: int = Field(..., ge=0, description="Total character count of all evidence")
    context_limit_reached: bool = Field(False, description="Whether context budget was exhausted")
    truncated: bool = Field(False, description="Whether evidence was truncated")
    truncation_reason: Optional[str] = Field(None, description="Reason for truncation")
    
    # Retrieval metadata
    retrieval_metadata: RetrievalMetadata = Field(..., description="Metadata about retrieval process")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "How does the OrderService authenticate users?",
                "repository_id": "123e4567-e89b-12d3-a456-426614174000",
                "analysis_run_id": None,
                "evidence": [],
                "graph_evidence": [],
                "total_evidence_items": 12,
                "total_characters": 8542,
                "context_limit_reached": False,
                "truncated": False,
                "truncation_reason": None,
                "retrieval_metadata": {
                    "total_candidates": 50,
                    "selected_evidence": 12,
                    "semantic_candidates": 30,
                    "keyword_candidates": 25,
                    "deduplicated_count": 5,
                    "graph_enrichments": 2,
                    "semantic_weight": 0.6,
                    "keyword_weight": 0.4
                }
            }
        }


# Request schemas for API endpoints

class RAGContextRequest(BaseModel):
    """
    Request schema for building RAG context.
    """
    question: str = Field(..., min_length=1, max_length=1000, description="User's question about the repository")
    top_k: int = Field(10, ge=1, le=100, description="Number of chunks to retrieve")
    semantic_weight: float = Field(0.5, ge=0, le=1, description="Weight for semantic search")
    keyword_weight: float = Field(0.5, ge=0, le=1, description="Weight for keyword search")
    
    # Context budgeting
    max_evidence_items: Optional[int] = Field(None, ge=1, le=100, description="Maximum evidence items to include")
    max_characters: Optional[int] = Field(None, ge=1000, description="Maximum total characters")
    max_chunk_characters: Optional[int] = Field(None, ge=100, description="Maximum characters per chunk")
    
    # Graph enrichment
    include_graph_evidence: bool = Field(True, description="Include graph relationship evidence")
    graph_depth: int = Field(1, ge=0, le=3, description="Depth for graph traversal")
    max_graph_nodes: int = Field(10, ge=1, le=50, description="Maximum graph nodes per evidence item")
    
    # Filtering
    analysis_run_id: Optional[str] = Field(None, description="Filter by specific analysis run UUID")
    chunk_type: Optional[str] = Field(None, description="Filter by chunk type")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "How does the OrderService authenticate users?",
                "top_k": 10,
                "semantic_weight": 0.6,
                "keyword_weight": 0.4,
                "max_evidence_items": 15,
                "max_characters": 10000,
                "max_chunk_characters": 1000,
                "include_graph_evidence": True,
                "graph_depth": 1,
                "max_graph_nodes": 10,
                "analysis_run_id": None,
                "chunk_type": None
            }
        }


class RAGContextResponse(BaseModel):
    """
    Response schema for RAG context endpoint.
    
    Returns the complete context package.
    """
    context: RAGContext = Field(..., description="Complete RAG context package")
    
    class Config:
        json_schema_extra = {
            "example": {
                "context": {
                    "question": "How does the OrderService authenticate users?",
                    "repository_id": "123e4567-e89b-12d3-a456-426614174000",
                    "analysis_run_id": None,
                    "evidence": [],
                    "graph_evidence": [],
                    "total_evidence_items": 12,
                    "total_characters": 8542,
                    "context_limit_reached": False,
                    "truncated": False,
                    "truncation_reason": None,
                    "retrieval_metadata": {
                        "total_candidates": 50,
                        "selected_evidence": 12,
                        "semantic_candidates": 30,
                        "keyword_candidates": 25,
                        "deduplicated_count": 5,
                        "graph_enrichments": 2,
                        "semantic_weight": 0.6,
                        "keyword_weight": 0.4
                    }
                }
            }
        }
