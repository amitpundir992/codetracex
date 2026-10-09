"""
Tests for Phase 19: CI & Test Intelligence.

This test suite covers:
- Test detection service
- Test coverage analyzer
- CI intelligence service
- Test recommendation service
- API endpoints
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import (
    Repository, AnalysisRun, Commit, CommitFileChange, File, Symbol, Import,
    AnalysisStatus, SymbolType, ChangeType as DBChangeType
)
from app.services.test_detection_service import TestDetectionService
from app.services.test_coverage_analyzer import TestCoverageAnalyzer
from app.services.ci_intelligence_service import CIIntelligenceService
from app.services.test_recommendation_service import TestRecommendationService
from app.schemas.change_analysis import ChangedFile, ChangedSymbol, ChangeType
from app.schemas.test_intelligence import (
    TestFramework, TestType, TestCoverageType
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
        description="Test repository with tests",
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
        completed_at=datetime.utcnow(),
        total_files=10,
        analyzed_files=10
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@pytest.fixture
def sample_test_files(db: Session, sample_analysis_run: AnalysisRun):
    """Create sample test files with symbols."""
    # Test file 1: pytest-style tests
    test_file1 = File(
        id=uuid4(),
        repository_id=sample_analysis_run.repository_id,
        analysis_run_id=sample_analysis_run.id,
        path="tests/test_user_service.py",
        filename="test_user_service.py",
        extension=".py",
        language="Python",
        size_bytes=1024,
        line_count=50
    )
    db.add(test_file1)
    
    # Test file 2: another test file
    test_file2 = File(
        id=uuid4(),
        repository_id=sample_analysis_run.repository_id,
        analysis_run_id=sample_analysis_run.id,
        path="tests/test_auth.py",
        filename="test_auth.py",
        extension=".py",
        language="Python",
        size_bytes=512,
        line_count=30
    )
    db.add(test_file2)
    
    # Source file
    source_file = File(
        id=uuid4(),
        repository_id=sample_analysis_run.repository_id,
        analysis_run_id=sample_analysis_run.id,
        path="src/services/user_service.py",
        filename="user_service.py",
        extension=".py",
        language="Python",
        size_bytes=2048,
        line_count=100
    )
    db.add(source_file)
    
    db.commit()
    
    # Add test symbols to test_file1
    test_symbols = [
        Symbol(
            id=uuid4(),
            file_id=test_file1.id,
            analysis_run_id=sample_analysis_run.id,
            name="test_create_user",
            symbol_type=SymbolType.FUNCTION,
            language="Python",
            start_line=10,
            end_line=20
        ),
        Symbol(
            id=uuid4(),
            file_id=test_file1.id,
            analysis_run_id=sample_analysis_run.id,
            name="test_update_user",
            symbol_type=SymbolType.FUNCTION,
            language="Python",
            start_line=22,
            end_line=30
        )
    ]
    
    for symbol in test_symbols:
        db.add(symbol)
    
    # Add source symbol
    source_symbol = Symbol(
        id=uuid4(),
        file_id=source_file.id,
        analysis_run_id=sample_analysis_run.id,
        name="create_user",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=15,
        end_line=25
    )
    db.add(source_symbol)
    
    db.commit()
    
    # Add imports
    imports = [
        Import(
            id=uuid4(),
            file_id=test_file1.id,
            analysis_run_id=sample_analysis_run.id,
            source="services.user_service",
            imported_names="create_user",
            line_number=1
        ),
        Import(
            id=uuid4(),
            file_id=test_file1.id,
            analysis_run_id=sample_analysis_run.id,
            source="pytest",
            imported_names="",
            line_number=2
        )
    ]
    
    for imp in imports:
        db.add(imp)
    
    db.commit()
    
    return {
        'test_file1': test_file1,
        'test_file2': test_file2,
        'source_file': source_file,
        'test_symbols': test_symbols,
        'source_symbol': source_symbol
    }


@pytest.fixture
def sample_commits(db: Session, sample_repository: Repository):
    """Create sample commits."""
    base_commit = Commit(
        id=uuid4(),
        repository_id=sample_repository.id,
        commit_hash="base123",
        author_name="Test Author",
        author_email="test@example.com",
        commit_message="Base commit",
        committed_at=datetime.utcnow() - timedelta(days=2)
    )
    db.add(base_commit)
    
    head_commit = Commit(
        id=uuid4(),
        repository_id=sample_repository.id,
        commit_hash="head456",
        author_name="Test Author",
        author_email="test@example.com",
        commit_message="Changed user service",
        committed_at=datetime.utcnow() - timedelta(days=1)
    )
    db.add(head_commit)
    
    db.commit()
    
    # File change
    file_change = CommitFileChange(
        id=uuid4(),
        commit_id=head_commit.id,
        path="src/services/user_service.py",
        change_type=DBChangeType.MODIFIED,
        additions=10,
        deletions=5
    )
    db.add(file_change)
    db.commit()
    
    return {'base': base_commit, 'head': head_commit}


@pytest.fixture
def sample_ci_workflow_file(db: Session, sample_analysis_run: AnalysisRun):
    """Create a sample CI workflow file."""
    workflow_file = File(
        id=uuid4(),
        repository_id=sample_analysis_run.repository_id,
        analysis_run_id=sample_analysis_run.id,
        path=".github/workflows/ci.yml",
        filename="ci.yml",
        extension=".yml",
        language="YAML",
        size_bytes=512,
        line_count=30
    )
    db.add(workflow_file)
    db.commit()
    db.refresh(workflow_file)
    return workflow_file


# ============================================================
# Test Detection Service Tests
# ============================================================

def test_is_test_file(db: Session):
    """Test test file detection."""
    service = TestDetectionService(db)
    
    # Test files
    assert service.is_test_file("tests/test_user.py")
    assert service.is_test_file("test_auth.py")
    assert service.is_test_file("user.test.js")
    assert service.is_test_file("auth.spec.ts")
    assert service.is_test_file("__tests__/user.js")
    
    # Not test files
    assert not service.is_test_file("src/user.py")
    assert not service.is_test_file("models/auth.py")
    assert not service.is_test_file("config.yml")


def test_is_test_symbol(db: Session, sample_test_files):
    """Test test symbol detection."""
    service = TestDetectionService(db)
    
    test_symbol = sample_test_files['test_symbols'][0]
    source_symbol = sample_test_files['source_symbol']
    
    assert service.is_test_symbol(test_symbol)
    assert not service.is_test_symbol(source_symbol)


def test_detect_framework(db: Session, sample_test_files):
    """Test framework detection."""
    service = TestDetectionService(db)
    
    # Get imports for test file
    test_file = sample_test_files['test_file1']
    imports = db.query(Import).filter(Import.file_id == test_file.id).all()
    
    framework = service.detect_framework(imports, "Python")
    assert framework == TestFramework.PYTEST


def test_classify_test_type(db: Session):
    """Test test type classification."""
    service = TestDetectionService(db)
    
    # Unit test
    assert service.classify_test_type("test_create_user", "tests/unit/test_user.py") == TestType.UNIT
    
    # Integration test
    assert service.classify_test_type("test_integration_flow", "tests/integration/test_api.py") == TestType.INTEGRATION
    
    # E2E test
    assert service.classify_test_type("test_e2e_user_flow", "tests/e2e/test_flow.py") == TestType.E2E


def test_get_test_files(
    db: Session,
    sample_repository: Repository,
    sample_analysis_run: AnalysisRun,
    sample_test_files
):
    """Test getting all test files."""
    service = TestDetectionService(db)
    
    test_files = service.get_test_files(
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis_run.id
    )
    
    assert len(test_files) == 2
    assert any(tf.file_path == "tests/test_user_service.py" for tf in test_files)
    assert any(tf.file_path == "tests/test_auth.py" for tf in test_files)
    
    # Check test file with symbols
    user_test = next(tf for tf in test_files if tf.file_path == "tests/test_user_service.py")
    assert user_test.test_count == 2
    assert user_test.framework == TestFramework.PYTEST
    assert len(user_test.test_cases) == 2


def test_get_tests_importing_symbol(
    db: Session,
    sample_repository: Repository,
    sample_analysis_run: AnalysisRun,
    sample_test_files
):
    """Test finding tests that import a specific symbol."""
    service = TestDetectionService(db)
    
    tests = service.get_tests_importing_symbol(
        repository_id=sample_repository.id,
        symbol_name="create_user",
        analysis_run_id=sample_analysis_run.id
    )
    
    assert len(tests) == 1
    assert tests[0].file_path == "tests/test_user_service.py"


# ============================================================
# Test Coverage Analyzer Tests
# ============================================================

def test_analyze_test_coverage(
    db: Session,
    sample_repository: Repository,
    sample_analysis_run: AnalysisRun,
    sample_test_files
):
    """Test comprehensive test coverage analysis."""
    analyzer = TestCoverageAnalyzer(db)
    
    # Create changed files and symbols
    changed_files = [
        ChangedFile(
            path="src/services/user_service.py",
            change_type=ChangeType.MODIFIED,
            additions=10,
            deletions=5,
            is_test=False,
            is_source=True,
            language="Python"
        )
    ]
    
    changed_symbols = [
        ChangedSymbol(
            name="create_user",
            qualified_name="src/services/user_service.py:create_user",
            symbol_type="function",
            change_type=ChangeType.MODIFIED,
            file_path="src/services/user_service.py",
            line_number=15,
            is_public=True
        )
    ]
    
    affected_tests, uncovered_areas = analyzer.analyze_test_coverage(
        repository_id=sample_repository.id,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        analysis_run_id=sample_analysis_run.id
    )
    
    # Should find tests that import create_user
    assert len(affected_tests) > 0
    high_confidence = [t for t in affected_tests if t.confidence == "high"]
    assert len(high_confidence) > 0
    
    # Check coverage type
    direct_import_tests = [
        t for t in affected_tests
        if t.coverage_type == TestCoverageType.DIRECT_IMPORT
    ]
    assert len(direct_import_tests) > 0


def test_identify_uncovered_areas(
    db: Session,
    sample_repository: Repository,
    sample_analysis_run: AnalysisRun
):
    """Test identification of uncovered areas."""
    analyzer = TestCoverageAnalyzer(db)
    
    # Changed symbols with no test coverage
    changed_files = [
        ChangedFile(
            path="src/services/payment_service.py",
            change_type=ChangeType.MODIFIED,
            additions=20,
            deletions=0,
            is_test=False,
            is_source=True,
            language="Python"
        )
    ]
    
    changed_symbols = [
        ChangedSymbol(
            name="process_payment",
            qualified_name="src/services/payment_service.py:process_payment",
            symbol_type="function",
            change_type=ChangeType.ADDED,
            file_path="src/services/payment_service.py",
            line_number=10,
            is_public=True
        )
    ]
    
    affected_tests, uncovered_areas = analyzer.analyze_test_coverage(
        repository_id=sample_repository.id,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        analysis_run_id=sample_analysis_run.id
    )
    
    # Should identify uncovered area
    assert len(uncovered_areas) > 0
    assert uncovered_areas[0].file_path == "src/services/payment_service.py"
    assert "process_payment" in uncovered_areas[0].changed_symbols


def test_file_path_to_module(db: Session):
    """Test file path to module name conversion."""
    analyzer = TestCoverageAnalyzer(db)
    
    assert analyzer._file_path_to_module("src/services/user_service.py") == "src.services.user_service"
    assert analyzer._file_path_to_module("app/main.py") == "app.main"


def test_are_module_siblings(db: Session):
    """Test module sibling detection."""
    analyzer = TestCoverageAnalyzer(db)
    
    # Matching patterns
    assert analyzer._are_module_siblings("tests/test_user.py", "src/user.py")
    assert analyzer._are_module_siblings("src/user.test.ts", "src/user.ts")
    assert analyzer._are_module_siblings("tests/test_auth_service.py", "src/auth_service.py")
    
    # Non-matching
    assert not analyzer._are_module_siblings("tests/test_user.py", "src/payment.py")


# ============================================================
# CI Intelligence Service Tests
# ============================================================

def test_is_ci_workflow_file(db: Session):
    """Test CI workflow file detection."""
    service = CIIntelligenceService(db)
    
    # GitHub Actions
    assert service.is_ci_workflow_file(".github/workflows/ci.yml")
    assert service.is_ci_workflow_file(".github/workflows/test.yaml")
    
    # GitLab CI
    assert service.is_ci_workflow_file(".gitlab-ci.yml")
    
    # CircleCI
    assert service.is_ci_workflow_file(".circleci/config.yml")
    
    # Not CI files
    assert not service.is_ci_workflow_file("config.yml")
    assert not service.is_ci_workflow_file("src/main.py")


def test_extract_test_commands(db: Session):
    """Test test command extraction."""
    service = CIIntelligenceService(db)
    
    content = """
    name: CI
    on: push
    jobs:
      test:
        runs-on: ubuntu-latest
        steps:
          - run: pytest tests/
          - run: npm test
          - run: echo "done"
    """
    
    commands = service.extract_test_commands(content)
    
    assert len(commands) >= 2
    assert any('pytest' in cmd for cmd in commands)
    assert any('npm test' in cmd for cmd in commands)


def test_get_ci_jobs(
    db: Session,
    sample_repository: Repository,
    sample_analysis_run: AnalysisRun,
    sample_ci_workflow_file
):
    """Test getting CI jobs."""
    service = CIIntelligenceService(db)
    
    ci_jobs = service.get_ci_jobs(
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis_run.id
    )
    
    assert len(ci_jobs) > 0
    assert ci_jobs[0].workflow_file == ".github/workflows/ci.yml"
    assert ci_jobs[0].runs_tests


def test_get_relevant_ci_checks(
    db: Session,
    sample_repository: Repository,
    sample_analysis_run: AnalysisRun,
    sample_ci_workflow_file
):
    """Test getting relevant CI checks."""
    service = CIIntelligenceService(db)
    
    changed_files = [
        ChangedFile(
            path="src/services/user_service.py",
            change_type=ChangeType.MODIFIED,
            additions=10,
            deletions=5,
            is_test=False,
            is_source=True,
            language="Python"
        )
    ]
    
    relevant_checks = service.get_relevant_ci_checks(
        repository_id=sample_repository.id,
        changed_files=changed_files,
        analysis_run_id=sample_analysis_run.id
    )
    
    assert len(relevant_checks) > 0
    assert relevant_checks[0].runs_affected_tests


# ============================================================
# Test Recommendation Service Tests
# ============================================================

def test_analyze_test_intelligence(
    db: Session,
    sample_repository: Repository,
    sample_commits,
    sample_test_files,
    sample_ci_workflow_file
):
    """Test comprehensive test intelligence analysis."""
    service = TestRecommendationService(db)
    
    # Create changed files and symbols
    changed_files = [
        ChangedFile(
            path="src/services/user_service.py",
            change_type=ChangeType.MODIFIED,
            additions=10,
            deletions=5,
            is_test=False,
            is_source=True,
            language="Python"
        )
    ]
    
    changed_symbols = [
        ChangedSymbol(
            name="create_user",
            qualified_name="src/services/user_service.py:create_user",
            symbol_type="function",
            change_type=ChangeType.MODIFIED,
            file_path="src/services/user_service.py",
            line_number=15,
            is_public=True
        )
    ]
    
    result = service.analyze_test_intelligence(
        repository_id=sample_repository.id,
        base_sha=sample_commits['base'].commit_hash,
        head_sha=sample_commits['head'].commit_hash,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        include_ci_analysis=True,
        include_local_recommendations=True
    )
    
    # Validate response
    assert result.base_sha == sample_commits['base'].commit_hash
    assert result.head_sha == sample_commits['head'].commit_hash
    assert result.total_test_files > 0
    assert len(result.affected_tests) > 0
    assert len(result.local_test_recommendations) > 0
    assert result.summary != ""


def test_build_local_recommendations(
    db: Session,
    sample_test_files
):
    """Test local test recommendation building."""
    service = TestRecommendationService(db)
    
    from app.schemas.test_intelligence import AffectedTest
    
    affected_tests = [
        AffectedTest(
            test_file="tests/test_user_service.py",
            test_name="test_create_user",
            coverage_type=TestCoverageType.DIRECT_IMPORT,
            confidence="high",
            evidence=["Test imports create_user"],
            changed_symbols=["create_user"]
        )
    ]
    
    changed_files = [
        ChangedFile(
            path="src/services/user_service.py",
            change_type=ChangeType.MODIFIED,
            additions=10,
            deletions=5,
            is_test=False,
            is_source=True,
            language="Python"
        )
    ]
    
    recommendations = service._build_local_recommendations(
        affected_tests,
        changed_files
    )
    
    assert len(recommendations) > 0
    assert recommendations[0].priority == "high"
    assert "pytest" in recommendations[0].command


def test_suggest_test_command(db: Session):
    """Test test command suggestion."""
    service = TestRecommendationService(db)
    
    assert "pytest" in service._suggest_test_command("tests/test_user.py")
    assert "npm test" in service._suggest_test_command("tests/user.test.js")
    assert "go test" in service._suggest_test_command("user_test.go")


def test_group_test_files_by_type(db: Session):
    """Test test file grouping."""
    service = TestRecommendationService(db)
    
    test_files = [
        "tests/test_user.py",
        "tests/test_auth.py",
        "tests/user.test.js",
        "tests/auth.test.ts"
    ]
    
    grouped = service._group_test_files_by_type(test_files)
    
    assert "python" in grouped
    assert "javascript" in grouped
    assert "typescript" in grouped
    assert len(grouped["python"]) == 2


# ============================================================
# Integration Tests
# ============================================================

def test_end_to_end_test_intelligence(
    db: Session,
    sample_repository: Repository,
    sample_analysis_run: AnalysisRun,
    sample_commits,
    sample_test_files,
    sample_ci_workflow_file
):
    """Test complete test intelligence flow."""
    # 1. Detect tests
    test_service = TestDetectionService(db)
    test_files = test_service.get_test_files(
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis_run.id
    )
    assert len(test_files) > 0
    
    # 2. Analyze coverage
    analyzer = TestCoverageAnalyzer(db)
    changed_files = [
        ChangedFile(
            path="src/services/user_service.py",
            change_type=ChangeType.MODIFIED,
            additions=10,
            deletions=5,
            is_test=False,
            is_source=True,
            language="Python"
        )
    ]
    changed_symbols = [
        ChangedSymbol(
            name="create_user",
            qualified_name="src/services/user_service.py:create_user",
            symbol_type="function",
            change_type=ChangeType.MODIFIED,
            file_path="src/services/user_service.py",
            line_number=15,
            is_public=True
        )
    ]
    affected_tests, uncovered_areas = analyzer.analyze_test_coverage(
        repository_id=sample_repository.id,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        analysis_run_id=sample_analysis_run.id
    )
    assert len(affected_tests) > 0
    
    # 3. Analyze CI
    ci_service = CIIntelligenceService(db)
    ci_analysis = ci_service.analyze_ci_for_changes(
        repository_id=sample_repository.id,
        changed_files=changed_files,
        analysis_run_id=sample_analysis_run.id
    )
    assert len(ci_analysis['ci_jobs']) > 0
    
    # 4. Build recommendations
    recommendation_service = TestRecommendationService(db)
    result = recommendation_service.analyze_test_intelligence(
        repository_id=sample_repository.id,
        base_sha=sample_commits['base'].commit_hash,
        head_sha=sample_commits['head'].commit_hash,
        changed_files=changed_files,
        changed_symbols=changed_symbols
    )
    
    # Validate complete response
    assert result.total_test_files > 0
    assert len(result.affected_tests) > 0
    assert len(result.local_test_recommendations) > 0
    assert len(result.evidence) > 0
    assert result.summary != ""
