"""
Pydantic schemas for Phase 20: Test Results & Failure Intelligence API.

This module defines request/response schemas for:
- Test result import
- Test run listing
- Test failure retrieval
- Failure explanation
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from decimal import Decimal


# Test result import schemas

class TestResultImportRequest(BaseModel):
    """Request to import test results."""
    report_content: str = Field(
        ...,
        description="Raw test report content (XML or JSON)",
        min_length=1
    )
    format_hint: str = Field(
        'auto',
        description="Format hint: auto, junit_xml, normalized_json"
    )
    commit_sha: Optional[str] = Field(
        None,
        description="Optional commit SHA this run was executed against",
        min_length=7,
        max_length=40
    )
    analysis_run_id: Optional[UUID] = Field(
        None,
        description="Optional analysis run ID to associate with"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "report_content": "<testsuites>...</testsuites>",
                "format_hint": "junit_xml",
                "commit_sha": "abc123def456"
            }
        }


class TestResultImportResponse(BaseModel):
    """Response after importing test results."""
    test_run_id: UUID = Field(..., description="Imported test run UUID")
    repository_id: UUID = Field(..., description="Repository UUID")
    status: str = Field(..., description="Import status")
    total_tests: int = Field(..., description="Total test cases", ge=0)
    passed_tests: int = Field(..., description="Passed tests", ge=0)
    failed_tests: int = Field(..., description="Failed tests", ge=0)
    skipped_tests: int = Field(..., description="Skipped tests", ge=0)
    error_tests: int = Field(..., description="Error tests", ge=0)
    source_format: str = Field(..., description="Detected format")
    was_duplicate: bool = Field(
        False,
        description="Whether this was a duplicate import"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_run_id": "550e8400-e29b-41d4-a716-446655440000",
                "repository_id": "550e8400-e29b-41d4-a716-446655440001",
                "status": "completed",
                "total_tests": 100,
                "passed_tests": 95,
                "failed_tests": 5,
                "skipped_tests": 0,
                "error_tests": 0,
                "source_format": "junit_xml",
                "was_duplicate": False
            }
        }


# Test run listing schemas

class TestRunSummary(BaseModel):
    """Summary of a test run."""
    id: UUID
    repository_id: UUID
    commit_sha: Optional[str]
    source_format: str
    status: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    total_duration_ms: Optional[int]
    imported_at: datetime
    
    class Config:
        from_attributes = True


class TestRunListResponse(BaseModel):
    """Response with list of test runs."""
    repository_id: UUID
    total_count: int = Field(..., ge=0)
    limit: int
    offset: int
    test_runs: List[TestRunSummary]
    
    class Config:
        json_schema_extra = {
            "example": {
                "repository_id": "550e8400-e29b-41d4-a716-446655440001",
                "total_count": 25,
                "limit": 10,
                "offset": 0,
                "test_runs": []
            }
        }


# Test case schemas

class TestCaseDetail(BaseModel):
    """Detailed test case information."""
    id: UUID
    suite_name: str
    test_name: str
    class_name: Optional[str]
    full_name: str
    outcome: str
    duration_ms: Optional[int]
    failure_message: Optional[str]
    failure_type: Optional[str]
    failure_stacktrace: Optional[str]
    failure_classification: Optional[str]
    classification_confidence: Optional[Decimal]
    classification_evidence: Optional[str]
    
    class Config:
        from_attributes = True


class TestRunDetailResponse(BaseModel):
    """Detailed test run with test cases."""
    id: UUID
    repository_id: UUID
    commit_sha: Optional[str]
    analysis_run_id: Optional[UUID]
    source_format: str
    status: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    total_duration_ms: Optional[int]
    imported_at: datetime
    processed_at: Optional[datetime]
    test_cases: List[TestCaseDetail] = Field(
        default_factory=list,
        description="Test cases (limited to 100)"
    )
    
    class Config:
        from_attributes = True


# Failure analysis schemas

class FailureCorrelationSchema(BaseModel):
    """Correlation between failure and code changes."""
    test_case_id: UUID
    test_name: str
    correlation_type: str = Field(
        ...,
        description="Type: direct_import, module_sibling, etc."
    )
    confidence: str = Field(..., description="Confidence: high, medium, low")
    changed_files: List[str]
    changed_symbols: List[str]
    evidence: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_case_id": "550e8400-e29b-41d4-a716-446655440002",
                "test_name": "tests.test_user.TestUser.test_create_user",
                "correlation_type": "direct_import",
                "confidence": "high",
                "changed_files": ["services/user_service.py"],
                "changed_symbols": ["services/user_service.py::create_user"],
                "evidence": ["Test imports create_user which was modified"]
            }
        }


class HistoricalTrendSchema(BaseModel):
    """Historical trend for a test."""
    test_name: str
    trend_type: str = Field(
        ...,
        description="Type: repeated_failure, regression, fixed, potentially_flaky, duration_increase"
    )
    description: str
    runs_analyzed: int = Field(..., ge=0)
    evidence: List[str]
    confidence: str = Field(..., description="Confidence: high, medium, low")
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_name": "tests.test_user.test_create_user",
                "trend_type": "repeated_failure",
                "description": "Test failed in 3 of last 5 runs",
                "runs_analyzed": 5,
                "evidence": ["Failed in current run and 2 historical runs"],
                "confidence": "high"
            }
        }


class TestFailuresResponse(BaseModel):
    """Response with test failures and analysis."""
    test_run_id: UUID
    repository_id: UUID
    total_failures: int = Field(..., ge=0)
    failed_tests: List[TestCaseDetail]
    correlations: List[FailureCorrelationSchema] = Field(
        default_factory=list,
        description="Code change correlations (if commit associated)"
    )
    trends: List[HistoricalTrendSchema] = Field(
        default_factory=list,
        description="Historical trends"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_run_id": "550e8400-e29b-41d4-a716-446655440000",
                "repository_id": "550e8400-e29b-41d4-a716-446655440001",
                "total_failures": 5,
                "failed_tests": [],
                "correlations": [],
                "trends": []
            }
        }


# Failure explanation schemas

class FailureExplainRequest(BaseModel):
    """Request to explain a test failure."""
    test_case_id: UUID = Field(..., description="Test case UUID to explain")
    include_correlations: bool = Field(
        True,
        description="Include code change correlations"
    )
    include_trends: bool = Field(
        True,
        description="Include historical trends"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_case_id": "550e8400-e29b-41d4-a716-446655440002",
                "include_correlations": True,
                "include_trends": True
            }
        }


class FailureExplainResponse(BaseModel):
    """LLM-generated explanation of test failure."""
    test_name: str
    failure_summary: str = Field(
        ...,
        description="Brief summary of what happened"
    )
    potential_causes: str = Field(
        ...,
        description="Possible causes based on evidence"
    )
    investigation_steps: str = Field(
        ...,
        description="What to investigate next"
    )
    related_changes: str = Field(
        ...,
        description="How code changes might relate"
    )
    uncertainty: str = Field(
        ...,
        description="What is unclear or unknown"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_name": "tests.test_user.test_create_user",
                "failure_summary": "Test failed with assertion error",
                "potential_causes": "Based on correlation evidence...",
                "investigation_steps": "1. Check user_service.py changes\n2. Review test assertions",
                "related_changes": "Test imports create_user which was modified",
                "uncertainty": "Unable to determine exact cause without source code inspection"
            }
        }
