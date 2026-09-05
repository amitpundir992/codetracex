"""
Tests for persistence service.

These tests verify the PersistenceService correctly saves and retrieves
analysis results from the database.
"""
# Load environment variables before any other imports
from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.services.persistence_service import PersistenceService
from app.db.models import Repository, AnalysisRun, AnalysisStatus, Symbol, SymbolType
from app.db.session import SessionLocal, engine, Base
from app.services.static_analyzer import (
    StaticAnalysisResult,
    AnalysisSummary,
    Symbol as SymbolSchema,
    Import as ImportSchema,
    Call as CallSchema
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def persistence_service(db_session: Session) -> PersistenceService:
    """Create a persistence service instance."""
    return PersistenceService(db_session)


@pytest.fixture
def sample_static_analysis() -> StaticAnalysisResult:
    """Create sample static analysis results."""
    return StaticAnalysisResult(
        summary=AnalysisSummary(
            total_files=10,
            analyzed_files=8,
            skipped_files=1,
            failed_files=1,
            total_symbols=50,
            symbols_by_type={"function": 30, "class": 15, "method": 5},
            total_imports=20,
            total_calls=100
        ),
        all_symbols=[
            SymbolSchema(
                name="calculate_sum",
                type="function",
                language="Python",
                file="src/utils.py",
                start_line=10,
                end_line=15,
                parent=None
            ),
            SymbolSchema(
                name="Calculator",
                type="class",
                language="Python",
                file="src/calculator.py",
                start_line=1,
                end_line=20,
                parent=None
            ),
            SymbolSchema(
                name="add",
                type="method",
                language="Python",
                file="src/calculator.py",
                start_line=5,
                end_line=7,
                parent="Calculator"
            )
        ],
        all_imports=[
            ImportSchema(
                file="src/app.py",
                source="flask",
                names=["Flask", "request"],
                line=1
            ),
            ImportSchema(
                file="src/utils.py",
                source="typing",
                names=["List", "Dict"],
                line=1
            )
        ],
        all_calls=[
            CallSchema(
                file="src/main.py",
                caller="main",
                callee="process_data",
                line=25
            )
        ]
    )


@pytest.fixture
def sample_file_metadata() -> List[Dict[str, Any]]:
    """Create sample file metadata."""
    return [
        {
            "path": "src/app.py",
            "filename": "app.py",
            "extension": ".py",
            "language": "Python",
            "size_bytes": 1523,
            "lines": 45,
            "is_sensitive": False
        },
        {
            "path": "src/utils.py",
            "filename": "utils.py",
            "extension": ".py",
            "language": "Python",
            "size_bytes": 890,
            "lines": 30,
            "is_sensitive": False
        },
        {
            "path": ".env",
            "filename": ".env",
            "extension": ".env",
            "language": None,
            "size_bytes": 256,
            "lines": 10,
            "is_sensitive": True
        }
    ]


class TestRepositoryPersistence:
    """Tests for repository creation and retrieval."""
    
    def test_create_repository(self, persistence_service: PersistenceService, db_session: Session):
        """Test creating a new repository."""
        repo = persistence_service.create_or_get_repository(
            owner="facebook",
            name="react",
            github_url="https://github.com/facebook/react",
            default_branch="main",
            description="The library for web and native user interfaces.",
            language="JavaScript",
            stars=100000
        )
        
        assert repo.id is not None
        assert repo.owner == "facebook"
        assert repo.name == "react"
        assert repo.full_name == "facebook/react"
        assert repo.github_url == "https://github.com/facebook/react"
        assert repo.stars == 100000
    
    def test_get_existing_repository(self, persistence_service: PersistenceService, db_session: Session):
        """Test that create_or_get_repository returns existing repository."""
        # Create repository first time
        repo1 = persistence_service.create_or_get_repository(
            owner="openai",
            name="gpt-3",
            github_url="https://github.com/openai/gpt-3",
            default_branch="main"
        )
        
        repo1_id = repo1.id
        
        # Try to create same repository again
        repo2 = persistence_service.create_or_get_repository(
            owner="openai",
            name="gpt-3",
            github_url="https://github.com/openai/gpt-3",
            default_branch="main"
        )
        
        # Should return the same repository
        assert repo2.id == repo1_id
        assert repo2.full_name == "openai/gpt-3"
    
    def test_update_repository_metadata(self, persistence_service: PersistenceService, db_session: Session):
        """Test that repository metadata is updated on subsequent calls."""
        # Create with initial metadata
        repo1 = persistence_service.create_or_get_repository(
            owner="google",
            name="tensorflow",
            github_url="https://github.com/google/tensorflow",
            default_branch="master",
            stars=50000
        )
        
        # Update with new metadata
        repo2 = persistence_service.create_or_get_repository(
            owner="google",
            name="tensorflow",
            github_url="https://github.com/google/tensorflow",
            default_branch="master",
            stars=55000  # Updated star count
        )
        
        # Should be same repository with updated data
        assert repo2.id == repo1.id
        assert repo2.stars == 55000


class TestAnalysisRunPersistence:
    """Tests for analysis run creation and updates."""
    
    def test_create_analysis_run(self, persistence_service: PersistenceService, db_session: Session):
        """Test creating an analysis run."""
        # Create repository first
        repo = persistence_service.create_or_get_repository(
            owner="microsoft",
            name="vscode",
            github_url="https://github.com/microsoft/vscode",
            default_branch="main"
        )
        
        # Create analysis run
        analysis = persistence_service.create_analysis_run(repo)
        
        assert analysis.id is not None
        assert analysis.repository_id == repo.id
        assert analysis.status == AnalysisStatus.RUNNING
        assert analysis.started_at is not None
        assert analysis.completed_at is None
    
    def test_mark_analysis_completed(self, persistence_service: PersistenceService, db_session: Session):
        """Test marking an analysis as completed."""
        repo = persistence_service.create_or_get_repository(
            owner="django",
            name="django",
            github_url="https://github.com/django/django",
            default_branch="main"
        )
        
        analysis = persistence_service.create_analysis_run(repo)
        
        # Mark as completed
        persistence_service.mark_analysis_completed(
            analysis,
            total_files=100,
            analyzed_files=95,
            total_symbols=500,
            total_imports=150,
            total_calls=300
        )
        
        db_session.refresh(analysis)
        
        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.completed_at is not None
        assert analysis.total_files == 100
        assert analysis.analyzed_files == 95
        assert analysis.total_symbols == 500
    
    def test_mark_analysis_failed(self, persistence_service: PersistenceService, db_session: Session):
        """Test marking an analysis as failed."""
        repo = persistence_service.create_or_get_repository(
            owner="python",
            name="cpython",
            github_url="https://github.com/python/cpython",
            default_branch="main"
        )
        
        analysis = persistence_service.create_analysis_run(repo)
        
        # Mark as failed
        persistence_service.mark_analysis_failed(
            analysis,
            "Failed to download repository: Connection timeout"
        )
        
        db_session.refresh(analysis)
        
        assert analysis.status == AnalysisStatus.FAILED
        assert analysis.completed_at is not None
        assert "Connection timeout" in analysis.error_message


class TestFullAnalysisPersistence:
    """Tests for persisting complete analysis results."""
    
    def test_persist_analysis_result(
        self,
        persistence_service: PersistenceService,
        db_session: Session,
        sample_static_analysis: StaticAnalysisResult,
        sample_file_metadata: List[Dict[str, Any]]
    ):
        """Test persisting a complete analysis result."""
        # Create repository and analysis run
        repo = persistence_service.create_or_get_repository(
            owner="nodejs",
            name="node",
            github_url="https://github.com/nodejs/node",
            default_branch="main"
        )
        
        analysis = persistence_service.create_analysis_run(repo)
        
        # Persist the analysis result
        persistence_service.persist_analysis_result(
            repository=repo,
            analysis_run=analysis,
            static_analysis=sample_static_analysis,
            file_metadata=sample_file_metadata
        )
        
        # Verify analysis was marked as completed
        db_session.refresh(analysis)
        assert analysis.status == AnalysisStatus.COMPLETED
        assert analysis.total_files == 3
        assert analysis.total_symbols == 3
        assert analysis.total_imports == 2
        assert analysis.total_calls == 1
    
    def test_persist_files(
        self,
        persistence_service: PersistenceService,
        db_session: Session,
        sample_static_analysis: StaticAnalysisResult,
        sample_file_metadata: List[Dict[str, Any]]
    ):
        """Test that files are persisted correctly."""
        repo = persistence_service.create_or_get_repository(
            owner="rust-lang",
            name="rust",
            github_url="https://github.com/rust-lang/rust",
            default_branch="master"
        )
        
        analysis = persistence_service.create_analysis_run(repo)
        
        persistence_service.persist_analysis_result(
            repository=repo,
            analysis_run=analysis,
            static_analysis=sample_static_analysis,
            file_metadata=sample_file_metadata
        )
        
        # Query files
        from app.db.models import File
        files = db_session.query(File).filter_by(analysis_run_id=analysis.id).all()
        
        assert len(files) == 3
        assert any(f.filename == "app.py" for f in files)
        assert any(f.is_sensitive for f in files)  # .env file
    
    def test_persist_symbols(
        self,
        persistence_service: PersistenceService,
        db_session: Session,
        sample_static_analysis: StaticAnalysisResult,
        sample_file_metadata: List[Dict[str, Any]]
    ):
        """Test that symbols are persisted correctly."""
        repo = persistence_service.create_or_get_repository(
            owner="golang",
            name="go",
            github_url="https://github.com/golang/go",
            default_branch="master"
        )
        
        analysis = persistence_service.create_analysis_run(repo)
        
        persistence_service.persist_analysis_result(
            repository=repo,
            analysis_run=analysis,
            static_analysis=sample_static_analysis,
            file_metadata=sample_file_metadata
        )
        
        # Query symbols
        from app.db.models import Symbol
        symbols = db_session.query(Symbol).filter_by(analysis_run_id=analysis.id).all()
        
        assert len(symbols) == 3
        
        # Check function
        func_symbol = next(s for s in symbols if s.name == "calculate_sum")
        assert func_symbol.symbol_type == SymbolType.FUNCTION
        assert func_symbol.language == "Python"
        
        # Check class
        class_symbol = next(s for s in symbols if s.name == "Calculator")
        assert class_symbol.symbol_type == SymbolType.CLASS
        
        # Check method with parent
        method_symbol = next(s for s in symbols if s.name == "add")
        assert method_symbol.symbol_type == SymbolType.METHOD
        assert method_symbol.parent_symbol_id == class_symbol.id
    
    def test_persist_imports(
        self,
        persistence_service: PersistenceService,
        db_session: Session,
        sample_static_analysis: StaticAnalysisResult,
        sample_file_metadata: List[Dict[str, Any]]
    ):
        """Test that imports are persisted correctly."""
        repo = persistence_service.create_or_get_repository(
            owner="rails",
            name="rails",
            github_url="https://github.com/rails/rails",
            default_branch="main"
        )
        
        analysis = persistence_service.create_analysis_run(repo)
        
        persistence_service.persist_analysis_result(
            repository=repo,
            analysis_run=analysis,
            static_analysis=sample_static_analysis,
            file_metadata=sample_file_metadata
        )
        
        # Query imports
        from app.db.models import Import
        imports = db_session.query(Import).filter_by(analysis_run_id=analysis.id).all()
        
        assert len(imports) == 2
        assert any(i.source == "flask" for i in imports)
        assert any(i.source == "typing" for i in imports)
    
    def test_persist_calls(
        self,
        persistence_service: PersistenceService,
        db_session: Session,
        sample_static_analysis: StaticAnalysisResult,
        sample_file_metadata: List[Dict[str, Any]]
    ):
        """Test that function calls are persisted correctly."""
        repo = persistence_service.create_or_get_repository(
            owner="laravel",
            name="laravel",
            github_url="https://github.com/laravel/laravel",
            default_branch="main"
        )
        
        analysis = persistence_service.create_analysis_run(repo)
        
        persistence_service.persist_analysis_result(
            repository=repo,
            analysis_run=analysis,
            static_analysis=sample_static_analysis,
            file_metadata=sample_file_metadata
        )
        
        # Query calls
        from app.db.models import Call
        calls = db_session.query(Call).filter_by(analysis_run_id=analysis.id).all()
        
        assert len(calls) == 1
        assert calls[0].caller_name == "main"
        assert calls[0].callee_name == "process_data"


class TestTransactionRollback:
    """Tests for transaction handling and rollback."""
    
    def test_rollback_on_error(self, persistence_service: PersistenceService, db_session: Session):
        """Test that transaction is rolled back on error."""
        repo = persistence_service.create_or_get_repository(
            owner="test",
            name="test-repo",
            github_url="https://github.com/test/test-repo",
            default_branch="main"
        )
        
        analysis = persistence_service.create_analysis_run(repo)
        
        # Create invalid static analysis (will cause error)
        invalid_analysis = StaticAnalysisResult(
            summary=AnalysisSummary(
                total_files=1,
                analyzed_files=1,
                skipped_files=0,
                failed_files=0,
                total_symbols=1,
                symbols_by_type={"function": 1},
                total_imports=0,
                total_calls=0
            ),
            all_symbols=[
                SymbolSchema(
                    name="test_func",
                    type="function",
                    language="Python",
                    file="test.py",
                    start_line=1,
                    end_line=5,
                    parent=None
                )
            ],
            all_imports=[],
            all_calls=[]
        )
        
        # Try to persist with missing file metadata (should cause FK constraint error)
        with pytest.raises(Exception):
            persistence_service.persist_analysis_result(
                repository=repo,
                analysis_run=analysis,
                static_analysis=invalid_analysis,
                file_metadata=[]  # Empty - symbols reference non-existent files
            )
        
        # Verify analysis was marked as failed
        db_session.refresh(analysis)
        assert analysis.status == AnalysisStatus.FAILED
