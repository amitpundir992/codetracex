"""
Test Coverage Analyzer for Phase 19: CI & Test Intelligence.

This service maps code changes to affected tests using dependency analysis.

Architecture Philosophy:

    EVIDENCE-BASED COVERAGE MAPPING
    
    This service uses static analysis to find tests affected by changes:
    - Tests that import changed symbols (direct)
    - Tests that import changed modules (indirect)
    - Tests in same module structure (sibling)
    - Tests that call changed APIs (API consumer)
    - Tests that follow naming conventions (pattern)
    
    It does NOT:
    - Measure runtime code coverage
    - Execute tests to see what breaks
    - Guess at test relationships
    
    Flow:
    1. Get changed files and symbols
    2. Find tests that import changed symbols
    3. Find tests in related modules
    4. Classify coverage relationships
    5. Identify uncovered areas

Repository Isolation:

    All queries scoped by repository_id.
    Coverage analysis is deterministic.
"""
from typing import List, Dict, Optional, Set, Tuple
from uuid import UUID
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.schemas.change_analysis import ChangedFile, ChangedSymbol
from app.schemas.test_intelligence import (
    AffectedTest, UncoveredArea, TestCoverageType
)
from app.services.test_detection_service import TestDetectionService

logger = logging.getLogger(__name__)


class TestCoverageAnalyzer:
    """
    Service for mapping changes to affected tests.
    
    Uses test detection and dependency analysis.
    """
    
    def __init__(self, db: Session):
        """
        Initialize test coverage analyzer.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.test_detector = TestDetectionService(db)
    
    def analyze_test_coverage(
        self,
        repository_id: UUID,
        changed_files: List[ChangedFile],
        changed_symbols: List[ChangedSymbol],
        analysis_run_id: Optional[UUID] = None
    ) -> Tuple[List[AffectedTest], List[UncoveredArea]]:
        """
        Analyze test coverage for changes.
        
        Args:
            repository_id: Repository UUID
            changed_files: List of changed files
            changed_symbols: List of changed symbols
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            Tuple of (affected tests, uncovered areas)
        """
        # Get all test files
        all_test_files = self.test_detector.get_test_files(
            repository_id,
            analysis_run_id
        )
        
        if not all_test_files:
            logger.warning(f"No test files found in repository {repository_id}")
            uncovered = self._identify_uncovered_areas(
                changed_files,
                changed_symbols,
                []
            )
            return [], uncovered
        
        # Find affected tests
        affected_tests = self._find_affected_tests(
            all_test_files,
            changed_files,
            changed_symbols
        )
        
        # Identify uncovered areas
        uncovered_areas = self._identify_uncovered_areas(
            changed_files,
            changed_symbols,
            affected_tests
        )
        
        logger.info(
            f"Found {len(affected_tests)} affected tests, "
            f"{len(uncovered_areas)} uncovered areas"
        )
        
        return affected_tests, uncovered_areas
    
    def _find_affected_tests(
        self,
        all_test_files: List,
        changed_files: List[ChangedFile],
        changed_symbols: List[ChangedSymbol]
    ) -> List[AffectedTest]:
        """
        Find tests affected by changes.
        
        Args:
            all_test_files: All test files in repository
            changed_files: Changed files
            changed_symbols: Changed symbols
            
        Returns:
            List of affected tests
        """
        affected_tests = []
        
        # Build lookup structures
        changed_symbol_names = {s.name for s in changed_symbols}
        changed_qualified_names = {s.qualified_name for s in changed_symbols}
        changed_file_paths = {f.path for f in changed_files}
        
        # Map symbols to their files
        symbol_to_file = {s.qualified_name: s.file_path for s in changed_symbols}
        
        # Check each test file
        for test_file in all_test_files:
            # Skip if test file itself was changed (not testing the change)
            if test_file.file_path in changed_file_paths:
                continue
            
            # Check each test case
            for test_case in test_file.test_cases:
                # Check for direct symbol imports
                imported_changed_symbols = [
                    sym for sym in changed_symbol_names
                    if sym in test_case.imports_symbols
                ]
                
                if imported_changed_symbols:
                    evidence = [
                        f"Test imports {sym} which was modified"
                        for sym in imported_changed_symbols
                    ]
                    
                    affected_tests.append(AffectedTest(
                        test_file=test_file.file_path,
                        test_name=test_case.name,
                        coverage_type=TestCoverageType.DIRECT_IMPORT,
                        confidence="high",
                        evidence=evidence,
                        changed_symbols=imported_changed_symbols
                    ))
                    continue
            
            # Check for module-level imports (indirect)
            indirect_imports = []
            for changed_symbol in changed_symbols:
                # Extract module path from file path
                module_path = self._file_path_to_module(changed_symbol.file_path)
                
                # Check if test imports this module
                for imported_module in test_file.imports_from:
                    if module_path in imported_module or imported_module in module_path:
                        indirect_imports.append((changed_symbol.name, module_path))
            
            if indirect_imports:
                evidence = [
                    f"Test imports module containing {sym}"
                    for sym, mod in indirect_imports
                ]
                changed_syms = [sym for sym, _ in indirect_imports]
                
                affected_tests.append(AffectedTest(
                    test_file=test_file.file_path,
                    test_name=None,  # Whole file affected
                    coverage_type=TestCoverageType.INDIRECT_IMPORT,
                    confidence="medium",
                    evidence=evidence[:3],  # Limit evidence items
                    changed_symbols=changed_syms
                ))
                continue
            
            # Check for module sibling relationship (path-based)
            for changed_file in changed_files:
                if changed_file.is_test:
                    continue
                
                if self._are_module_siblings(test_file.file_path, changed_file.path):
                    evidence = [
                        f"Test file follows naming convention for {changed_file.path}"
                    ]
                    
                    affected_tests.append(AffectedTest(
                        test_file=test_file.file_path,
                        test_name=None,
                        coverage_type=TestCoverageType.MODULE_SIBLING,
                        confidence="medium",
                        evidence=evidence,
                        changed_symbols=[]
                    ))
                    break
        
        return affected_tests
    
    def _identify_uncovered_areas(
        self,
        changed_files: List[ChangedFile],
        changed_symbols: List[ChangedSymbol],
        affected_tests: List[AffectedTest]
    ) -> List[UncoveredArea]:
        """
        Identify changed areas without obvious test coverage.
        
        Args:
            changed_files: Changed files
            changed_symbols: Changed symbols
            affected_tests: Tests already identified as affected
            
        Returns:
            List of uncovered areas
        """
        uncovered_areas = []
        
        # Get covered symbols (symbols mentioned in affected tests)
        covered_symbols = set()
        for test in affected_tests:
            covered_symbols.update(test.changed_symbols)
        
        # Group uncovered symbols by file
        uncovered_by_file: Dict[str, List[str]] = {}
        for symbol in changed_symbols:
            if symbol.name not in covered_symbols:
                if symbol.file_path not in uncovered_by_file:
                    uncovered_by_file[symbol.file_path] = []
                uncovered_by_file[symbol.file_path].append(symbol.name)
        
        # Create uncovered area entries
        for file_path, symbols in uncovered_by_file.items():
            # Determine severity based on file type and symbol count
            is_source = any(
                f.path == file_path and f.is_source
                for f in changed_files
            )
            
            if not is_source:
                # Config/doc files are low severity
                severity = "low"
                explanation = f"Non-source file changed without test coverage"
            elif len(symbols) >= 3:
                severity = "high"
                explanation = f"{len(symbols)} changed symbols without obvious test coverage"
            elif len(symbols) >= 2:
                severity = "medium"
                explanation = f"{len(symbols)} changed symbols without obvious test coverage"
            else:
                severity = "medium"
                explanation = f"Changed symbol without obvious test coverage"
            
            uncovered_areas.append(UncoveredArea(
                file_path=file_path,
                changed_symbols=symbols,
                severity=severity,
                explanation=explanation
            ))
        
        return uncovered_areas
    
    def _file_path_to_module(self, file_path: str) -> str:
        """
        Convert file path to module name.
        
        Args:
            file_path: File path
            
        Returns:
            Module name
        """
        # Remove extension
        path = Path(file_path)
        module = str(path.with_suffix(''))
        
        # Convert path separators to dots
        module = module.replace('/', '.').replace('\\', '.')
        
        # Remove leading dots
        module = module.lstrip('.')
        
        return module
    
    def _are_module_siblings(self, test_path: str, source_path: str) -> bool:
        """
        Check if test and source files are module siblings.
        
        Siblings follow patterns like:
        - tests/test_foo.py tests src/foo.py
        - src/foo.test.ts tests src/foo.ts
        
        Args:
            test_path: Test file path
            source_path: Source file path
            
        Returns:
            True if they are siblings
        """
        test_name = Path(test_path).stem
        source_name = Path(source_path).stem
        
        # Remove test prefixes/suffixes
        test_name_clean = (
            test_name
            .replace('test_', '')
            .replace('_test', '')
            .replace('.test', '')
            .replace('.spec', '')
            .replace('_spec', '')
        )
        
        # Check if names match
        if test_name_clean == source_name:
            return True
        
        # Check if source name is in test name
        if source_name in test_name_clean:
            return True
        
        return False
    
    def get_tests_for_file(
        self,
        repository_id: UUID,
        file_path: str,
        analysis_run_id: Optional[UUID] = None
    ) -> List[AffectedTest]:
        """
        Get tests that cover a specific file.
        
        Args:
            repository_id: Repository UUID
            file_path: File path to find tests for
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            List of tests covering the file
        """
        # Get all test files
        all_test_files = self.test_detector.get_test_files(
            repository_id,
            analysis_run_id
        )
        
        # Create a pseudo change for this file
        from app.schemas.change_analysis import ChangeType
        changed_file = ChangedFile(
            path=file_path,
            change_type=ChangeType.MODIFIED,
            additions=0,
            deletions=0,
            is_test=False,
            is_source=True
        )
        
        # Find affected tests (without symbols for now)
        affected_tests = self._find_affected_tests(
            all_test_files,
            [changed_file],
            []
        )
        
        return affected_tests
