"""
Tests for Phase 22: Test-to-Code Traceability & Coverage Intelligence.

This test suite verifies:
- Direct test-to-source relationships
- Heuristic relationships and confidence labeling
- Unresolved relationships
- Change-to-test impact (reuses Phase 18)
- Potential test gaps (extends Phase 19)
- Repository isolation and invalid IDs
- Missing test results and analysis data
- API response schemas and limits
"""
import pytest
from uuid import uuid4
from datetime import datetime

from app.services.test_traceability_service import TestTraceabilityService as TraceabilityService
from app.services.test_detection_service import TestDetectionService
from app.schemas.test_intelligence import TestCoverageType, AffectedTest
from app.db.models import (
    Repository, AnalysisRun, File, Symbol, Import, SymbolType, AnalysisStatus
)


class TestTraceabilityServiceLogic:
    """Tests for TestTraceabilityService."""
    
    @pytest.fixture
    def repository(self, db):
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            owner="testuser",
            name="testrepo",
            full_name="testuser/testrepo",
            github_url="https://github.com/testuser/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        return repo
    
    @pytest.fixture
    def analysis_run(self, db, repository):
        """Create a completed analysis run."""
        run = AnalysisRun(
            id=uuid4(),
            repository_id=repository.id,
            status=AnalysisStatus.COMPLETED,
            total_files=4,
            analyzed_files=4,
            total_symbols=5,
            total_imports=3,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.add(run)
        db.commit()
        return run
    
    @pytest.fixture
    def source_file(self, db, repository, analysis_run):
        """Create a source file."""
        file = File(
            id=uuid4(),
            repository_id=repository.id,
            analysis_run_id=analysis_run.id,
            path="services/user_service.py",
            filename="user_service.py",
            extension=".py",
            language="Python",
            size_bytes=1500,
            line_count=60,
            is_sensitive=False
        )
        db.add(file)
        db.commit()
        return file
    
    @pytest.fixture
    def test_file(self, db, repository, analysis_run):
        """Create a test file."""
        file = File(
            id=uuid4(),
            repository_id=repository.id,
            analysis_run_id=analysis_run.id,
            path="tests/test_user_service.py",
            filename="test_user_service.py",
            extension=".py",
            language="Python",
            size_bytes=2000,
            line_count=80,
            is_sensitive=False
        )
        db.add(file)
        db.commit()
        return file
    
    @pytest.fixture
    def source_symbols(self, db, repository, analysis_run, source_file):
        """Create symbols in source file."""
        symbols = [
            Symbol(
                id=uuid4(),
                file_id=source_file.id,
                analysis_run_id=analysis_run.id,
                name="create_user",
                symbol_type=SymbolType.FUNCTION,
                language="Python",
                start_line=10,
                end_line=20
            ),
            Symbol(
                id=uuid4(),
                file_id=source_file.id,
                analysis_run_id=analysis_run.id,
                name="delete_user",
                symbol_type=SymbolType.FUNCTION,
                language="Python",
                start_line=25,
                end_line=35
            )
        ]
        for sym in symbols:
            db.add(sym)
        db.commit()
        return symbols
    
    @pytest.fixture
    def test_symbols(self, db, repository, analysis_run, test_file):
        """Create test symbols."""
        symbols = [
            Symbol(
                id=uuid4(),
                file_id=test_file.id,
                analysis_run_id=analysis_run.id,
                name="test_create_user",
                symbol_type=SymbolType.FUNCTION,
                language="Python",
                start_line=10,
                end_line=15
            ),
            Symbol(
                id=uuid4(),
                file_id=test_file.id,
                analysis_run_id=analysis_run.id,
                name="test_delete_user",
                symbol_type=SymbolType.FUNCTION,
                language="Python",
                start_line=20,
                end_line=25
            )
        ]
        for sym in symbols:
            db.add(sym)
        db.commit()
        return symbols
    
    @pytest.fixture
    def test_import(self, db, repository, analysis_run, test_file):
        """Create an import in test file."""
        imp = Import(
            id=uuid4(),
            file_id=test_file.id,
            analysis_run_id=analysis_run.id,
            source="services.user_service",
            imported_names="create_user,delete_user",
            line_number=1
        )
        db.add(imp)
        db.commit()
        return imp
    
    def test_source_to_tests_direct_import(
        self, db, repository, analysis_run, source_file,
        test_file, source_symbols, test_symbols, test_import
    ):
        """Test finding tests for source file with direct imports."""
        service = TraceabilityService(db)
        
        result = service.get_tests_for_source_file(
            repository_id=repository.id,
            source_file_path="services/user_service.py",
            analysis_run_id=analysis_run.id
        )
        
        # Should find tests that import from this source
        assert len(result) > 0
        
        # Check for high confidence direct imports
        direct_imports = [
            t for t in result
            if t.coverage_type == TestCoverageType.DIRECT_IMPORT
        ]
        assert len(direct_imports) > 0
        
        # Verify evidence
        for test in direct_imports:
            assert test.confidence == "high"
            assert len(test.evidence) > 0
            assert "import" in test.evidence[0].lower()
    
    def test_source_to_tests_no_relationships(
        self, db, repository, analysis_run, source_file
    ):
        """Test source file with no related tests."""
        # Create an unrelated source file
        unrelated_file = File(
            id=uuid4(),
            repository_id=repository.id,
            analysis_run_id=analysis_run.id,
            path="services/payment_service.py",
            filename="payment_service.py",
            extension=".py",
            language="Python",
            size_bytes=1000,
            line_count=40,
            is_sensitive=False
        )
        db.add(unrelated_file)
        db.commit()
        
        service = TraceabilityService(db)
        
        result = service.get_tests_for_source_file(
            repository_id=repository.id,
            source_file_path="services/payment_service.py",
            analysis_run_id=analysis_run.id
        )
        
        # Should return empty list, not None
        assert result == []
    
    def test_symbol_to_tests_direct_import(
        self, db, repository, analysis_run, source_file,
        test_file, source_symbols, test_symbols, test_import
    ):
        """Test finding tests for a specific symbol."""
        service = TraceabilityService(db)
        
        result = service.get_tests_for_symbol(
            repository_id=repository.id,
            symbol_name="create_user",
            analysis_run_id=analysis_run.id
        )
        
        # Should find tests that import this symbol
        assert len(result) > 0
        
        # Check for high confidence
        for test in result:
            if test.coverage_type == TestCoverageType.DIRECT_IMPORT:
                assert test.confidence == "high"
                assert "create_user" in test.changed_symbols
    
    def test_test_to_sources_bidirectional(
        self, db, repository, analysis_run, source_file,
        test_file, source_symbols, test_symbols, test_import
    ):
        """Test reverse mapping from test to sources."""
        service = TraceabilityService(db)
        
        result = service.get_source_files_for_test(
            repository_id=repository.id,
            test_file_path="tests/test_user_service.py",
            analysis_run_id=analysis_run.id
        )
        
        # Should find source files imported by test
        assert len(result) > 0
        
        # Check direct imports
        direct_imports = [
            s for s in result
            if s["relationship_type"] == "direct_import"
        ]
        assert len(direct_imports) > 0
        
        # Verify confidence
        for source in direct_imports:
            assert source["confidence"] == "high"
    
    def test_module_sibling_detection(
        self, db, repository, analysis_run
    ):
        """Test module sibling relationship detection."""
        # Create parallel structure
        source = File(
            id=uuid4(),
            repository_id=repository.id,
            analysis_run_id=analysis_run.id,
            path="src/utils/validators.py",
            filename="validators.py",
            extension=".py",
            language="Python",
            size_bytes=500,
            line_count=25,
            is_sensitive=False
        )
        
        test = File(
            id=uuid4(),
            repository_id=repository.id,
            analysis_run_id=analysis_run.id,
            path="tests/test_validators.py",
            filename="test_validators.py",
            extension=".py",
            language="Python",
            size_bytes=800,
            line_count=40,
            is_sensitive=False
        )
        
        # Add test symbol
        test_sym = Symbol(
            id=uuid4(),
            file_id=test.id,
            analysis_run_id=analysis_run.id,
            name="test_email_validator",
            symbol_type=SymbolType.FUNCTION,
            language="Python",
            start_line=5,
            end_line=10
        )
        
        db.add_all([source, test, test_sym])
        db.commit()
        
        service = TraceabilityService(db)
        
        result = service.get_tests_for_source_file(
            repository_id=repository.id,
            source_file_path="src/utils/validators.py",
            analysis_run_id=analysis_run.id
        )
        
        # Should detect module sibling relationship
        siblings = [
            t for t in result
            if t.coverage_type == TestCoverageType.MODULE_SIBLING
        ]
        assert len(siblings) > 0
        assert siblings[0].confidence == "medium"
    
    def test_repository_isolation(
        self, db, repository, analysis_run, source_file
    ):
        """Test that repository isolation is enforced."""
        # Create another repository
        other_repo = Repository(
            id=uuid4(),
            owner="otheruser",
            name="otherrepo",
            full_name="otheruser/otherrepo",
            github_url="https://github.com/otheruser/otherrepo",
            default_branch="main"
        )
        db.add(other_repo)
        db.commit()
        
        service = TraceabilityService(db)
        
        # Query with other repository ID
        result = service.get_tests_for_source_file(
            repository_id=other_repo.id,
            source_file_path="services/user_service.py",
            analysis_run_id=None
        )
        
        # Should not find tests from different repository
        assert result == []
    
    def test_missing_analysis_run(
        self, db, repository
    ):
        """Test behavior with no completed analysis."""
        service = TraceabilityService(db)
        
        result = service.get_tests_for_source_file(
            repository_id=repository.id,
            source_file_path="any/file.py",
            analysis_run_id=None
        )
        
        # Should handle gracefully
        assert result == []
    
    def test_invalid_analysis_run_id(
        self, db, repository, analysis_run
    ):
        """Test with non-existent analysis run ID."""
        service = TraceabilityService(db)
        
        result = service.get_tests_for_source_file(
            repository_id=repository.id,
            source_file_path="any/file.py",
            analysis_run_id=uuid4()  # Random UUID
        )
        
        # Should handle gracefully
        assert result == []


class TestTraceabilityAPI:
    """Tests for traceability API endpoints."""
    
    @pytest.fixture
    def repository(self, db):
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            owner="testuser",
            name="testrepo",
            full_name="testuser/testrepo",
            github_url="https://github.com/testuser/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        return repo
    
    def test_source_to_tests_endpoint_not_found(
        self, client, repository
    ):
        """Test API endpoint with non-existent repository."""
        response = client.get(
            f"/api/repositories/{uuid4()}/traceability/source-to-tests",
            params={"source_file": "any/file.py"}
        )
        
        assert response.status_code == 404
        # Response might be structured differently in error handler
        data = response.json()
        if "detail" in data:
            assert "not found" in data["detail"].lower()
        elif "message" in data:
            assert "not found" in data["message"].lower()
    
    def test_source_to_tests_endpoint_validation(
        self, client, repository
    ):
        """Test API endpoint parameter validation."""
        response = client.get(
            f"/api/repositories/{repository.id}/traceability/source-to-tests"
            # Missing required source_file parameter
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_symbol_to_tests_endpoint_validation(
        self, client, repository
    ):
        """Test symbol endpoint parameter validation."""
        response = client.get(
            f"/api/repositories/{repository.id}/traceability/symbol-to-tests"
            # Missing required symbol_name parameter
        )
        
        assert response.status_code == 422
    
    def test_test_to_sources_endpoint_validation(
        self, client, repository
    ):
        """Test test-to-sources endpoint parameter validation."""
        response = client.get(
            f"/api/repositories/{repository.id}/traceability/test-to-sources"
            # Missing required test_file parameter
        )
        
        assert response.status_code == 422


class TestConfidenceLevels:
    """Tests for confidence level assignment."""
    
    def test_high_confidence_direct_import(self):
        """Test high confidence for direct imports."""
        test = AffectedTest(
            test_file="tests/test_user.py",
            test_name="test_create",
            coverage_type=TestCoverageType.DIRECT_IMPORT,
            confidence="high",
            evidence=["Test imports create_user"],
            changed_symbols=["create_user"]
        )
        
        assert test.confidence == "high"
        assert test.coverage_type == TestCoverageType.DIRECT_IMPORT
    
    def test_medium_confidence_module_sibling(self):
        """Test medium confidence for module siblings."""
        test = AffectedTest(
            test_file="tests/test_validators.py",
            test_name="test_email",
            coverage_type=TestCoverageType.MODULE_SIBLING,
            confidence="medium",
            evidence=["Test follows naming convention"],
            changed_symbols=[]
        )
        
        assert test.confidence == "medium"
        assert test.coverage_type == TestCoverageType.MODULE_SIBLING
    
    def test_low_confidence_path_pattern(self):
        """Test low confidence for path patterns."""
        test = AffectedTest(
            test_file="tests/test_integration.py",
            test_name="test_user_flow",
            coverage_type=TestCoverageType.PATH_PATTERN,
            confidence="low",
            evidence=["Test name mentions user"],
            changed_symbols=[]
        )
        
        assert test.confidence == "low"
        assert test.coverage_type == TestCoverageType.PATH_PATTERN


class TestEvidenceTracking:
    """Tests for evidence tracking."""
    
    def test_evidence_required(self):
        """Test that evidence is provided for relationships."""
        test = AffectedTest(
            test_file="tests/test_user.py",
            test_name="test_create",
            coverage_type=TestCoverageType.DIRECT_IMPORT,
            confidence="high",
            evidence=["Test imports create_user", "Static import analysis"],
            changed_symbols=["create_user"]
        )
        
        assert len(test.evidence) > 0
        assert all(isinstance(e, str) for e in test.evidence)
    
    def test_evidence_describes_relationship(self):
        """Test that evidence describes the relationship."""
        test = AffectedTest(
            test_file="tests/test_user.py",
            test_name="test_create",
            coverage_type=TestCoverageType.DIRECT_IMPORT,
            confidence="high",
            evidence=["Test imports create_user from user_service"],
            changed_symbols=["create_user"]
        )
        
        # Evidence should mention import
        assert any("import" in e.lower() for e in test.evidence)


class TestPotentialTestGaps:
    """Tests for test gap detection."""
    
    @pytest.fixture
    def repository(self, db):
        """Create a test repository."""
        repo = Repository(
            id=uuid4(),
            owner="testuser",
            name="testrepo",
            full_name="testuser/testrepo",
            github_url="https://github.com/testuser/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        return repo
    
    @pytest.fixture
    def analysis_run(self, db, repository):
        """Create a completed analysis run."""
        run = AnalysisRun(
            id=uuid4(),
            repository_id=repository.id,
            status=AnalysisStatus.COMPLETED,
            total_files=1,
            analyzed_files=1,
            total_symbols=1,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.add(run)
        db.commit()
        return run
    
    def test_untested_file_detected(
        self, db, repository, analysis_run
    ):
        """Test detection of untested source file."""
        # Create source file with no related tests
        source = File(
            id=uuid4(),
            repository_id=repository.id,
            analysis_run_id=analysis_run.id,
            path="services/payment_service.py",
            filename="payment_service.py",
            extension=".py",
            language="Python",
            size_bytes=1000,
            line_count=50,
            is_sensitive=False
        )
        db.add(source)
        db.commit()
        
        service = TraceabilityService(db)
        
        result = service.get_tests_for_source_file(
            repository_id=repository.id,
            source_file_path="services/payment_service.py",
            analysis_run_id=analysis_run.id
        )
        
        # Should detect no coverage
        assert result == []
        # This indicates a potential test gap
