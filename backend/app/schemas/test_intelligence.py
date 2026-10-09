"""
Pydantic schemas for Phase 19: CI & Test Intelligence.

This module defines schemas for test detection, test coverage analysis,
CI workflow intelligence, and test recommendations.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class TestFramework(str, Enum):
    """Detected test framework."""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    MOCHA = "mocha"
    VITEST = "vitest"
    JUNIT = "junit"
    TESTNG = "testng"
    RSPEC = "rspec"
    GO_TEST = "go_test"
    CARGO_TEST = "cargo_test"
    UNKNOWN = "unknown"


class TestType(str, Enum):
    """Type of test."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    FUNCTIONAL = "functional"
    UNKNOWN = "unknown"


class TestCase(BaseModel):
    """Individual test case within a test file."""
    name: str = Field(..., description="Test function/method name")
    line_number: Optional[int] = Field(None, description="Line number in file", ge=1)
    test_type: TestType = Field(TestType.UNKNOWN, description="Type of test")
    imports_symbols: List[str] = Field(
        default_factory=list,
        description="Symbols imported by this test"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "test_create_user",
                "line_number": 42,
                "test_type": "unit",
                "imports_symbols": ["create_user", "User"]
            }
        }


class TestFile(BaseModel):
    """Information about a test file."""
    file_path: str = Field(..., description="Test file path")
    language: Optional[str] = Field(None, description="Programming language")
    framework: TestFramework = Field(
        TestFramework.UNKNOWN,
        description="Detected test framework"
    )
    test_count: int = Field(0, description="Number of tests in file", ge=0)
    test_cases: List[TestCase] = Field(
        default_factory=list,
        description="Individual test cases"
    )
    imports_from: List[str] = Field(
        default_factory=list,
        description="Source modules/files imported"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "tests/test_user_service.py",
                "language": "Python",
                "framework": "pytest",
                "test_count": 5,
                "test_cases": [],
                "imports_from": ["services.user_service", "models.user"]
            }
        }


class TestCoverageType(str, Enum):
    """Type of test coverage relationship."""
    DIRECT_IMPORT = "direct_import"  # Test imports changed symbol
    INDIRECT_IMPORT = "indirect_import"  # Test imports module containing changed symbol
    MODULE_SIBLING = "module_sibling"  # Test in same module structure
    API_CONSUMER = "api_consumer"  # Test calls changed API endpoint
    WORKFLOW_RELATED = "workflow_related"  # Test exercises workflow containing change
    PATH_PATTERN = "path_pattern"  # Test follows naming convention for changed file


class AffectedTest(BaseModel):
    """Test that may be affected by changes."""
    test_file: str = Field(..., description="Test file path")
    test_name: Optional[str] = Field(None, description="Specific test function/method")
    coverage_type: TestCoverageType = Field(
        ...,
        description="How this test relates to changes"
    )
    confidence: str = Field(
        ...,
        description="Confidence level (high/medium/low)"
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="Evidence for why this test is affected"
    )
    changed_symbols: List[str] = Field(
        default_factory=list,
        description="Changed symbols relevant to this test"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_file": "tests/test_user_service.py",
                "test_name": "test_create_user",
                "coverage_type": "direct_import",
                "confidence": "high",
                "evidence": [
                    "Test imports create_user which was modified",
                    "Test directly calls create_user function"
                ],
                "changed_symbols": ["create_user"]
            }
        }


class UncoveredArea(BaseModel):
    """Area of change with no obvious test coverage."""
    file_path: str = Field(..., description="Changed file path")
    changed_symbols: List[str] = Field(
        default_factory=list,
        description="Changed symbols without obvious tests"
    )
    severity: str = Field(
        ...,
        description="Severity (low/medium/high)"
    )
    explanation: str = Field(
        ...,
        description="Why this appears uncovered"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "src/services/payment_service.py",
                "changed_symbols": ["process_payment", "validate_card"],
                "severity": "high",
                "explanation": "No test files found that import these changed functions"
            }
        }


class CIJob(BaseModel):
    """CI job that runs tests."""
    workflow_file: str = Field(..., description="Workflow YAML file path")
    job_name: str = Field(..., description="Job name in workflow")
    runs_tests: bool = Field(False, description="Whether job executes tests")
    test_commands: List[str] = Field(
        default_factory=list,
        description="Test commands executed"
    )
    triggers_on: List[str] = Field(
        default_factory=list,
        description="Trigger conditions (push/pull_request/paths)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_file": ".github/workflows/ci.yml",
                "job_name": "test",
                "runs_tests": True,
                "test_commands": ["pytest tests/", "npm test"],
                "triggers_on": ["push", "pull_request"]
            }
        }


class RelevantCICheck(BaseModel):
    """CI check relevant to changes."""
    workflow_file: str = Field(..., description="Workflow file path")
    job_name: str = Field(..., description="Job name")
    relevance: str = Field(
        ...,
        description="Why this check is relevant"
    )
    confidence: str = Field(
        ...,
        description="Confidence level (high/medium/low)"
    )
    runs_affected_tests: bool = Field(
        False,
        description="Whether job runs affected tests"
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="Evidence for relevance"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_file": ".github/workflows/ci.yml",
                "job_name": "backend-tests",
                "relevance": "Runs pytest on changed Python files",
                "confidence": "high",
                "runs_affected_tests": True,
                "evidence": [
                    "Job runs 'pytest tests/'",
                    "Triggered on Python file changes"
                ]
            }
        }


class LocalTestRecommendation(BaseModel):
    """Recommendation for local testing before PR."""
    command: str = Field(..., description="Test command to run")
    reason: str = Field(..., description="Why run this command")
    priority: str = Field(
        ...,
        description="Priority (high/medium/low)"
    )
    test_files: List[str] = Field(
        default_factory=list,
        description="Specific test files covered"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "command": "pytest tests/test_user_service.py -v",
                "reason": "Tests functions directly modified in user_service.py",
                "priority": "high",
                "test_files": ["tests/test_user_service.py"]
            }
        }


class TestIntelligenceRequest(BaseModel):
    """Request for test intelligence analysis."""
    base_sha: str = Field(
        ...,
        description="Base commit SHA",
        min_length=7,
        max_length=40
    )
    head_sha: str = Field(
        ...,
        description="Head commit SHA",
        min_length=7,
        max_length=40
    )
    include_ci_analysis: bool = Field(
        True,
        description="Include CI workflow analysis"
    )
    include_local_recommendations: bool = Field(
        True,
        description="Include local testing recommendations"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "base_sha": "abc123def456",
                "head_sha": "789ghi012jkl",
                "include_ci_analysis": True,
                "include_local_recommendations": True
            }
        }


class TestIntelligenceResponse(BaseModel):
    """
    Complete test intelligence analysis.
    
    Provides deterministic test coverage mapping,
    CI relevance analysis, and test recommendations.
    """
    # Metadata
    base_sha: str = Field(..., description="Base commit SHA")
    head_sha: str = Field(..., description="Head commit SHA")
    
    # Test detection
    total_test_files: int = Field(
        0,
        description="Total test files in repository",
        ge=0
    )
    affected_tests: List[AffectedTest] = Field(
        default_factory=list,
        description="Tests likely affected by changes"
    )
    uncovered_areas: List[UncoveredArea] = Field(
        default_factory=list,
        description="Changed areas without obvious test coverage"
    )
    
    # CI analysis
    ci_jobs: List[CIJob] = Field(
        default_factory=list,
        description="CI jobs that run tests"
    )
    relevant_ci_checks: List[RelevantCICheck] = Field(
        default_factory=list,
        description="CI checks relevant to changes"
    )
    
    # Recommendations
    local_test_recommendations: List[LocalTestRecommendation] = Field(
        default_factory=list,
        description="Tests to run locally before PR"
    )
    
    # Evidence
    evidence: List[str] = Field(
        default_factory=list,
        description="Evidence for test intelligence findings"
    )
    
    # Summary
    summary: str = Field(
        "",
        description="High-level test impact summary"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "base_sha": "abc123",
                "head_sha": "789ghi",
                "total_test_files": 24,
                "affected_tests": [],
                "uncovered_areas": [],
                "ci_jobs": [],
                "relevant_ci_checks": [],
                "local_test_recommendations": [],
                "evidence": [],
                "summary": "5 tests directly affected, 2 uncovered areas identified"
            }
        }


class TestExplainRequest(BaseModel):
    """Request for LLM explanation of test intelligence."""
    test_intelligence: TestIntelligenceResponse = Field(
        ...,
        description="Test intelligence data to explain"
    )
    changed_files: List[str] = Field(
        default_factory=list,
        description="List of changed file paths for context"
    )
    focus_area: Optional[str] = Field(
        None,
        description="Specific area to focus explanation on"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_intelligence": {},
                "changed_files": ["src/services/user_service.py"],
                "focus_area": "uncovered_areas"
            }
        }


class TestExplainResponse(BaseModel):
    """LLM-generated explanation of test intelligence."""
    test_impact_summary: str = Field(
        "",
        description="Summary of test impact"
    )
    affected_tests_explanation: str = Field(
        "",
        description="Explanation of why tests are affected"
    )
    coverage_gaps_explanation: str = Field(
        "",
        description="Explanation of coverage gaps"
    )
    ci_recommendations: str = Field(
        "",
        description="CI-specific recommendations"
    )
    local_testing_guidance: str = Field(
        "",
        description="Guidance for local testing"
    )
    reviewer_testing_focus: str = Field(
        "",
        description="What reviewers should focus on for testing"
    )
    uncertainty: str = Field(
        "",
        description="Areas where evidence is insufficient"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "test_impact_summary": "Changes to user_service.py affect 5 unit tests",
                "affected_tests_explanation": "Tests import and call modified functions",
                "coverage_gaps_explanation": "payment_service.py changes lack test coverage",
                "ci_recommendations": "CI will run affected tests automatically",
                "local_testing_guidance": "Run pytest tests/test_user_service.py",
                "reviewer_testing_focus": "Verify test coverage for payment flow",
                "uncertainty": "Unable to detect integration tests for payment API"
            }
        }
