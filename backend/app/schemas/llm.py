"""
Pydantic schemas for Phase 12: LLM Reasoning & Grounded Explanations.

These schemas define the request/response structure for the Ask API endpoint
and the grounded answer format with citations.

Design Principles:

1. GROUNDED ANSWERS
   - Answer must reference supplied evidence
   - Citations must be traceable to RAG context
   - Insufficient evidence is explicitly indicated

2. CITATION TRACEABILITY
   - Citations reference evidence IDs from RAG context
   - Source location preserved (file, lines, symbol)
   - No fabricated citations allowed

3. SECURITY
   - No API keys exposed
   - Repository content treated as untrusted data
   - Bounded inputs to prevent resource exhaustion
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class Citation(BaseModel):
    """
    A citation linking answer content to repository evidence.
    
    Citations preserve complete traceability to the original source code
    or documentation that supports the answer.
    """
    # Evidence reference
    evidence_id: UUID = Field(..., description="Chunk ID from RAG context evidence")
    
    # Source location
    file_path: str = Field(..., description="File path in repository")
    start_line: int = Field(..., ge=1, description="Starting line number")
    end_line: int = Field(..., ge=1, description="Ending line number")
    
    # Context
    symbol_name: Optional[str] = Field(None, description="Symbol name if applicable")
    symbol_type: Optional[str] = Field(None, description="Symbol type: function, class, method, etc.")
    
    # Excerpt
    excerpt: str = Field(..., max_length=500, description="Brief excerpt from source (truncated)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "evidence_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_path": "backend/services/auth_service.py",
                "start_line": 42,
                "end_line": 78,
                "symbol_name": "AuthService.verify_token",
                "symbol_type": "method",
                "excerpt": "def verify_token(self, token: str) -> bool:\n    \"\"\"Verify JWT token...\"\"\""
            }
        }


class GroundedAnswer(BaseModel):
    """
    A grounded answer to a user question about a repository.
    
    The answer is grounded in the repository evidence retrieved by the RAG
    pipeline. All claims should be traceable to the supplied evidence.
    
    IMPORTANT: This is NOT a free-form chat response. It is explicitly
    constrained to explain the repository based on retrieved evidence.
    """
    # Question
    question: str = Field(..., description="Original user question")
    
    # Answer
    answer: str = Field(..., description="Grounded answer based on repository evidence")
    
    # Evidence
    citations: List[Citation] = Field(
        default_factory=list,
        description="Citations supporting the answer"
    )
    
    # Confidence indicators
    is_sufficient_evidence: bool = Field(
        ...,
        description="Whether retrieved evidence was sufficient to answer the question"
    )
    
    confidence_note: Optional[str] = Field(
        None,
        description="Note about answer confidence or evidence limitations"
    )
    
    # Metadata
    evidence_count: int = Field(..., ge=0, description="Number of evidence items used")
    repository_id: UUID = Field(..., description="Repository being queried")
    analysis_run_id: Optional[UUID] = Field(None, description="Specific analysis run if filtered")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "How does the AuthService verify tokens?",
                "answer": "The AuthService verifies JWT tokens using the verify_token method...",
                "citations": [],
                "is_sufficient_evidence": True,
                "confidence_note": None,
                "evidence_count": 3,
                "repository_id": "123e4567-e89b-12d3-a456-426614174000",
                "analysis_run_id": None
            }
        }


class AskRequest(BaseModel):
    """
    Request schema for the Ask API endpoint.
    
    Combines question with optional retrieval configuration.
    """
    # Question
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's question about the repository"
    )
    
    # Retrieval configuration (optional, inherits RAG context defaults)
    top_k: int = Field(
        10,
        ge=1,
        le=50,
        description="Number of chunks to retrieve"
    )
    
    semantic_weight: float = Field(
        0.5,
        ge=0,
        le=1,
        description="Weight for semantic search (0-1)"
    )
    
    keyword_weight: float = Field(
        0.5,
        ge=0,
        le=1,
        description="Weight for keyword search (0-1)"
    )
    
    # Filtering
    analysis_run_id: Optional[str] = Field(
        None,
        description="Filter by specific analysis run UUID"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "How does the OrderService handle payment processing?",
                "top_k": 10,
                "semantic_weight": 0.6,
                "keyword_weight": 0.4,
                "analysis_run_id": None
            }
        }


class AskResponse(BaseModel):
    """
    Response schema for the Ask API endpoint.
    
    Returns the grounded answer with all supporting metadata.
    """
    answer: GroundedAnswer = Field(..., description="Grounded answer to the question")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": {
                    "question": "How does the OrderService handle payment processing?",
                    "answer": "The OrderService handles payment processing through...",
                    "citations": [],
                    "is_sufficient_evidence": True,
                    "confidence_note": None,
                    "evidence_count": 5,
                    "repository_id": "123e4567-e89b-12d3-a456-426614174000",
                    "analysis_run_id": None
                }
            }
        }


class InsufficientEvidenceResponse(BaseModel):
    """
    Response when there is insufficient evidence to answer the question.
    
    This is returned when the RAG context contains no relevant evidence
    or when the LLM cannot provide a grounded answer.
    """
    question: str = Field(..., description="Original user question")
    message: str = Field(..., description="Explanation of why evidence was insufficient")
    evidence_count: int = Field(0, description="Number of evidence items retrieved")
    repository_id: UUID = Field(..., description="Repository being queried")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "How does the FooService work?",
                "message": "No relevant code or documentation was found for this question.",
                "evidence_count": 0,
                "repository_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
