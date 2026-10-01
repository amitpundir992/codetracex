"""
Pydantic schemas for Phase 16: Advanced Repository Investigation.

These schemas define the investigation request/response structure with:
- Investigation intent classification
- Unified evidence model
- Grounded claims with certainty levels
- Follow-up question generation
- Lightweight conversation context

Design Principles:

1. GROUNDING
   - Claims categorized as confirmed/inferred/uncertain
   - Every claim traceable to evidence
   - Explicit limitations when evidence is missing

2. EVIDENCE TRACEABILITY
   - Unified evidence model across all retrieval sources
   - Deterministic deduplication
   - Source metadata preserved

3. INVESTIGATION FLOW
   - Intent-based evidence gathering
   - Bounded context budgets
   - Contextual follow-up questions

4. SECURITY
   - Repository isolation
   - Analysis run isolation
   - No credential exposure
   - Bounded inputs
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class InvestigationIntent(str, Enum):
    """
    Classification of investigation question types.
    
    Used to determine which evidence sources to prioritize.
    """
    GENERAL_REPOSITORY = "general_repository_question"
    SYMBOL_EXPLANATION = "symbol_explanation"
    API_EXPLANATION = "api_explanation"
    WORKFLOW_EXPLANATION = "workflow_explanation"
    DEPENDENCY_QUESTION = "dependency_question"
    IMPACT_QUESTION = "impact_question"
    HISTORY_QUESTION = "history_question"
    ARCHITECTURE_QUESTION = "architecture_question"
    DATABASE_QUESTION = "database_question"
    UNKNOWN = "unknown"


class EvidenceType(str, Enum):
    """Types of investigation evidence."""
    FILE = "file"
    SYMBOL = "symbol"
    API_ENDPOINT = "api_endpoint"
    GRAPH_RELATIONSHIP = "graph_relationship"
    WORKFLOW_NODE = "workflow_node"
    WORKFLOW_EDGE = "workflow_edge"
    GIT_COMMIT = "git_commit"
    COMMIT_FILE_CHANGE = "commit_file_change"
    SEMANTIC_CHUNK = "semantic_chunk"
    HYBRID_SEARCH = "hybrid_search"


class CertaintyLevel(str, Enum):
    """Certainty level for claims."""
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNCERTAIN = "uncertain"


class InvestigationEvidence(BaseModel):
    """
    Unified evidence item for investigation responses.
    
    Consolidates evidence from multiple sources:
    - Hybrid search
    - Graph traversal
    - Workflow analysis
    - Git history
    - Direct entity lookup
    """
    # Identity
    evidence_id: str = Field(..., description="Unique identifier for this evidence")
    evidence_type: EvidenceType = Field(..., description="Type of evidence")
    
    # Retrieval metadata
    retrieval_score: Optional[float] = Field(None, ge=0, le=1, description="Relevance score if from search")
    retrieval_source: str = Field(..., description="Source: semantic, keyword, hybrid, graph, workflow, git, direct")
    
    # Content
    content: str = Field(..., description="Evidence content (code, text, or description)")
    content_truncated: bool = Field(False, description="Whether content was truncated")
    
    # Source traceability
    repository_id: UUID = Field(..., description="Repository this evidence belongs to")
    analysis_run_id: Optional[UUID] = Field(None, description="Analysis run if applicable")
    file_path: Optional[str] = Field(None, description="File path if applicable")
    start_line: Optional[int] = Field(None, ge=1, description="Start line if applicable")
    end_line: Optional[int] = Field(None, ge=1, description="End line if applicable")
    language: Optional[str] = Field(None, description="Programming language")
    
    # Entity references
    symbol_id: Optional[UUID] = Field(None, description="Symbol ID if applicable")
    symbol_name: Optional[str] = Field(None, description="Symbol name")
    symbol_type: Optional[str] = Field(None, description="Symbol type: function, class, method, etc.")
    
    api_endpoint_id: Optional[UUID] = Field(None, description="API endpoint ID if applicable")
    api_endpoint_method: Optional[str] = Field(None, description="HTTP method")
    api_endpoint_path: Optional[str] = Field(None, description="API path")
    
    commit_id: Optional[UUID] = Field(None, description="Commit ID if from git history")
    commit_sha: Optional[str] = Field(None, description="Git commit SHA")
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional context-specific metadata")
    
    class Config:
        from_attributes = True


class GroundedClaim(BaseModel):
    """
    A grounded claim with explicit certainty level and evidence references.
    
    Distinguishes between confirmed facts, inferences, and uncertain statements.
    """
    claim_text: str = Field(..., description="The claim being made")
    certainty: CertaintyLevel = Field(..., description="Certainty level")
    evidence_ids: List[str] = Field(default_factory=list, description="Evidence IDs supporting this claim")
    reasoning: Optional[str] = Field(None, description="Explanation of the reasoning")
    
    class Config:
        json_schema_extra = {
            "example": {
                "claim_text": "OrderController.create_order calls OrderService.create_order",
                "certainty": "confirmed",
                "evidence_ids": ["evidence_001", "evidence_002"],
                "reasoning": "Direct call relationship found in static analysis"
            }
        }


class FollowUpQuestion(BaseModel):
    """
    A suggested follow-up investigation question.
    
    Grounded in the available repository context.
    """
    question: str = Field(..., description="The follow-up question")
    rationale: Optional[str] = Field(None, description="Why this question is relevant")
    related_evidence_ids: List[str] = Field(default_factory=list, description="Evidence that prompted this question")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Which API endpoints require authentication?",
                "rationale": "Authentication system was discussed",
                "related_evidence_ids": ["evidence_003"]
            }
        }


class InvestigationGrounding(BaseModel):
    """
    Metadata about answer grounding and evidence quality.
    """
    is_grounded: bool = Field(..., description="Whether answer is grounded in repository evidence")
    evidence_count: int = Field(..., ge=0, description="Number of evidence items")
    evidence_truncated: bool = Field(False, description="Whether evidence was truncated due to limits")
    truncation_reason: Optional[str] = Field(None, description="Why evidence was truncated")
    confidence_note: Optional[str] = Field(None, description="Note about confidence or limitations")


class ConversationContext(BaseModel):
    """
    Lightweight conversation context for reference resolution.
    
    Allows references like 'that function', 'this endpoint' without full chat history.
    """
    last_symbols: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Recently discussed symbols [{id, name, type}]",
        max_length=10
    )
    last_files: List[str] = Field(
        default_factory=list,
        description="Recently discussed file paths",
        max_length=10
    )
    last_endpoints: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Recently discussed endpoints [{id, method, path}]",
        max_length=10
    )
    last_question: Optional[str] = Field(None, description="Previous question for context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "last_symbols": [
                    {"id": "uuid-here", "name": "AuthService.verify_token", "type": "method"}
                ],
                "last_files": ["backend/services/auth_service.py"],
                "last_endpoints": [
                    {"id": "uuid-here", "method": "POST", "path": "/api/auth/login"}
                ],
                "last_question": "How does authentication work?"
            }
        }


class InvestigationRequest(BaseModel):
    """
    Request to investigate a repository question.
    """
    question: str = Field(..., min_length=1, max_length=1000, description="Investigation question")
    analysis_run_id: Optional[UUID] = Field(None, description="Specific analysis run to query")
    conversation_context: Optional[ConversationContext] = Field(
        None,
        description="Previous investigation context for reference resolution"
    )
    
    # Investigation options
    max_evidence: Optional[int] = Field(10, ge=1, le=50, description="Maximum evidence items")
    include_graph: Optional[bool] = Field(True, description="Include graph relationships")
    include_workflow: Optional[bool] = Field(True, description="Include workflow information")
    include_git_history: Optional[bool] = Field(False, description="Include git history")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "How does authentication work?",
                "analysis_run_id": None,
                "conversation_context": None,
                "max_evidence": 10,
                "include_graph": True,
                "include_workflow": True,
                "include_git_history": False
            }
        }


class InvestigationResponse(BaseModel):
    """
    Response to an investigation request.
    
    Contains grounded answer with claims, evidence, citations, and follow-up questions.
    """
    # Question
    question: str = Field(..., description="Original investigation question")
    detected_intent: InvestigationIntent = Field(..., description="Detected question intent")
    
    # Answer
    answer: str = Field(..., description="Grounded answer based on repository evidence")
    
    # Grounded claims
    claims: List[GroundedClaim] = Field(
        default_factory=list,
        description="Individual claims with certainty levels"
    )
    
    # Evidence
    evidence: List[InvestigationEvidence] = Field(
        default_factory=list,
        description="Retrieved evidence supporting the answer"
    )
    
    # Grounding metadata
    grounding: InvestigationGrounding = Field(..., description="Evidence quality metadata")
    
    # Limitations
    limitations: List[str] = Field(
        default_factory=list,
        description="Explicit limitations or missing evidence"
    )
    
    # Follow-up questions
    follow_up_questions: List[FollowUpQuestion] = Field(
        default_factory=list,
        description="Suggested next investigation questions"
    )
    
    # Context for next turn
    conversation_context: ConversationContext = Field(
        ...,
        description="Updated conversation context for follow-up questions"
    )
    
    # Metadata
    repository_id: UUID = Field(..., description="Repository queried")
    analysis_run_id: Optional[UUID] = Field(None, description="Analysis run used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "How does authentication work?",
                "detected_intent": "general_repository_question",
                "answer": "Authentication is implemented in AuthService...",
                "claims": [
                    {
                        "claim_text": "AuthService.verify_token validates JWT tokens",
                        "certainty": "confirmed",
                        "evidence_ids": ["evidence_001"],
                        "reasoning": "Method implementation found in auth_service.py"
                    }
                ],
                "evidence": [],
                "grounding": {
                    "is_grounded": True,
                    "evidence_count": 5,
                    "evidence_truncated": False,
                    "truncation_reason": None,
                    "confidence_note": None
                },
                "limitations": [],
                "follow_up_questions": [
                    {
                        "question": "Which API endpoints require authentication?",
                        "rationale": "Authentication system was discussed",
                        "related_evidence_ids": ["evidence_001"]
                    }
                ],
                "conversation_context": {
                    "last_symbols": [],
                    "last_files": [],
                    "last_endpoints": [],
                    "last_question": "How does authentication work?"
                },
                "repository_id": "uuid-here",
                "analysis_run_id": None
            }
        }


class InsufficientEvidenceResponse(BaseModel):
    """
    Response when insufficient evidence is available to answer the question.
    """
    question: str = Field(..., description="Original question")
    reason: str = Field(..., description="Why evidence was insufficient")
    suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions for refining the question"
    )
    evidence_count: int = Field(..., ge=0, description="Number of evidence items retrieved")
    repository_id: UUID = Field(..., description="Repository queried")
