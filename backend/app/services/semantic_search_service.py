"""
Semantic search service using pgvector similarity.

Phase 9: Embeddings + pgvector

This service provides semantic similarity search over repository chunks.

Architecture:
    
    User Query
        ↓
    EmbeddingService (query → vector)
        ↓
    SemanticSearchService (similarity search)
        ↓
    pgvector cosine similarity
        ↓
    Ranked chunks with source traceability

Security:
    - Repository isolation enforced
    - Analysis run isolation supported
    - Bounded top_k to prevent resource exhaustion
    - UUID validation
    
Similarity Metric:
    - Cosine similarity (via vector_cosine_ops index)
    - Returns distance (lower = more similar)
    - Distance is converted to similarity score (1 - distance)
"""
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.db.models import SemanticChunk, File, Symbol, ApiEndpoint
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class SemanticSearchResult:
    """
    Container for a semantic search result.
    
    Provides source traceability for RAG/citation.
    """
    
    def __init__(
        self,
        chunk_id: UUID,
        similarity_score: float,
        content: str,
        chunk_type: str,
        file_path: str,
        start_line: int,
        end_line: int,
        language: Optional[str] = None,
        symbol_name: Optional[str] = None,
        symbol_type: Optional[str] = None,
        api_endpoint_method: Optional[str] = None,
        api_endpoint_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.chunk_id = chunk_id
        self.similarity_score = similarity_score
        self.content = content
        self.chunk_type = chunk_type
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.language = language
        self.symbol_name = symbol_name
        self.symbol_type = symbol_type
        self.api_endpoint_method = api_endpoint_method
        self.api_endpoint_path = api_endpoint_path
        self.metadata = metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'chunk_id': str(self.chunk_id),
            'similarity_score': self.similarity_score,
            'content': self.content,
            'chunk_type': self.chunk_type,
            'file_path': self.file_path,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'language': self.language,
            'symbol_name': self.symbol_name,
            'symbol_type': self.symbol_type,
            'api_endpoint_method': self.api_endpoint_method,
            'api_endpoint_path': self.api_endpoint_path,
            'metadata': self.metadata
        }


class SemanticSearchService:
    """
    Service for semantic similarity search over repository chunks.
    
    This service handles:
    - Query embedding generation
    - pgvector similarity search
    - Repository isolation
    - Result ranking and limiting
    - Source traceability extraction
    
    Usage:
        service = SemanticSearchService(db)
        results = service.search(
            repository_id=repo_id,
            query="how does authentication work?",
            top_k=5
        )
    """
    
    MAX_TOP_K = 100  # Maximum results to prevent resource exhaustion
    
    def __init__(self, db: Session):
        """
        Initialize semantic search service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.embedding_service = EmbeddingService()
    
    def search(
        self,
        repository_id: UUID,
        query: str,
        top_k: int = 10,
        analysis_run_id: Optional[UUID] = None
    ) -> List[SemanticSearchResult]:
        """
        Perform semantic similarity search.
        
        This method:
        1. Generates query embedding
        2. Executes pgvector similarity search
        3. Enforces repository isolation
        4. Returns ranked results with source traceability
        
        Args:
            repository_id: UUID of repository to search
            query: Natural language query
            top_k: Number of results to return (max 100)
            analysis_run_id: Optional UUID to filter by specific analysis
            
        Returns:
            List of SemanticSearchResult objects, ranked by similarity
            
        Raises:
            ValueError: If top_k exceeds maximum or query is empty
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        
        if top_k > self.MAX_TOP_K:
            logger.warning(f"top_k={top_k} exceeds maximum, capping at {self.MAX_TOP_K}")
            top_k = self.MAX_TOP_K
        
        # Generate query embedding
        logger.info(f"Generating embedding for query: {query[:50]}...")
        query_embedding = self.embedding_service.embed(query)
        
        if query_embedding is None:
            logger.error("Failed to generate query embedding")
            return []
        
        # Build query with repository isolation
        query_filter = [SemanticChunk.repository_id == repository_id]
        
        # Optional analysis run filtering
        if analysis_run_id:
            query_filter.append(SemanticChunk.analysis_run_id == analysis_run_id)
        
        # Execute similarity search using pgvector
        # cosine distance: <=> operator in pgvector
        # Lower distance = more similar
        try:
            results = (
                self.db.query(
                    SemanticChunk,
                    SemanticChunk.embedding.cosine_distance(query_embedding).label('distance'),
                    File.path.label('file_path'),
                    Symbol.name.label('symbol_name'),
                    Symbol.symbol_type.label('symbol_type'),
                    ApiEndpoint.method.label('api_method'),
                    ApiEndpoint.path.label('api_path')
                )
                .join(File, SemanticChunk.file_id == File.id)
                .outerjoin(Symbol, SemanticChunk.symbol_id == Symbol.id)
                .outerjoin(ApiEndpoint, SemanticChunk.api_endpoint_id == ApiEndpoint.id)
                .filter(and_(*query_filter))
                .order_by('distance')
                .limit(top_k)
                .all()
            )
            
            logger.info(f"Found {len(results)} similar chunks")
            
            # Convert to SearchResult objects
            search_results = []
            for chunk, distance, file_path, symbol_name, symbol_type, api_method, api_path in results:
                # Convert distance to similarity score (1 - distance for cosine)
                similarity_score = 1.0 - distance
                
                result = SemanticSearchResult(
                    chunk_id=chunk.id,
                    similarity_score=similarity_score,
                    content=chunk.content,
                    chunk_type=chunk.chunk_type.value,
                    file_path=file_path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    language=chunk.language,
                    symbol_name=symbol_name,
                    symbol_type=symbol_type.value if symbol_type else None,
                    api_endpoint_method=api_method.value if api_method else None,
                    api_endpoint_path=api_path,
                    metadata=None  # Can parse chunk.metadata_json if needed
                )
                search_results.append(result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise
    
    def search_by_chunk_type(
        self,
        repository_id: UUID,
        query: str,
        chunk_type: str,
        top_k: int = 10,
        analysis_run_id: Optional[UUID] = None
    ) -> List[SemanticSearchResult]:
        """
        Perform semantic search filtered by chunk type.
        
        Args:
            repository_id: UUID of repository to search
            query: Natural language query
            chunk_type: Type of chunks to search ("symbol", "api_endpoint", etc.)
            top_k: Number of results to return
            analysis_run_id: Optional UUID to filter by specific analysis
            
        Returns:
            List of SemanticSearchResult objects
        """
        from app.db.models import ChunkType
        
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        
        if top_k > self.MAX_TOP_K:
            top_k = self.MAX_TOP_K
        
        # Validate chunk_type
        try:
            chunk_type_enum = ChunkType[chunk_type.upper()]
        except KeyError:
            raise ValueError(f"Invalid chunk type: {chunk_type}")
        
        # Generate query embedding
        query_embedding = self.embedding_service.embed(query)
        
        if query_embedding is None:
            logger.error("Failed to generate query embedding")
            return []
        
        # Build query with filters
        query_filter = [
            SemanticChunk.repository_id == repository_id,
            SemanticChunk.chunk_type == chunk_type_enum
        ]
        
        if analysis_run_id:
            query_filter.append(SemanticChunk.analysis_run_id == analysis_run_id)
        
        # Execute search
        try:
            results = (
                self.db.query(
                    SemanticChunk,
                    SemanticChunk.embedding.cosine_distance(query_embedding).label('distance'),
                    File.path.label('file_path'),
                    Symbol.name.label('symbol_name'),
                    Symbol.symbol_type.label('symbol_type'),
                    ApiEndpoint.method.label('api_method'),
                    ApiEndpoint.path.label('api_path')
                )
                .join(File, SemanticChunk.file_id == File.id)
                .outerjoin(Symbol, SemanticChunk.symbol_id == Symbol.id)
                .outerjoin(ApiEndpoint, SemanticChunk.api_endpoint_id == ApiEndpoint.id)
                .filter(and_(*query_filter))
                .order_by('distance')
                .limit(top_k)
                .all()
            )
            
            # Convert to SearchResult objects
            search_results = []
            for chunk, distance, file_path, symbol_name, symbol_type, api_method, api_path in results:
                similarity_score = 1.0 - distance
                
                result = SemanticSearchResult(
                    chunk_id=chunk.id,
                    similarity_score=similarity_score,
                    content=chunk.content,
                    chunk_type=chunk.chunk_type.value,
                    file_path=file_path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    language=chunk.language,
                    symbol_name=symbol_name,
                    symbol_type=symbol_type.value if symbol_type else None,
                    api_endpoint_method=api_method.value if api_method else None,
                    api_endpoint_path=api_path
                )
                search_results.append(result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Semantic search by type failed: {e}")
            raise
