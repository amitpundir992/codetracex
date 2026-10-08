"""
Tests for Phase 18: Pull Request & Change Intelligence.

This test suite covers:
- Change detection service
- Symbol change analyzer
- Risk analyzer
- Change impact service (integration)
- API endpoint
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import (
    Repository, AnalysisRun, Commit, CommitFileChange, File, Symbol,
    AnalysisStatus, SymbolType, ChangeType as DBChangeType
)
from app.services.change_detection_service import ChangeDetectionService
from app.services.symbol_change_analyzer import SymbolChangeAnalyzer
from app.services.change_risk_analyzer import ChangeRiskAnalyzer
from app.services.change_impact_service import ChangeImpactService
from app.schemas.change_analysis import (
    ChangeType, ChangedFile, ChangedSymbol, ChangeAnalysisRequest
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_repository(db: Session) -> Repository:
    """Create a sample repository."""
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        full_name="testorg/test-repo",
        owner="testorg",
        github_url="https://github.com/testorg/test-repo",
        description="Test repository",
        default_branch="main",
        stars=100,
        language="Python"
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


@pytest.fixture
def sample_analysis_run(db: Session, sample_repository: Repository) -> AnalysisRun:
    """Create a sample analysis run."""
    analysis = AnalysisRun(
        id=uuid4(),
        repository_id=sample_repository.id,
        status=AnalysisStatus.COMPLETED,
        started_at=datetime.utcnow() - timedelta(hours=1),
        completed_at=datetime.utcnow()
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@pytest.fixture
def sample_commits(db: Session, sample_repository: Repository):
    """Create sample commits with file changes."""
    # Base commit
    base_commit = Commit(
        id=uuid4(),
        repository_id=sample_repository.id,
        commit_hash="abc123def456",
        author_name="Test Author",
        author_email="test@example.com",
        commit_message="Base commit",
        committed_at=datetime.utcnow() - timedelta(days=2)
    )
    db.add(base_commit)
    
    # Head commit with changes
    head_commit = Commit(
        id=uuid4(),
        repository_id=sample_repository.id,
        commit_hash="789ghi012jkl",
        author_name="Test Author",
        author_email="test@example.com",
        commit_message="Head commit with changes",
        committed_at=datetime.utcnow() - timedelta(days=1)
    )
    db.add(head_commit)
    db.commit()
    
    # File changes for head commit
    file_changes = [
        CommitFileChange(
            id=uuid4(),
            commit_id=head_commit.id,
            path="src/services/user_service.py",
            change_type=DBChangeType.MODIFIED,
            additions=25,
            deletions=10
        ),
        CommitFileChange(
            id=uuid4(),
            commit_id=head_commit.id,
            path="src/api/user_routes.py",
            change_type=DBChangeType.MODIFIED,
            additions=5,
            deletions=2
        ),
        CommitFileChange(
            id=uuid4(),
            commit_id=head_commit.id,
            path="tests/test_user_service.py",
            change_type=DBChangeType.ADDED,
            additions=50,
            deletions=0
        )
    ]
    
    for change in file_changes:
        db.add(change)
    
    db.commit()
    
    return {
        'base': base_commit,
        'head': head_commit,
        'changes': file_changes
    }


@pytest.fixture
def sample_files_with_symbols(
    db: Session,
    sample_analysis_run: AnalysisRun
):
    """Create sample files with symbols."""
    # Create files
    file1 = File(
        id=uuid4(),
        repository_id=sample_analysis_run.repository_id,
        analysis_run_id=sample_analysis_run.id,
        path="src/services/user_service.py",
        filename="user_service.py",
        extension=".py",
        language="Python",
        size_bytes=1024,
        line_count=100
    )
    db.add(file1)
    
    file2 = File(
        id=uuid4(),
        repository_id=sample_analysis_run.repository_id,
        analysis_run_id=sample_analysis_run.id,
        path="src/api/user_routes.py",
        filename="user_routes.py",
        extension=".py",
        language="Python",
        size_bytes=512,
        line_count=50
    )
    db.add(file2)
    db.commit()
    
    # Create symbols
    symbols = [
        Symbol(
            id=uuid4(),
            file_id=file1.id,
            analysis_run_id=sample_analysis_run.id,
            name="create_user",
            symbol_type=SymbolType.FUNCTION,
            language="Python",
            start_line=42,
            end_line=50
        ),
        Symbol(
            id=uuid4(),
            file_id=file1.id,
            analysis_run_id=sample_analysis_run.id,
            name="UserService",
            symbol_type=SymbolType.CLASS,
            language="Python",
            start_line=10,
            end_line=40
        ),
        Symbol(
            id=uuid4(),
            file_id=file2.id,
            analysis_run_id=sample_analysis_run.id,
            name="create_user_endpoint",
            symbol_type=SymbolType.FUNCTION,
            language="Python",
            start_line=15,
            end_line=25
        )
    ]
    
    for symbol in symbols:
        db.add(symbol)
    
    db.commit()
    
    return {
        'files': [file1, file2],
        'symbols': symbols
    }


# ============================================================
# ChangeDetectionService Tests
# ============================================================

class TestChangeDetectionService:
    """Tests for ChangeDetectionService."""
    
    def test_get_commit_file_changes(
        self,
        db: Session,
        sample_repository: Repository,
        sample_commits
    ):
        """Test retrieving file changes for a single commit."""
        service = ChangeDetectionService(db)
        
        changes = service.get_commit_file_changes(
            repository_id=sample_repository.id,
            commit_sha="789ghi"  # Abbreviated SHA
        )
        
        assert len(changes) == 3
        assert any(f.path == "src/services/user_service.py" for f in changes)
        assert any(f.is_test for f in changes)
        assert any(f.is_source and not f.is_test for f in changes)
    
    def test_get_commit_file_changes_not_found(
        self,
        db: Session,
        sample_repository: Repository
    ):
        """Test error when commit not found."""
        service = ChangeDetectionService(db)
        
        with pytest.raises(ValueError, match="not found"):
            service.get_commit_file_changes(
                repository_id=sample_repository.id,
                commit_sha="nonexistent"
            )
    
    def test_is_test_file(self, db: Session):
        """Test test file detection."""
        service = ChangeDetectionService(db)
        
        assert service._is_test_file("tests/test_user.py")
        assert service._is_test_file("src/__tests__/user.test.js")
        assert service._is_test_file("spec/user_spec.rb")
        assert not service._is_test_file("src/user.py")
    
    def test_is_source_file(self, db: Session):
        """Test source file detection."""
        service = ChangeDetectionService(db)
        
        assert service._is_source_file("src/user.py", "Python")
        assert service._is_source_file("src/user.js", "JavaScript")
        assert not service._is_source_file("README.md", "Markdown")
        assert not service._is_source_file("config.json", "JSON")


# ============================================================
# SymbolChangeAnalyzer Tests
# ============================================================

class TestSymbolChangeAnalyzer:
    """Tests for SymbolChangeAnalyzer."""
    
    def test_analyze_symbol_changes_modified_file(
        self,
        db: Session,
        sample_repository: Repository,
        sample_files_with_symbols
    ):
        """Test analyzing symbol changes for modified files."""
        analyzer = SymbolChangeAnalyzer(db)
        
        changed_files = [
            ChangedFile(
                path="src/services/user_service.py",
                change_type=ChangeType.MODIFIED,
                additions=25,
                deletions=10,
                is_source=True,
                is_test=False,
                language="Python"
            )
        ]
        
        changed_symbols = analyzer.analyze_symbol_changes(
            repository_id=sample_repository.id,
            changed_files=changed_files
        )
        
        # Should mark symbols as potentially modified
        assert len(changed_symbols) > 0
        assert all(s.change_type == ChangeType.MODIFIED for s in changed_symbols)
    
    def test_analyze_symbol_changes_added_file(
        self,
        db: Session,
        sample_repository: Repository,
        sample_files_with_symbols
    ):
        """Test analyzing symbol changes for added files."""
        analyzer = SymbolChangeAnalyzer(db)
        
        changed_files = [
            ChangedFile(
                path="src/api/user_routes.py",
                change_type=ChangeType.ADDED,
                additions=50,
                deletions=0,
                is_source=True,
                is_test=False,
                language="Python"
            )
        ]
        
        changed_symbols = analyzer.analyze_symbol_changes(
            repository_id=sample_repository.id,
            changed_files=changed_files
        )
        
        # Should mark symbols as added
        assert len(changed_symbols) > 0
        assert all(s.change_type == ChangeType.ADDED for s in changed_symbols)
    
    def test_is_public_symbol(self, db: Session):
        """Test public symbol detection."""
        analyzer = SymbolChangeAnalyzer(db)
        
        # Create test symbols
        public_symbol = Symbol(
            id=uuid4(),
            file_id=uuid4(),
            analysis_run_id=uuid4(),
            name="public_function",
            symbol_type=SymbolType.FUNCTION,
            language="Python",
            start_line=1,
            end_line=10
        )
        
        private_symbol = Symbol(
            id=uuid4(),
            file_id=uuid4(),
            analysis_run_id=uuid4(),
            name="_private_function",
            symbol_type=SymbolType.FUNCTION,
            language="Python",
            start_line=1,
            end_line=10
        )
        
        assert analyzer._is_public_symbol(public_symbol)
        assert not analyzer._is_public_symbol(private_symbol)


# ============================================================
# ChangeRiskAnalyzer Tests
# ============================================================

class TestChangeRiskAnalyzer:
    """Tests for ChangeRiskAnalyzer."""
    
    def test_analyze_risk_security_files(self, db: Session):
        """Test risk analysis for security-related files."""
        analyzer = ChangeRiskAnalyzer(db)
        
        changed_files = [
            ChangedFile(
                path="src/auth/authentication.py",
                change_type=ChangeType.MODIFIED,
                additions=25,
                deletions=10,
                is_source=True,
                is_test=False,
                language="Python"
            )
        ]
        
        risk = analyzer.analyze_risk(
            repository_id=uuid4(),
            changed_files=changed_files,
            changed_symbols=[],
            affected_endpoints=[],
            affected_workflows=[],
            dependency_impact={}
        )
        
        assert risk.risk_level in ["medium", "high", "critical"]
        assert any(s.signal_type == "security_code_change" for s in risk.signals)
    
    def test_analyze_risk_many_files(self, db: Session):
        """Test risk analysis for many changed files."""
        analyzer = ChangeRiskAnalyzer(db)
        
        # Create 15 changed files (above threshold)
        changed_files = [
            ChangedFile(
                path=f"src/file_{i}.py",
                change_type=ChangeType.MODIFIED,
                additions=10,
                deletions=5,
                is_source=True,
                is_test=False,
                language="Python"
            )
            for i in range(15)
        ]
        
        risk = analyzer.analyze_risk(
            repository_id=uuid4(),
            changed_files=changed_files,
            changed_symbols=[],
            affected_endpoints=[],
            affected_workflows=[],
            dependency_impact={}
        )
        
        assert any(s.signal_type == "many_files_changed" for s in risk.signals)
    
    def test_analyze_risk_low_risk(self, db: Session):
        """Test risk analysis for low-risk changes."""
        analyzer = ChangeRiskAnalyzer(db)
        
        changed_files = [
            ChangedFile(
                path="src/utils/helper.py",
                change_type=ChangeType.MODIFIED,
                additions=5,
                deletions=2,
                is_source=True,
                is_test=False,
                language="Python"
            )
        ]
        
        risk = analyzer.analyze_risk(
            repository_id=uuid4(),
            changed_files=changed_files,
            changed_symbols=[],
            affected_endpoints=[],
            affected_workflows=[],
            dependency_impact={}
        )
        
        assert risk.risk_level == "low"
        assert risk.risk_score < 31


# ============================================================
# ChangeImpactService Integration Tests
# ============================================================

class TestChangeImpactService:
    """Integration tests for ChangeImpactService."""
    
    def test_analyze_change_impact_single_commit(
        self,
        db: Session,
        sample_repository: Repository,
        sample_commits,
        sample_files_with_symbols
    ):
        """Test full change impact analysis for single commit."""
        service = ChangeImpactService(db)
        
        result = service.analyze_change_impact(
            repository_id=sample_repository.id,
            commit_sha="789ghi",
            max_depth=3,
            include_tests=True,
            include_workflows=False  # Skip workflows for faster test
        )
        
        assert 'metadata' in result
        assert 'changed_files' in result
        assert 'changed_symbols' in result
        assert 'risk' in result
        assert 'evidence' in result
        
        assert result['metadata']['files_changed'] > 0
        assert result['risk'].risk_level in ["low", "medium", "high", "critical"]
    
    def test_analyze_change_impact_invalid_commit(
        self,
        db: Session,
        sample_repository: Repository
    ):
        """Test error handling for invalid commit."""
        service = ChangeImpactService(db)
        
        with pytest.raises(ValueError, match="not found"):
            service.analyze_change_impact(
                repository_id=sample_repository.id,
                commit_sha="nonexistent"
            )


# ============================================================
# API Endpoint Tests
# ============================================================

class TestChangeAnalysisAPI:
    """Tests for change analysis API endpoint."""
    
    def test_validate_input_mode_success(self):
        """Test input mode validation with valid input."""
        from app.api.change_analysis import _validate_input_mode, ChangeInputType
        
        # Test commit range
        request = ChangeAnalysisRequest(
            base_sha="abc123def",
            head_sha="def456ghi"
        )
        assert _validate_input_mode(request) == ChangeInputType.COMMIT_RANGE
        
        # Test single commit
        request = ChangeAnalysisRequest(commit_sha="abc123def")
        assert _validate_input_mode(request) == ChangeInputType.SINGLE_COMMIT
        
        # Test pull request
        request = ChangeAnalysisRequest(pull_request_number=123)
        assert _validate_input_mode(request) == ChangeInputType.PULL_REQUEST
    
    def test_validate_input_mode_no_input(self):
        """Test input mode validation with no input."""
        from app.api.change_analysis import _validate_input_mode
        from fastapi import HTTPException
        
        request = ChangeAnalysisRequest()
        
        with pytest.raises(HTTPException) as exc_info:
            _validate_input_mode(request)
        
        assert exc_info.value.status_code == 400
    
    def test_validate_input_mode_multiple_inputs(self):
        """Test input mode validation with multiple inputs."""
        from app.api.change_analysis import _validate_input_mode
        from fastapi import HTTPException
        
        request = ChangeAnalysisRequest(
            base_sha="abc123def",
            head_sha="def456ghi",
            commit_sha="ghi789jkl"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            _validate_input_mode(request)
        
        assert exc_info.value.status_code == 400


# ============================================================
# Integration: Full Flow Test
# ============================================================

class TestFullChangeAnalysisFlow:
    """Integration test for full change analysis flow."""
    
    def test_full_flow(
        self,
        db: Session,
        sample_repository: Repository,
        sample_commits,
        sample_files_with_symbols
    ):
        """Test complete change analysis flow from detection to risk."""
        # Step 1: Change detection
        change_detection = ChangeDetectionService(db)
        changed_files, metadata = change_detection.detect_changes(
            repository_id=sample_repository.id,
            commit_sha="789ghi"
        )
        
        assert len(changed_files) > 0
        assert metadata['files_changed'] > 0
        
        # Step 2: Symbol analysis
        symbol_analyzer = SymbolChangeAnalyzer(db)
        changed_symbols = symbol_analyzer.analyze_symbol_changes(
            repository_id=sample_repository.id,
            changed_files=changed_files
        )
        
        # Step 3: Risk analysis
        risk_analyzer = ChangeRiskAnalyzer(db)
        risk = risk_analyzer.analyze_risk(
            repository_id=sample_repository.id,
            changed_files=changed_files,
            changed_symbols=changed_symbols,
            affected_endpoints=[],
            affected_workflows=[],
            dependency_impact={}
        )
        
        assert risk.risk_score >= 0
        assert risk.risk_score <= 100
        assert risk.risk_level in ["low", "medium", "high", "critical"]
