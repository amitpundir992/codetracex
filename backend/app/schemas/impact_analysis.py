"""
Pydantic schemas for Phase 13: AI Impact Analysis + Change Planning.

These schemas define the request/response structure for impact analysis,
implementation planning, and change impact exploration.

Design Principles:

1. DETERMINISTIC EVIDENCE
   - All impacts must trace back to repository intelligence
   - LLM explains but does not discover dependencies
   - Clear separation of verified facts from inferences

2. GROUNDING
   - Every impact item references source evidence
   - Citations link to actual repository data
   - Uncertainty is explicitly indicated

3. BOUNDED ANALYSIS
   - Depth limits enforced (max 10)
   - Node and edge limits (500/1000)
   - Truncation explicitly reported

4. REPOSITORY ISOLATION
   - All queries scoped by repository_id
   - Analysis run validation required
   - No cross-repository contamination
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from uuid import UUID


# ============================================================================
# TARGET IDENTIFICATION
# ============================================================================

class ImpactTarget(BaseModel):
    """
    Represents the identified target for impact analysis.
    
    The target is the repository entity (symbol, file, or API endpoint)
    that the user wants to analyze for potential change impact.
    """
    # Target type
    target_type: Literal["symbol", "file", "api_endpoint"] = Field(
        ...,
        description="Type of target entity"
    )
    
    # Target identification
    target_id: UUID = Field(..., description="UUID of the target entity")
    name: str = Field(..., description="Name or path of target")
    
    # Symbol-specific fields
    symbol_type: Optional[str] = Field(None, description="Type: function, class, method")
    qualified_name: Optional[str] = Field(None, description="Qualified symbol name")
    
    # File-specific fields
    file_path: Optional[str] = Field(None, description="Relative file path")
    language: Optional[str] = Field(None, description="Programming language")
    
    # API-specific fields
    http_method: Optional[str] = Field(None, description="HTTP method: GET, POST, etc.")
    endpoint_path: Optional[str] = Field(None, description="API endpoint path")
    framework: Optional[str] = Field(None, description="Web framework")
    handler_name: Optional[str] = Field(None, description="Handler function name")
    
    class Config:
        json_schema_extra = {
            "example": {
                "target_type": "symbol",
                "target_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "OrderService.create_order",
                "symbol_type": "method",
                "qualified_name": "services.order.OrderService.create_order",
                "file_path": "backend/services/order_service.py",
                "language": "python"
            }
        }


class TargetCandidate(BaseModel):
    """
    Represents a candidate target when identification is ambiguous.
    """
    target: ImpactTarget = Field(..., description="Candidate target")
    match_score: float = Field(..., ge=0, le=1, description="Confidence score 0-1")
    match_reason: str = Field(..., description="Why this candidate matched")


class TargetIdentificationResult(BaseModel):
    """
    Result of target identification process.
    
    Can be unambiguous (single target), ambiguous (multiple candidates),
    or not found.
    """
    status: Literal["found", "ambiguous", "not_found"] = Field(
        ...,
        description="Identification status"
    )
    
    # Found
    target: Optional[ImpactTarget] = Field(None, description="Identified target (if found)")
    
    # Ambiguous
    candidates: List[TargetCandidate] = Field(
        default_factory=list,
        description="Candidate targets if ambiguous"
    )
    
    # Not found
    message: Optional[str] = Field(None, description="Message if not found or ambiguous")


# ============================================================================
# IMPACT ITEMS
# ============================================================================

class ImpactEvidence(BaseModel):
    """
    Evidence supporting an impact claim.
    
    All evidence must trace back to deterministic repository intelligence.
    """
    source_type: Literal[
        "dependency_graph",
        "api_analysis",
        "workflow_analysis",
        "git_history",
        "semantic_search",
        "keyword_search",
        "hybrid_search"
    ] = Field(..., description="Source of evidence")
    
    # Location
    file_path: str = Field(..., description="File path")
    start_line: Optional[int] = Field(None, description="Starting line")
    end_line: Optional[int] = Field(None, description="Ending line")
    
    # Entity
    symbol_name: Optional[str] = Field(None, description="Symbol name")
    symbol_type: Optional[str] = Field(None, description="Symbol type")
    
    # Relationship
    relationship_type: str = Field(..., description="Type: calls, imports, contains, etc.")
    relationship_direction: Literal["outgoing", "incoming"] = Field(
        ...,
        description="Direction of relationship"
    )
    
    # Context
    excerpt: Optional[str] = Field(None, max_length=500, description="Code excerpt")
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_type": "dependency_graph",
                "file_path": "backend/controllers/order_controller.py",
                "start_line": 42,
                "end_line": 45,
                "symbol_name": "OrderController.create",
                "symbol_type": "method",
                "relationship_type": "calls",
                "relationship_direction": "incoming",
                "excerpt": "def create(self):\n    order = OrderService.create_order(...)"
            }
        }


class ImpactItem(BaseModel):
    """
    A single impact item representing an entity affected by the change.
    """
    # Impact classification
    impact_category: Literal[
        "direct_caller",
        "transitive_caller",
        "direct_callee",
        "transitive_callee",
        "dependent_file",
        "dependency_file",
        "api_endpoint",
        "workflow",
        "test",
        "historical_cochange"
    ] = Field(..., description="Category of impact")
    
    # Entity
    entity_type: Literal["symbol", "file", "api_endpoint"] = Field(
        ...,
        description="Type of impacted entity"
    )
    entity_id: UUID = Field(..., description="UUID of entity")
    entity_name: str = Field(..., description="Name or path")
    
    # Symbol-specific
    symbol_type: Optional[str] = Field(None, description="Symbol type")
    file_path: Optional[str] = Field(None, description="File path")
    
    # API-specific
    http_method: Optional[str] = Field(None, description="HTTP method")
    endpoint_path: Optional[str] = Field(None, description="Endpoint path")
    
    # Impact details
    depth: int = Field(..., ge=0, description="Distance from target (0=direct)")
    reason: str = Field(..., description="Human-readable impact reason")
    
    # Evidence
    evidence: List[ImpactEvidence] = Field(
        default_factory=list,
        description="Evidence supporting this impact"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "impact_category": "direct_caller",
                "entity_type": "symbol",
                "entity_id": "123e4567-e89b-12d3-a456-426614174001",
                "entity_name": "OrderController.create",
                "symbol_type": "method",
                "file_path": "backend/controllers/order_controller.py",
                "depth": 1,
                "reason": "Directly calls target method",
                "evidence": []
            }
        }


# ============================================================================
# IMPLEMENTATION PLANNING
# ============================================================================

class ImplementationStep(BaseModel):
    """
    A single step in the implementation plan.
    
    IMPORTANT: This is a recommendation for the developer.
    CodeTraceX does NOT execute these steps.
    """
    step_number: int = Field(..., ge=1, description="Step order")
    action: str = Field(..., description="Action to perform")
    
    # Target files/symbols
    target_files: List[str] = Field(
        default_factory=list,
        description="Files to modify"
    )
    target_symbols: List[str] = Field(
        default_factory=list,
        description="Symbols to modify"
    )
    
    # Reasoning
    reason: str = Field(..., description="Why this step is necessary")
    evidence_references: List[str] = Field(
        default_factory=list,
        description="References to evidence supporting this step"
    )
    
    # Dependencies
    depends_on_steps: List[int] = Field(
        default_factory=list,
        description="Step numbers this step depends on"
    )
    
    # Risk
    risk_level: Literal["low", "medium", "high", "unknown"] = Field(
        "medium",
        description="Risk level of this change"
    )
    uncertainty_note: Optional[str] = Field(
        None,
        description="Note about uncertainties or assumptions"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "step_number": 1,
                "action": "Update OrderService.create_order signature",
                "target_files": ["backend/services/order_service.py"],
                "target_symbols": ["OrderService.create_order"],
                "reason": "Add new parameter for customer notifications",
                "evidence_references": ["OrderService method signature found at line 42"],
                "depends_on_steps": [],
                "risk_level": "medium",
                "uncertainty_note": None
            }
        }


class ImplementationPlan(BaseModel):
    """
    A complete implementation plan for the requested change.
    
    The plan is generated by the LLM based on repository evidence
    and deterministic impact analysis.
    
    CRITICAL: CodeTraceX does NOT execute this plan.
    It is a recommendation for the developer.
    """
    summary: str = Field(..., description="High-level summary of the plan")
    
    steps: List[ImplementationStep] = Field(
        default_factory=list,
        description="Ordered list of implementation steps"
    )
    
    estimated_files_affected: int = Field(
        ...,
        ge=0,
        description="Estimated number of files to modify"
    )
    
    overall_risk: Literal["low", "medium", "high", "unknown"] = Field(
        "medium",
        description="Overall risk assessment"
    )
    
    assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions made during planning"
    )
    
    limitations: List[str] = Field(
        default_factory=list,
        description="Known limitations or uncertainties"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "summary": "Add customer notifications to order creation",
                "steps": [],
                "estimated_files_affected": 5,
                "overall_risk": "medium",
                "assumptions": ["Email service is available"],
                "limitations": ["Cannot determine runtime behavior"]
            }
        }


# ============================================================================
# IMPACT SUMMARY
# ============================================================================

class TruncationInfo(BaseModel):
    """
    Information about analysis truncation due to limits.
    """
    is_truncated: bool = Field(..., description="Whether results were truncated")
    truncation_reason: Optional[str] = Field(
        None,
        description="Reason: max_depth, max_nodes, max_edges"
    )
    nodes_analyzed: int = Field(..., ge=0, description="Number of nodes analyzed")
    edges_analyzed: int = Field(..., ge=0, description="Number of edges analyzed")
    max_nodes: int = Field(..., ge=0, description="Maximum nodes limit")
    max_edges: int = Field(..., ge=0, description="Maximum edges limit")


class ImpactSummary(BaseModel):
    """
    High-level summary of impact analysis results.
    """
    total_impacts: int = Field(..., ge=0, description="Total number of impacts")
    direct_impacts: int = Field(..., ge=0, description="Direct impacts")
    transitive_impacts: int = Field(..., ge=0, description="Transitive impacts")
    
    affected_files_count: int = Field(..., ge=0, description="Number of affected files")
    affected_symbols_count: int = Field(..., ge=0, description="Number of affected symbols")
    affected_endpoints_count: int = Field(..., ge=0, description="Number of affected API endpoints")
    
    max_depth_reached: int = Field(..., ge=0, description="Maximum depth reached")
    
    has_api_impact: bool = Field(False, description="Whether APIs are impacted")
    has_workflow_impact: bool = Field(False, description="Whether workflows are impacted")
    has_test_impact: bool = Field(False, description="Whether tests are impacted")


# ============================================================================
# IMPACT CITATION
# ============================================================================

class ImpactCitation(BaseModel):
    """
    Citation linking impact analysis claims to repository evidence.
    
    Similar to Phase 12 Citation but specialized for impact analysis.
    """
    # Source
    source_type: Literal[
        "graph_analysis",
        "api_analysis",
        "workflow_analysis",
        "git_history",
        "code_search"
    ] = Field(..., description="Source of citation")
    
    # Location
    file_path: str = Field(..., description="File path")
    start_line: Optional[int] = Field(None, ge=1, description="Starting line")
    end_line: Optional[int] = Field(None, ge=1, description="Ending line")
    
    # Context
    symbol_name: Optional[str] = Field(None, description="Symbol name if applicable")
    claim: str = Field(..., description="Specific claim being cited")
    
    # Evidence
    excerpt: Optional[str] = Field(None, max_length=500, description="Code excerpt")


# ============================================================================
# REQUEST / RESPONSE
# ============================================================================

class ImpactAnalysisRequest(BaseModel):
    """
    Request for impact analysis.
    
    The question is natural language describing the intended change.
    Target identification can be done automatically or explicitly provided.
    """
    # User input
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's question about change impact"
    )
    
    # Optional explicit target
    target_type: Optional[Literal["symbol", "file", "api_endpoint"]] = Field(
        None,
        description="Explicit target type"
    )
    target_id: Optional[str] = Field(None, description="Explicit target UUID")
    
    # Analysis configuration
    depth: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum traversal depth"
    )
    
    include_implementation_plan: bool = Field(
        True,
        description="Whether to generate implementation plan"
    )
    
    # Filtering
    analysis_run_id: Optional[str] = Field(
        None,
        description="Specific analysis run UUID"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What would be affected if I change OrderService.create_order?",
                "target_type": None,
                "target_id": None,
                "depth": 3,
                "include_implementation_plan": True,
                "analysis_run_id": None
            }
        }


class ImpactAnalysisResponse(BaseModel):
    """
    Complete impact analysis response.
    
    Contains deterministic impact analysis, LLM-generated explanations,
    implementation plan, and supporting evidence.
    """
    # Status
    status: Literal["success", "ambiguous_target", "target_not_found", "insufficient_evidence"] = Field(
        ...,
        description="Analysis status"
    )
    
    # Question
    question: str = Field(..., description="Original question")
    
    # Target
    target: Optional[ImpactTarget] = Field(None, description="Identified target")
    target_identification: Optional[TargetIdentificationResult] = Field(
        None,
        description="Target identification details if ambiguous"
    )
    
    # Summary
    summary: Optional[ImpactSummary] = Field(None, description="Impact summary")
    
    # Impacts
    impacts: List[ImpactItem] = Field(
        default_factory=list,
        description="List of all impacts"
    )
    
    # Affected entities (deduplicated)
    affected_files: List[str] = Field(
        default_factory=list,
        description="List of affected file paths"
    )
    affected_endpoints: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of affected API endpoints"
    )
    
    # Workflow impact (if applicable)
    affected_workflows: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Affected workflows"
    )
    
    # Historical evidence (if applicable)
    historical_evidence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Git history evidence"
    )
    
    # LLM-generated content
    explanation: Optional[str] = Field(
        None,
        description="LLM explanation of impact"
    )
    implementation_plan: Optional[ImplementationPlan] = Field(
        None,
        description="LLM-generated implementation plan"
    )
    
    # Evidence and grounding
    citations: List[ImpactCitation] = Field(
        default_factory=list,
        description="Citations supporting claims"
    )
    
    confidence_note: Optional[str] = Field(
        None,
        description="Note about confidence or limitations"
    )
    
    # Metadata
    truncation: Optional[TruncationInfo] = Field(None, description="Truncation information")
    analysis_run_id: Optional[UUID] = Field(None, description="Analysis run used")
    repository_id: UUID = Field(..., description="Repository analyzed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "question": "What would be affected if I change OrderService.create_order?",
                "target": None,
                "summary": None,
                "impacts": [],
                "affected_files": [],
                "affected_endpoints": [],
                "affected_workflows": [],
                "historical_evidence": [],
                "explanation": "Changing OrderService.create_order would impact...",
                "implementation_plan": None,
                "citations": [],
                "confidence_note": None,
                "truncation": None,
                "analysis_run_id": None,
                "repository_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
