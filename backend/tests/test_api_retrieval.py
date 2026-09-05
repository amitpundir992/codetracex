"""
Tests for repository retrieval API endpoints (Phase 4).

These tests verify the GET endpoints that retrieve persisted analysis results
from the database.
"""
# Load environment variables before any other imports
from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, UTC
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal, engine, Base
from app.db.models import Repository, AnalysisRun, File, Symbol, AnalysisStatus, SymbolType
from app.db import get_db


client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def override_get_db(db_session: Session):
    """Override the get_db dependency to use test database."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sample_data(db_session: Session):
    """Create sample data for testing retrieval endpoints."""
    # Create repository
    repo = Repository(
        owner="facebook",
        name="react",
        full_name="facebook/react",
        github_url="https://github.com/facebook/react",
        default_branch="main",
        description="The library for web and native user interfaces.",
        language="JavaScript",
        stars=200000
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    
    # Create analysis run 1 (completed)
    analysis1 = AnalysisRun(
        repository_id=repo.id,
        status=AnalysisStatus.COMPLETED,
        total_files=100,
        analyzed_files=95,
        total_symbols=500,
        total_imports=150,
        total_calls=300,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC)
    )
    db_session.add(analysis1)
    db_session.commit()
    db_session.refresh(analysis1)
    
    # Create analysis run 2 (older)
    analysis2 = AnalysisRun(
        repository_id=repo.id,
        status=AnalysisStatus.COMPLETED,
        total_files=90,
        analyzed_files=85,
        total_symbols=450,
        total_imports=140,
        total_calls=280,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        completed_at=datetime(2024, 1, 1, tzinfo=UTC)
    )
    db_session.add(analysis2)
    db_session.commit()
    db_session.refresh(analysis2)
    
    # Add some files to analysis1
    file1 = File(
        repository_id=repo.id,
        analysis_run_id=analysis1.id,
        path="src/index.js",
        filename="index.js",
        extension=".js",
        language="JavaScript",
        size_bytes=1523,
        line_count=45,
        is_sensitive=False
    )
    file2 = File(
        repository_id=repo.id,
        analysis_run_id=analysis1.id,
        path="src/App.js",
        filename="App.js",
        extension=".js",
        language="JavaScript",
        size_bytes=2890,
        line_count=78,
        is_sensitive=False
    )
    db_session.add_all([file1, file2])
    db_session.commit()
    db_session.refresh(file1)
    db_session.refresh(file2)
    
    # Add some symbols
    symbol1 = Symbol(
        file_id=file1.id,
        analysis_run_id=analysis1.id,
        name="render",
        symbol_type=SymbolType.FUNCTION,
        language="JavaScript",
        start_line=10,
        end_line=25
    )
    symbol2 = Symbol(
        file_id=file2.id,
        analysis_run_id=analysis1.id,
        name="App",
        symbol_type=SymbolType.FUNCTION,
        language="JavaScript",
        start_line=5,
        end_line=50
    )
    db_session.add_all([symbol1, symbol2])
    db_session.commit()
    
    return {
        "repository": repo,
        "analysis1": analysis1,
        "analysis2": analysis2,
        "files": [file1, file2],
        "symbols": [symbol1, symbol2]
    }


class TestListRepositoriesEndpoint:
    """Tests for GET /api/repositories endpoint."""
    
    def test_list_empty_repositories(self, override_get_db, db_session: Session):
        """Test listing repositories when database is empty."""
        response = client.get("/api/repositories")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["repositories"] == []
    
    def test_list_repositories(self, override_get_db, db_session: Session, sample_data):
        """Test listing all repositories."""
        response = client.get("/api/repositories")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["repositories"]) == 1
        
        repo = data["repositories"][0]
        assert repo["owner"] == "facebook"
        assert repo["name"] == "react"
        assert repo["full_name"] == "facebook/react"
        assert repo["stars"] == 200000
    
    def test_list_repositories_with_limit(self, override_get_db, db_session: Session):
        """Test pagination with limit parameter."""
        # Create multiple repositories
        for i in range(5):
            repo = Repository(
                owner=f"owner{i}",
                name=f"repo{i}",
                full_name=f"owner{i}/repo{i}",
                github_url=f"https://github.com/owner{i}/repo{i}",
                default_branch="main"
            )
            db_session.add(repo)
        db_session.commit()
        
        response = client.get("/api/repositories?limit=3")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["repositories"]) == 3
    
    def test_list_repositories_with_offset(self, override_get_db, db_session: Session):
        """Test pagination with offset parameter."""
        # Create multiple repositories
        repos = []
        for i in range(5):
            repo = Repository(
                owner=f"owner{i}",
                name=f"repo{i}",
                full_name=f"owner{i}/repo{i}",
                github_url=f"https://github.com/owner{i}/repo{i}",
                default_branch="main"
            )
            db_session.add(repo)
            repos.append(repo)
        db_session.commit()
        
        response = client.get("/api/repositories?offset=2&limit=2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["repositories"]) == 2


class TestGetRepositoryEndpoint:
    """Tests for GET /api/repositories/{repository_id} endpoint."""
    
    def test_get_repository(self, override_get_db, db_session: Session, sample_data):
        """Test getting a specific repository."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(f"/api/repositories/{repo_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == repo_id
        assert data["owner"] == "facebook"
        assert data["name"] == "react"
        assert data["description"] == "The library for web and native user interfaces."
        assert data["analysis_count"] == 2  # Two analysis runs
    
    def test_get_nonexistent_repository(self, override_get_db, db_session: Session):
        """Test getting a repository that doesn't exist."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/repositories/{fake_uuid}")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_get_repository_invalid_uuid(self, override_get_db, db_session: Session):
        """Test getting a repository with invalid UUID format."""
        response = client.get("/api/repositories/invalid-uuid")
        
        assert response.status_code == 422  # Validation error


class TestGetLatestAnalysisEndpoint:
    """Tests for GET /api/repositories/{repository_id}/analysis/latest endpoint."""
    
    def test_get_latest_analysis(self, override_get_db, db_session: Session, sample_data):
        """Test getting the latest analysis for a repository."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(f"/api/repositories/{repo_id}/analysis/latest")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return analysis1 (the most recent)
        assert data["id"] == str(sample_data["analysis1"].id)
        assert data["status"] == "completed"
        assert data["total_files"] == 100
        assert data["total_symbols"] == 500
    
    def test_get_latest_analysis_no_runs(self, override_get_db, db_session: Session):
        """Test getting latest analysis when repository has no runs."""
        # Create repo without analysis runs
        repo = Repository(
            owner="test",
            name="test-repo",
            full_name="test/test-repo",
            github_url="https://github.com/test/test-repo",
            default_branch="main"
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)
        
        response = client.get(f"/api/repositories/{repo.id}/analysis/latest")
        
        assert response.status_code == 404
        data = response.json()
        assert "no analysis" in data["detail"].lower()


class TestListAnalysesEndpoint:
    """Tests for GET /api/repositories/{repository_id}/analysis endpoint."""
    
    def test_list_analyses(self, override_get_db, db_session: Session, sample_data):
        """Test listing all analyses for a repository."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(f"/api/repositories/{repo_id}/analysis")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["analyses"]) == 2
        
        # Should be ordered by started_at desc (most recent first)
        assert data["analyses"][0]["id"] == str(sample_data["analysis1"].id)
        assert data["analyses"][1]["id"] == str(sample_data["analysis2"].id)
    
    def test_list_analyses_with_pagination(self, override_get_db, db_session: Session, sample_data):
        """Test listing analyses with pagination."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(f"/api/repositories/{repo_id}/analysis?limit=1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["analyses"]) == 1
    
    def test_list_analyses_empty(self, override_get_db, db_session: Session):
        """Test listing analyses for repository with no runs."""
        # Create repo without analysis runs
        repo = Repository(
            owner="empty",
            name="empty-repo",
            full_name="empty/empty-repo",
            github_url="https://github.com/empty/empty-repo",
            default_branch="main"
        )
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)
        
        response = client.get(f"/api/repositories/{repo.id}/analysis")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["analyses"] == []


class TestSearchSymbolsEndpoint:
    """Tests for GET /api/repositories/{repository_id}/symbols endpoint."""
    
    def test_search_symbols_by_name(self, override_get_db, db_session: Session, sample_data):
        """Test searching symbols by name."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(f"/api/repositories/{repo_id}/symbols?name=App")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        
        # Check that App symbol is found
        symbols = data["symbols"]
        assert any(s["name"] == "App" for s in symbols)
    
    def test_search_symbols_by_type(self, override_get_db, db_session: Session, sample_data):
        """Test searching symbols by type."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(f"/api/repositories/{repo_id}/symbols?type=function")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        
        # All returned symbols should be functions
        symbols = data["symbols"]
        assert all(s["type"] == "function" for s in symbols)
    
    def test_search_symbols_by_language(self, override_get_db, db_session: Session, sample_data):
        """Test searching symbols by language."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(f"/api/repositories/{repo_id}/symbols?language=JavaScript")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
    
    def test_search_symbols_combined_filters(self, override_get_db, db_session: Session, sample_data):
        """Test searching symbols with multiple filters."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(
            f"/api/repositories/{repo_id}/symbols?name=App&type=function&language=JavaScript"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should find the App function
        symbols = data["symbols"]
        assert len(symbols) >= 1
        matching = next((s for s in symbols if s["name"] == "App"), None)
        assert matching is not None
        assert matching["type"] == "function"
        assert matching["language"] == "JavaScript"
    
    def test_search_symbols_no_results(self, override_get_db, db_session: Session, sample_data):
        """Test searching symbols with no matching results."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(f"/api/repositories/{repo_id}/symbols?name=NonexistentSymbol")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["symbols"] == []
    
    def test_search_symbols_pagination(self, override_get_db, db_session: Session, sample_data):
        """Test symbol search pagination."""
        repo_id = str(sample_data["repository"].id)
        response = client.get(f"/api/repositories/{repo_id}/symbols?limit=1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["symbols"]) == 1
