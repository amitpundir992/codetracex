"""
API endpoints for Phase 20: Test Results & Failure Intelligence.

This module provides REST API endpoints for:
- Importing test results
- Listing test runs
- Retrieving test run details
- Analyzing test failures
- Generating failure explanations
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Repository, TestRun, TestCase, Commit
from app.schemas.test_results import (
    TestResultImportRequest,
    TestResultImportResponse,
    TestRunListResponse,
    TestRunSummary,
    TestRunDetailResponse,
    TestCaseDetail,
    TestFailuresResponse,
    FailureCorrelationSchema,
    HistoricalTrendSchema,
    FailureExplainRequest,
    FailureExplainResponse
)
from app.services.test_report_parser import parse_test_report
from app.services.test_result_persistence_service import TestResultPersistenceService
from app.services.test_failure_correlation_service import TestFailureCorrelationService
from app.services.test_historical_trends_service import HistoricalTrendsService
from app.services.test_failure_explainer_service import TestFailureExplainerService
from app.services.llm.gemini_provider import GeminiProvider
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()


@router.post(
    "/repositories/{repository_id}/test-results/import",
    response_model=TestResultImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import test results",
    description="""
Import test results from a report file.

Supports:
- JUnit XML (pytest-compatible)
- Normalized JSON format

Features:
- Idempotent import (same report won't be duplicated)
- Automatic failure classification
- Repository isolation
- Optional commit association

The report is parsed, validated, and stored with all test cases.
"""
)
async def import_test_results(
    repository_id: UUID,
    request: TestResultImportRequest,
    db: Session = Depends(get_db)
) -> TestResultImportResponse:
    """Import test results from report."""
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    try:
        # Parse report
        parsed_result = parse_test_report(
            content=request.report_content,
            format_hint=request.format_hint
        )
        
        # Persist to database
        persistence_service = TestResultPersistenceService(db)
        test_run = persistence_service.persist_test_result(
            repository_id=repository_id,
            parsed_result=parsed_result,
            commit_sha=request.commit_sha,
            analysis_run_id=request.analysis_run_id
        )
        
        # Check if was duplicate
        was_duplicate = (test_run.test_cases.__len__() == 0 if hasattr(test_run, 'test_cases') else False)
        
        # Get commit SHA if available
        commit_sha = None
        if test_run.commit_id:
            commit = db.query(Commit).filter(Commit.id == test_run.commit_id).first()
            if commit:
                commit_sha = commit.sha[:12]
        
        logger.info(
            f"Imported test run {test_run.id}: "
            f"{test_run.passed_tests}P/{test_run.failed_tests}F/"
            f"{test_run.skipped_tests}S/{test_run.error_tests}E"
        )
        
        return TestResultImportResponse(
            test_run_id=test_run.id,
            repository_id=repository_id,
            status=test_run.status.value,
            total_tests=test_run.total_tests,
            passed_tests=test_run.passed_tests,
            failed_tests=test_run.failed_tests,
            skipped_tests=test_run.skipped_tests,
            error_tests=test_run.error_tests,
            source_format=test_run.source_format,
            was_duplicate=was_duplicate
        )
    
    except ValueError as e:
        logger.warning(f"Invalid test report: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid test report: {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Failed to import test results: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import test results: {str(e)}"
        )


@router.get(
    "/repositories/{repository_id}/test-results",
    response_model=TestRunListResponse,
    summary="List test runs",
    description="""
List test runs for a repository.

Supports:
- Pagination (limit/offset)
- Optional commit SHA filter
- Ordered by import time (newest first)

Returns summary information for each test run.
"""
)
async def list_test_runs(
    repository_id: UUID,
    limit: int = 50,
    offset: int = 0,
    commit_sha: Optional[str] = None,
    db: Session = Depends(get_db)
) -> TestRunListResponse:
    """List test runs for a repository."""
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Validate pagination
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100"
        )
    
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Offset must be non-negative"
        )
    
    try:
        persistence_service = TestResultPersistenceService(db)
        
        # Get test runs
        test_runs = persistence_service.list_test_runs(
            repository_id=repository_id,
            limit=limit,
            offset=offset,
            commit_sha=commit_sha
        )
        
        # Get total count
        query = db.query(TestRun).filter(TestRun.repository_id == repository_id)
        if commit_sha:
            query = query.join(Commit, TestRun.commit_id == Commit.id).filter(
                Commit.sha.startswith(commit_sha)
            )
        total_count = query.count()
        
        # Build summaries
        summaries = []
        for test_run in test_runs:
            commit_sha_short = None
            if test_run.commit_id:
                commit = db.query(Commit).filter(Commit.id == test_run.commit_id).first()
                if commit:
                    commit_sha_short = commit.sha[:12]
            
            summaries.append(TestRunSummary(
                id=test_run.id,
                repository_id=test_run.repository_id,
                commit_sha=commit_sha_short,
                source_format=test_run.source_format,
                status=test_run.status.value,
                total_tests=test_run.total_tests,
                passed_tests=test_run.passed_tests,
                failed_tests=test_run.failed_tests,
                skipped_tests=test_run.skipped_tests,
                error_tests=test_run.error_tests,
                total_duration_ms=test_run.total_duration_ms,
                imported_at=test_run.imported_at
            ))
        
        return TestRunListResponse(
            repository_id=repository_id,
            total_count=total_count,
            limit=limit,
            offset=offset,
            test_runs=summaries
        )
    
    except Exception as e:
        logger.error(f"Failed to list test runs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list test runs: {str(e)}"
        )


@router.get(
    "/repositories/{repository_id}/test-results/{run_id}",
    response_model=TestRunDetailResponse,
    summary="Get test run details",
    description="""
Get detailed information about a test run.

Returns:
- Test run metadata
- Up to 100 test cases (for performance)
- Full test details including failures

For large test runs, use pagination or failure-only endpoints.
"""
)
async def get_test_run_detail(
    repository_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db)
) -> TestRunDetailResponse:
    """Get detailed test run information."""
    persistence_service = TestResultPersistenceService(db)
    
    # Get test run with repository isolation
    test_run = persistence_service.get_test_run(run_id, repository_id)
    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run {run_id} not found in repository {repository_id}"
        )
    
    try:
        # Get test cases (limited to 100)
        test_cases = (
            db.query(TestCase)
            .filter(TestCase.test_run_id == run_id)
            .limit(100)
            .all()
        )
        
        # Get commit SHA
        commit_sha_short = None
        if test_run.commit_id:
            commit = db.query(Commit).filter(Commit.id == test_run.commit_id).first()
            if commit:
                commit_sha_short = commit.sha[:12]
        
        # Build response
        test_case_details = [
            TestCaseDetail(
                id=tc.id,
                suite_name=tc.suite_name,
                test_name=tc.test_name,
                class_name=tc.class_name,
                full_name=tc.full_name,
                outcome=tc.outcome.value,
                duration_ms=tc.duration_ms,
                failure_message=tc.failure_message,
                failure_type=tc.failure_type,
                failure_stacktrace=tc.failure_stacktrace,
                failure_classification=tc.failure_classification.value if tc.failure_classification else None,
                classification_confidence=tc.classification_confidence,
                classification_evidence=tc.classification_evidence
            )
            for tc in test_cases
        ]
        
        return TestRunDetailResponse(
            id=test_run.id,
            repository_id=test_run.repository_id,
            commit_sha=commit_sha_short,
            analysis_run_id=test_run.analysis_run_id,
            source_format=test_run.source_format,
            status=test_run.status.value,
            total_tests=test_run.total_tests,
            passed_tests=test_run.passed_tests,
            failed_tests=test_run.failed_tests,
            skipped_tests=test_run.skipped_tests,
            error_tests=test_run.error_tests,
            total_duration_ms=test_run.total_duration_ms,
            imported_at=test_run.imported_at,
            processed_at=test_run.processed_at,
            test_cases=test_case_details
        )
    
    except Exception as e:
        logger.error(f"Failed to get test run detail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get test run detail: {str(e)}"
        )


@router.get(
    "/repositories/{repository_id}/test-results/{run_id}/failures",
    response_model=TestFailuresResponse,
    summary="Get test failures with analysis",
    description="""
Get failed tests with correlation and trend analysis.

Returns:
- Failed and error test cases
- Code change correlations (if commit associated)
- Historical trends

This endpoint provides comprehensive failure intelligence.
"""
)
async def get_test_failures(
    repository_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db)
) -> TestFailuresResponse:
    """Get test failures with analysis."""
    persistence_service = TestResultPersistenceService(db)
    
    # Get test run with repository isolation
    test_run = persistence_service.get_test_run(run_id, repository_id)
    if not test_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run {run_id} not found in repository {repository_id}"
        )
    
    try:
        # Get failed test cases
        failed_tests = persistence_service.get_failed_test_cases(run_id, repository_id)
        
        # Build test case details
        test_case_details = [
            TestCaseDetail(
                id=tc.id,
                suite_name=tc.suite_name,
                test_name=tc.test_name,
                class_name=tc.class_name,
                full_name=tc.full_name,
                outcome=tc.outcome.value,
                duration_ms=tc.duration_ms,
                failure_message=tc.failure_message,
                failure_type=tc.failure_type,
                failure_stacktrace=tc.failure_stacktrace,
                failure_classification=tc.failure_classification.value if tc.failure_classification else None,
                classification_confidence=tc.classification_confidence,
                classification_evidence=tc.classification_evidence
            )
            for tc in failed_tests
        ]
        
        # Get correlations if commit available
        correlations = []
        if test_run.commit_id:
            try:
                commit = db.query(Commit).filter(Commit.id == test_run.commit_id).first()
                if commit:
                    correlation_service = TestFailureCorrelationService(db)
                    failure_correlations = correlation_service.correlate_failures_with_commit(
                        test_run_id=run_id,
                        repository_id=repository_id,
                        commit_sha=commit.sha,
                        analysis_run_id=test_run.analysis_run_id
                    )
                    
                    correlations = [
                        FailureCorrelationSchema(
                            test_case_id=fc.test_case_id,
                            test_name=fc.test_name,
                            correlation_type=fc.correlation_type,
                            confidence=fc.confidence,
                            changed_files=fc.changed_files,
                            changed_symbols=fc.changed_symbols,
                            evidence=fc.evidence
                        )
                        for fc in failure_correlations
                    ]
            except Exception as e:
                logger.warning(f"Failed to get correlations: {e}")
        
        # Get historical trends
        trends = []
        try:
            trends_service = HistoricalTrendsService(db)
            test_trends = trends_service.analyze_trends(
                repository_id=repository_id,
                test_run_id=run_id,
                lookback_days=30
            )
            
            trends = [
                HistoricalTrendSchema(
                    test_name=tt.test_name,
                    trend_type=tt.trend_type,
                    description=tt.description,
                    runs_analyzed=tt.runs_analyzed,
                    evidence=tt.evidence,
                    confidence=tt.confidence
                )
                for tt in test_trends
            ]
        except Exception as e:
            logger.warning(f"Failed to get trends: {e}")
        
        return TestFailuresResponse(
            test_run_id=run_id,
            repository_id=repository_id,
            total_failures=len(failed_tests),
            failed_tests=test_case_details,
            correlations=correlations,
            trends=trends
        )
    
    except Exception as e:
        logger.error(f"Failed to get test failures: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get test failures: {str(e)}"
        )


@router.post(
    "/repositories/{repository_id}/test-results/explain",
    response_model=FailureExplainResponse,
    summary="Explain test failure using LLM",
    description="""
Generate LLM-powered explanation of a test failure.

Requires GEMINI_API_KEY configuration.

The explanation is grounded in:
- Failure information
- Classification evidence
- Code change correlations
- Historical trends

The LLM will not invent code or make unsupported claims.
"""
)
async def explain_test_failure(
    repository_id: UUID,
    request: FailureExplainRequest,
    db: Session = Depends(get_db)
) -> FailureExplainResponse:
    """Generate LLM explanation for test failure."""
    # Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Check LLM configuration
    if not settings.GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service not configured. Set GEMINI_API_KEY to enable explanations."
        )
    
    try:
        # Initialize LLM provider
        llm_provider = GeminiProvider(api_key=settings.GEMINI_API_KEY)
        
        # Initialize explainer service
        explainer_service = TestFailureExplainerService(db, llm_provider)
        
        # Generate explanation
        explanation = explainer_service.explain_failure(
            test_case_id=request.test_case_id,
            repository_id=repository_id,
            include_correlations=request.include_correlations,
            include_trends=request.include_trends
        )
        
        if not explanation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test case not found or failed to generate explanation"
            )
        
        return FailureExplainResponse(
            test_name=explanation.test_name,
            failure_summary=explanation.failure_summary,
            potential_causes=explanation.potential_causes,
            investigation_steps=explanation.investigation_steps,
            related_changes=explanation.related_changes,
            uncertainty=explanation.uncertainty
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Failed to explain test failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to explain test failure: {str(e)}"
        )
