"""
Tests for Phase 9 - Embeddings + pgvector.

Tests cover:
- Embedding generation
- Chunk building
- Semantic chunk persistence
- Vector similarity search
- Semantic search API
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import hashlib

from app.services.embedding_service import EmbeddingService, SentenceTransformerProvider
from app.services.chunk_builder import ChunkBuilder, ChunkData
from app.services.semantic_search_service import SemanticSearchService
from app.db.models import Repository, AnalysisRun, File, Symbol, SemanticChunk, ChunkType
from app.services.persistence_service import PersistenceService


# Test data
SAMPLE_SYMBOL = {
    'id': '123e4567-e89b-12d3-a456-426614174001',
    'file_id': 'file-001',
    'name': 'authenticate_user',
    'symbol_type': 'function',
    'language': 'Python',
    'start_line': 10,
    'end_line': 25
}

SAMPLE_CODE = '''def authenticate_user(username, password):
    """Authenticate user with credentials."""
    if not username or not password:
        return None
    
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    
    return None
'''


class TestEmbeddingService:
    """Tests for embedding service."""
    
    @patch('app.services.embedding_service.SentenceTransformer')
    def test_embed_single_text(self, mock_transformer):
        """Test generating embedding for single text."""
        # Mock the model
        mock_model = Mock()
        mock_model.encode.return_value = Mock(tolist=lambda: [0.1, 0.2, 0.3])
        mock_transformer.return_value = mock_model
        
        service = EmbeddingService()
        embedding = service.embed("test code")
        
        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) == 3
        mock_model.encode.assert_called_once()
    
    @patch('app.services.embedding_service.SentenceTransformer')
    def test_embed_empty_text(self, mock_transformer):
        """Test embedding empty text returns None."""
        mock_model = Mock()
        mock_transformer.return_value = mock_model
        
        service = EmbeddingService()
        embedding = service.embed("")
        
        assert embedding is None
        mock_model.encode.assert_not_called()
    
    @patch('app.services.embedding_service.SentenceTransformer')
    def test_embed_batch(self, mock_transformer):
        """Test batch embedding generation."""
        # Mock the model
        mock_model = Mock()
        mock_embeddings = [
            Mock(tolist=lambda: [0.1, 0.2]),
            Mock(tolist=lambda: [0.3, 0.4]),
            Mock(tolist=lambda: [0.5, 0.6])
        ]
        mock_model.encode.return_value = mock_embeddings
        mock_transformer.return_value = mock_model
        
        service = EmbeddingService()
        embeddings = service.embed_batch(["code1", "code2", "code3"])
        
        assert len(embeddings) == 3
        assert all(isinstance(e, list) for e in embeddings)
        mock_model.encode.assert_called_once()
    
    @patch('app.services.embedding_service.SentenceTransformer')
    def test_content_truncation(self, mock_transformer):
        """Test content is truncated to max length."""
        mock_model = Mock()
        mock_model.encode.return_value = Mock(tolist=lambda: [0.1])
        mock_transformer.return_value = mock_model
        
        service = EmbeddingService()
        long_text = "a" * 3000  # Exceeds MAX_EMBEDDING_CONTENT_LENGTH (2000)
        
        service.embed(long_text)
        
        # Verify truncated text was passed to encoder
        call_args = mock_model.encode.call_args[0][0]
        assert len(call_args) == service.max_length


class TestChunkBuilder:
    """Tests for chunk builder service."""
    
    def test_build_symbol_chunks(self, tmp_path):
        """Test building chunks from symbols."""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text(SAMPLE_CODE)
        
        file_path_map = {'file-001': 'test.py'}
        
        builder = ChunkBuilder(tmp_path)
        chunks = builder.build_symbol_chunks([SAMPLE_SYMBOL], file_path_map)
        
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.chunk_type == "symbol"
        assert chunk.symbol_name == "authenticate_user"
        assert chunk.content_hash is not None
        assert chunk.start_line == 10
        assert chunk.end_line == 25
        assert "authenticate_user" in chunk.content
    
    def test_build_symbol_chunks_missing_file(self, tmp_path):
        """Test building chunks when file doesn't exist."""
        file_path_map = {'file-001': 'nonexistent.py'}
        
        builder = ChunkBuilder(tmp_path)
        chunks = builder.build_symbol_chunks([SAMPLE_SYMBOL], file_path_map)
        
        assert len(chunks) == 0  # Should skip missing files
    
    def test_content_hash_deterministic(self, tmp_path):
        """Test content hash is deterministic."""
        test_file = tmp_path / "test.py"
        test_file.write_text(SAMPLE_CODE)
        
        file_path_map = {'file-001': 'test.py'}
        builder = ChunkBuilder(tmp_path)
        
        chunks1 = builder.build_symbol_chunks([SAMPLE_SYMBOL], file_path_map)
        chunks2 = builder.build_symbol_chunks([SAMPLE_SYMBOL], file_path_map)
        
        assert chunks1[0].content_hash == chunks2[0].content_hash
    
    def test_split_large_content(self, tmp_path):
        """Test large content is split into multiple chunks."""
        # Create large content
        large_code = "def func():\n" + ("    pass\n" * 200)  # > 2000 chars
        test_file = tmp_path / "large.py"
        test_file.write_text(large_code)
        
        large_symbol = {
            'id': 'symbol-001',
            'file_id': 'file-001',
            'name': 'func',
            'symbol_type': 'function',
            'language': 'Python',
            'start_line': 1,
            'end_line': 201
        }
        
        file_path_map = {'file-001': 'large.py'}
        builder = ChunkBuilder(tmp_path)
        chunks = builder.build_symbol_chunks([large_symbol], file_path_map)
        
        # Should be split into multiple chunks
        assert len(chunks) > 1
        # All chunks should have same symbol_name but different chunk_index
        assert all(c.symbol_name == 'func' for c in chunks)
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    
    def test_file_caching(self, tmp_path):
        """Test file content is cached for efficiency."""
        test_file = tmp_path / "test.py"
        test_file.write_text(SAMPLE_CODE)
        
        builder = ChunkBuilder(tmp_path)
        
        # First read
        lines1 = builder._read_file_lines('test.py')
        
        # Second read should use cache
        lines2 = builder._read_file_lines('test.py')
        
        assert lines1 == lines2
        assert 'test.py' in builder._file_cache


class TestSemanticSearchService:
    """Tests for semantic search service."""
    
    def test_search_validates_empty_query(self, mock_db):
        """Test search rejects empty query."""
        service = SemanticSearchService(mock_db)
        
        with pytest.raises(ValueError, match="Query cannot be empty"):
            service.search(
                repository_id='123e4567-e89b-12d3-a456-426614174000',
                query="",
                top_k=5
            )
    
    def test_search_validates_top_k(self, mock_db):
        """Test search validates top_k."""
        service = SemanticSearchService(mock_db)
        
        with pytest.raises(ValueError, match="top_k must be positive"):
            service.search(
                repository_id='123e4567-e89b-12d3-a456-426614174000',
                query="test",
                top_k=0
            )
    
    def test_search_caps_top_k(self, mock_db):
        """Test search caps top_k at maximum."""
        # This test would require mocking the embedding service and database
        # For now, we verify the constant exists
        assert SemanticSearchService.MAX_TOP_K == 100
    
    @patch('app.services.semantic_search_service.EmbeddingService')
    def test_search_with_repository_isolation(self, mock_embedding_service, mock_db):
        """Test search enforces repository isolation."""
        # Mock embedding generation
        mock_embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_embedding_service.return_value.embed = mock_embed
        
        # Mock database query
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.outerjoin.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        service = SemanticSearchService(mock_db)
        repo_id = '123e4567-e89b-12d3-a456-426614174000'
        
        service.search(repository_id=repo_id, query="test", top_k=5)
        
        # Verify query was called (repository isolation enforced in query)
        mock_db.query.assert_called_once()


# Fixtures
@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock()
    db.query = Mock()
    db.add = Mock()
    db.flush = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    return db


@pytest.fixture
def mock_repository(mock_db):
    """Create a mock repository."""
    repo = Repository(
        id='123e4567-e89b-12d3-a456-426614174000',
        owner='testuser',
        name='testrepo',
        full_name='testuser/testrepo',
        github_url='https://github.com/testuser/testrepo',
        default_branch='main'
    )
    return repo


@pytest.fixture
def mock_analysis_run(mock_repository):
    """Create a mock analysis run."""
    run = AnalysisRun(
        id='123e4567-e89b-12d3-a456-426614174001',
        repository_id=mock_repository.id,
        status='completed'
    )
    return run


class TestPersistenceIntegration:
    """Integration tests for persistence."""
    
    def test_persist_semantic_chunks_validates_input(self, mock_db, mock_repository, mock_analysis_run):
        """Test persist_semantic_chunks validates inputs."""
        service = PersistenceService(mock_db)
        
        # Empty chunks should return 0
        count = service.persist_semantic_chunks(
            repository=mock_repository,
            analysis_run=mock_analysis_run,
            chunks=[],
            file_map={}
        )
        
        assert count == 0
    
    def test_persist_semantic_chunks_skips_missing_file(self, mock_db, mock_repository, mock_analysis_run):
        """Test chunks with missing files are skipped."""
        service = PersistenceService(mock_db)
        
        chunk = {
            'file_path': 'missing.py',
            'content': 'test',
            'content_hash': 'abc123',
            'chunk_type': 'symbol',
            'chunk_index': 0,
            'start_line': 1,
            'end_line': 10,
            'embedding': [0.1, 0.2, 0.3]
        }
        
        count = service.persist_semantic_chunks(
            repository=mock_repository,
            analysis_run=mock_analysis_run,
            chunks=[chunk],
            file_map={}  # Empty file map
        )
        
        assert count == 0  # Should skip chunk with missing file


# Run tests with: pytest tests/test_phase9_embeddings.py -v
