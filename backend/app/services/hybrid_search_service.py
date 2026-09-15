"""
Hybrid search service combining semantic and keyword retrieval.

Phase 10: Hybrid Retrieval

This service orchestrates the fusion of semantic (vector) and keyword (full-text)
retrieval to provide superior search results across different query types.

Architecture:
    
    User Query
        |
        +----------------------+
        |                      |
        v                      v
    Vector Retrieval      Keyword Retrieval
    (pgvector)            (PostgreSQL FTS)
        |                      |
        +----------+-----------+
                   |
                   v
            Score Normalization
                   |
                   v
             Result Fusion
                   |
                   v
         Deterministically Ranked
               Results

Fusion Algorithm:
    
    1. Execute both searches in parallel
    2. Normalize scores to [0, 1] range:
       - Semantic: Already in [0, 1] (1 - cosine distance)
       - Keyword: Normalize ts_rank using min-max scaling
    3. Apply configurable weights:
       - Semantic weight (default: 0.5)
       - Keyword weight (default: 0.5)
    4. Combine scores:
       final_score = (semantic_weight * semantic_score) + (keyword_weight * keyword_score)
    5. Deduplicate chunks (same chunk_id from both sources)
    6. Rank by final score descending
    7. Return top_k results

Score Interpretation:
    - Semantic score: Cosine similarity (0-1, higher = more similar)
    - Keyword score: PostgreSQL ts_rank (normalized to 0-1)
    - Final score: Weighted combination (0-1, higher = better match)

Deduplication:
    - Chunks appearing in both result sets are merged
    - Final score uses combined weighted score
    - Metadata preserved from both sources

Security:
    - Repository isolation enforced at search level
    - Analysis run isolation preserved
    - Bounded top_k prevents resource exhaustion
    - No SQL injection (parameterized queries)
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.semantic_search_service import SemanticSearchService, SemanticSearchResult
from app.services.keyword_search_service import KeywordSearchService, KeywordSearchResult

logger = logging.getLogger(__name__)


class HybridSearchResult:
    """
    Container for a hybrid search result.
    
    Includes scores from both retrieval methods plus final combined score.
    """
    
    def __init__(
        self,
        chunk_id: UUID,
        final_score: float,
        semantic_score: Optional[float],
        keyword_score: Optional[float],
        retrieval_source: str,  # 'semantic', 'keyword', or 'hybrid'
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
        self.final_score = final_score
        self.semantic_score = semantic_score
        self.keyword_score = keyword_score
        self.retrieval_source = retrieval_source
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
            'final_score': self.final_score,
            'semantic_score': self.semantic_score,
            'keyword_score': self.keyword_score,
            'retrieval_source': self.retrieval_source,
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


class HybridSearchService:
    """
    Service for hybrid semantic + keyword search with result fusion.
    
    This service handles:
    - Parallel execution of semantic and keyword searches
    - Score normalization
    - Result fusion with configurable weights
    - Deduplication
    - Final ranking
    
    Usage:
        service = HybridSearchService(db)
        results = service.search(
            repository_id=repo_id,
            query="How does OrderService authenticate users?",
            top_k=10,
            semantic_weight=0.6,
            keyword_weight=0.4
        )
    """
    
    MAX_TOP_K = 100  # Maximum results to prevent resource exhaustion
    DEFAULT_SEMANTIC_WEIGHT = 0.5
    DEFAULT_KEYWORD_WEIGHT = 0.5
    
    def __init__(self, db: Session):
        """
        Initialize hybrid search service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.semantic_service = SemanticSearchService(db)
        self.keyword_service = KeywordSearchService(db)
    
    def search(
        self,
        repository_id: UUID,
        query: str,
        top_k: int = 10,
        semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
        keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
        analysis_run_id: Optional[UUID] = None
    ) -> List[HybridSearchResult]:
        """
        Perform hybrid search combining semantic and keyword retrieval.
        
        This method:
        1. Executes semantic search (vector similarity)
        2. Executes keyword search (full-text)
        3. Normalizes scores from both sources
        4. Applies configurable weights
        5. Fuses and deduplicates results
        6. Returns top_k ranked results
        
        Args:
            repository_id: UUID of repository to search
            query: Natural language or keyword query
            top_k: Number of results to return (max 100)
            semantic_weight: Weight for semantic scores (0-1, default: 0.5)
            keyword_weight: Weight for keyword scores (0-1, default: 0.5)
            analysis_run_id: Optional UUID to filter by specific analysis
            
        Returns:
            List of HybridSearchResult objects, ranked by final score
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        
        if top_k > self.MAX_TOP_K:
            logger.warning(f"top_k={top_k} exceeds maximum, capping at {self.MAX_TOP_K}")
            top_k = self.MAX_TOP_K
        
        # Validate weights
        if semantic_weight < 0 or semantic_weight > 1:
            raise ValueError("semantic_weight must be between 0 and 1")
        
        if keyword_weight < 0 or keyword_weight > 1:
            raise ValueError("keyword_weight must be between 0 and 1")
        
        # Weights should sum to 1 for normalized combination
        # Auto-normalize if they don't
        weight_sum = semantic_weight + keyword_weight
        if weight_sum == 0:
            raise ValueError("At least one weight must be greater than 0")
        
        if abs(weight_sum - 1.0) > 0.01:  # Allow small floating point differences
            logger.warning(f"Weights sum to {weight_sum}, normalizing to 1.0")
            semantic_weight = semantic_weight / weight_sum
            keyword_weight = keyword_weight / weight_sum
        
        logger.info(f"Hybrid search: query='{query[:50]}...', weights=(sem={semantic_weight:.2f}, kw={keyword_weight:.2f})")
        
        # Execute both searches
        # Request more results than top_k to ensure we have enough after fusion
        # Use 2x top_k as a heuristic (will deduplicate later)
        retrieval_k = min(top_k * 2, self.MAX_TOP_K)
        
        semantic_results: List[SemanticSearchResult] = []
        keyword_results: List[KeywordSearchResult] = []
        
        # Execute semantic search
        try:
            semantic_results = self.semantic_service.search(
                repository_id=repository_id,
                query=query,
                top_k=retrieval_k,
                analysis_run_id=analysis_run_id
            )
            logger.info(f"Semantic search returned {len(semantic_results)} results")
        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")
            # Continue with keyword-only results
        
        # Execute keyword search
        try:
            keyword_results = self.keyword_service.search(
                repository_id=repository_id,
                query=query,
                top_k=retrieval_k,
                analysis_run_id=analysis_run_id
            )
            logger.info(f"Keyword search returned {len(keyword_results)} results")
        except Exception as e:
            logger.warning(f"Keyword search failed: {e}")
            # Continue with semantic-only results
        
        # If both searches failed, return empty
        if not semantic_results and not keyword_results:
            logger.warning("Both semantic and keyword searches returned no results")
            return []
        
        # Normalize and fuse results
        hybrid_results = self._fuse_results(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight
        )
        
        # Sort by final score descending and return top_k
        hybrid_results.sort(key=lambda r: r.final_score, reverse=True)
        
        return hybrid_results[:top_k]
    
    def search_by_chunk_type(
        self,
        repository_id: UUID,
        query: str,
        chunk_type: str,
        top_k: int = 10,
        semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
        keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
        analysis_run_id: Optional[UUID] = None
    ) -> List[HybridSearchResult]:
        """
        Perform hybrid search filtered by chunk type.
        
        Args:
            repository_id: UUID of repository to search
            query: Natural language or keyword query
            chunk_type: Type of chunks to search ("symbol", "api_endpoint", etc.)
            top_k: Number of results to return
            semantic_weight: Weight for semantic scores
            keyword_weight: Weight for keyword scores
            analysis_run_id: Optional UUID to filter by specific analysis
            
        Returns:
            List of HybridSearchResult objects
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        
        if top_k > self.MAX_TOP_K:
            top_k = self.MAX_TOP_K
        
        # Validate and normalize weights
        weight_sum = semantic_weight + keyword_weight
        if weight_sum == 0:
            raise ValueError("At least one weight must be greater than 0")
        
        if abs(weight_sum - 1.0) > 0.01:
            semantic_weight = semantic_weight / weight_sum
            keyword_weight = keyword_weight / weight_sum
        
        # Execute both searches
        retrieval_k = min(top_k * 2, self.MAX_TOP_K)
        
        semantic_results: List[SemanticSearchResult] = []
        keyword_results: List[KeywordSearchResult] = []
        
        # Execute semantic search with chunk_type filter
        try:
            semantic_results = self.semantic_service.search_by_chunk_type(
                repository_id=repository_id,
                query=query,
                chunk_type=chunk_type,
                top_k=retrieval_k,
                analysis_run_id=analysis_run_id
            )
        except Exception as e:
            logger.warning(f"Semantic search by type failed: {e}")
        
        # Execute keyword search with chunk_type filter
        try:
            keyword_results = self.keyword_service.search_by_chunk_type(
                repository_id=repository_id,
                query=query,
                chunk_type=chunk_type,
                top_k=retrieval_k,
                analysis_run_id=analysis_run_id
            )
        except Exception as e:
            logger.warning(f"Keyword search by type failed: {e}")
        
        # If both searches failed, return empty
        if not semantic_results and not keyword_results:
            return []
        
        # Fuse results
        hybrid_results = self._fuse_results(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight
        )
        
        # Sort and return top_k
        hybrid_results.sort(key=lambda r: r.final_score, reverse=True)
        
        return hybrid_results[:top_k]
    
    def _fuse_results(
        self,
        semantic_results: List[SemanticSearchResult],
        keyword_results: List[KeywordSearchResult],
        semantic_weight: float,
        keyword_weight: float
    ) -> List[HybridSearchResult]:
        """
        Fuse semantic and keyword results with score normalization.
        
        Algorithm:
        1. Normalize keyword scores (semantic already in [0,1])
        2. Build maps of results by chunk_id
        3. Merge results, applying weights
        4. Handle chunks from both sources (deduplication)
        5. Handle chunks from single source only
        
        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            semantic_weight: Weight for semantic scores
            keyword_weight: Weight for keyword scores
            
        Returns:
            List of fused HybridSearchResult objects
        """
        # Normalize keyword scores to [0, 1] using min-max scaling
        normalized_keyword = self._normalize_keyword_scores(keyword_results)
        
        # Build dictionaries for fast lookup
        semantic_map: Dict[UUID, SemanticSearchResult] = {
            r.chunk_id: r for r in semantic_results
        }
        
        keyword_map: Dict[UUID, Tuple[KeywordSearchResult, float]] = {
            r.chunk_id: (r, norm_score) 
            for r, norm_score in zip(keyword_results, normalized_keyword)
        }
        
        # Get all unique chunk IDs
        all_chunk_ids = set(semantic_map.keys()) | set(keyword_map.keys())
        
        # Fuse results
        hybrid_results: List[HybridSearchResult] = []
        
        for chunk_id in all_chunk_ids:
            semantic_result = semantic_map.get(chunk_id)
            keyword_data = keyword_map.get(chunk_id)
            
            # Determine scores and source
            semantic_score = None
            keyword_score = None
            retrieval_source = ""
            
            if semantic_result and keyword_data:
                # Chunk appears in both result sets
                semantic_score = semantic_result.similarity_score
                keyword_score = keyword_data[1]
                retrieval_source = "hybrid"
                # Use semantic result for metadata (both have same chunk)
                base_result = semantic_result
            elif semantic_result:
                # Chunk only in semantic results
                semantic_score = semantic_result.similarity_score
                keyword_score = 0.0  # No keyword match
                retrieval_source = "semantic"
                base_result = semantic_result
            else:
                # Chunk only in keyword results
                semantic_score = 0.0  # No semantic match
                keyword_score = keyword_data[1]
                retrieval_source = "keyword"
                base_result = keyword_data[0]
            
            # Calculate final weighted score
            final_score = (semantic_weight * semantic_score) + (keyword_weight * keyword_score)
            
            # Create hybrid result
            # For single-source results (semantic-only or keyword-only), preserve the score even if 0
            # For hybrid results, set to None if 0
            display_semantic_score = None
            display_keyword_score = None
            
            if retrieval_source == "semantic":
                display_semantic_score = semantic_score  # Always show for semantic-only
            elif retrieval_source == "keyword":
                display_keyword_score = keyword_score  # Always show for keyword-only
            else:  # hybrid
                display_semantic_score = semantic_score if semantic_score > 0 else None
                display_keyword_score = keyword_score if keyword_score > 0 else None
            
            hybrid_result = HybridSearchResult(
                chunk_id=chunk_id,
                final_score=final_score,
                semantic_score=display_semantic_score,
                keyword_score=display_keyword_score,
                retrieval_source=retrieval_source,
                content=base_result.content,
                chunk_type=base_result.chunk_type,
                file_path=base_result.file_path,
                start_line=base_result.start_line,
                end_line=base_result.end_line,
                language=base_result.language,
                symbol_name=base_result.symbol_name,
                symbol_type=base_result.symbol_type,
                api_endpoint_method=base_result.api_endpoint_method,
                api_endpoint_path=base_result.api_endpoint_path,
                metadata=base_result.metadata
            )
            
            hybrid_results.append(hybrid_result)
        
        logger.info(f"Fused {len(hybrid_results)} unique chunks from {len(semantic_results)} semantic + {len(keyword_results)} keyword results")
        
        return hybrid_results
    
    def _normalize_keyword_scores(
        self, 
        keyword_results: List[KeywordSearchResult]
    ) -> List[float]:
        """
        Normalize keyword ts_rank scores to [0, 1] range using min-max scaling.
        
        Args:
            keyword_results: Results from keyword search with ts_rank scores
            
        Returns:
            List of normalized scores in [0, 1] range
        """
        if not keyword_results:
            return []
        
        # Extract scores
        scores = [r.relevance_score for r in keyword_results]
        
        # Min-max normalization
        min_score = min(scores)
        max_score = max(scores)
        
        # Handle edge case where all scores are the same
        if max_score == min_score:
            # All scores are equal, normalize to 1.0
            return [1.0] * len(scores)
        
        # Normalize to [0, 1]
        normalized = [
            (score - min_score) / (max_score - min_score)
            for score in scores
        ]
        
        return normalized
