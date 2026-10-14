"""
Test result persistence service for Phase 20: Test Results & Failure Intelligence.

This service handles:
- Persisting parsed test results to database
- Idempotent import using content fingerprints
- Associating results with repository, commit, and analysis run
- Storing test cases with classifications
"""
import json
import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    TestRun, TestCase, Repository, Commit, AnalysisRun,
    TestRunStatus, TestOutcome, FailureClassification
)
from app.services.test_report_parser import ParsedTestResult, ParsedTestCase
from app.services.test_failure_classifier import FailureClassifier

logger = logging.getLogger(__name__)


class TestResultPersistenceService:
    """
    Service for persisting test results to database.
    
    Provides idempotent import based on content fingerprints.
    """
    
    def __init__(self, db: Session):
        """
        Initialize service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.classifier = FailureClassifier()
    
    def persist_test_result(
        self,
        repository_id: UUID,
        parsed_result: ParsedTestResult,
        commit_sha: Optional[str] = None,
        analysis_run_id: Optional[UUID] = None
    ) -> TestRun:
        """
        Persist parsed test result to database.
        
        Idempotent: If same report already exists (based on fingerprint),
        returns existing TestRun without creating duplicate.
        
        Args:
            repository_id: Repository UUID
            parsed_result: Parsed test result
            commit_sha: Optional commit SHA
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            TestRun instance (new or existing)
            
        Raises:
            ValueError: If repository not found
        """
        # Validate repository exists
        repository = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if not repository:
            raise ValueError(f"Repository {repository_id} not found")
        
        # Compute fingerprint for idempotency
        fingerprint = parsed_result.compute_fingerprint()
        
        # Check if already imported
        existing_run = (
            self.db.query(TestRun)
            .filter(
                TestRun.repository_id == repository_id,
                TestRun.content_fingerprint == fingerprint
            )
            .first()
        )
        
        if existing_run:
            logger.info(f"Test run already imported: {existing_run.id}")
            return existing_run
        
        # Resolve commit if SHA provided
        commit_id = None
        if commit_sha:
            commit = (
                self.db.query(Commit)
                .filter(
                    Commit.repository_id == repository_id,
                    Commit.sha.startswith(commit_sha)
                )
                .first()
            )
            if commit:
                commit_id = commit.id
            else:
                logger.warning(f"Commit {commit_sha} not found in repository {repository_id}")
        
        # Validate analysis run if provided
        if analysis_run_id:
            analysis_run = (
                self.db.query(AnalysisRun)
                .filter(
                    AnalysisRun.id == analysis_run_id,
                    AnalysisRun.repository_id == repository_id
                )
                .first()
            )
            if not analysis_run:
                logger.warning(f"Analysis run {analysis_run_id} not found or mismatched repository")
                analysis_run_id = None
        
        # Create TestRun
        test_run = TestRun(
            repository_id=repository_id,
            commit_id=commit_id,
            analysis_run_id=analysis_run_id,
            source_format=parsed_result.source_format,
            content_fingerprint=fingerprint,
            status=TestRunStatus.IMPORTED,
            total_tests=parsed_result.total_tests,
            passed_tests=parsed_result.passed_tests,
            failed_tests=parsed_result.failed_tests,
            skipped_tests=parsed_result.skipped_tests,
            error_tests=parsed_result.error_tests,
            total_duration_ms=parsed_result.total_duration_ms,
            report_metadata=json.dumps(parsed_result.report_metadata) if parsed_result.report_metadata else None,
            imported_at=datetime.utcnow()
        )
        
        try:
            self.db.add(test_run)
            self.db.flush()  # Get test_run.id
            
            # Persist test cases
            self._persist_test_cases(test_run.id, parsed_result.test_cases)
            
            # Mark as completed
            test_run.status = TestRunStatus.COMPLETED
            test_run.processed_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                f"Persisted test run {test_run.id}: "
                f"{parsed_result.passed_tests}P/{parsed_result.failed_tests}F/"
                f"{parsed_result.skipped_tests}S/{parsed_result.error_tests}E"
            )
            
            return test_run
        
        except IntegrityError as e:
            self.db.rollback()
            # Possible race condition, try to retrieve existing
            existing_run = (
                self.db.query(TestRun)
                .filter(
                    TestRun.repository_id == repository_id,
                    TestRun.content_fingerprint == fingerprint
                )
                .first()
            )
            if existing_run:
                logger.info(f"Test run already imported (race condition): {existing_run.id}")
                return existing_run
            raise
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to persist test result: {e}", exc_info=True)
            raise
    
    def _persist_test_cases(self, test_run_id: UUID, parsed_cases: List[ParsedTestCase]) -> None:
        """
        Persist test cases for a test run.
        
        Args:
            test_run_id: TestRun UUID
            parsed_cases: List of parsed test cases
        """
        for parsed_case in parsed_cases:
            # Classify failure if failed/error
            classification = None
            classification_confidence = None
            classification_evidence = None
            
            if parsed_case.outcome in ('failed', 'error'):
                cls, conf, evidence = self.classifier.classify_failure(
                    failure_message=parsed_case.failure_message,
                    failure_type=parsed_case.failure_type,
                    failure_stacktrace=parsed_case.failure_stacktrace
                )
                classification = cls
                classification_confidence = conf
                classification_evidence = '\n'.join(evidence)
            
            # Map outcome string to enum
            outcome_map = {
                'passed': TestOutcome.PASSED,
                'failed': TestOutcome.FAILED,
                'skipped': TestOutcome.SKIPPED,
                'error': TestOutcome.ERROR
            }
            outcome = outcome_map.get(parsed_case.outcome, TestOutcome.ERROR)
            
            # Map classification string to enum
            classification_enum = None
            if classification:
                classification_map = {
                    'assertion': FailureClassification.ASSERTION,
                    'import_error': FailureClassification.IMPORT_ERROR,
                    'setup_error': FailureClassification.SETUP_ERROR,
                    'timeout': FailureClassification.TIMEOUT,
                    'dependency_error': FailureClassification.DEPENDENCY_ERROR,
                    'network_error': FailureClassification.NETWORK_ERROR,
                    'unknown': FailureClassification.UNKNOWN
                }
                classification_enum = classification_map.get(classification, FailureClassification.UNKNOWN)
            
            test_case = TestCase(
                test_run_id=test_run_id,
                suite_name=parsed_case.suite_name,
                test_name=parsed_case.test_name,
                class_name=parsed_case.class_name,
                full_name=parsed_case.full_name,
                outcome=outcome,
                duration_ms=parsed_case.duration_ms,
                failure_message=parsed_case.failure_message,
                failure_type=parsed_case.failure_type,
                failure_stacktrace=parsed_case.failure_stacktrace,
                failure_classification=classification_enum,
                classification_confidence=classification_confidence,
                classification_evidence=classification_evidence,
                test_metadata=json.dumps(parsed_case.metadata) if parsed_case.metadata else None
            )
            
            self.db.add(test_case)
    
    def get_test_run(self, test_run_id: UUID, repository_id: UUID) -> Optional[TestRun]:
        """
        Get test run by ID with repository isolation.
        
        Args:
            test_run_id: TestRun UUID
            repository_id: Repository UUID (for isolation)
            
        Returns:
            TestRun or None
        """
        return (
            self.db.query(TestRun)
            .filter(
                TestRun.id == test_run_id,
                TestRun.repository_id == repository_id
            )
            .first()
        )
    
    def list_test_runs(
        self,
        repository_id: UUID,
        limit: int = 50,
        offset: int = 0,
        commit_sha: Optional[str] = None
    ) -> List[TestRun]:
        """
        List test runs for a repository.
        
        Args:
            repository_id: Repository UUID
            limit: Maximum results (default 50, max 100)
            offset: Results to skip (default 0)
            commit_sha: Optional commit SHA filter
            
        Returns:
            List of TestRun instances
        """
        limit = min(limit, 100)
        
        query = self.db.query(TestRun).filter(TestRun.repository_id == repository_id)
        
        if commit_sha:
            # Join with commits to filter by SHA
            query = query.join(Commit, TestRun.commit_id == Commit.id).filter(
                Commit.sha.startswith(commit_sha)
            )
        
        return (
            query
            .order_by(TestRun.imported_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
    
    def get_failed_test_cases(
        self,
        test_run_id: UUID,
        repository_id: UUID
    ) -> List[TestCase]:
        """
        Get all failed and error test cases for a run.
        
        Args:
            test_run_id: TestRun UUID
            repository_id: Repository UUID (for isolation)
            
        Returns:
            List of TestCase instances
        """
        # Verify test run belongs to repository
        test_run = self.get_test_run(test_run_id, repository_id)
        if not test_run:
            return []
        
        return (
            self.db.query(TestCase)
            .filter(
                TestCase.test_run_id == test_run_id,
                TestCase.outcome.in_([TestOutcome.FAILED, TestOutcome.ERROR])
            )
            .all()
        )
