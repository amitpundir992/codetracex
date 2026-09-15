"""
Keyword search service using PostgreSQL full-text search.

Phase 10: Hybrid Retrieval

This service provides deterministic keyword-based retrieval using PostgreSQL's
native full-text search capabilities (tsvector, tsquery).

Architecture:
    
    User Query
        ↓
    KeywordSearchService (query → tsquery)
        ↓
    PostgreSQL full-text search (tsvector GIN index)
        ↓
    Ranked chunks with relevance scores

Features:
    - PostgreSQL full-text search (no external search engine)
    - GIN index for fast text matching
    - ts_rank for relevance scoring
    - Repository isolation
    - Analysis run filtering
    - Chunk type filtering
    - Bounded top_k

Search Behavior:
    - Exact matches: "OrderService" → finds OrderService
    - API paths: "/api/orders" → finds matching paths
    - Technology names: "Razorpay" → finds framework mentions
    - Symbol names: function and class names
    - Multi-word: "user authentication" → finds both words

Security:
    - Repository isolation enforced
    - Analysis run isolation supported
    - Bounded top_k to prevent resource exhaustion
    - UUID validation
    - Parameterized queries (no SQL injection)
"""
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, text
from sqlalchemy.sql import select

from app.db.models import SemanticChunk, File, Symbol, ApiEndpoint

logger = logging.getLogger(__name__)


class KeywordSearchResult:
    """
    Container for a keyword search result.
    
    Maintains compatibility with SemanticSearchResult for easy fusion.
    """
    
    def __init__(
        self,
        chunk_id: UUID,
        relevance_score: float,
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
        self.relevance_score = relevance_score
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
            'relevance_score': self.relevance_score,
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


class KeywordSearchService:
    """
    Service for keyword-based full-text search over repository chunks.
    
    This service handles:
    - PostgreSQL full-text search query generation
    - Relevance ranking using ts_rank
    - Repository isolation
    - Result limiting
    - Source traceability extraction
    
    Usage:
        service = KeywordSearchService(db)
        results = service.search(
            repository_id=repo_id,
            query="OrderService",
            top_k=10
        )
    """
    
    MAX_TOP_K = 100  # Maximum results to prevent resource exhaustion
    
    def __init__(self, db: Session):
        """
        Initialize keyword search service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def search(
        self,
        repository_id: UUID,
        query: str,
        top_k: int = 10,
        analysis_run_id: Optional[UUID] = None
    ) -> List[KeywordSearchResult]:
        """
        Perform keyword-based full-text search.
        
        This method:
        1. Converts query to PostgreSQL tsquery
        2. Executes full-text search against tsvector column
        3. Ranks results by relevance (ts_rank)
        4. Enforces repository isolation
        5. Returns ranked results with source traceability
        
        Args:
            repository_id: UUID of repository to search
            query: Keyword query (e.g., "OrderService", "/api/orders")
            top_k: Number of results to return (max 100)
            analysis_run_id: Optional UUID to filter by specific analysis
            
        Returns:
            List of KeywordSearchResult objects, ranked by relevance
            
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
        
        # Build query filters
        query_filter = [SemanticChunk.repository_id == repository_id]
        
        # Optional analysis run filtering
        if analysis_run_id:
            query_filter.append(SemanticChunk.analysis_run_id == analysis_run_id)
        
        # Prepare tsquery
        # Use websearch_to_tsquery for more user-friendly query parsing
        # It handles phrases, AND/OR logic, and special characters better
        # Alternative: plainto_tsquery (simpler, treats everything as AND)
        tsquery_text = f"websearch_to_tsquery('english', :query)"
        
        try:
            # Execute full-text search
            # ts_rank returns relevance score (higher = more relevant)
            results = (
                self.db.query(
                    SemanticChunk,
                    func.ts_rank(SemanticChunk.content_tsv, text(tsquery_text)).label('rank'),
                    File.path.label('file_path'),
                    Symbol.name.label('symbol_name'),
                    Symbol.symbol_type.label('symbol_type'),
                    ApiEndpoint.method.label('api_method'),
                    ApiEndpoint.path.label('api_path')
                )
                .join(File, SemanticChunk.file_id == File.id)
                .outerjoin(Symbol, SemanticChunk.symbol_id == Symbol.id)
                .outerjoin(ApiEndpoint, SemanticChunk.api_endpoint_id == ApiEndpoint.id)
                .filter(
                    and_(*query_filter),
                    SemanticChunk.content_tsv.op('@@')(text(tsquery_text))
                )
                .params(query=query)
                .order_by(text('rank DESC'))
                .limit(top_k)
                .all()
            )
            
            logger.info(f"Found {len(results)} matching chunks for keyword query: {query[:50]}...")
            
            # Convert to KeywordSearchResult objects
            search_results = []
            for chunk, rank, file_path, symbol_name, symbol_type, api_method, api_path in results:
                result = KeywordSearchResult(
                    chunk_id=chunk.id,
                    relevance_score=float(rank),
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
                    metadata=None
                )
                search_results.append(result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            raise
    
    def search_by_chunk_type(
        self,
        repository_id: UUID,
        query: str,
        chunk_type: str,
        top_k: int = 10,
        analysis_run_id: Optional[UUID] = None
    ) -> List[KeywordSearchResult]:
        """
        Perform keyword search filtered by chunk type.
        
        Args:
            repository_id: UUID of repository to search
            query: Keyword query
            chunk_type: Type of chunks to search ("symbol", "api_endpoint", etc.)
            top_k: Number of results to return
            analysis_run_id: Optional UUID to filter by specific analysis
            
        Returns:
            List of KeywordSearchResult objects
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
        
        # Build query filters
        query_filter = [
            SemanticChunk.repository_id == repository_id,
            SemanticChunk.chunk_type == chunk_type_enum
        ]
        
        if analysis_run_id:
            query_filter.append(SemanticChunk.analysis_run_id == analysis_run_id)
        
        # Prepare tsquery
        tsquery_text = f"websearch_to_tsquery('english', :query)"
        
        try:
            # Execute search
            results = (
                self.db.query(
                    SemanticChunk,
                    func.ts_rank(SemanticChunk.content_tsv, text(tsquery_text)).label('rank'),
                    File.path.label('file_path'),
                    Symbol.name.label('symbol_name'),
                    Symbol.symbol_type.label('symbol_type'),
                    ApiEndpoint.method.label('api_method'),
                    ApiEndpoint.path.label('api_path')
                )
                .join(File, SemanticChunk.file_id == File.id)
                .outerjoin(Symbol, SemanticChunk.symbol_id == Symbol.id)
                .outerjoin(ApiEndpoint, SemanticChunk.api_endpoint_id == ApiEndpoint.id)
                .filter(
                    and_(*query_filter),
                    SemanticChunk.content_tsv.op('@@')(text(tsquery_text))
                )
                .params(query=query)
                .order_by(text('rank DESC'))
                .limit(top_k)
                .all()
            )
            
            # Convert to KeywordSearchResult objects
            search_results = []
            for chunk, rank, file_path, symbol_name, symbol_type, api_method, api_path in results:
                result = KeywordSearchResult(
                    chunk_id=chunk.id,
                    relevance_score=float(rank),
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
            logger.error(f"Keyword search by type failed: {e}")
            raise
