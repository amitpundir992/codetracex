"""
Tests for Target Identification Service (Phase 13).

Tests deterministic target matching for symbols, files, and API endpoints.
"""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from app.services.target_identification_service import TargetIdentificationService
from app.db.models import Repository, AnalysisRun, File, Symbol, ApiEndpoint, SymbolType, HttpMethod, AnalysisStatus


@pytest.fixture
def sample_repository(db: Session):
    """Create a sample repository with symbols, files, and endpoints."""
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
    
    # Create files
    file1 = File(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="src/services/order_service.py",
        filename="order_service.py",
        language="python",
        size_bytes=1000
    )
    db.add(file1)
    
    file2 = File(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="src/controllers/order_controller.py",
        filename="order_controller.py",
        language="python",
        size_bytes=800
    )
    db.add(file2)
    
    # Create symbols
    class_symbol = Symbol(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=file1.id,
        name="OrderService",
        symbol_type=SymbolType.CLASS,
        language="python",
        start_line=10,
        end_line=50
    )
    db.add(class_symbol)
    
    method_symbol = Symbol(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=file1.id,
        name="create_order",
        symbol_type=SymbolType.METHOD,
        language="python",
        parent_symbol_id=class_symbol.id,
        start_line=20,
        end_line=30
    )
    db.add(method_symbol)
    
    # Create API endpoint
    endpoint = ApiEndpoint(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=file2.id,
        method=HttpMethod.POST,
        path="/api/orders",
        framework="fastapi",
        handler_name="create_order_handler"
    )
    db.add(endpoint)
    
    db.commit()
    
    return {
        "repository": repo,
        "analysis_run": analysis_run,
        "file1": file1,
        "file2": file2,
        "class_symbol": class_symbol,
        "method_symbol": method_symbol,
        "endpoint": endpoint
    }


class TestTargetIdentification:
    """Tests for target identification."""
    
    def test_identify_symbol_by_id(self, db: Session, sample_repository):
        """Test identifying symbol by explicit ID."""
        service = TargetIdentificationService(db)
        symbol = sample_repository["method_symbol"]
        repo = sample_repository["repository"]
        
        result = service.identify_target_from_query(
            query="What calls create_order?",
            repository_id=repo.id,
            target_type="symbol",
            target_id=symbol.id
        )
        
        assert result.status == "found"
        assert result.target is not None
        assert result.target.target_id == symbol.id
        assert result.target.name == "create_order"
        assert result.target.target_type == "symbol"
    
    def test_identify_symbol_by_exact_name(self, db: Session, sample_repository):
        """Test identifying symbol by exact name match."""
        service = TargetIdentificationService(db)
        repo = sample_repository["repository"]
        
        result = service.identify_target_from_query(
            query="What calls create_order?",
            repository_id=repo.id
        )
        
        assert result.status == "found"
        assert result.target is not None
        assert result.target.name == "create_order"
    
    def test_identify_symbol_by_qualified_name(self, db: Session, sample_repository):
        """Test identifying symbol by qualified name."""
        service = TargetIdentificationService(db)
        repo = sample_repository["repository"]
        
        result = service.identify_target_from_query(
            query="What affects OrderService.create_order?",
            repository_id=repo.id
        )
        
        assert result.status == "found"
        assert result.target is not None
        assert result.target.name == "create_order"
        assert result.target.qualified_name == "OrderService.create_order"
    
    def test_identify_file_by_path(self, db: Session, sample_repository):
        """Test identifying file by path."""
        service = TargetIdentificationService(db)
        repo = sample_repository["repository"]
        
        result = service.identify_target_from_query(
            query="What depends on src/services/order_service.py?",
            repository_id=repo.id
        )
        
        assert result.status == "found"
        assert result.target is not None
        assert result.target.target_type == "file"
        assert result.target.file_path == "src/services/order_service.py"
    
    def test_identify_endpoint_by_method_and_path(self, db: Session, sample_repository):
        """Test identifying API endpoint by method and path."""
        service = TargetIdentificationService(db)
        repo = sample_repository["repository"]
        
        result = service.identify_target_from_query(
            query="What would break if I change POST /api/orders?",
            repository_id=repo.id
        )
        
        assert result.status == "found"
        assert result.target is not None
        assert result.target.target_type == "api_endpoint"
        assert result.target.http_method == "POST"
        assert result.target.endpoint_path == "/api/orders"
    
    def test_target_not_found(self, db: Session, sample_repository):
        """Test handling when target is not found."""
        service = TargetIdentificationService(db)
        repo = sample_repository["repository"]
        
        result = service.identify_target_from_query(
            query="What affects NonExistentService?",
            repository_id=repo.id
        )
        
        assert result.status == "not_found"
        assert result.target is None
        assert result.message is not None
    
    def test_repository_isolation(self, db: Session, sample_repository):
        """Test that repository isolation is enforced."""
        service = TargetIdentificationService(db)
        other_repo_id = uuid4()
        
        result = service.identify_target_from_query(
            query="What calls create_order?",
            repository_id=other_repo_id
        )
        
        assert result.status == "not_found"
    
    def test_analysis_run_isolation(self, db: Session, sample_repository):
        """Test that analysis run isolation is enforced."""
        service = TargetIdentificationService(db)
        repo = sample_repository["repository"]
        wrong_analysis_run_id = uuid4()
        
        result = service.identify_target_from_query(
            query="What calls create_order?",
            repository_id=repo.id,
            analysis_run_id=wrong_analysis_run_id
        )
        
        assert result.status == "not_found"
    
    def test_partial_symbol_name_match(self, db: Session, sample_repository):
        """Test partial symbol name matching with confidence score."""
        service = TargetIdentificationService(db)
        repo = sample_repository["repository"]
        
        result = service.identify_target_from_query(
            query="What affects order?",
            repository_id=repo.id,
            target_type="symbol"
        )
        
        # Should find OrderService or create_order
        assert result.status in ["found", "ambiguous"]
        
        if result.status == "found":
            assert "order" in result.target.name.lower()
        else:
            assert len(result.candidates) > 0
            assert any("order" in c.target.name.lower() for c in result.candidates)
