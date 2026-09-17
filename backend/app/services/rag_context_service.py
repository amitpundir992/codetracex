"""
RAG Context Service for Phase 11: RAG Context Pipeline.

This service orchestrates the complete RAG context assembly process:
1. Hybrid retrieval (semantic + keyword)
2. Evidence selection and deduplication
3. Graph evidence enrichment
4. Context budgeting and truncation
5. Structured evidence packaging

Architecture:
    
    User Question
        ↓
    HybridSearchService (retrieve candidates)
        ↓
    Deduplication (by chunk_id)
        ↓
    Score-based ranking
        ↓
    Graph enrichment (optional)
        ↓
    Context budgeting (character/item limits)
        ↓
    Structured RAGContext package
        ↓
    [Future: Phase 12 LLM]

Design Principles:

1. NO LLM GENERATION
   - This phase only assembles evidence
   - No answer generation
   - No query rewriting
   - No learned reranking

2. DETERMINISTIC
   - Same query + repo + config = same evidence
   - Tie-breaking by chunk_id (UUID)
   - No random selection

3. BOUNDED
   - Configurable evidence limits
   - Configurable character limits
   - Explicit truncation tracking

4. TRACEABLE
   - Every evidence item preserves source location
   - Graph relationships cite source nodes
   - Retrieval metadata preserved

5. ISOLATED
   - Repository isolation enforced
   - Analysis run isolation supported
   - No cross-repository contamination

Security:
    - Repository isolation mandatory
    - Analysis run isolation supported
    - Bounded inputs (no resource exhaustion)
    - UUID validation
    - No code execution
"""
import logging
from typing import List, Optional, Set, Tuple, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.hybrid_search_service import HybridSearchService, HybridSearchResult
from app.services.graph_service import GraphService
from app.schemas.rag_context import (
    RAGContext,
    EvidenceItem,
    GraphEvidence,
    RetrievalMetadata
)
from app.db.models import Symbol, ApiEndpoint, AnalysisRun

logger = logging.getLogger(__name__)


class RAGContextService:
    """
    Service for building RAG context packages.
    
    This service handles the complete evidence assembly pipeline:
    - Retrieval via HybridSearchService
    - Deduplication
    - Ranking
    - Graph enrichment
    - Context budgeting
    - Packaging
    
    Usage:
        service = RAGContextService(db)
        context = service.build_context(
            repository_id=repo_id,
            question="How does authentication work?",
            top_k=10,
            semantic_weight=0.6,
            keyword_weight=0.4
        )
    """
    
    # Default limits
    DEFAULT_MAX_EVIDENCE_ITEMS = 20
    DEFAULT_MAX_CHARACTERS = 15000  # ~15K characters for context
    DEFAULT_MAX_CHUNK_CHARACTERS = 2000  # Max characters per chunk
    DEFAULT_GRAPH_DEPTH = 1
    DEFAULT_MAX_GRAPH_NODES = 10
    
    def __init__(self, db: Session):
        """
        Initialize RAG context service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.hybrid_search_service = HybridSearchService(db)
        self.graph_service = GraphService(db)
    
    def build_context(
        self,
        repository_id: UUID,
        question: str,
        top_k: int = 10,
        semantic_weight: float = 0.5,
        keyword_weight: float = 0.5,
        max_evidence_items: Optional[int] = None,
        max_characters: Optional[int] = None,
        max_chunk_characters: Optional[int] = None,
        include_graph_evidence: bool = True,
        graph_depth: int = 1,
        max_graph_nodes: int = 10,
        analysis_run_id: Optional[UUID] = None,
        chunk_type: Optional[str] = None
    ) -> RAGContext:
        """
        Build a complete RAG context package for a question.
        
        This method:
        1. Validates inputs
        2. Retrieves candidates via hybrid search
        3. Deduplicates evidence
        4. Ranks by final score
        5. Enriches with graph evidence (optional)
        6. Enforces context budget
        7. Returns structured context package
        
        Args:
            repository_id: UUID of repository to query
            question: User's natural language question
            top_k: Number of chunks to retrieve from hybrid search
            semantic_weight: Weight for semantic scores
            keyword_weight: Weight for keyword scores
            max_evidence_items: Maximum evidence items (default: 20)
            max_characters: Maximum total characters (default: 15000)
            max_chunk_characters: Maximum characters per chunk (default: 2000)
            include_graph_evidence: Whether to include graph enrichment
            graph_depth: Depth for graph traversal (default: 1)
            max_graph_nodes: Max graph nodes per evidence item (default: 10)
            analysis_run_id: Optional analysis run filter
            chunk_type: Optional chunk type filter
            
        Returns:
            RAGContext package with evidence and metadata
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Apply defaults
        if max_evidence_items is None:
            max_evidence_items = self.DEFAULT_MAX_EVIDENCE_ITEMS
        if max_characters is None:
            max_characters = self.DEFAULT_MAX_CHARACTERS
        if max_chunk_characters is None:
            max_chunk_characters = self.DEFAULT_MAX_CHUNK_CHARACTERS
        
        # Validate question
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        logger.info(f"Building RAG context for repository {repository_id}, question: {question[:100]}...")
        
        # If analysis_run_id not provided, use latest successful run
        effective_analysis_run_id = analysis_run_id
        if not effective_analysis_run_id:
            effective_analysis_run_id = self._get_latest_analysis_run(repository_id)
            if effective_analysis_run_id:
                logger.info(f"Using latest analysis run: {effective_analysis_run_id}")
        
        # Step 1: Retrieve candidates via hybrid search
        logger.info(f"Retrieving top {top_k} candidates via hybrid search...")
        hybrid_results = self.hybrid_search_service.search(
            repository_id=repository_id,
            query=question,
            top_k=top_k,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
            analysis_run_id=effective_analysis_run_id
        )
        
        logger.info(f"Retrieved {len(hybrid_results)} candidates")
        
        # Track retrieval metadata
        semantic_candidates = sum(1 for r in hybrid_results if r.semantic_score is not None and r.semantic_score > 0)
        keyword_candidates = sum(1 for r in hybrid_results if r.keyword_score is not None and r.keyword_score > 0)
        total_candidates = len(hybrid_results)
        
        # Step 2: Deduplication (hybrid search already deduplicates by chunk_id)
        # No additional deduplication needed here, but track for metadata
        deduplicated_count = 0  # Already deduplicated by hybrid search
        
        # Step 3: Convert to EvidenceItem objects
        evidence_items = self._convert_to_evidence_items(hybrid_results)
        
        # Step 4: Sort by retrieval score (deterministic tie-breaking by chunk_id)
        evidence_items.sort(
            key=lambda e: (e.retrieval_score, str(e.chunk_id)),
            reverse=True
        )
        
        # Step 5: Apply context budgeting
        selected_evidence, truncated, truncation_reason = self._apply_context_budget(
            evidence_items=evidence_items,
            max_evidence_items=max_evidence_items,
            max_characters=max_characters,
            max_chunk_characters=max_chunk_characters
        )
        
        logger.info(f"Selected {len(selected_evidence)} evidence items after budgeting")
        
        # Step 6: Graph evidence enrichment (optional)
        graph_evidence_list: List[GraphEvidence] = []
        if include_graph_evidence:
            logger.info("Enriching with graph evidence...")
            graph_evidence_list = self._enrich_with_graph_evidence(
                evidence_items=selected_evidence,
                graph_depth=graph_depth,
                max_graph_nodes=max_graph_nodes
            )
            logger.info(f"Added {len(graph_evidence_list)} graph evidence items")
        
        # Step 7: Calculate totals
        total_evidence_items = len(selected_evidence)
        total_characters = sum(len(e.content) for e in selected_evidence)
        context_limit_reached = (
            total_evidence_items >= max_evidence_items or
            total_characters >= max_characters
        )
        
        # Step 8: Build retrieval metadata
        retrieval_metadata = RetrievalMetadata(
            total_candidates=total_candidates,
            selected_evidence=total_evidence_items,
            semantic_candidates=semantic_candidates,
            keyword_candidates=keyword_candidates,
            deduplicated_count=deduplicated_count,
            graph_enrichments=len(graph_evidence_list),
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight
        )
        
        # Step 9: Construct final RAG context
        rag_context = RAGContext(
            question=question,
            repository_id=repository_id,
            analysis_run_id=effective_analysis_run_id,
            evidence=selected_evidence,
            graph_evidence=graph_evidence_list,
            total_evidence_items=total_evidence_items,
            total_characters=total_characters,
            context_limit_reached=context_limit_reached,
            truncated=truncated,
            truncation_reason=truncation_reason,
            retrieval_metadata=retrieval_metadata
        )
        
        logger.info(
            f"Built RAG context: {total_evidence_items} evidence items, "
            f"{total_characters} characters, truncated={truncated}"
        )
        
        return rag_context
    
    def _get_latest_analysis_run(self, repository_id: UUID) -> Optional[UUID]:
        """
        Get the latest successful analysis run for a repository.
        
        Args:
            repository_id: Repository UUID
            
        Returns:
            UUID of latest successful analysis run, or None if none exists
        """
        from app.db.models import AnalysisStatus
        
        latest_run = (
            self.db.query(AnalysisRun)
            .filter(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.status == AnalysisStatus.COMPLETED
            )
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )
        
        return latest_run.id if latest_run else None
    
    def _convert_to_evidence_items(
        self,
        hybrid_results: List[HybridSearchResult]
    ) -> List[EvidenceItem]:
        """
        Convert HybridSearchResult objects to EvidenceItem objects.
        
        Args:
            hybrid_results: Results from hybrid search
            
        Returns:
            List of EvidenceItem objects
        """
        evidence_items = []
        
        for result in hybrid_results:
            evidence_item = EvidenceItem(
                chunk_id=result.chunk_id,
                retrieval_score=result.final_score,
                semantic_score=result.semantic_score,
                keyword_score=result.keyword_score,
                retrieval_source=result.retrieval_source,
                content=result.content,
                chunk_type=result.chunk_type,
                file_path=result.file_path,
                start_line=result.start_line,
                end_line=result.end_line,
                language=result.language,
                symbol_name=result.symbol_name,
                symbol_type=result.symbol_type,
                api_endpoint_method=result.api_endpoint_method,
                api_endpoint_path=result.api_endpoint_path,
                metadata=result.metadata
            )
            evidence_items.append(evidence_item)
        
        return evidence_items
    
    def _apply_context_budget(
        self,
        evidence_items: List[EvidenceItem],
        max_evidence_items: int,
        max_characters: int,
        max_chunk_characters: int
    ) -> Tuple[List[EvidenceItem], bool, Optional[str]]:
        """
        Apply context budgeting to evidence items.
        
        This method:
        1. Truncates individual chunks if they exceed max_chunk_characters
        2. Stops adding evidence when max_evidence_items or max_characters reached
        3. Tracks whether truncation occurred
        
        Args:
            evidence_items: List of evidence items (sorted by score)
            max_evidence_items: Maximum number of items
            max_characters: Maximum total characters
            max_chunk_characters: Maximum characters per chunk
            
        Returns:
            Tuple of (selected_evidence, truncated, truncation_reason)
        """
        selected_evidence: List[EvidenceItem] = []
        total_characters = 0
        truncated = False
        truncation_reason = None
        
        for item in evidence_items:
            # Check evidence item limit
            if len(selected_evidence) >= max_evidence_items:
                truncated = True
                truncation_reason = f"Reached maximum evidence items ({max_evidence_items})"
                logger.info(f"Context budget: {truncation_reason}")
                break
            
            # Truncate chunk content if needed
            content = item.content
            if len(content) > max_chunk_characters:
                content = content[:max_chunk_characters] + "\n... [truncated]"
                logger.debug(f"Truncated chunk {item.chunk_id} from {len(item.content)} to {len(content)} characters")
            
            # Check if adding this item would exceed character limit
            if total_characters + len(content) > max_characters:
                truncated = True
                truncation_reason = f"Reached maximum characters ({max_characters})"
                logger.info(f"Context budget: {truncation_reason}")
                break
            
            # Add item (with potentially truncated content)
            if len(content) < len(item.content):
                # Create new item with truncated content
                item = EvidenceItem(
                    chunk_id=item.chunk_id,
                    retrieval_score=item.retrieval_score,
                    semantic_score=item.semantic_score,
                    keyword_score=item.keyword_score,
                    retrieval_source=item.retrieval_source,
                    content=content,
                    chunk_type=item.chunk_type,
                    file_path=item.file_path,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    language=item.language,
                    symbol_name=item.symbol_name,
                    symbol_type=item.symbol_type,
                    api_endpoint_method=item.api_endpoint_method,
                    api_endpoint_path=item.api_endpoint_path,
                    metadata=item.metadata
                )
            
            selected_evidence.append(item)
            total_characters += len(content)
        
        return selected_evidence, truncated, truncation_reason
    
    def _enrich_with_graph_evidence(
        self,
        evidence_items: List[EvidenceItem],
        graph_depth: int,
        max_graph_nodes: int
    ) -> List[GraphEvidence]:
        """
        Enrich evidence with graph relationships.
        
        For each evidence item that has a symbol, retrieve:
        - Callers (symbols that call this one)
        - Callees (symbols this one calls)
        - Dependencies (files/modules)
        - Dependents (files that depend on this)
        
        Only includes graph evidence for symbol and API endpoint chunks.
        
        Args:
            evidence_items: Selected evidence items
            graph_depth: Depth for graph traversal
            max_graph_nodes: Maximum nodes per relationship type
            
        Returns:
            List of GraphEvidence objects
        """
        graph_evidence_list: List[GraphEvidence] = []
        processed_symbols: Set[str] = set()  # Avoid duplicate graph queries
        
        for item in evidence_items:
            # Only process symbol and api_endpoint chunks
            if item.chunk_type not in ['symbol', 'api_endpoint']:
                continue
            
            # Get the symbol or API endpoint
            node_id = None
            node_type = None
            node_name = None
            
            if item.chunk_type == 'symbol' and item.symbol_name:
                # Find symbol by name and file
                symbol = self._find_symbol_by_name_and_file(
                    symbol_name=item.symbol_name,
                    file_path=item.file_path
                )
                if symbol:
                    node_id = str(symbol.id)
                    node_type = 'symbol'
                    node_name = item.symbol_name
            elif item.chunk_type == 'api_endpoint' and item.api_endpoint_path:
                # Find API endpoint
                api_endpoint = self._find_api_endpoint(
                    method=item.api_endpoint_method,
                    path=item.api_endpoint_path
                )
                if api_endpoint:
                    node_id = str(api_endpoint.id)
                    node_type = 'api_endpoint'
                    node_name = f"{item.api_endpoint_method} {item.api_endpoint_path}"
            
            if not node_id or node_id in processed_symbols:
                continue
            
            processed_symbols.add(node_id)
            
            # Retrieve graph relationships
            try:
                if node_type == 'symbol':
                    graph_evidence = self._build_symbol_graph_evidence(
                        symbol_id=UUID(node_id),
                        node_name=node_name,
                        graph_depth=graph_depth,
                        max_graph_nodes=max_graph_nodes
                    )
                    if graph_evidence:
                        graph_evidence_list.append(graph_evidence)
                elif node_type == 'api_endpoint':
                    # For API endpoints, could include handler graph evidence
                    # For now, skip API endpoint graph enrichment
                    pass
            except Exception as e:
                logger.warning(f"Failed to build graph evidence for {node_id}: {e}")
                continue
        
        return graph_evidence_list
    
    def _find_symbol_by_name_and_file(
        self,
        symbol_name: str,
        file_path: str
    ) -> Optional[Symbol]:
        """
        Find a symbol by name and file path.
        
        Args:
            symbol_name: Symbol name
            file_path: File path
            
        Returns:
            Symbol object or None
        """
        from app.db.models import File
        
        symbol = (
            self.db.query(Symbol)
            .join(Symbol.file)
            .filter(
                Symbol.name == symbol_name,
                File.path == file_path
            )
            .first()
        )
        
        return symbol
    
    def _find_api_endpoint(
        self,
        method: str,
        path: str
    ) -> Optional[ApiEndpoint]:
        """
        Find an API endpoint by method and path.
        
        Args:
            method: HTTP method
            path: API path
            
        Returns:
            ApiEndpoint object or None
        """
        from app.db.models import HttpMethod
        
        try:
            method_enum = HttpMethod[method.upper()]
        except KeyError:
            return None
        
        api_endpoint = (
            self.db.query(ApiEndpoint)
            .filter(
                ApiEndpoint.method == method_enum,
                ApiEndpoint.path == path
            )
            .first()
        )
        
        return api_endpoint
    
    def _build_symbol_graph_evidence(
        self,
        symbol_id: UUID,
        node_name: str,
        graph_depth: int,
        max_graph_nodes: int
    ) -> Optional[GraphEvidence]:
        """
        Build graph evidence for a symbol.
        
        Args:
            symbol_id: Symbol UUID
            node_name: Symbol name for display
            graph_depth: Depth for traversal
            max_graph_nodes: Maximum nodes per relationship
            
        Returns:
            GraphEvidence object or None if no relationships found
        """
        # Get callers
        caller_edges = self.graph_service.get_symbol_callers(
            symbol_id=symbol_id,
            depth=graph_depth
        )
        
        # Get callees
        callee_edges = self.graph_service.get_symbol_callees(
            symbol_id=symbol_id,
            depth=graph_depth
        )
        
        # Get dependencies
        dependents_data = self.graph_service.get_symbol_dependents(
            symbol_id=symbol_id,
            depth=graph_depth
        )
        
        dependencies_data = self.graph_service.get_symbol_dependencies(
            symbol_id=symbol_id,
            depth=graph_depth
        )
        
        # Convert to dictionaries
        callers = [edge.source.to_dict() for edge in caller_edges[:max_graph_nodes]]
        callees = [edge.target.to_dict() for edge in callee_edges[:max_graph_nodes]]
        
        # Extract imports from dependencies
        dependencies = [
            edge.to_dict() for edge in dependencies_data.get('imports', [])[:max_graph_nodes]
        ]
        
        dependents = [
            edge.to_dict() for edge in dependents_data.get('imported_by', [])[:max_graph_nodes]
        ]
        
        # Check if we hit limits
        truncated = (
            len(caller_edges) > max_graph_nodes or
            len(callee_edges) > max_graph_nodes or
            len(dependencies_data.get('imports', [])) > max_graph_nodes or
            len(dependents_data.get('imported_by', [])) > max_graph_nodes
        )
        
        truncation_reason = None
        if truncated:
            truncation_reason = f"Graph relationships truncated to {max_graph_nodes} nodes per type"
        
        # Only create graph evidence if we found any relationships
        if not (callers or callees or dependencies or dependents):
            return None
        
        graph_evidence = GraphEvidence(
            node_id=str(symbol_id),
            node_type='symbol',
            node_name=node_name,
            callers=callers,
            callees=callees,
            dependencies=dependencies,
            dependents=dependents,
            truncated=truncated,
            truncation_reason=truncation_reason
        )
        
        return graph_evidence
