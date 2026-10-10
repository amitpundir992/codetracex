"""
API endpoints for Phase 19: CI & Test Intelligence.

This module provides REST API endpoints for test coverage analysis,
CI recommendations, and test intelligence explanations.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Repository, AnalysisRun, Commit
from app.schemas.test_intelligence import (
    TestIntelligenceRequest,
    TestIntelligenceResponse,
    TestExplainRequest,
    TestExplainResponse
)
from app.services.change_detection_service import ChangeDetectionService
from app.services.symbol_change_analyzer import SymbolChangeAnalyzer
from app.services.test_recommendation_service import TestRecommendationService
from app.services.test_intelligence_explainer import TestIntelligenceExplainer
from app.services.llm.gemini_provider import GeminiProvider
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()


def _get_test_intelligence_explainer() -> Optional[TestIntelligenceExplainer]:
    """
    Get test intelligence explainer if LLM is configured.
    
    Returns:
        TestIntelligenceExplainer instance or None if not configured
    """
    try:
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not configured; LLM explanations disabled")
            return None
        
        provider = GeminiProvider(api_key=settings.GEMINI_API_KEY)
        return TestIntelligenceExplainer(llm_provider=provider)
    except Exception as e:
        logger.warning(f"Failed to initialize test intelligence explainer: {e}")
        return None


@router.post(
    "/repositories/{repository_id}/test-intelligence",
    response_model=TestIntelligenceResponse,
    summary="Analyze test intelligence for changes",
    description="""
Analyze test coverage and CI recommendations for code changes between commits.

This endpoint provides:
- Tests affected by changes (deterministic)
- Uncovered areas (gaps in test coverage)
- CI workflows that will run tests
- Local test recommendations

**Input:**
- Base commit SHA
- Head commit SHA
- Optional: Include CI analysis
- Optional: Include local recommendations

**Output:**
- Deterministic test coverage mapping
- CI job analysis
- Local test recommendations
- Evidence for findings

**Requirements:**
- Repository must exist and be analyzed
- Commits must exist in database
- Tests will be detected from repository structure

**Note:** This is deterministic analysis without LLM explanation.
For human-readable explanations, use POST /repositories/{repository_id}/test-intelligence/explain
"""
)
async def analyze_test_intelligence(
    repository_id: UUID,
    request: TestIntelligenceRequest,
    db: Session = Depends(get_db)
) -> TestIntelligenceResponse:
    """
    Analyze test intelligence for changes.
    
    Args:
        repository_id: Repository UUID
        request: Test intelligence request
        db: Database session
        
    Returns:
        Test intelligence response with deterministic analysis
        
    Raises:
        HTTPException: If repository not found or commits invalid
    """
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Get latest analysis run
    latest_analysis = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.repository_id == repository_id)
        .order_by(AnalysisRun.started_at.desc())
        .first()
    )
    
    if not latest_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis run found for repository {repository_id}. Analyze the repository first."
        )
    
    # Validate commits exist
    base_commit = (
        db.query(Commit)
        .filter(
            Commit.repository_id == repository_id,
            Commit.sha.startswith(request.base_sha)
        )
        .first()
    )
    
    if not base_commit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Base commit {request.base_sha} not found in repository"
        )
    
    head_commit = (
        db.query(Commit)
        .filter(
            Commit.repository_id == repository_id,
            Commit.sha.startswith(request.head_sha)
        )
        .first()
    )
    
    if not head_commit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Head commit {request.head_sha} not found in repository"
        )
    
    try:
        # Detect changes
        change_service = ChangeDetectionService(db)
        changed_files = change_service.detect_changes_between_commits(
            repository_id=repository_id,
            base_sha=base_commit.sha,
            head_sha=head_commit.sha
        )
        
        # Analyze symbol changes
        symbol_analyzer = SymbolChangeAnalyzer(db)
        changed_symbols = symbol_analyzer.analyze_symbol_changes(
            repository_id=repository_id,
            changed_files=changed_files,
            analysis_run_id=latest_analysis.id
        )
        
        # Analyze test intelligence
        test_service = TestRecommendationService(db)
        test_intelligence = test_service.analyze_test_intelligence(
            repository_id=repository_id,
            base_sha=base_commit.sha,
            head_sha=head_commit.sha,
            changed_files=changed_files,
            changed_symbols=changed_symbols,
            include_ci_analysis=request.include_ci_analysis,
            include_local_recommendations=request.include_local_recommendations,
            analysis_run_id=latest_analysis.id
        )
        
        logger.info(
            f"Test intelligence analysis completed for {repository_id}: "
            f"{len(test_intelligence.affected_tests)} affected tests, "
            f"{len(test_intelligence.uncovered_areas)} uncovered areas"
        )
        
        return test_intelligence
    
    except Exception as e:
        logger.error(f"Error analyzing test intelligence: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze test intelligence: {str(e)}"
        )


@router.post(
    "/repositories/{repository_id}/test-intelligence/explain",
    response_model=TestExplainResponse,
    summary="Generate LLM explanation of test intelligence",
    description="""
Generate human-readable explanations of test intelligence findings using LLM.

This endpoint provides:
- Test impact summary
- Explanation of why tests are affected
- Coverage gap analysis
- CI recommendations
- Local testing guidance
- Reviewer focus areas

**Input:**
- Test intelligence data (from test-intelligence endpoint)
- Changed file paths for context
- Optional: Focus area for explanation

**Output:**
- Grounded LLM explanations
- Human-readable recommendations
- Uncertainty indicators

**Requirements:**
- GEMINI_API_KEY must be configured
- Test intelligence data must be provided

**Note:** Explanations are grounded in the provided evidence.
The LLM will not invent tests, CI jobs, or commands.
"""
)
async def explain_test_intelligence(
    repository_id: UUID,
    request: TestExplainRequest,
    db: Session = Depends(get_db)
) -> TestExplainResponse:
    """
    Generate LLM explanation of test intelligence.
    
    Args:
        repository_id: Repository UUID
        request: Test explain request with test intelligence data
        db: Database session
        
    Returns:
        Test explanation response with LLM-generated explanations
        
    Raises:
        HTTPException: If LLM not configured or generation fails
    """
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Get explainer
    explainer = _get_test_intelligence_explainer()
    if not explainer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service not configured. Set GEMINI_API_KEY to enable explanations."
        )
    
    try:
        # Generate explanation
        explanation = explainer.explain_test_intelligence(
            test_intelligence=request.test_intelligence,
            changed_files=request.changed_files,
            focus_area=request.focus_area
        )
        
        logger.info(f"Generated test intelligence explanation for repository {repository_id}")
        
        return explanation
    
    except Exception as e:
        logger.error(f"Error generating test intelligence explanation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate explanation: {str(e)}"
        )


@router.get(
    "/repositories/{repository_id}/test-files",
    summary="List all test files in repository",
    description="""
List all test files detected in the repository.

This endpoint provides:
- Test file paths
- Detected test frameworks
- Test counts per file
- Import relationships

**Requirements:**
- Repository must exist and be analyzed

**Note:** This is a utility endpoint for exploring test structure.
"""
)
async def list_test_files(
    repository_id: UUID,
    db: Session = Depends(get_db)
):
    """
    List all test files in repository.
    
    Args:
        repository_id: Repository UUID
        db: Database session
        
    Returns:
        List of test files
        
    Raises:
        HTTPException: If repository not found or not analyzed
    """
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Get latest analysis run
    latest_analysis = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.repository_id == repository_id)
        .order_by(AnalysisRun.started_at.desc())
        .first()
    )
    
    if not latest_analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis run found for repository {repository_id}"
        )
    
    try:
        from app.services.test_detection_service import TestDetectionService
        
        test_service = TestDetectionService(db)
        test_files = test_service.get_test_files(
            repository_id=repository_id,
            analysis_run_id=latest_analysis.id
        )
        
        return {
            "repository_id": str(repository_id),
            "total_test_files": len(test_files),
            "test_files": [tf.dict() for tf in test_files]
        }
    
    except Exception as e:
        logger.error(f"Error listing test files: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list test files: {str(e)}"
        )
