"""
Test Detection Service for Phase 19: CI & Test Intelligence.

This service identifies test files and extracts test cases using
existing file and symbol analysis.

Architecture Philosophy:

    DETERMINISTIC TEST DETECTION
    
    This service uses static analysis to:
    - Identify test files by path patterns
    - Extract test functions/methods from symbols
    - Map test imports to source files
    - Detect test frameworks
    
    It does NOT:
    - Execute tests
    - Measure code coverage
    - Analyze runtime behavior
    
    Flow:
    1. Query files with test-like patterns
    2. Filter symbols for test functions/methods
    3. Detect framework from imports/patterns
    4. Build test catalog

Repository Isolation:

    All queries scoped by repository_id.
    Test detection uses existing database facts.
"""
from typing import List, Dict, Optional, Set
from uuid import UUID
import logging
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.models import File, Symbol, Import, AnalysisRun
from app.schemas.test_intelligence import (
    TestFile, TestCase, TestFramework, TestType
)

logger = logging.getLogger(__name__)


class TestDetectionService:
    """
    Service for detecting test files and extracting test cases.
    
    Uses existing file and symbol analysis from the database.
    """
    
    # Test file path patterns
    TEST_DIR_PATTERNS = {
        'test', 'tests', '__tests__', 'spec', 'specs', 
        'test_', 'e2e', 'integration', 'unit'
    }
    
    TEST_FILE_PATTERNS = [
        'test_', '_test', '.test.', '.spec.', '_spec', 
        'test.', 'spec.'
    ]
    
    # Framework detection patterns (import module names)
    FRAMEWORK_IMPORTS = {
        TestFramework.PYTEST: {'pytest', '_pytest'},
        TestFramework.UNITTEST: {'unittest'},
        TestFramework.JEST: {'jest', '@jest'},
        TestFramework.MOCHA: {'mocha'},
        TestFramework.VITEST: {'vitest'},
        TestFramework.JUNIT: {'junit', 'org.junit'},
        TestFramework.TESTNG: {'testng', 'org.testng'},
        TestFramework.RSPEC: {'rspec'},
        TestFramework.GO_TEST: {'testing'},  # Go testing package
        TestFramework.CARGO_TEST: {},  # Rust uses #[test] attributes
    }
    
    # Test function name patterns
    TEST_FUNCTION_PATTERNS = [
        'test_', 'test', 'should_', 'it_', 'describe_',
        'spec_', 'example_'
    ]
    
    def __init__(self, db: Session):
        """
        Initialize test detection service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def is_test_file(self, path: str) -> bool:
        """
        Determine if a file is likely a test file.
        
        Uses heuristics based on path and filename patterns.
        
        Args:
            path: File path
            
        Returns:
            True if likely a test file
        """
        path_lower = path.lower()
        parts = Path(path).parts
        
        # Check directory patterns
        if any(part.lower() in self.TEST_DIR_PATTERNS for part in parts):
            return True
        
        # Check file name patterns
        filename = Path(path).name.lower()
        if any(pattern in filename for pattern in self.TEST_FILE_PATTERNS):
            return True
        
        return False
    
    def detect_framework(
        self,
        file_imports: List[Import],
        language: Optional[str]
    ) -> TestFramework:
        """
        Detect test framework from imports and language.
        
        Args:
            file_imports: Import statements in the test file
            language: Programming language
            
        Returns:
            Detected test framework
        """
        # Extract module names from imports
        import_modules = set()
        for imp in file_imports:
            if imp.source:
                # Get root module (e.g., "pytest" from "pytest.fixtures")
                root_module = imp.source.split('.')[0]
                import_modules.add(root_module)
        
        # Check framework patterns
        for framework, patterns in self.FRAMEWORK_IMPORTS.items():
            if patterns and any(pattern in import_modules for pattern in patterns):
                return framework
        
        # Language-specific defaults
        if language == "Python":
            # If no specific framework detected, might be unittest
            if any('unittest' in m for m in import_modules):
                return TestFramework.UNITTEST
            # Default to pytest for Python tests
            return TestFramework.PYTEST
        elif language in ["JavaScript", "TypeScript"]:
            # Default to Jest for JS/TS
            return TestFramework.JEST
        elif language == "Java":
            return TestFramework.JUNIT
        elif language == "Go":
            return TestFramework.GO_TEST
        elif language == "Rust":
            return TestFramework.CARGO_TEST
        
        return TestFramework.UNKNOWN
    
    def is_test_symbol(self, symbol: Symbol) -> bool:
        """
        Determine if a symbol is likely a test function/method.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if likely a test
        """
        if symbol.symbol_type not in ['function', 'method']:
            return False
        
        name_lower = symbol.name.lower()
        
        # Check test name patterns
        for pattern in self.TEST_FUNCTION_PATTERNS:
            if name_lower.startswith(pattern):
                return True
        
        # Check for common test decorators in qualified name
        if symbol.qualified_name:
            qual_lower = symbol.qualified_name.lower()
            if '@test' in qual_lower or 'test(' in qual_lower:
                return True
        
        return False
    
    def classify_test_type(self, test_name: str, file_path: str) -> TestType:
        """
        Classify test type from name and path.
        
        Args:
            test_name: Test function name
            file_path: Test file path
            
        Returns:
            Test type classification
        """
        name_lower = test_name.lower()
        path_lower = file_path.lower()
        
        # E2E tests
        if 'e2e' in path_lower or 'end_to_end' in path_lower:
            return TestType.E2E
        if 'e2e' in name_lower or 'end_to_end' in name_lower:
            return TestType.E2E
        
        # Integration tests
        if 'integration' in path_lower:
            return TestType.INTEGRATION
        if 'integration' in name_lower or 'integr' in name_lower:
            return TestType.INTEGRATION
        
        # Functional tests
        if 'functional' in path_lower or 'feature' in path_lower:
            return TestType.FUNCTIONAL
        if 'functional' in name_lower or 'feature' in name_lower:
            return TestType.FUNCTIONAL
        
        # Default to unit test
        if 'unit' in path_lower:
            return TestType.UNIT
        if 'unit' in name_lower:
            return TestType.UNIT
        
        # If in a 'tests' directory without subdirectory, likely unit
        parts = Path(path_lower).parts
        if 'tests' in parts or 'test' in parts:
            return TestType.UNIT
        
        return TestType.UNKNOWN
    
    def get_test_files(
        self,
        repository_id: UUID,
        analysis_run_id: Optional[UUID] = None
    ) -> List[TestFile]:
        """
        Get all test files in repository.
        
        Args:
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run UUID (uses latest if not provided)
            
        Returns:
            List of test files with metadata
        """
        # Get latest analysis run if not provided
        if not analysis_run_id:
            latest_run = (
                self.db.query(AnalysisRun)
                .filter(AnalysisRun.repository_id == repository_id)
                .order_by(AnalysisRun.created_at.desc())
                .first()
            )
            if not latest_run:
                logger.warning(f"No analysis run found for repository {repository_id}")
                return []
            analysis_run_id = latest_run.id
        
        # Query files that match test patterns
        files = (
            self.db.query(File)
            .filter(
                and_(
                    File.repository_id == repository_id,
                    File.analysis_run_id == analysis_run_id
                )
            )
            .all()
        )
        
        test_files = []
        for file in files:
            if not self.is_test_file(file.path):
                continue
            
            # Get symbols in this file
            symbols = (
                self.db.query(Symbol)
                .filter(Symbol.file_id == file.id)
                .all()
            )
            
            # Filter test symbols
            test_symbols = [s for s in symbols if self.is_test_symbol(s)]
            
            # Get imports
            file_imports = (
                self.db.query(Import)
                .filter(Import.file_id == file.id)
                .all()
            )
            
            # Detect framework
            framework = self.detect_framework(file_imports, file.language)
            
            # Build test cases
            test_cases = []
            imported_symbols = set()
            for imp in file_imports:
                if imp.imported_names:
                    # Split comma-separated names
                    names = [name.strip() for name in imp.imported_names.split(',') if name.strip()]
                    imported_symbols.update(names)
            
            for test_symbol in test_symbols:
                test_type = self.classify_test_type(test_symbol.name, file.path)
                
                test_case = TestCase(
                    name=test_symbol.name,
                    line_number=test_symbol.start_line,
                    test_type=test_type,
                    imports_symbols=list(imported_symbols)  # Same imports for all tests in file
                )
                test_cases.append(test_case)
            
            # Get source modules imported
            imports_from = set()
            for imp in file_imports:
                if imp.source:
                    imports_from.add(imp.source)
            
            test_file = TestFile(
                file_path=file.path,
                language=file.language,
                framework=framework,
                test_count=len(test_cases),
                test_cases=test_cases,
                imports_from=list(imports_from)
            )
            test_files.append(test_file)
        
        logger.info(
            f"Detected {len(test_files)} test files with "
            f"{sum(tf.test_count for tf in test_files)} test cases"
        )
        
        return test_files
    
    def get_test_files_for_paths(
        self,
        repository_id: UUID,
        file_paths: List[str],
        analysis_run_id: Optional[UUID] = None
    ) -> List[TestFile]:
        """
        Get test files for specific paths.
        
        Args:
            repository_id: Repository UUID
            file_paths: List of file paths to check
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            List of test files matching paths
        """
        all_test_files = self.get_test_files(repository_id, analysis_run_id)
        
        # Filter to matching paths
        return [tf for tf in all_test_files if tf.file_path in file_paths]
    
    def get_tests_importing_symbol(
        self,
        repository_id: UUID,
        symbol_name: str,
        analysis_run_id: Optional[UUID] = None
    ) -> List[TestFile]:
        """
        Find test files that import a specific symbol.
        
        Args:
            repository_id: Repository UUID
            symbol_name: Symbol name to search for
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            List of test files that import the symbol
        """
        all_test_files = self.get_test_files(repository_id, analysis_run_id)
        
        # Filter to tests that import this symbol
        matching_tests = []
        for test_file in all_test_files:
            # Check if any test case imports this symbol
            for test_case in test_file.test_cases:
                if symbol_name in test_case.imports_symbols:
                    matching_tests.append(test_file)
                    break
        
        return matching_tests
    
    def get_tests_importing_module(
        self,
        repository_id: UUID,
        module_name: str,
        analysis_run_id: Optional[UUID] = None
    ) -> List[TestFile]:
        """
        Find test files that import a specific module.
        
        Args:
            repository_id: Repository UUID
            module_name: Module name to search for
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            List of test files that import the module
        """
        all_test_files = self.get_test_files(repository_id, analysis_run_id)
        
        # Filter to tests that import this module
        return [
            tf for tf in all_test_files
            if module_name in tf.imports_from
        ]
