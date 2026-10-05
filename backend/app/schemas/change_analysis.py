"""
Pydantic schemas for Phase 18: Pull Request & Change Intelligence.

This module defines request and response schemas for change analysis endpoints.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from enum import Enum


class ChangeInputType(str, Enum):
    """Type of change input."""
    PULL_REQUEST = "pull_request"
    COMMIT_RANGE = "commit_range"
    SINGLE_COMMIT = "single_commit"


class ChangeAnalysisRequest(BaseModel):
    """
    Request schema for change analysis.
    
    Supports three input modes:
    1. Pull request number
    2. Base SHA + head SHA
    3. Single commit SHA
    """
    # Pull request mode
    pull_request_number: Optional[int] = Field(
        None,
        description="GitHub pull request number",
        ge=1
    )
    
    # Commit range mode
    base_sha: Optional[str] = Field(
        None,
        description="Base commit SHA (for comparison)",
        min_length=7,
        max_length=40
    )
    head_sha: Optional[str] = Field(
        None,
        description="Head commit SHA (for comparison)",
        min_length=7,
        max_length=40
    )
    
    # Single commit mode
    commit_sha: Optional[str] = Field(
        None,
        description="Single commit SHA to analyze",
        min_length=7,
        max_length=40
    )
    
    # Analysis options
    max_depth: int = Field(
        3,
        description="Maximum dependency graph traversal depth",
        ge=1,
        le=10
    )
    include_tests: bool = Field(
        True,
        description="Include test file analysis"
    )
    include_workflows: bool = Field(
        True,
        description="Include workflow impact analysis"
    )
    
    @field_validator("pull_request_number", "base_sha", "head_sha", "commit_sha")
    @classmethod
    def validate_input_mode(cls, v, info):
        """Validate that exactly one input mode is provided."""
        # This validation happens per-field, so we'll do full validation in the endpoint
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "base_sha": "abc123def456",
                "head_sha": "789ghi012jkl",
                "max_depth": 3,
                "include_tests": True,
                "include_workflows": True
            }
        }


class ChangeType(str, Enum):
    """Type of file or symbol change."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    UNKNOWN = "unknown"


class ChangedFile(BaseModel):
    """Information about a changed file."""
    path: str = Field(..., description="File path")
    change_type: ChangeType = Field(..., description="Type of change")
    old_path: Optional[str] = Field(None, description="Original path (for renames)")
    additions: int = Field(0, description="Lines added", ge=0)
    deletions: int = Field(0, description="Lines deleted", ge=0)
    is_test: bool = Field(False, description="Whether this is a test file")
    is_source: bool = Field(False, description="Whether this is a source file")
    language: Optional[str] = Field(None, description="Programming language")
    
    class Config:
        json_schema_extra = {
            "example": {
                "path": "src/services/user_service.py",
                "change_type": "modified",
                "additions": 25,
                "deletions": 10,
                "is_test": False,
                "is_source": True,
                "language": "Python"
            }
        }


class ChangedSymbol(BaseModel):
    """Information about a changed symbol."""
    name: str = Field(..., description="Symbol name")
    qualified_name: str = Field(..., description="Fully qualified symbol name")
    symbol_type: str = Field(..., description="Symbol type (function, class, method)")
    change_type: ChangeType = Field(..., description="Type of change")
    file_path: str = Field(..., description="File containing the symbol")
    line_number: Optional[int] = Field(None, description="Line number in file", ge=1)
    is_public: bool = Field(True, description="Whether symbol is likely public API")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "create_user",
                "qualified_name": "services.user_service.create_user",
                "symbol_type": "function",
                "change_type": "modified",
                "file_path": "src/services/user_service.py",
                "line_number": 42,
                "is_public": True
            }
        }


class AffectedEndpoint(BaseModel):
    """Information about an affected API endpoint."""
    method: str = Field(..., description="HTTP method")
    route: str = Field(..., description="API route")
    handler: Optional[str] = Field(None, description="Handler function name")
    file_path: str = Field(..., description="File containing the endpoint")
    directly_affected: bool = Field(
        False,
        description="Whether the endpoint handler was directly changed"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "method": "POST",
                "route": "/api/users",
                "handler": "create_user",
                "file_path": "src/api/user_routes.py",
                "directly_affected": False
            }
        }


class AffectedWorkflow(BaseModel):
    """Information about an affected workflow."""
    entry_point: str = Field(..., description="Workflow entry point")
    entry_type: str = Field(..., description="Entry point type (endpoint/symbol)")
    changed_nodes: List[str] = Field(
        default_factory=list,
        description="Nodes in workflow that were changed"
    )
    total_nodes: int = Field(0, description="Total nodes in workflow", ge=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "entry_point": "POST /api/users",
                "entry_type": "endpoint",
                "changed_nodes": ["create_user", "validate_email"],
                "total_nodes": 8
            }
        }


class DependencyImpact(BaseModel):
    """Information about dependency impact."""
    affected_callers: List[str] = Field(
        default_factory=list,
        description="Symbols that call changed code"
    )
    affected_callees: List[str] = Field(
        default_factory=list,
        description="Symbols called by changed code"
    )
    affected_files: List[str] = Field(
        default_factory=list,
        description="Files that depend on changed files"
    )
    truncated: bool = Field(False, description="Whether results were truncated")
    traversal_depth: int = Field(0, description="Actual traversal depth", ge=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "affected_callers": ["api.user_routes.create_user_endpoint"],
                "affected_callees": ["db.models.User.save"],
                "affected_files": ["api/user_routes.py", "tests/test_users.py"],
                "truncated": False,
                "traversal_depth": 3
            }
        }


class RelevantTest(BaseModel):
    """Information about a relevant test."""
    file_path: str = Field(..., description="Test file path")
    test_name: Optional[str] = Field(None, description="Specific test function name")
    relationship: str = Field(
        ...,
        description="Relationship to change (directly_tests/imports_changed/path_related)"
    )
    confidence: str = Field(
        ...,
        description="Confidence level (high/medium/low)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "tests/test_user_service.py",
                "test_name": "test_create_user",
                "relationship": "directly_tests",
                "confidence": "high"
            }
        }


class RiskSignal(BaseModel):
    """Individual risk signal."""
    signal_type: str = Field(..., description="Type of risk signal")
    severity: str = Field(..., description="Severity (low/medium/high/critical)")
    description: str = Field(..., description="Human-readable description")
    evidence: List[str] = Field(
        default_factory=list,
        description="Supporting evidence"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "signal_type": "public_api_change",
                "severity": "high",
                "description": "Public API endpoint handler modified",
                "evidence": ["POST /api/users handler changed"]
            }
        }


class ChangeRisk(BaseModel):
    """Risk assessment for the change."""
    risk_level: str = Field(..., description="Overall risk level (low/medium/high/critical)")
    risk_score: int = Field(..., description="Numeric risk score (0-100)", ge=0, le=100)
    signals: List[RiskSignal] = Field(
        default_factory=list,
        description="Individual risk signals"
    )
    explanation: str = Field(
        "",
        description="Risk explanation summary"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "risk_level": "medium",
                "risk_score": 65,
                "signals": [],
                "explanation": "Moderate risk due to API changes affecting multiple workflows"
            }
        }


class ChangeEvidence(BaseModel):
    """Evidence item for change analysis."""
    evidence_type: str = Field(..., description="Type of evidence")
    description: str = Field(..., description="Evidence description")
    reference: Optional[Dict[str, Any]] = Field(
        None,
        description="Reference to repository entity (file/symbol/endpoint/etc)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "evidence_type": "file_change",
                "description": "Modified src/services/user_service.py (+25, -10)",
                "reference": {"file_path": "src/services/user_service.py"}
            }
        }


class PRMetadata(BaseModel):
    """Pull request metadata (optional)."""
    number: int = Field(..., description="PR number", ge=1)
    title: str = Field(..., description="PR title")
    body: str = Field("", description="PR description/body")
    author: str = Field(..., description="PR author username")
    state: str = Field(..., description="PR state (open/closed)")
    merged: bool = Field(False, description="Whether PR is merged")
    base_ref: str = Field(..., description="Base branch name")
    head_ref: str = Field(..., description="Head branch name")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "number": 123,
                "title": "Add user authentication",
                "body": "Implements JWT-based authentication for API endpoints",
                "author": "developer",
                "state": "open",
                "merged": False,
                "base_ref": "main",
                "head_ref": "feature/auth",
                "created_at": "2026-10-01T10:00:00Z"
            }
        }


class ChangeSummaryMetadata(BaseModel):
    """Metadata about the change analysis."""
    input_type: ChangeInputType = Field(..., description="Type of input provided")
    base_sha: str = Field(..., description="Base commit SHA")
    head_sha: str = Field(..., description="Head commit SHA")
    files_changed: int = Field(0, description="Total files changed", ge=0)
    symbols_changed: int = Field(0, description="Total symbols changed", ge=0)
    insertions: int = Field(0, description="Total line insertions", ge=0)
    deletions: int = Field(0, description="Total line deletions", ge=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "input_type": "commit_range",
                "base_sha": "abc123def456",
                "head_sha": "789ghi012jkl",
                "files_changed": 8,
                "symbols_changed": 15,
                "insertions": 120,
                "deletions": 42
            }
        }


class ChangeAnalysisResponse(BaseModel):
    """
    Complete response for change analysis.
    
    Contains deterministic change analysis combined with
    LLM-generated explanations and reasoning.
    """
    # Change metadata
    metadata: ChangeSummaryMetadata = Field(..., description="Change metadata")
    pr_metadata: Optional[PRMetadata] = Field(None, description="PR metadata (if applicable)")
    
    # Deterministic analysis
    files: List[ChangedFile] = Field(
        default_factory=list,
        description="Changed files"
    )
    symbols: List[ChangedSymbol] = Field(
        default_factory=list,
        description="Changed symbols"
    )
    affected_apis: List[AffectedEndpoint] = Field(
        default_factory=list,
        description="Affected API endpoints"
    )
    affected_workflows: List[AffectedWorkflow] = Field(
        default_factory=list,
        description="Affected workflows"
    )
    dependency_impact: DependencyImpact = Field(
        ...,
        description="Dependency and impact analysis"
    )
    relevant_tests: List[RelevantTest] = Field(
        default_factory=list,
        description="Potentially relevant tests"
    )
    risk: ChangeRisk = Field(..., description="Risk assessment")
    
    # Evidence
    evidence: List[ChangeEvidence] = Field(
        default_factory=list,
        description="Supporting evidence for analysis"
    )
    
    # LLM-generated content (grounded)
    summary: str = Field("", description="High-level change summary")
    technical_changes: str = Field("", description="Technical changes explanation")
    reviewer_attention: str = Field("", description="Points requiring reviewer attention")
    testing_considerations: str = Field("", description="Testing considerations")
    potential_impact: str = Field("", description="Potential impact explanation")
    uncertainty: str = Field("", description="Areas of uncertainty or insufficient evidence")
    
    class Config:
        json_schema_extra = {
            "example": {
                "metadata": {
                    "input_type": "commit_range",
                    "base_sha": "abc123",
                    "head_sha": "789ghi",
                    "files_changed": 3,
                    "symbols_changed": 5,
                    "insertions": 50,
                    "deletions": 20
                },
                "files": [],
                "symbols": [],
                "affected_apis": [],
                "affected_workflows": [],
                "dependency_impact": {
                    "affected_callers": [],
                    "affected_callees": [],
                    "affected_files": [],
                    "truncated": False,
                    "traversal_depth": 2
                },
                "relevant_tests": [],
                "risk": {
                    "risk_level": "medium",
                    "risk_score": 50,
                    "signals": []
                },
                "evidence": [],
                "summary": "Modified user authentication logic",
                "technical_changes": "Updated JWT token validation",
                "reviewer_attention": "Check token expiration handling",
                "testing_considerations": "Review authentication test coverage",
                "potential_impact": "May affect all authenticated endpoints",
                "uncertainty": "Unable to determine runtime token refresh behavior"
            }
        }


class InsufficientEvidenceResponse(BaseModel):
    """Response when there is insufficient evidence for analysis."""
    insufficient_evidence: bool = Field(True, description="Insufficient evidence flag")
    reason: str = Field(..., description="Reason for insufficient evidence")
    metadata: Optional[ChangeSummaryMetadata] = Field(
        None,
        description="Partial metadata if available"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "insufficient_evidence": True,
                "reason": "No repository analysis found. Please analyze the repository first.",
                "metadata": None
            }
        }
