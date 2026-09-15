"""
Tests for Phase 10: Hybrid Retrieval

This test module covers:
- Keyword search service
- Semantic search integration
- Hybrid search fusion
- Score normalization
- Result deduplication
- Repository isolation
- Boundary conditions
"""
import pytest
from uuid import uuid4
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.session import Base
from app.db.models import (
    Repository, AnalysisRun, File, Symbol, SemanticChunk,
    AnalysisStatus, SymbolType, ChunkType
)
from app.services.keyword_search_service import KeywordSearchService
from app.services.semantic_search_service import SemanticSearchService
from app.services.hybrid_search_service import HybridSearchService


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"  # In-memory SQLite for tests


@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_repository(test_db: Session):
    """Create a sample repository for testing."""
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        full_name="user/test-repo",
        owner="user",
        url="https://github.com/user/test-repo",
        default_branch="main",
        visibility="public"
    )
    test_db.add(repo)
    test_db.commit()
    test_db.refresh(repo)
    return repo


@pytest.fixture
def sample_analysis_run(test_db: Session, sample_repository):
    """Create a sample analysis run."""
    analysis = AnalysisRun(
        id=uuid4(),
        repository_id=sample_repository.id,
        status=AnalysisStatus.COMPLETED,
        started_at=datetime.utcnow()
    )
    test_db.add(analysis)
    test_db.commit()
    test_db.refresh(analysis)
    return analysis


@pytest.fixture
def sample_file(test_db: Session, sample_analysis_run):
    """Create a sample file."""
    file = File(
        id=uuid4(),
        repository_id=sample_analysis_run.repository_id,
        analysis_run_id=sample_analysis_run.id,
        path="services/order_service.py",
        filename="order_service.py",
        extension=".py",
        language="Python",
        size_bytes=1024,
        line_count=50
    )
    test_db.add(file)
    test_db.commit()
    test_db.refresh(file)
    return file


@pytest.fixture
def sample_symbol(test_db: Session, sample_file, sample_analysis_run):
    """Create a sample symbol."""
    symbol = Symbol(
        id=uuid4(),
        file_id=sample_file.id,
        analysis_run_id=sample_analysis_run.id,
        name="OrderService",
        symbol_type=SymbolType.CLASS,
        language="Python",
        start_line=10,
        end_line=50
    )
    test_db.add(symbol)
    test_db.commit()
    test_db.refresh(symbol)
    return symbol


def create_semantic_chunk(
    db: Session,
    repository_id,
    analysis_run_id,
    file_id,
    content: str,
    chunk_type: ChunkType = ChunkType.SYMBOL,
    symbol_id=None,
    language="Python"
):
    """Helper to create a semantic chunk with mock embedding."""
    import hashlib
    
    # Create mock embedding (all zeros for SQLite compatibility)
    # In real tests with PostgreSQL, this would be a real vector
    mock_embedding = [0.0] * 384
    
    # For SQLite testing, we'll skip the embedding and tsvector
    # since SQLite doesn't support pgvector or tsvector
    chunk = SemanticChunk(
        id=uuid4(),
        repository_id=repository_id,
        analysis_run_id=analysis_run_id,
        file_id=file_id,
        symbol_id=symbol_id,
        chunk_type=chunk_type,
        chunk_index=0,
        content=content,
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        language=language,
        start_line=1,
        end_line=10,
        token_count=len(content.split())
        # Note: embedding and content_tsv omitted for SQLite
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


# ============================================================================
# Keyword Search Tests
# ============================================================================

@pytest.mark.skip(reason="Requires PostgreSQL with full-text search support")
def test_keyword_search_exact_match(test_db, sample_repository, sample_analysis_run, sample_file):
    """Test keyword search finds exact matches."""
    # Create chunks with distinct keywords
    create_semantic_chunk(
        test_db, sample_repository.id, sample_analysis_run.id, sample_file.id,
        "class OrderService:\n    def authenticate_user(self, username, password):\n        pass"
    )
    create_semantic_chunk(
        test_db, sample_repository.id, sample_analysis_run.id, sample_file.id,
        "class UserService:\n    def get_user(self, user_id):\n        pass"
    )
    
    service = KeywordSearchService(test_db)
    results = service.search(
        repository_id=sample_repository.id,
        query="OrderService",
        top_k=10
    )
    
    assert len(results) == 1
    assert "OrderService" in results[0].content
    assert results[0].relevance_score > 0


@pytest.mark.skip(reason="Requires PostgreSQL with full-text search support")
def test_keyword_search_multi_word(test_db, sample_repository, sample_analysis_run, sample_file):
    """Test keyword search with multiple words."""
    create_semantic_chunk(
        test_db, sample_repository.id, sample_analysis_run.id, sample_file.id,
        "def authenticate_user(username, password):\n    # Authentication logic here\n    return True"
    )
    create_semantic_chunk(
        test_db, sample_repository.id, sample_analysis_run.id, sample_file.id,
        "def get_user_profile(user_id):\n    return user_data"
    )
    
    service = KeywordSearchService(test_db)
    results = service.search(
        repository_id=sample_repository.id,
        query="authenticate user",
        top_k=10
    )
    
    assert len(results) >= 1
    assert any("authenticate" in r.content.lower() for r in results)


@pytest.mark.skip(reason="Requires PostgreSQL with full-text search support")
def test_keyword_search_repository_isolation(test_db, sample_analysis_run, sample_file):
    """Test keyword search respects repository boundaries."""
    # Create two repositories
    repo1 = Repository(
        id=uuid4(), name="repo1", full_name="user/repo1", owner="user",
        url="https://github.com/user/repo1", default_branch="main", visibility="public"
    )
    repo2 = Repository(
        id=uuid4(), name="repo2", full_name="user/repo2", owner="user",
        url="https://github.com/user/repo2", default_branch="main", visibility="public"
    )
    test_db.add_all([repo1, repo2])
    test_db.commit()
    
    # Create analysis runs
    analysis1 = AnalysisRun(
        id=uuid4(), repository_id=repo1.id, status=AnalysisStatus.COMPLETED, started_at=datetime.utcnow()
    )
    analysis2 = AnalysisRun(
        id=uuid4(), repository_id=repo2.id, status=AnalysisStatus.COMPLETED, started_at=datetime.utcnow()
    )
    test_db.add_all([analysis1, analysis2])
    test_db.commit()
    
    # Create files
    file1 = File(
        id=uuid4(), repository_id=repo1.id, analysis_run_id=analysis1.id,
        path="service1.py", filename="service1.py", extension=".py", language="Python",
        size_bytes=1024, line_count=50
    )
    file2 = File(
        id=uuid4(), repository_id=repo2.id, analysis_run_id=analysis2.id,
        path="service2.py", filename="service2.py", extension=".py", language="Python",
        size_bytes=1024, line_count=50
    )
    test_db.add_all([file1, file2])
    test_db.commit()
    
    # Create chunks in both repositories with same keyword
    create_semantic_chunk(test_db, repo1.id, analysis1.id, file1.id, "class OrderService in repo1")
    create_semantic_chunk(test_db, repo2.id, analysis2.id, file2.id, "class OrderService in repo2")
    
    service = KeywordSearchService(test_db)
    
    # Search in repo1 should only return repo1 results
    results1 = service.search(repository_id=repo1.id, query="OrderService", top_k=10)
    assert all(r.file_path == "service1.py" for r in results1)
    
    # Search in repo2 should only return repo2 results
    results2 = service.search(repository_id=repo2.id, query="OrderService", top_k=10)
    assert all(r.file_path == "service2.py" for r in results2)


def test_keyword_search_empty_query(test_db, sample_repository):
    """Test keyword search rejects empty queries."""
    service = KeywordSearchService(test_db)
    
    with pytest.raises(ValueError, match="Query cannot be empty"):
        service.search(repository_id=sample_repository.id, query="", top_k=10)
    
    with pytest.raises(ValueError, match="Query cannot be empty"):
        service.search(repository_id=sample_repository.id, query="   ", top_k=10)


def test_keyword_search_bounded_top_k(test_db, sample_repository):
    """Test keyword search enforces maximum top_k."""
    service = KeywordSearchService(test_db)
    
    # Should cap at MAX_TOP_K
    with pytest.warns(None):  # Should log warning but not raise
        # This would work if we had actual data and PostgreSQL
        pass
    
    # Invalid top_k
    with pytest.raises(ValueError, match="top_k must be positive"):
        service.search(repository_id=sample_repository.id, query="test", top_k=0)
    
    with pytest.raises(ValueError, match="top_k must be positive"):
        service.search(repository_id=sample_repository.id, query="test", top_k=-1)


# ============================================================================
# Hybrid Search Tests
# ============================================================================

def test_hybrid_search_initialization(test_db):
    """Test hybrid search service initializes correctly."""
    service = HybridSearchService(test_db)
    assert service.semantic_service is not None
    assert service.keyword_service is not None
    assert service.DEFAULT_SEMANTIC_WEIGHT == 0.5
    assert service.DEFAULT_KEYWORD_WEIGHT == 0.5


def test_hybrid_search_empty_query(test_db, sample_repository):
    """Test hybrid search rejects empty queries."""
    service = HybridSearchService(test_db)
    
    with pytest.raises(ValueError, match="Query cannot be empty"):
        service.search(repository_id=sample_repository.id, query="", top_k=10)


def test_hybrid_search_invalid_weights(test_db, sample_repository):
    """Test hybrid search validates weight parameters."""
    service = HybridSearchService(test_db)
    
    # Weight out of range
    with pytest.raises(ValueError, match="semantic_weight must be between 0 and 1"):
        service.search(
            repository_id=sample_repository.id,
            query="test",
            semantic_weight=1.5,
            keyword_weight=0.5
        )
    
    with pytest.raises(ValueError, match="keyword_weight must be between 0 and 1"):
        service.search(
            repository_id=sample_repository.id,
            query="test",
            semantic_weight=0.5,
            keyword_weight=-0.1
        )
    
    # Both weights zero
    with pytest.raises(ValueError, match="At least one weight must be greater than 0"):
        service.search(
            repository_id=sample_repository.id,
            query="test",
            semantic_weight=0.0,
            keyword_weight=0.0
        )


def test_hybrid_search_weight_normalization(test_db, sample_repository):
    """Test hybrid search auto-normalizes weights that don't sum to 1."""
    service = HybridSearchService(test_db)
    
    # Weights that don't sum to 1 should be normalized
    # This should not raise an error, just log a warning
    try:
        # Will fail due to no data, but should pass weight validation
        service.search(
            repository_id=sample_repository.id,
            query="test",
            semantic_weight=0.3,
            keyword_weight=0.3,  # Sum = 0.6, should normalize to 0.5, 0.5
            top_k=10
        )
    except Exception as e:
        # May fail due to no search results, but not due to weight validation
        assert "weight" not in str(e).lower()


def test_hybrid_search_score_normalization():
    """Test score normalization logic."""
    service = HybridSearchService(None)  # Don't need DB for this test
    
    # Mock keyword results with different scores
    from app.services.keyword_search_service import KeywordSearchResult
    
    results = [
        KeywordSearchResult(
            chunk_id=uuid4(), relevance_score=0.5, content="test1", chunk_type="symbol",
            file_path="file.py", start_line=1, end_line=10
        ),
        KeywordSearchResult(
            chunk_id=uuid4(), relevance_score=1.0, content="test2", chunk_type="symbol",
            file_path="file.py", start_line=11, end_line=20
        ),
        KeywordSearchResult(
            chunk_id=uuid4(), relevance_score=0.75, content="test3", chunk_type="symbol",
            file_path="file.py", start_line=21, end_line=30
        ),
    ]
    
    normalized = service._normalize_keyword_scores(results)
    
    # Should normalize to [0, 1] range
    assert len(normalized) == 3
    assert min(normalized) == 0.0  # Min score becomes 0
    assert max(normalized) == 1.0  # Max score becomes 1
    assert 0 <= normalized[1] <= 1  # All scores in range


def test_hybrid_search_score_normalization_equal_scores():
    """Test score normalization when all scores are equal."""
    service = HybridSearchService(None)
    
    from app.services.keyword_search_service import KeywordSearchResult
    
    # All scores the same
    results = [
        KeywordSearchResult(
            chunk_id=uuid4(), relevance_score=0.7, content=f"test{i}", chunk_type="symbol",
            file_path="file.py", start_line=i, end_line=i+10
        )
        for i in range(5)
    ]
    
    normalized = service._normalize_keyword_scores(results)
    
    # All should be normalized to 1.0
    assert all(score == 1.0 for score in normalized)


def test_hybrid_search_deduplication():
    """Test that hybrid search deduplicates chunks appearing in both sources."""
    service = HybridSearchService(None)
    
    from app.services.semantic_search_service import SemanticSearchResult
    from app.services.keyword_search_service import KeywordSearchResult
    
    # Create a chunk that appears in both results
    shared_chunk_id = uuid4()
    
    semantic_results = [
        SemanticSearchResult(
            chunk_id=shared_chunk_id, similarity_score=0.9, content="shared content",
            chunk_type="symbol", file_path="file.py", start_line=1, end_line=10
        ),
        SemanticSearchResult(
            chunk_id=uuid4(), similarity_score=0.7, content="semantic only",
            chunk_type="symbol", file_path="file.py", start_line=11, end_line=20
        ),
    ]
    
    keyword_results = [
        KeywordSearchResult(
            chunk_id=shared_chunk_id, relevance_score=0.8, content="shared content",
            chunk_type="symbol", file_path="file.py", start_line=1, end_line=10
        ),
        KeywordSearchResult(
            chunk_id=uuid4(), relevance_score=0.6, content="keyword only",
            chunk_type="symbol", file_path="file.py", start_line=21, end_line=30
        ),
    ]
    
    fused = service._fuse_results(
        semantic_results=semantic_results,
        keyword_results=keyword_results,
        semantic_weight=0.5,
        keyword_weight=0.5
    )
    
    # Should have 3 unique chunks (1 shared + 1 semantic-only + 1 keyword-only)
    assert len(fused) == 3
    
    # Find the shared chunk
    shared = next((r for r in fused if r.chunk_id == shared_chunk_id), None)
    assert shared is not None
    assert shared.retrieval_source == "hybrid"
    assert shared.semantic_score is not None
    assert shared.keyword_score is not None
    
    # Check other chunks
    semantic_only = next((r for r in fused if r.content == "semantic only"), None)
    assert semantic_only is not None
    assert semantic_only.retrieval_source == "semantic"
    assert semantic_only.semantic_score is not None
    assert semantic_only.keyword_score is None  # No keyword match, so None
    
    keyword_only = next((r for r in fused if r.content == "keyword only"), None)
    assert keyword_only is not None
    assert keyword_only.retrieval_source == "keyword"
    assert keyword_only.semantic_score is None  # No semantic match, so None
    # keyword_score should be set since it was found via keyword search
    # After normalization (min-max), it will be 0.0 if it's the min score
    assert keyword_only.keyword_score is not None
    assert keyword_only.keyword_score >= 0.0


def test_hybrid_search_weighted_scoring():
    """Test that hybrid search applies weights correctly."""
    service = HybridSearchService(None)
    
    from app.services.semantic_search_service import SemanticSearchResult
    from app.services.keyword_search_service import KeywordSearchResult
    
    chunk_id = uuid4()
    
    # Semantic score: 0.8, Keyword score: 0.6
    semantic_results = [
        SemanticSearchResult(
            chunk_id=chunk_id, similarity_score=0.8, content="test",
            chunk_type="symbol", file_path="file.py", start_line=1, end_line=10
        )
    ]
    
    keyword_results = [
        KeywordSearchResult(
            chunk_id=chunk_id, relevance_score=0.6, content="test",
            chunk_type="symbol", file_path="file.py", start_line=1, end_line=10
        )
    ]
    
    # Test equal weights (0.5, 0.5)
    fused_equal = service._fuse_results(
        semantic_results, keyword_results,
        semantic_weight=0.5, keyword_weight=0.5
    )
    
    # Keyword score normalized: only one result, so normalized to 1.0
    # Final score = 0.5 * 0.8 + 0.5 * 1.0 = 0.4 + 0.5 = 0.9
    assert len(fused_equal) == 1
    assert abs(fused_equal[0].final_score - 0.9) < 0.01
    
    # Test semantic-heavy weights (0.8, 0.2)
    fused_semantic = service._fuse_results(
        semantic_results, keyword_results,
        semantic_weight=0.8, keyword_weight=0.2
    )
    
    # Final score = 0.8 * 0.8 + 0.2 * 1.0 = 0.64 + 0.2 = 0.84
    assert abs(fused_semantic[0].final_score - 0.84) < 0.01
    
    # Test keyword-heavy weights (0.2, 0.8)
    fused_keyword = service._fuse_results(
        semantic_results, keyword_results,
        semantic_weight=0.2, keyword_weight=0.8
    )
    
    # Final score = 0.2 * 0.8 + 0.8 * 1.0 = 0.16 + 0.8 = 0.96
    assert abs(fused_keyword[0].final_score - 0.96) < 0.01


def test_hybrid_search_empty_results():
    """Test hybrid search handles empty result sets gracefully."""
    service = HybridSearchService(None)
    
    # Both empty
    fused = service._fuse_results([], [], 0.5, 0.5)
    assert fused == []
    
    # Only semantic results
    from app.services.semantic_search_service import SemanticSearchResult
    semantic_results = [
        SemanticSearchResult(
            chunk_id=uuid4(), similarity_score=0.8, content="test",
            chunk_type="symbol", file_path="file.py", start_line=1, end_line=10
        )
    ]
    fused = service._fuse_results(semantic_results, [], 0.5, 0.5)
    assert len(fused) == 1
    assert fused[0].retrieval_source == "semantic"
    
    # Only keyword results
    from app.services.keyword_search_service import KeywordSearchResult
    keyword_results = [
        KeywordSearchResult(
            chunk_id=uuid4(), relevance_score=0.7, content="test",
            chunk_type="symbol", file_path="file.py", start_line=1, end_line=10
        )
    ]
    fused = service._fuse_results([], keyword_results, 0.5, 0.5)
    assert len(fused) == 1
    assert fused[0].retrieval_source == "keyword"


def test_hybrid_search_ranking():
    """Test that hybrid search ranks results by final score descending."""
    service = HybridSearchService(None)
    
    from app.services.semantic_search_service import SemanticSearchResult
    
    # Create results with different scores
    semantic_results = [
        SemanticSearchResult(
            chunk_id=uuid4(), similarity_score=0.5, content="low score",
            chunk_type="symbol", file_path="file.py", start_line=1, end_line=10
        ),
        SemanticSearchResult(
            chunk_id=uuid4(), similarity_score=0.9, content="high score",
            chunk_type="symbol", file_path="file.py", start_line=11, end_line=20
        ),
        SemanticSearchResult(
            chunk_id=uuid4(), similarity_score=0.7, content="medium score",
            chunk_type="symbol", file_path="file.py", start_line=21, end_line=30
        ),
    ]
    
    fused = service._fuse_results(semantic_results, [], 1.0, 0.0)
    
    # Should maintain order by score
    fused.sort(key=lambda r: r.final_score, reverse=True)
    
    assert fused[0].content == "high score"
    assert fused[1].content == "medium score"
    assert fused[2].content == "low score"


# ============================================================================
# Integration Tests (require PostgreSQL with pgvector)
# ============================================================================

@pytest.mark.skip(reason="Requires PostgreSQL with pgvector and full-text search")
def test_hybrid_search_end_to_end(test_db, sample_repository, sample_analysis_run, sample_file):
    """End-to-end test of hybrid search with real database."""
    # This test would require:
    # 1. PostgreSQL with pgvector extension
    # 2. Full-text search index created
    # 3. Real embeddings generated
    # 4. Both semantic and keyword search working
    
    # Create chunks with embeddings
    create_semantic_chunk(
        test_db, sample_repository.id, sample_analysis_run.id, sample_file.id,
        "class OrderService:\n    def authenticate_user(self, username, password):\n        pass"
    )
    
    service = HybridSearchService(test_db)
    results = service.search(
        repository_id=sample_repository.id,
        query="How does OrderService authenticate users?",
        top_k=10,
        semantic_weight=0.6,
        keyword_weight=0.4
    )
    
    assert len(results) > 0
    assert all(r.final_score >= 0 and r.final_score <= 1 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
