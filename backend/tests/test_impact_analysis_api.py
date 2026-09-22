"""
API tests for Phase 13: Impact Analysis endpoint.

Tests the POST /api/repositories/{repo_id}/impact-analysis endpoint.
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.models import (
    Repository, AnalysisRun, File, Symbol, Call,
    SymbolType, AnalysisStatus
)


@pytest.fixture
def test_data(db: Session):
    """Create test repository with symbols."""
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        full_name="test/test-repo",
        owner="test",
        github_url="https://github.com/test/test-repo",
        default_branch="main",
        description="Test repository"
    )
    db.add(repo)
    
    analysis_run = AnalysisRun(
        id=uuid4(),
        repository_id=repo.id,
        status=AnalysisStatus.COMPLETED
    )
    db.add(analysis_run)
    
    file1 = File(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="src/service.py",
        filename="service.py",
        language="python",
        size_bytes=1000
    )
    db.add(file1)
    
    symbol1 = Symbol(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=file1.id,
        name="process_order",
        symbol_type=SymbolType.FUNCTION,
        start_line=10,
        end_line=20
    )
    db.add(symbol1)
    
    symbol2 = Symbol(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=file1.id,
        name="validate_order",
        symbol_type=SymbolType.FUNCTION,
        start_line=25,
        end_line=35
    )
    db.add(symbol2)
    
    # Create call relationship
    call = Call(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=file1.id,
        caller_name="validate_order",
        callee_name="process_order",
        line_number=30
    )
    db.add(call)
    
    db.commit()
    
    return {
        "repository": repo,
        "analysis_run": analysis_run,
        "symbol1": symbol1,
        "symbol2": symbol2
    }


class TestImpactAnalysisAPI:
    """Tests for impact analysis API endpoint."""
    
    def test_valid_impact_analysis_request(self, test_data):
        """Test valid impact analysis request."""
        client = TestClient(app)
        repo = test_data["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/impact-analysis",
            json={
                "question": "What would be affected if I change process_order?",
                "depth": 3,
                "include_implementation_plan": False
            }
        )
        
        # Should succeed (200) or be service unavailable (503) if LLM not configured
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "question" in data
            assert data["question"] == "What would be affected if I change process_order?"
    
    def test_explicit_target_id(self, test_data):
        """Test impact analysis with explicit target ID."""
        client = TestClient(app)
        repo = test_data["repository"]
        symbol = test_data["symbol1"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/impact-analysis",
            json={
                "question": "What affects this symbol?",
                "target_type": "symbol",
                "target_id": str(symbol.id),
                "depth": 2,
                "include_implementation_plan": False
            }
        )
        
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "success":
                assert data["target"]["target_id"] == str(symbol.id)
    
    def test_invalid_repository_id(self):
        """Test with invalid repository ID."""
        client = TestClient(app)
        fake_repo_id = uuid4()
        
        response = client.post(
            f"/api/repositories/{fake_repo_id}/impact-analysis",
            json={
                "question": "What affects something?",
                "depth": 3
            }
        )
        
        assert response.status_code == 404
    
    def test_invalid_analysis_run_id(self, test_data):
        """Test with invalid analysis run ID."""
        client = TestClient(app)
        repo = test_data["repository"]
        fake_run_id = uuid4()
        
        response = client.post(
            f"/api/repositories/{repo.id}/impact-analysis",
            json={
                "question": "What affects something?",
                "analysis_run_id": str(fake_run_id),
                "depth": 3
            }
        )
        
        assert response.status_code == 404
    
    def test_missing_question(self, test_data):
        """Test with missing question field."""
        client = TestClient(app)
        repo = test_data["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/impact-analysis",
            json={
                "depth": 3
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_depth_validation(self, test_data):
        """Test depth parameter validation."""
        client = TestClient(app)
        repo = test_data["repository"]
        
        # Depth too high (should be capped by service)
        response = client.post(
            f"/api/repositories/{repo.id}/impact-analysis",
            json={
                "question": "What affects process_order?",
                "depth": 100
            }
        )
        
        # Should not error on depth validation (backend caps it)
        assert response.status_code in [200, 503]
        
        # Depth too low
        response = client.post(
            f"/api/repositories/{repo.id}/impact-analysis",
            json={
                "question": "What affects process_order?",
                "depth": 0
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_target_not_found_response(self, test_data):
        """Test response when target is not found."""
        client = TestClient(app)
        repo = test_data["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/impact-analysis",
            json={
                "question": "What affects NonExistentSymbol123?",
                "depth": 3
            }
        )
        
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert data["status"] in ["target_not_found", "ambiguous_target", "success"]
    
    def test_include_implementation_plan(self, test_data):
        """Test requesting implementation plan."""
        client = TestClient(app)
        repo = test_data["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/impact-analysis",
            json={
                "question": "What affects process_order?",
                "depth": 2,
                "include_implementation_plan": True
            }
        )
        
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "success":
                # Implementation plan may or may not be present depending on LLM
                assert "implementation_plan" in data
