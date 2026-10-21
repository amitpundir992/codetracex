"""
Test Traceability Service for Phase 22: Test-to-Code Traceability & Coverage Intelligence.

This service provides comprehensive test-to-code and code-to-test traceability
using existing Phase 19 infrastructure.

Architecture Philosophy:

    BIDIRECTIONAL TRACEABILITY
    
    This service provides:
    - Source file → Related tests (reverse of Phase 19)
    - Symbol → Related tests
    - Test file → Related source files
    - Evidence and confidence for all relationships
    
    It does NOT:
    - Measure runtime code coverage
    - Execute tests or analyze test runs
    - Invent relationships without evidence
    
    Flow:
    1. Query existing imports, symbols, and relationships
    2. Map tests to source using static evidence
    3. Provide reverse mapping (source to tests)
    4. Label confidence based on evidence type

Repository Isolation:

    All queries scoped by repository_id.
    Traceability is deterministic and evidence-based.
"""
from typing import List, Dict, Optional, Set, Tuple
from uuid import UUID
import logging
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.models import File, Symbol, Import, AnalysisRun
from app.schemas.test_intelligence import (
    TestFile, TestCase, TestCoverageType, AffectedTest
)
from app.services.test_detection_service import TestDetectionService

logger = logging.getLogger(__name__)


class TestTraceabilityRelationship:
    """
    Represents a test-to-source or source-to-test relationship.
    """
    
    def __init__(
        self,
        test_file: str,
        source_file: str,
        test_name: Optional[str] = None,
        source_symbol: Optional[str] = None,
        relationship_type: TestCoverageType = TestCoverageType.DIRECT_IMPORT,
        confidence: str = "medium",
        evidence: List[str] = None,
        is_bidirectional: bool = True
    ):
        self.test_file = test_file
        self.source_file = source_file
        self.test_name = test_name
        self.source_symbol = source_symbol
        self.relationship_type = relationship_type
        self.confidence = confidence
        self.evidence = evidence or []
        self.is_bidirectional = is_bidirectional


class TestTraceabilityService:
    """
    Service for comprehensive test-to-code traceability.
    
    Provides bidirectional mapping between tests and source code.
    """
    
    def __init__(self, db: Session):
        """
        Initialize test traceability service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.test_detector = TestDetectionService(db)
    
    def get_tests_for_source_file(
        self,
        repository_id: UUID,
        source_file_path: str,
        analysis_run_id: Optional[UUID] = None
    ) -> List[AffectedTest]:
        """
        Find all tests that relate to a source file.
        
        Args:
            repository_id: Repository UUID
            source_file_path: Source file path
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            List of affected tests with evidence
        """
        # Get test files
        all_test_files = self.test_detector.get_test_files(
            repository_id,
            analysis_run_id
        )
        
        if not all_test_files:
            logger.info(f"No test files found for repository {repository_id}")
            return []
        
        affected_tests = []
        
        # Get source file from database
        query = self.db.query(File).filter(
            File.path == source_file_path
        )
        
        if analysis_run_id:
            query = query.filter(File.analysis_run_id == analysis_run_id)
        else:
            # Get latest analysis
            latest_run = self.db.query(AnalysisRun).filter(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.status == 'completed'
            ).order_by(AnalysisRun.started_at.desc()).first()
            
            if not latest_run:
                logger.warning(f"No completed analysis found for repository {repository_id}")
                return []
            
            query = query.filter(File.analysis_run_id == latest_run.id)
        
        source_file = query.first()
        if not source_file:
            logger.warning(f"Source file {source_file_path} not found")
            return []
        
        # Get symbols in source file
        source_symbols = self.db.query(Symbol).filter(
            Symbol.file_id == source_file.id
        ).all()
        
        source_symbol_names = {sym.name for sym in source_symbols}
        
        # Module path for matching
        source_module = self._file_path_to_module(source_file_path)
        
        # Check each test file for relationships
        for test_file in all_test_files:
            # Direct import: test imports from this source file
            if source_module in test_file.imports_from or source_file_path in test_file.imports_from:
                for test_case in test_file.test_cases:
                    # Check if test imports specific symbols
                    imported_symbols = set(test_case.imports_symbols) & source_symbol_names
                    
                    if imported_symbols:
                        affected_tests.append(AffectedTest(
                            test_file=test_file.file_path,
                            test_name=test_case.name,
                            coverage_type=TestCoverageType.DIRECT_IMPORT,
                            confidence="high",
                            evidence=[
                                f"Test imports {len(imported_symbols)} symbol(s) from {source_file_path}",
                                f"Imported symbols: {', '.join(sorted(imported_symbols))}"
                            ],
                            changed_symbols=list(imported_symbols)
                        ))
                    else:
                        # Test imports module but not specific symbols
                        affected_tests.append(AffectedTest(
                            test_file=test_file.file_path,
                            test_name=test_case.name,
                            coverage_type=TestCoverageType.INDIRECT_IMPORT,
                            confidence="medium",
                            evidence=[
                                f"Test imports module {source_module}",
                                "Specific imported symbols unknown"
                            ],
                            changed_symbols=[]
                        ))
            
            # Module sibling: tests in parallel structure
            elif self._are_module_siblings(test_file.file_path, source_file_path):
                for test_case in test_file.test_cases:
                    affected_tests.append(AffectedTest(
                        test_file=test_file.file_path,
                        test_name=test_case.name,
                        coverage_type=TestCoverageType.MODULE_SIBLING,
                        confidence="medium",
                        evidence=[
                            f"Test file {test_file.file_path} follows naming convention for {source_file_path}",
                            "Tests typically cover nearby source files"
                        ],
                        changed_symbols=[]
                    ))
            
            # Path pattern: test name matches source file/module
            else:
                test_name_lower = Path(test_file.file_path).stem.lower()
                source_name_lower = Path(source_file_path).stem.lower()
                
                # Remove test prefix/suffix for comparison
                test_name_clean = test_name_lower.replace('test_', '').replace('_test', '')
                
                if source_name_lower in test_name_clean or test_name_clean in source_name_lower:
                    for test_case in test_file.test_cases:
                        affected_tests.append(AffectedTest(
                            test_file=test_file.file_path,
                            test_name=test_case.name,
                            coverage_type=TestCoverageType.PATH_PATTERN,
                            confidence="low",
                            evidence=[
                                f"Test file name pattern suggests relationship to {source_file_path}",
                                "Pattern-based heuristic match"
                            ],
                            changed_symbols=[]
                        ))
        
        # Deduplicate by test file and name
        seen = set()
        unique_tests = []
        for test in affected_tests:
            key = (test.test_file, test.test_name)
            if key not in seen:
                seen.add(key)
                unique_tests.append(test)
        
        logger.info(
            f"Found {len(unique_tests)} tests related to {source_file_path} "
            f"in repository {repository_id}"
        )
        
        return unique_tests
    
    def get_tests_for_symbol(
        self,
        repository_id: UUID,
        symbol_name: str,
        file_path: Optional[str] = None,
        analysis_run_id: Optional[UUID] = None
    ) -> List[AffectedTest]:
        """
        Find all tests that relate to a specific symbol.
        
        Args:
            repository_id: Repository UUID
            symbol_name: Symbol name to find tests for
            file_path: Optional file path to disambiguate symbol
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            List of affected tests with evidence
        """
        # Get test files
        all_test_files = self.test_detector.get_test_files(
            repository_id,
            analysis_run_id
        )
        
        if not all_test_files:
            logger.info(f"No test files found for repository {repository_id}")
            return []
        
        affected_tests = []
        
        # Check each test file
        for test_file in all_test_files:
            for test_case in test_file.test_cases:
                # Direct import: test imports this symbol
                if symbol_name in test_case.imports_symbols:
                    affected_tests.append(AffectedTest(
                        test_file=test_file.file_path,
                        test_name=test_case.name,
                        coverage_type=TestCoverageType.DIRECT_IMPORT,
                        confidence="high",
                        evidence=[
                            f"Test directly imports symbol '{symbol_name}'",
                            "Static import analysis"
                        ],
                        changed_symbols=[symbol_name]
                    ))
                
                # Test name pattern: test name mentions symbol
                elif symbol_name.lower() in test_case.name.lower():
                    affected_tests.append(AffectedTest(
                        test_file=test_file.file_path,
                        test_name=test_case.name,
                        coverage_type=TestCoverageType.PATH_PATTERN,
                        confidence="low",
                        evidence=[
                            f"Test name '{test_case.name}' mentions symbol '{symbol_name}'",
                            "Name-based heuristic match"
                        ],
                        changed_symbols=[symbol_name]
                    ))
        
        # Deduplicate
        seen = set()
        unique_tests = []
        for test in affected_tests:
            key = (test.test_file, test.test_name)
            if key not in seen:
                seen.add(key)
                unique_tests.append(test)
        
        logger.info(
            f"Found {len(unique_tests)} tests related to symbol '{symbol_name}' "
            f"in repository {repository_id}"
        )
        
        return unique_tests
    
    def get_source_files_for_test(
        self,
        repository_id: UUID,
        test_file_path: str,
        analysis_run_id: Optional[UUID] = None
    ) -> List[Dict[str, any]]:
        """
        Find all source files that a test file relates to.
        
        Args:
            repository_id: Repository UUID
            test_file_path: Test file path
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            List of related source files with relationship info
        """
        # Get test file info
        test_files = self.test_detector.get_test_files(
            repository_id,
            analysis_run_id
        )
        
        test_file = next(
            (tf for tf in test_files if tf.file_path == test_file_path),
            None
        )
        
        if not test_file:
            logger.warning(f"Test file {test_file_path} not found")
            return []
        
        related_sources = []
        seen_paths = set()
        
        # Direct imports: source files imported by test
        for import_path in test_file.imports_from:
            if import_path not in seen_paths:
                seen_paths.add(import_path)
                related_sources.append({
                    "source_file": import_path,
                    "relationship_type": "direct_import",
                    "confidence": "high",
                    "evidence": [f"Test imports from {import_path}"],
                    "imported_symbols": []  # Could be enhanced with symbol details
                })
        
        # Module siblings: source files in related paths
        # Get all source files (exclude test files)
        query = self.db.query(File)
        
        if analysis_run_id:
            query = query.filter(File.analysis_run_id == analysis_run_id)
        else:
            # Get latest analysis
            latest_run = self.db.query(AnalysisRun).filter(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.status == 'completed'
            ).order_by(AnalysisRun.started_at.desc()).first()
            
            if latest_run:
                query = query.filter(File.analysis_run_id == latest_run.id)
        
        all_files = query.all()
        
        # Filter out test files using test detector
        all_source_files = [f for f in all_files if not self.test_detector.is_test_file(f.path)]
        
        for source_file in all_source_files:
            if source_file.path not in seen_paths:
                if self._are_module_siblings(test_file_path, source_file.path):
                    seen_paths.add(source_file.path)
                    related_sources.append({
                        "source_file": source_file.path,
                        "relationship_type": "module_sibling",
                        "confidence": "medium",
                        "evidence": [
                            f"Test follows naming convention for {source_file.path}"
                        ],
                        "imported_symbols": []
                    })
        
        logger.info(
            f"Found {len(related_sources)} source files related to test {test_file_path}"
        )
        
        return related_sources
    
    def _file_path_to_module(self, file_path: str) -> str:
        """
        Convert file path to Python module path.
        
        Args:
            file_path: File path
            
        Returns:
            Module path
        """
        # Remove file extension
        module_path = Path(file_path).with_suffix('').as_posix()
        
        # Replace slashes with dots
        module_path = module_path.replace('/', '.')
        
        # Remove leading dots
        module_path = module_path.lstrip('.')
        
        return module_path
    
    def _are_module_siblings(self, test_path: str, source_path: str) -> bool:
        """
        Check if test and source are module siblings.
        
        Args:
            test_path: Test file path
            source_path: Source file path
            
        Returns:
            True if they are siblings
        """
        test_path_obj = Path(test_path)
        source_path_obj = Path(source_path)
        
        # Remove test directory prefix
        test_parts = [p for p in test_path_obj.parts if p not in ('tests', 'test', '__tests__')]
        source_parts = list(source_path_obj.parts)
        
        # Remove test prefix/suffix from filename
        test_name = test_path_obj.stem.replace('test_', '').replace('_test', '')
        source_name = source_path_obj.stem
        
        # Check if test name matches source name
        if test_name == source_name:
            return True
        
        # Check if they're in parallel directory structure
        if len(test_parts) >= 2 and len(source_parts) >= 2:
            # Compare directory structure (excluding filename)
            if test_parts[:-1] == source_parts[:-1]:
                return True
        
        return False
