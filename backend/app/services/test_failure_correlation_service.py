"""
Failure-to-code correlation service for Phase 20: Test Results & Failure Intelligence.

This service correlates test failures with code changes by reusing:
- Phase 18: Change Intelligence (changed files and symbols)
- Phase 19: Test Intelligence (test coverage and recommendations)
- Phase 3: Static Analysis (symbol intelligence)
- Phase 6: Git History (commit information)

All correlations are evidence-based and explicitly labeled with confidence.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import (
    TestCase, TestRun, Repository, Commit, File, Symbol, Import
)
from app.services.test_detection_service import TestDetectionService
from app.services.change_detection_service import ChangeDetectionService
from app.services.symbol_change_analyzer import SymbolChangeAnalyzer

logger = logging.getLogger(__name__)


class FailureCorrelation:
    """Represents a correlation between a test failure and code changes."""
    
    def __init__(
        self,
        test_case_id: UUID,
        test_name: str,
        correlation_type: str,
        confidence: str,
        changed_files: List[str],
        changed_symbols: List[str],
        evidence: List[str]
    ):
        self.test_case_id = test_case_id
        self.test_name = test_name
        self.correlation_type = correlation_type
        self.confidence = confidence
        self.changed_files = changed_files
        self.changed_symbols = changed_symbols
        self.evidence = evidence


class TestFailureCorrelationService:
    """
    Service for correlating test failures with code changes.
    
    Reuses Phase 18 and Phase 19 intelligence to identify potential
    relationships between failures and recent changes.
    """
    
    def __init__(self, db: Session):
        """
        Initialize service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.test_detection = TestDetectionService(db)
        self.change_detection = ChangeDetectionService(db)
        self.symbol_analyzer = SymbolChangeAnalyzer(db)
    
    def correlate_failures_with_commit(
        self,
        test_run_id: UUID,
        repository_id: UUID,
        commit_sha: str,
        analysis_run_id: Optional[UUID] = None
    ) -> List[FailureCorrelation]:
        """
        Correlate test failures with a specific commit.
        
        This method:
        1. Gets failed tests from the test run
        2. Detects changes in the commit
        3. Finds test files that import changed code
        4. Computes correlation confidence
        
        Args:
            test_run_id: TestRun UUID
            repository_id: Repository UUID
            commit_sha: Commit SHA to correlate with
            analysis_run_id: Optional analysis run for symbol lookup
            
        Returns:
            List of FailureCorrelation objects
        """
        # Validate test run belongs to repository
        test_run = (
            self.db.query(TestRun)
            .filter(
                TestRun.id == test_run_id,
                TestRun.repository_id == repository_id
            )
            .first()
        )
        
        if not test_run:
            logger.warning(f"Test run {test_run_id} not found in repository {repository_id}")
            return []
        
        # Get failed test cases
        failed_tests = (
            self.db.query(TestCase)
            .filter(TestCase.test_run_id == test_run_id)
            .filter(TestCase.outcome.in_(['failed', 'error']))
            .all()
        )
        
        if not failed_tests:
            logger.info(f"No failed tests in run {test_run_id}")
            return []
        
        # Detect changes in commit
        try:
            changed_files = self.change_detection.get_commit_file_changes(
                repository_id=repository_id,
                commit_sha=commit_sha
            )
        except Exception as e:
            logger.error(f"Failed to detect changes for commit {commit_sha}: {e}")
            return []
        
        if not changed_files:
            logger.info(f"No file changes detected for commit {commit_sha}")
            return []
        
        # Analyze symbol changes if analysis run available
        changed_symbols_map = {}  # file_path -> list of symbol names
        if analysis_run_id:
            try:
                symbol_changes = self.symbol_analyzer.analyze_symbol_changes(
                    repository_id=repository_id,
                    changed_files=changed_files,
                    analysis_run_id=analysis_run_id
                )
                
                for sym in symbol_changes:
                    file_path = sym.get('file_path')
                    symbol_name = sym.get('symbol_name')
                    if file_path and symbol_name:
                        if file_path not in changed_symbols_map:
                            changed_symbols_map[file_path] = []
                        changed_symbols_map[file_path].append(symbol_name)
            except Exception as e:
                logger.warning(f"Failed to analyze symbol changes: {e}")
        
        # Correlate each failed test
        correlations = []
        
        for test_case in failed_tests:
            correlation = self._correlate_test_with_changes(
                test_case=test_case,
                changed_files=changed_files,
                changed_symbols_map=changed_symbols_map,
                analysis_run_id=analysis_run_id
            )
            
            if correlation:
                correlations.append(correlation)
        
        logger.info(f"Found {len(correlations)} correlations for {len(failed_tests)} failed tests")
        
        return correlations
    
    def _correlate_test_with_changes(
        self,
        test_case: TestCase,
        changed_files: List[Any],
        changed_symbols_map: Dict[str, List[str]],
        analysis_run_id: Optional[UUID]
    ) -> Optional[FailureCorrelation]:
        """
        Correlate a single test case with code changes.
        
        Args:
            test_case: TestCase instance
            changed_files: List of changed file objects
            changed_symbols_map: Map of file paths to changed symbol names
            analysis_run_id: Optional analysis run ID
            
        Returns:
            FailureCorrelation or None
        """
        # Extract test file path from suite_name or metadata
        test_file_path = self._extract_test_file_path(test_case)
        
        if not test_file_path or not analysis_run_id:
            # Cannot correlate without test file path and analysis data
            return None
        
        # Find what the test file imports
        test_file = (
            self.db.query(File)
            .filter(
                File.path == test_file_path,
                File.analysis_run_id == analysis_run_id
            )
            .first()
        )
        
        if not test_file:
            return None
        
        # Get imports from test file
        imports = (
            self.db.query(Import)
            .filter(Import.file_id == test_file.id)
            .all()
        )
        
        # Check for direct import correlations
        correlated_files = []
        correlated_symbols = []
        evidence = []
        correlation_type = None
        confidence = None
        
        for changed_file in changed_files:
            changed_path = changed_file.file_path
            
            # Check if test directly imports changed file
            for imp in imports:
                # Convert import to file path (heuristic)
                # e.g., "services.user_service" -> "services/user_service.py"
                import_module = imp.imported_module
                possible_paths = [
                    import_module.replace('.', '/') + '.py',
                    import_module.replace('.', '/') + '.ts',
                    import_module.replace('.', '/') + '.js',
                ]
                
                if any(changed_path.endswith(p) for p in possible_paths):
                    correlated_files.append(changed_path)
                    evidence.append(f"Test imports module {import_module} from {changed_path}")
                    
                    # Check for symbol-level correlation
                    if changed_path in changed_symbols_map:
                        imported_symbols = imp.imported_names or []
                        for changed_symbol in changed_symbols_map[changed_path]:
                            if changed_symbol in imported_symbols or not imported_symbols:
                                correlated_symbols.append(f"{changed_path}::{changed_symbol}")
                                evidence.append(f"Test imports changed symbol {changed_symbol}")
                    
                    correlation_type = "direct_import"
                    confidence = "high"
        
        # If no direct import, check for module sibling relationship
        if not correlated_files:
            for changed_file in changed_files:
                if self._are_module_siblings(test_file_path, changed_file.file_path):
                    correlated_files.append(changed_file.file_path)
                    evidence.append(f"Test and {changed_file.file_path} are module siblings")
                    correlation_type = "module_sibling"
                    confidence = "medium"
        
        # If no correlation found, return None
        if not correlated_files:
            return None
        
        return FailureCorrelation(
            test_case_id=test_case.id,
            test_name=test_case.full_name,
            correlation_type=correlation_type or "unknown",
            confidence=confidence or "low",
            changed_files=correlated_files,
            changed_symbols=correlated_symbols,
            evidence=evidence
        )
    
    def _extract_test_file_path(self, test_case: TestCase) -> Optional[str]:
        """
        Extract test file path from test case.
        
        Args:
            test_case: TestCase instance
            
        Returns:
            File path or None
        """
        # Try to extract from metadata
        if test_case.test_metadata:
            import json
            try:
                metadata = json.loads(test_case.test_metadata)
                if 'file' in metadata:
                    return metadata['file']
            except:
                pass
        
        # Try to infer from suite_name
        suite_name = test_case.suite_name
        if suite_name:
            # e.g., "tests/test_user.py" or "tests.test_user"
            if '/' in suite_name:
                return suite_name
            else:
                # Convert module path to file path
                return suite_name.replace('.', '/') + '.py'
        
        return None
    
    def _are_module_siblings(self, path1: str, path2: str) -> bool:
        """
        Check if two paths are module siblings.
        
        Args:
            path1: First file path
            path2: Second file path
            
        Returns:
            True if siblings (same directory structure)
        """
        # Remove file extensions
        path1_base = path1.rsplit('.', 1)[0] if '.' in path1 else path1
        path2_base = path2.rsplit('.', 1)[0] if '.' in path2 else path2
        
        # Split into parts
        parts1 = path1_base.split('/')
        parts2 = path2_base.split('/')
        
        # Check if one is test version of other
        # e.g., "services/user.py" and "tests/test_user.py"
        if len(parts1) >= 1 and len(parts2) >= 1:
            filename1 = parts1[-1].replace('test_', '')
            filename2 = parts2[-1].replace('test_', '')
            
            if filename1 == filename2:
                return True
        
        return False
