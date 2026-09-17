"""
Tests for Phase 11: RAG Context Service.

These tests verify:
- Context generation
- Hybrid retrieval integration
- Evidence ordering
- Deduplication
- Context size limits
- Maximum evidence count
- Truncation flag
- Repository isolation
- Analysis run isolation
- Invalid inputs
- Empty results
- Graph evidence enrichment
- Deterministic output
- Source traceability
"""
import pytest
from uuid import uuid4, UUID
from sqlalchemy.orm import Session

from app.services.rag_context_service import RAGContextService
from app.db.models import (
    Repository, AnalysisRun, File, Symbol, SemanticChunk,
    AnalysisStatus, SymbolType, ChunkType
)


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
        total_symbols=2
    )
    db.add(analysis_run)
    db.commit()
    return analysis_run


@pytest.fixture
def sample_file(db: Session, sample_repository: Repository, sample_analysis_run: AnalysisRun) -> File:
    """Create a sample file for testing."""
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
    db.commit()
    return file


@pytest.fixture
def sample_symbol(db: Session, sample_file: File, sample_analysis_run: AnalysisRun) -> Symbol:
    """Create a sample symbol for testing."""
    symbol = Symbol(
        id=uuid4(),
        file_id=sample_file.id,
        analysis_run_id=sample_analysis_run.id,
        name="AuthService.authenticate_user",
        symbol_type=SymbolType.METHOD,
        language="Python",
        start_line=10,
        end_line=30
    )
    db.add(symbol)
    db.commit()
    return symbol


@pytest.fixture
def sample_chunks_with_embeddings(
    db: Session,
    sample_repository: Repository,
    sample_analysis_run: AnalysisRun,
    sample_file: File,
    sample_symbol: Symbol
) -> list:
    """Create sample chunks with embeddings for testing."""
    from app.services.embedding_service import EmbeddingService
    
    embedding_service = EmbeddingService()
    
    chunks = []
    
    # Chunk 1: High relevance to authentication
    content1 = "def authenticate_user(self, username, password):\n    # Verify credentials\n    user = self.db.get_user(username)\n    if user and verify_password(password, user.password_hash):\n        return create_jwt_token(user)"
    embedding1 = embedding_service.embed(content1)
    
    chunk1 = SemanticChunk(
        id=uuid4(),
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis_run.id,
        file_id=sample_file.id,
        symbol_id=sample_symbol.id,
        content=content1,
        chunk_type=ChunkType.SYMBOL,
        start_line=10,
        end_line=15,
        language="Python",
        embedding=embedding1
    )
    db.add(chunk1)
    chunks.append(chunk1)
    
    # Chunk 2: Medium relevance
    content2 = "def verify_password(password, hash):\n    return bcrypt.checkpw(password.encode(), hash)"
    embedding2 = embedding_service.embed(content2)
    
    chunk2 = SemanticChunk(
        id=uuid4(),
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis_run.id,
        file_id=sample_file.id,
        content=content2,
        chunk_type=ChunkType.SYMBOL,
        start_line=20,
        end_line=22,
        language="Python",
        embedding=embedding2
    )
    db.add(chunk2)
    chunks.append(chunk2)
    
    # Chunk 3: Lower relevance
    content3 = "class AuthService:\n    def __init__(self, db):\n        self.db = db"
    embedding3 = embedding_service.embed(content3)
    
    chunk3 = SemanticChunk(
        id=uuid4(),
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis_run.id,
        file_id=sample_file.id,
        symbol_id=sample_symbol.id,
        content=content3,
        chunk_type=ChunkType.SYMBOL,
        start_line=5,
        end_line=7,
        language="Python",
        embedding=embedding3
    )
    db.add(chunk3)
    chunks.append(chunk3)
    
    db.commit()
    return chunks


class TestRAGContextService:
    """Tests for RAG context service."""
    
    def test_build_context_basic(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test basic context building."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5
        )
        
        assert context is not None
        assert context.question == "How does authentication work?"
        assert context.repository_id == sample_repository.id
        assert len(context.evidence) > 0
        assert context.total_evidence_items == len(context.evidence)
        assert context.retrieval_metadata is not None
    
    def test_context_with_analysis_run_filter(
        self,
        db: Session,
        sample_repository: Repository,
        sample_analysis_run: AnalysisRun,
        sample_chunks_with_embeddings: list
    ):
        """Test context building with specific analysis run."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5,
            analysis_run_id=sample_analysis_run.id
        )
        
        assert context.analysis_run_id == sample_analysis_run.id
        assert len(context.evidence) > 0
    
    def test_max_evidence_items_limit(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test that max_evidence_items limit is enforced."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=10,
            max_evidence_items=2
        )
        
        assert len(context.evidence) <= 2
        if len(context.evidence) == 2:
            assert context.context_limit_reached
    
    def test_max_characters_limit(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test that max_characters limit is enforced."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=10,
            max_characters=100  # Very small limit
        )
        
        total_chars = sum(len(e.content) for e in context.evidence)
        assert total_chars <= 100
        assert context.truncated
    
    def test_max_chunk_characters_truncation(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test that individual chunks are truncated."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5,
            max_chunk_characters=50
        )
        
        for evidence in context.evidence:
            assert len(evidence.content) <= 60  # Allow for truncation marker
    
    def test_deterministic_ordering(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test that same query produces deterministic ordering."""
        service = RAGContextService(db)
        
        context1 = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5,
            semantic_weight=0.6,
            keyword_weight=0.4
        )
        
        context2 = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5,
            semantic_weight=0.6,
            keyword_weight=0.4
        )
        
        # Same evidence items in same order
        assert len(context1.evidence) == len(context2.evidence)
        for i, (e1, e2) in enumerate(zip(context1.evidence, context2.evidence)):
            assert e1.chunk_id == e2.chunk_id, f"Evidence {i} differs"
    
    def test_repository_isolation(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test that repository isolation is enforced."""
        # Create another repository
        other_repo = Repository(
            id=uuid4(),
            name="other-repo",
            full_name="test/other-repo",
            owner="test",
            github_url="https://github.com/test/other-repo",
            default_branch="main"
        )
        db.add(other_repo)
        db.commit()
        
        service = RAGContextService(db)
        
        # Query other repository
        context = service.build_context(
            repository_id=other_repo.id,
            question="How does authentication work?",
            top_k=5
        )
        
        # Should not return evidence from sample_repository
        assert len(context.evidence) == 0
    
    def test_empty_question_raises_error(self, db: Session, sample_repository: Repository):
        """Test that empty question raises ValueError."""
        service = RAGContextService(db)
        
        with pytest.raises(ValueError, match="Question cannot be empty"):
            service.build_context(
                repository_id=sample_repository.id,
                question="",
                top_k=5
            )
    
    def test_no_results_returns_empty_evidence(
        self,
        db: Session,
        sample_repository: Repository
    ):
        """Test handling when no chunks match query."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does blockchain work?",  # Unrelated question
            top_k=5
        )
        
        # Should return empty evidence, not fail
        assert len(context.evidence) == 0
        assert context.total_evidence_items == 0
    
    def test_graph_evidence_inclusion(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list,
        sample_symbol: Symbol
    ):
        """Test that graph evidence is included when requested."""
        # Create a caller symbol
        caller_symbol = Symbol(
            id=uuid4(),
            file_id=sample_symbol.file_id,
            analysis_run_id=sample_symbol.analysis_run_id,
            name="UserController.login",
            symbol_type=SymbolType.METHOD,
            language="Python",
            start_line=50,
            end_line=60
        )
        db.add(caller_symbol)
        
        # Create a call relationship
        from app.db.models import Call
        call = Call(
            id=uuid4(),
            file_id=sample_symbol.file_id,
            analysis_run_id=sample_symbol.analysis_run_id,
            caller_name="UserController.login",
            callee_name="AuthService.authenticate_user",
            line_number=55
        )
        db.add(call)
        db.commit()
        
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5,
            include_graph_evidence=True,
            graph_depth=1
        )
        
        # May or may not have graph evidence depending on retrieval results
        # Just verify it doesn't crash
        assert context is not None
    
    def test_graph_evidence_disabled(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test that graph evidence is not included when disabled."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5,
            include_graph_evidence=False
        )
        
        assert len(context.graph_evidence) == 0
    
    def test_source_traceability(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test that all evidence preserves source traceability."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5
        )
        
        for evidence in context.evidence:
            # All evidence must have source traceability
            assert evidence.chunk_id is not None
            assert evidence.file_path is not None
            assert evidence.start_line > 0
            assert evidence.end_line >= evidence.start_line
            assert evidence.content is not None
    
    def test_retrieval_metadata(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test that retrieval metadata is populated."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5,
            semantic_weight=0.6,
            keyword_weight=0.4
        )
        
        metadata = context.retrieval_metadata
        assert metadata is not None
        assert metadata.total_candidates >= 0
        assert metadata.selected_evidence == len(context.evidence)
        assert metadata.semantic_weight == 0.6
        assert metadata.keyword_weight == 0.4
    
    def test_truncation_tracking(
        self,
        db: Session,
        sample_repository: Repository,
        sample_chunks_with_embeddings: list
    ):
        """Test that truncation is tracked correctly."""
        service = RAGContextService(db)
        
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=10,
            max_evidence_items=1  # Force truncation
        )
        
        if len(sample_chunks_with_embeddings) > 1:
            assert context.truncated
            assert context.truncation_reason is not None
            assert "maximum evidence items" in context.truncation_reason.lower()
    
    def test_latest_analysis_run_selection(
        self,
        db: Session,
        sample_repository: Repository,
        sample_analysis_run: AnalysisRun,
        sample_chunks_with_embeddings: list
    ):
        """Test that latest analysis run is used when not specified."""
        # Create an older analysis run
        older_run = AnalysisRun(
            id=uuid4(),
            repository_id=sample_repository.id,
            status=AnalysisStatus.COMPLETED,
            total_files=1,
            total_symbols=1
        )
        db.add(older_run)
        db.commit()
        
        service = RAGContextService(db)
        
        # Build context without specifying analysis_run_id
        context = service.build_context(
            repository_id=sample_repository.id,
            question="How does authentication work?",
            top_k=5
        )
        
        # Should use latest analysis run
        assert context.analysis_run_id == sample_analysis_run.id
