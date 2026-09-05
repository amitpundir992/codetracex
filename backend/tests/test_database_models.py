"""
Tests for database models.

These tests verify the SQLAlchemy models work correctly with the database,
including relationships, constraints, and data integrity.
"""
# Load environment variables before any other imports
from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import uuid4

from app.db.models import (
    Repository,
    AnalysisRun,
    File,
    Symbol,
    Import,
    Call,
    Relationship,
    AnalysisStatus,
    SymbolType,
    RelationshipType
)
from app.db.session import SessionLocal, engine, Base


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = SessionLocal()
    
    yield session
    
    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_repository(db_session: Session) -> Repository:
    """Create a sample repository for testing."""
    repo = Repository(
        owner="facebook",
        name="react",
        full_name="facebook/react",
        github_url="https://github.com/facebook/react",
        default_branch="main",
        description="The library for web and native user interfaces.",
        language="JavaScript",
        stars=100000
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


@pytest.fixture
def sample_analysis_run(db_session: Session, sample_repository: Repository) -> AnalysisRun:
    """Create a sample analysis run for testing."""
    analysis = AnalysisRun(
        repository_id=sample_repository.id,
        status=AnalysisStatus.RUNNING,
        started_at=datetime.now(UTC)
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis)
    return analysis


class TestRepositoryModel:
    """Tests for Repository model."""
    
    def test_create_repository(self, db_session: Session):
        """Test creating a repository record."""
        repo = Repository(
            owner="openai",
            name="gpt-3",
            full_name="openai/gpt-3",
            github_url="https://github.com/openai/gpt-3",
            default_branch="main",
            description="GPT-3 model",
            language="Python",
            stars=5000
        )
        
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)
        
        assert repo.id is not None
        assert repo.owner == "openai"
        assert repo.name == "gpt-3"
        assert repo.full_name == "openai/gpt-3"
        assert repo.created_at is not None
        assert repo.updated_at is not None
    
    def test_unique_full_name_constraint(self, db_session: Session, sample_repository: Repository):
        """Test that full_name must be unique."""
        duplicate_repo = Repository(
            owner="facebook",
            name="react",
            full_name="facebook/react",
            github_url="https://github.com/facebook/react",
            default_branch="main"
        )
        
        db_session.add(duplicate_repo)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_repository_cascade_delete(self, db_session: Session, sample_repository: Repository):
        """Test that deleting a repository cascades to related records."""
        # Create an analysis run
        analysis = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.COMPLETED,
            started_at=datetime.now(UTC)
        )
        db_session.add(analysis)
        db_session.commit()
        
        # Delete the repository
        db_session.delete(sample_repository)
        db_session.commit()
        
        # Verify analysis run was also deleted
        remaining_analysis = db_session.query(AnalysisRun).filter_by(
            repository_id=sample_repository.id
        ).first()
        assert remaining_analysis is None


class TestAnalysisRunModel:
    """Tests for AnalysisRun model."""
    
    def test_create_analysis_run(self, db_session: Session, sample_repository: Repository):
        """Test creating an analysis run."""
        analysis = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.PENDING,
            started_at=datetime.now(UTC)
        )
        
        db_session.add(analysis)
        db_session.commit()
        db_session.refresh(analysis)
        
        assert analysis.id is not None
        assert analysis.repository_id == sample_repository.id
        assert analysis.status == AnalysisStatus.PENDING
        assert analysis.started_at is not None
        assert analysis.completed_at is None
    
    def test_complete_analysis_run(self, db_session: Session, sample_analysis_run: AnalysisRun):
        """Test completing an analysis run."""
        sample_analysis_run.status = AnalysisStatus.COMPLETED
        sample_analysis_run.completed_at = datetime.now(UTC)
        sample_analysis_run.total_files = 100
        sample_analysis_run.analyzed_files = 95
        sample_analysis_run.total_symbols = 500
        sample_analysis_run.total_imports = 150
        sample_analysis_run.total_calls = 300
        
        db_session.commit()
        db_session.refresh(sample_analysis_run)
        
        assert sample_analysis_run.status == AnalysisStatus.COMPLETED
        assert sample_analysis_run.completed_at is not None
        assert sample_analysis_run.total_files == 100
        assert sample_analysis_run.total_symbols == 500
    
    def test_fail_analysis_run(self, db_session: Session, sample_analysis_run: AnalysisRun):
        """Test marking an analysis run as failed."""
        sample_analysis_run.status = AnalysisStatus.FAILED
        sample_analysis_run.completed_at = datetime.now(UTC)
        sample_analysis_run.error_message = "Failed to download repository"
        
        db_session.commit()
        db_session.refresh(sample_analysis_run)
        
        assert sample_analysis_run.status == AnalysisStatus.FAILED
        assert sample_analysis_run.error_message == "Failed to download repository"


class TestFileModel:
    """Tests for File model."""
    
    def test_create_file(self, db_session: Session, sample_repository: Repository, sample_analysis_run: AnalysisRun):
        """Test creating a file record."""
        file = File(
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis_run.id,
            path="src/index.js",
            filename="index.js",
            extension=".js",
            language="JavaScript",
            size_bytes=1523,
            line_count=45,
            is_sensitive=False
        )
        
        db_session.add(file)
        db_session.commit()
        db_session.refresh(file)
        
        assert file.id is not None
        assert file.path == "src/index.js"
        assert file.filename == "index.js"
        assert file.language == "JavaScript"
    
    def test_file_unique_constraint(self, db_session: Session, sample_repository: Repository, sample_analysis_run: AnalysisRun):
        """Test that analysis_run_id + path must be unique."""
        file1 = File(
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis_run.id,
            path="src/app.js",
            filename="app.js",
            extension=".js"
        )
        
        db_session.add(file1)
        db_session.commit()
        
        # Try to create duplicate
        file2 = File(
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis_run.id,
            path="src/app.js",
            filename="app.js",
            extension=".js"
        )
        
        db_session.add(file2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSymbolModel:
    """Tests for Symbol model."""
    
    def test_create_symbol(self, db_session: Session, sample_repository: Repository, sample_analysis_run: AnalysisRun):
        """Test creating a symbol record."""
        # Create a file first
        file = File(
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis_run.id,
            path="src/utils.py",
            filename="utils.py",
            extension=".py"
        )
        db_session.add(file)
        db_session.commit()
        
        # Create a symbol
        symbol = Symbol(
            file_id=file.id,
            analysis_run_id=sample_analysis_run.id,
            name="calculate_sum",
            symbol_type=SymbolType.FUNCTION,
            language="Python",
            start_line=10,
            end_line=15
        )
        
        db_session.add(symbol)
        db_session.commit()
        db_session.refresh(symbol)
        
        assert symbol.id is not None
        assert symbol.name == "calculate_sum"
        assert symbol.symbol_type == SymbolType.FUNCTION
        assert symbol.language == "Python"
    
    def test_symbol_parent_relationship(self, db_session: Session, sample_repository: Repository, sample_analysis_run: AnalysisRun):
        """Test parent-child symbol relationships (e.g., class methods)."""
        # Create file
        file = File(
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis_run.id,
            path="src/calculator.py",
            filename="calculator.py",
            extension=".py"
        )
        db_session.add(file)
        db_session.commit()
        
        # Create parent class symbol
        parent_class = Symbol(
            file_id=file.id,
            analysis_run_id=sample_analysis_run.id,
            name="Calculator",
            symbol_type=SymbolType.CLASS,
            language="Python",
            start_line=1,
            end_line=20
        )
        db_session.add(parent_class)
        db_session.commit()
        db_session.refresh(parent_class)
        
        # Create child method symbol
        method = Symbol(
            file_id=file.id,
            analysis_run_id=sample_analysis_run.id,
            name="add",
            symbol_type=SymbolType.METHOD,
            language="Python",
            start_line=5,
            end_line=7,
            parent_symbol_id=parent_class.id
        )
        db_session.add(method)
        db_session.commit()
        db_session.refresh(method)
        
        assert method.parent_symbol_id == parent_class.id
        assert method.parent.name == "Calculator"


class TestImportModel:
    """Tests for Import model."""
    
    def test_create_import(self, db_session: Session, sample_repository: Repository, sample_analysis_run: AnalysisRun):
        """Test creating an import record."""
        # Create file
        file = File(
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis_run.id,
            path="src/app.py",
            filename="app.py",
            extension=".py"
        )
        db_session.add(file)
        db_session.commit()
        
        # Create import
        import_record = Import(
            file_id=file.id,
            analysis_run_id=sample_analysis_run.id,
            source="flask",
            imported_names="Flask,request,jsonify",
            line_number=1
        )
        
        db_session.add(import_record)
        db_session.commit()
        db_session.refresh(import_record)
        
        assert import_record.id is not None
        assert import_record.source == "flask"
        assert "Flask" in import_record.imported_names


class TestCallModel:
    """Tests for Call model."""
    
    def test_create_call(self, db_session: Session, sample_repository: Repository, sample_analysis_run: AnalysisRun):
        """Test creating a function call record."""
        # Create file
        file = File(
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis_run.id,
            path="src/main.py",
            filename="main.py",
            extension=".py"
        )
        db_session.add(file)
        db_session.commit()
        
        # Create call
        call = Call(
            file_id=file.id,
            analysis_run_id=sample_analysis_run.id,
            caller_name="main",
            callee_name="process_data",
            line_number=25
        )
        
        db_session.add(call)
        db_session.commit()
        db_session.refresh(call)
        
        assert call.id is not None
        assert call.caller_name == "main"
        assert call.callee_name == "process_data"


class TestRelationshipModel:
    """Tests for Relationship model."""
    
    def test_create_relationship(self, db_session: Session, sample_repository: Repository, sample_analysis_run: AnalysisRun):
        """Test creating a relationship record."""
        relationship = Relationship(
            analysis_run_id=sample_analysis_run.id,
            relationship_type=RelationshipType.IMPORTS,
            source_type="file",
            source_id=uuid4(),
            target_type="file",
            target_id=uuid4()
        )
        
        db_session.add(relationship)
        db_session.commit()
        db_session.refresh(relationship)
        
        assert relationship.id is not None
        assert relationship.relationship_type == RelationshipType.IMPORTS
