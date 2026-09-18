"""
Tests for Phase 11: RAG Context API endpoints.

These tests verify:
- API endpoint functionality
- Request validation
- Response format
- Error handling
- Repository not found
- Invalid parameters
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.models import (
    Repository, AnalysisRun, File, Symbol, SemanticChunk,
    AnalysisStatus, SymbolType, ChunkType
)


client = TestClient(app)


@pytest.fixture
def sample_repository(db: Session) -> Repository:
    """Create a sample repository for testing."""
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        full_name="test/test-repo",
        owner="test",
        github_url="https://github.com/test/test-repo",
        default_branch="main"
    )
    db.add(repo)
    db.commit()
    return repo


@pytest.fixture
def sample_analysis_run(db: Session, sample_repository: Repository) -> AnalysisRun:
    """Create a sample analysis run for testing."""
    analysis_run = AnalysisRun(
        id=uuid4(),
        repository_id=sample_repository.id,
        status=AnalysisStatus.COMPLETED,
        total_files=1,
        total_symbols=1
    )
    db.add(analysis_run)
    db.commit()
    return analysis_run


@pytest.fixture
def sample_data_with_chunks(
    db: Session,
    sample_repository: Repository,
    sample_analysis_run: AnalysisRun
) -> dict:
    """Create sample data with chunks for testing."""
    from app.services.embedding_service import EmbeddingService
    
    embedding_service = EmbeddingService()
    
    # Create file
    file = File(
        id=uuid4(),
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis_run.id,
        path="backend/services/auth_service.py",
        filename="auth_service.py",
        language="Python",
        size_bytes=1000,
        is_sensitive=False
    )
    db.add(file)
    
    # Create symbol
    symbol = Symbol(
        id=uuid4(),
        file_id=file.id,
        analysis_run_id=sample_analysis_run.id,
        name="AuthService.authenticate_user",
        symbol_type=SymbolType.METHOD,
        language="Python",
        start_line=10,
        end_line=30
    )
    db.add(symbol)
    
    # Create chunk with embedding
    import hashlib
    content = "def authenticate_user(self, username, password):\n    return verify_credentials(username, password)"
    embedding = embedding_service.embed(content)
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    
    chunk = SemanticChunk(
        id=uuid4(),
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis_run.id,
        file_id=file.id,
        symbol_id=symbol.id,
        content=content,
        content_hash=content_hash,
        chunk_type=ChunkType.SYMBOL,
        start_line=10,
        end_line=12,
        language="Python",
        embedding=embedding
    )
    db.add(chunk)
    db.commit()
    
    return {
        "repository": sample_repository,
        "analysis_run": sample_analysis_run,
        "file": file,
        "symbol": symbol,
        "chunk": chunk
    }


class TestRAGContextAPI:
    """Tests for RAG context API endpoints."""
    
    def test_build_context_success(self, sample_data_with_chunks: dict):
        """Test successful RAG context building."""
        repo = sample_data_with_chunks["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 5,
                "semantic_weight": 0.6,
                "keyword_weight": 0.4
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "context" in data
        context = data["context"]
        
        assert context["question"] == "How does authentication work?"
        assert context["repository_id"] == str(repo.id)
        assert "evidence" in context
        assert "graph_evidence" in context
        assert "total_evidence_items" in context
        assert "total_characters" in context
        assert "retrieval_metadata" in context
    
    def test_build_context_with_limits(self, sample_data_with_chunks: dict):
        """Test RAG context with custom limits."""
        repo = sample_data_with_chunks["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 10,
                "max_evidence_items": 5,
                "max_characters": 1000,
                "max_chunk_characters": 500
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        context = data["context"]
        
        assert len(context["evidence"]) <= 5
        assert context["total_characters"] <= 1000
    
    def test_build_context_with_graph_evidence(self, sample_data_with_chunks: dict):
        """Test RAG context with graph enrichment."""
        repo = sample_data_with_chunks["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 5,
                "include_graph_evidence": True,
                "graph_depth": 1,
                "max_graph_nodes": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        context = data["context"]
        
        assert "graph_evidence" in context
    
    def test_build_context_without_graph_evidence(self, sample_data_with_chunks: dict):
        """Test RAG context without graph enrichment."""
        repo = sample_data_with_chunks["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 5,
                "include_graph_evidence": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        context = data["context"]
        
        assert len(context["graph_evidence"]) == 0
    
    def test_build_context_with_analysis_run_id(self, sample_data_with_chunks: dict):
        """Test RAG context with specific analysis run."""
        repo = sample_data_with_chunks["repository"]
        analysis_run = sample_data_with_chunks["analysis_run"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 5,
                "analysis_run_id": str(analysis_run.id)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        context = data["context"]
        
        assert context["analysis_run_id"] == str(analysis_run.id)
    
    def test_repository_not_found(self):
        """Test error when repository doesn't exist."""
        fake_repo_id = uuid4()
        
        response = client.post(
            f"/api/repositories/{fake_repo_id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 5
            }
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_empty_question_error(self, sample_data_with_chunks: dict):
        """Test error when question is empty."""
        repo = sample_data_with_chunks["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "",
                "top_k": 5
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_analysis_run_id(self, sample_data_with_chunks: dict):
        """Test error when analysis_run_id is invalid."""
        repo = sample_data_with_chunks["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 5,
                "analysis_run_id": "not-a-uuid"
            }
        )
        
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()
    
    def test_invalid_weights(self, sample_data_with_chunks: dict):
        """Test that invalid weights are handled."""
        repo = sample_data_with_chunks["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 5,
                "semantic_weight": 1.5,  # Invalid: > 1
                "keyword_weight": 0.5
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_response_schema_completeness(self, sample_data_with_chunks: dict):
        """Test that response contains all required fields."""
        repo = sample_data_with_chunks["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "context" in data
        context = data["context"]
        
        # Check required fields
        required_fields = [
            "question",
            "repository_id",
            "evidence",
            "graph_evidence",
            "total_evidence_items",
            "total_characters",
            "context_limit_reached",
            "truncated",
            "retrieval_metadata"
        ]
        
        for field in required_fields:
            assert field in context, f"Missing required field: {field}"
        
        # Check retrieval metadata
        metadata = context["retrieval_metadata"]
        metadata_fields = [
            "total_candidates",
            "selected_evidence",
            "semantic_candidates",
            "keyword_candidates",
            "deduplicated_count",
            "graph_enrichments",
            "semantic_weight",
            "keyword_weight"
        ]
        
        for field in metadata_fields:
            assert field in metadata, f"Missing metadata field: {field}"
    
    def test_evidence_item_schema(self, sample_data_with_chunks: dict):
        """Test that evidence items have required fields."""
        repo = sample_data_with_chunks["repository"]
        
        response = client.post(
            f"/api/repositories/{repo.id}/rag/context",
            json={
                "question": "How does authentication work?",
                "top_k": 5
            }
        )
        
        assert response.status_code == 200
        context = response.json()["context"]
        
        if len(context["evidence"]) > 0:
            evidence = context["evidence"][0]
            
            # Required fields for evidence items
            required_fields = [
                "chunk_id",
                "retrieval_score",
                "retrieval_source",
                "content",
                "chunk_type",
                "file_path",
                "start_line",
                "end_line"
            ]
            
            for field in required_fields:
                assert field in evidence, f"Missing evidence field: {field}"
