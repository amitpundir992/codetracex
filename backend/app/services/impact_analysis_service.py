"""
Impact Analysis Service for Phase 13: AI Impact Analysis + Change Planning.

This service orchestrates deterministic impact analysis using existing services:
- GraphService: Dependency graph traversal
- WorkflowService: Workflow intelligence
- HybridSearchService: Code search
- GitHistoryService: Historical evidence

Architecture Philosophy:

    DETERMINISTIC ANALYSIS is the source of truth.
    
    This service DOES NOT discover new dependencies.
    It ORCHESTRATES existing intelligence services.
    
    Flow:
    1. Identify target entity
    2. Perform bounded graph traversal
    3. Collect dependency/dependent information
    4. Enrich with API/workflow intelligence
    5. Add historical evidence where relevant
    6. Structure for LLM reasoning
    
    The LLM explains and reasons over collected evidence.
    It does NOT discover dependencies.

Bounded Traversal:

    - Default depth: 3
    - Maximum depth: 10
    - Maximum nodes: 500
    - Maximum edges: 1000
    
    Explicit truncation reporting when limits reached.

Repository Isolation:

    All queries scoped by repository_id.
    Analysis run validation enforced.
    No cross-repository contamination.
"""
from typing import List, Dict, Set, Optional, Tuple, Any
from uuid import UUID
import logging
from collections import defaultdict

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from app.db.models import (
    Symbol, File, ApiEndpoint, Call, Import,
    Relationship, AnalysisRun, Repository
)
from app.services.graph_service import GraphService, GraphNode, GraphEdge
from app.services.workflow_service import WorkflowService
from app.schemas.impact_analysis import (
    ImpactTarget,
    ImpactItem,
    ImpactEvidence,
    ImpactSummary,
    TruncationInfo
)

logger = logging.getLogger(__name__)


class ImpactAnalysisService:
    """
    Service for deterministic impact analysis.
    
    Orchestrates graph traversal, dependency analysis, and evidence collection
    using existing repository intelligence.
    """
    
    # Limits
    DEFAULT_DEPTH = 3
    MAX_DEPTH = 10
    MAX_NODES = 500
    MAX_EDGES = 1000
    
    def __init__(self, db: Session):
        """
        Initialize impact analysis service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.graph_service = GraphService(db)
        self.workflow_service = WorkflowService(db)
    
    def analyze_symbol_impact(
        self,
        symbol_id: UUID,
        repository_id: UUID,
        analysis_run_id: Optional[UUID] = None,
        depth: int = DEFAULT_DEPTH
    ) -> Dict[str, Any]:
        """
        Analyze impact of changing a symbol.
        
        Performs bounded graph traversal to identify:
        - Direct callers
        - Transitive callers
        - Direct callees
        - Transitive callees
        - Affected files
        - Affected API endpoints
        - Affected workflows
        
        Args:
            symbol_id: UUID of target symbol
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            depth: Maximum traversal depth (1-10)
            
        Returns:
            Dictionary containing:
            - impacts: List of ImpactItem objects
            - summary: ImpactSummary object
            - truncation: TruncationInfo object
            - affected_files: List of file paths
            - affected_endpoints: List of endpoint info
            - affected_workflows: List of workflow info
        """
        depth = min(max(depth, 1), self.MAX_DEPTH)
        
        # Verify repository isolation
        symbol = self.db.query(Symbol).filter(
            Symbol.id == symbol_id,
            Symbol.repository_id == repository_id
        ).first()
        
        if not symbol:
            return self._empty_result(repository_id, analysis_run_id)
        
        if analysis_run_id and symbol.analysis_run_id != analysis_run_id:
            return self._empty_result(repository_id, analysis_run_id)
        
        # Track nodes and edges
        all_impacts: List[ImpactItem] = []
        seen_nodes = set()
        edge_count = 0
        truncated = False
        truncation_reason = None
        
        # Get direct callers
        direct_caller_edges = self.graph_service.get_symbol_callers(symbol_id, depth=1)
        
        for edge in direct_caller_edges:
            if len(seen_nodes) >= self.MAX_NODES:
                truncated = True
                truncation_reason = "max_nodes"
                break
            
            edge_count += 1
            if edge_count >= self.MAX_EDGES:
                truncated = True
                truncation_reason = "max_edges"
                break
            
            caller_id = edge.source.id
            if caller_id not in seen_nodes:
                seen_nodes.add(caller_id)
                
                impact = self._create_symbol_impact(
                    edge.source,
                    "direct_caller",
                    1,
                    "Directly calls the target symbol",
                    edge
                )
                all_impacts.append(impact)
        
        # Get transitive callers (depth > 1)
        if depth > 1 and not truncated:
            transitive_edges = self.graph_service.get_symbol_callers(symbol_id, depth=depth)
            
            for edge in transitive_edges:
                if len(seen_nodes) >= self.MAX_NODES:
                    truncated = True
                    truncation_reason = "max_nodes"
                    break
                
                edge_count += 1
                if edge_count >= self.MAX_EDGES:
                    truncated = True
                    truncation_reason = "max_edges"
                    break
                
                caller_id = edge.source.id
                
                # Skip if already seen as direct caller
                if caller_id not in seen_nodes:
                    seen_nodes.add(caller_id)
                    
                    # Determine depth (approximate)
                    impact_depth = 2  # Transitive
                    if edge.target.id != str(symbol_id):
                        impact_depth = 3
                    
                    impact = self._create_symbol_impact(
                        edge.source,
                        "transitive_caller",
                        impact_depth,
                        "Transitively calls the target symbol",
                        edge
                    )
                    all_impacts.append(impact)
        
        # Get direct callees
        if not truncated:
            callee_edges = self.graph_service.get_symbol_callees(symbol_id, depth=1)
            
            for edge in callee_edges:
                if len(seen_nodes) >= self.MAX_NODES:
                    truncated = True
                    truncation_reason = "max_nodes"
                    break
                
                edge_count += 1
                if edge_count >= self.MAX_EDGES:
                    truncated = True
                    truncation_reason = "max_edges"
                    break
                
                callee_id = edge.target.id
                if callee_id not in seen_nodes:
                    seen_nodes.add(callee_id)
                    
                    impact = self._create_symbol_impact(
                        edge.target,
                        "direct_callee",
                        1,
                        "Called by the target symbol",
                        edge
                    )
                    all_impacts.append(impact)
        
        # Get transitive callees
        if depth > 1 and not truncated:
            transitive_callee_edges = self.graph_service.get_symbol_callees(symbol_id, depth=depth)
            
            for edge in transitive_callee_edges:
                if len(seen_nodes) >= self.MAX_NODES:
                    truncated = True
                    truncation_reason = "max_nodes"
                    break
                
                edge_count += 1
                if edge_count >= self.MAX_EDGES:
                    truncated = True
                    truncation_reason = "max_edges"
                    break
                
                callee_id = edge.target.id
                
                if callee_id not in seen_nodes:
                    seen_nodes.add(callee_id)
                    
                    impact_depth = 2
                    if edge.source.id != str(symbol_id):
                        impact_depth = 3
                    
                    impact = self._create_symbol_impact(
                        edge.target,
                        "transitive_callee",
                        impact_depth,
                        "Transitively called by the target symbol",
                        edge
                    )
                    all_impacts.append(impact)
        
        # Collect affected files
        affected_files = self._collect_affected_files(all_impacts, symbol)
        
        # Collect affected API endpoints
        affected_endpoints = self._collect_affected_endpoints(
            all_impacts,
            symbol,
            repository_id,
            analysis_run_id
        )
        
        # Collect affected workflows (if applicable)
        affected_workflows = self._collect_affected_workflows(
            symbol,
            repository_id,
            analysis_run_id,
            depth
        )
        
        # Build summary
        summary = self._build_summary(
            all_impacts,
            affected_files,
            affected_endpoints,
            affected_workflows,
            depth
        )
        
        # Build truncation info
        truncation = TruncationInfo(
            is_truncated=truncated,
            truncation_reason=truncation_reason,
            nodes_analyzed=len(seen_nodes),
            edges_analyzed=edge_count,
            max_nodes=self.MAX_NODES,
            max_edges=self.MAX_EDGES
        )
        
        return {
            "impacts": all_impacts,
            "summary": summary,
            "truncation": truncation,
            "affected_files": affected_files,
            "affected_endpoints": affected_endpoints,
            "affected_workflows": affected_workflows
        }
    
    def analyze_file_impact(
        self,
        file_id: UUID,
        repository_id: UUID,
        analysis_run_id: Optional[UUID] = None,
        depth: int = DEFAULT_DEPTH
    ) -> Dict[str, Any]:
        """
        Analyze impact of changing a file.
        
        Identifies:
        - Files that import this file
        - Files this file imports
        - Symbols in this file and their impacts
        
        Args:
            file_id: UUID of target file
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            depth: Maximum traversal depth
            
        Returns:
            Impact analysis result dictionary
        """
        depth = min(max(depth, 1), self.MAX_DEPTH)
        
        # Verify repository isolation
        file = self.db.query(File).filter(
            File.id == file_id,
            File.repository_id == repository_id
        ).first()
        
        if not file:
            return self._empty_result(repository_id, analysis_run_id)
        
        if analysis_run_id and file.analysis_run_id != analysis_run_id:
            return self._empty_result(repository_id, analysis_run_id)
        
        all_impacts: List[ImpactItem] = []
        seen_files = set([str(file_id)])
        
        # Get files that import this file
        dependent_edges = self.graph_service.get_file_dependents(file_id, depth=depth)
        
        for edge in dependent_edges:
            file_key = edge.source.id
            if file_key not in seen_files:
                seen_files.add(file_key)
                
                impact = ImpactItem(
                    impact_category="dependent_file",
                    entity_type="file",
                    entity_id=UUID(edge.source.id),
                    entity_name=edge.source.name,
                    file_path=edge.source.file_path,
                    depth=1,
                    reason="Imports the target file",
                    evidence=[]
                )
                all_impacts.append(impact)
        
        # Get files this file imports
        dependency_edges = self.graph_service.get_file_dependencies(file_id, depth=1)
        
        for edge in dependency_edges:
            file_key = edge.target.id
            if file_key not in seen_files:
                seen_files.add(file_key)
                
                impact = ImpactItem(
                    impact_category="dependency_file",
                    entity_type="file",
                    entity_id=UUID(edge.target.id),
                    entity_name=edge.target.name,
                    file_path=edge.target.file_path,
                    depth=1,
                    reason="Imported by the target file",
                    evidence=[]
                )
                all_impacts.append(impact)
        
        # Get symbols in this file and analyze their impact
        symbols = self.db.query(Symbol).filter(
            Symbol.file_id == file_id
        ).all()
        
        for symbol in symbols:
            # Get direct callers only (to avoid explosion)
            caller_edges = self.graph_service.get_symbol_callers(symbol.id, depth=1)
            
            for edge in caller_edges:
                caller_file_id = edge.source.file
                if caller_file_id and caller_file_id not in seen_files:
                    impact = self._create_symbol_impact(
                        edge.source,
                        "direct_caller",
                        1,
                        f"Calls {symbol.name} in target file",
                        edge
                    )
                    all_impacts.append(impact)
        
        # Collect affected files
        affected_files = list(set(
            impact.file_path for impact in all_impacts
            if impact.file_path
        ))
        
        # Collect affected endpoints
        affected_endpoints = self._collect_affected_endpoints_for_file(
            file_id,
            repository_id,
            analysis_run_id
        )
        
        # Build summary
        summary = ImpactSummary(
            total_impacts=len(all_impacts),
            direct_impacts=len([i for i in all_impacts if i.depth == 1]),
            transitive_impacts=len([i for i in all_impacts if i.depth > 1]),
            affected_files_count=len(affected_files),
            affected_symbols_count=len([i for i in all_impacts if i.entity_type == "symbol"]),
            affected_endpoints_count=len(affected_endpoints),
            max_depth_reached=depth,
            has_api_impact=len(affected_endpoints) > 0,
            has_workflow_impact=False,
            has_test_impact=False
        )
        
        truncation = TruncationInfo(
            is_truncated=False,
            truncation_reason=None,
            nodes_analyzed=len(seen_files),
            edges_analyzed=len(all_impacts),
            max_nodes=self.MAX_NODES,
            max_edges=self.MAX_EDGES
        )
        
        return {
            "impacts": all_impacts,
            "summary": summary,
            "truncation": truncation,
            "affected_files": affected_files,
            "affected_endpoints": affected_endpoints,
            "affected_workflows": []
        }
    
    def analyze_endpoint_impact(
        self,
        endpoint_id: UUID,
        repository_id: UUID,
        analysis_run_id: Optional[UUID] = None,
        depth: int = DEFAULT_DEPTH
    ) -> Dict[str, Any]:
        """
        Analyze impact of changing an API endpoint.
        
        If endpoint has handler symbol, analyze symbol impact.
        Also check for other endpoints in same file.
        
        Args:
            endpoint_id: UUID of target endpoint
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            depth: Maximum traversal depth
            
        Returns:
            Impact analysis result dictionary
        """
        # Verify repository isolation
        endpoint = self.db.query(ApiEndpoint).options(
            joinedload(ApiEndpoint.file),
            joinedload(ApiEndpoint.symbol)
        ).filter(
            ApiEndpoint.id == endpoint_id,
            ApiEndpoint.repository_id == repository_id
        ).first()
        
        if not endpoint:
            return self._empty_result(repository_id, analysis_run_id)
        
        if analysis_run_id and endpoint.analysis_run_id != analysis_run_id:
            return self._empty_result(repository_id, analysis_run_id)
        
        # If endpoint has handler symbol, analyze it
        if endpoint.symbol_id:
            result = self.analyze_symbol_impact(
                endpoint.symbol_id,
                repository_id,
                analysis_run_id,
                depth
            )
            
            # Add endpoint-specific context
            result["endpoint_info"] = {
                "method": endpoint.method.value,
                "path": endpoint.path,
                "framework": endpoint.framework,
                "handler_name": endpoint.handler_name
            }
            
            return result
        
        # No handler symbol - analyze file
        if endpoint.file_id:
            result = self.analyze_file_impact(
                endpoint.file_id,
                repository_id,
                analysis_run_id,
                depth
            )
            
            result["endpoint_info"] = {
                "method": endpoint.method.value,
                "path": endpoint.path,
                "framework": endpoint.framework,
                "handler_name": endpoint.handler_name
            }
            
            return result
        
        # No symbol or file - minimal result
        return self._empty_result(repository_id, analysis_run_id)
    
    def _create_symbol_impact(
        self,
        node: GraphNode,
        category: str,
        depth: int,
        reason: str,
        edge: Optional[GraphEdge] = None
    ) -> ImpactItem:
        """
        Create an ImpactItem from a GraphNode.
        
        Args:
            node: GraphNode from graph service
            category: Impact category
            depth: Distance from target
            reason: Impact reason
            edge: Optional edge providing evidence
            
        Returns:
            ImpactItem object
        """
        evidence = []
        
        if edge:
            evidence.append(ImpactEvidence(
                source_type="dependency_graph",
                file_path=node.file_path or "unknown",
                start_line=None,
                end_line=None,
                symbol_name=node.name,
                symbol_type=node.type,
                relationship_type=edge.relationship_type,
                relationship_direction="incoming" if "caller" in category else "outgoing",
                excerpt=None
            ))
        
        return ImpactItem(
            impact_category=category,
            entity_type="symbol",
            entity_id=UUID(node.id),
            entity_name=node.name,
            symbol_type=node.type,
            file_path=node.file_path,
            depth=depth,
            reason=reason,
            evidence=evidence
        )
    
    def _collect_affected_files(
        self,
        impacts: List[ImpactItem],
        target_symbol: Symbol
    ) -> List[str]:
        """
        Collect unique file paths from impacts.
        
        Args:
            impacts: List of impact items
            target_symbol: Target symbol
            
        Returns:
            List of unique file paths
        """
        files = set()
        
        # Add target file
        if target_symbol.file:
            files.add(target_symbol.file.file_path)
        
        # Add impact files
        for impact in impacts:
            if impact.file_path:
                files.add(impact.file_path)
        
        return sorted(list(files))
    
    def _collect_affected_endpoints(
        self,
        impacts: List[ImpactItem],
        target_symbol: Symbol,
        repository_id: UUID,
        analysis_run_id: Optional[UUID]
    ) -> List[Dict[str, str]]:
        """
        Collect API endpoints affected by symbol impacts.
        
        Args:
            impacts: List of impact items
            target_symbol: Target symbol
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            
        Returns:
            List of endpoint info dictionaries
        """
        endpoints = []
        checked_symbols = set()
        
        # Check target symbol
        target_endpoints = self.db.query(ApiEndpoint).filter(
            ApiEndpoint.symbol_id == target_symbol.id
        ).all()
        
        for ep in target_endpoints:
            endpoints.append({
                "method": ep.method.value,
                "path": ep.path,
                "handler": ep.handler_name or "unknown",
                "file": ep.file.file_path if ep.file else "unknown"
            })
        
        checked_symbols.add(str(target_symbol.id))
        
        # Check impacted symbols
        for impact in impacts:
            if impact.entity_type == "symbol":
                symbol_id_str = str(impact.entity_id)
                if symbol_id_str not in checked_symbols:
                    checked_symbols.add(symbol_id_str)
                    
                    symbol_endpoints = self.db.query(ApiEndpoint).filter(
                        ApiEndpoint.symbol_id == impact.entity_id
                    ).all()
                    
                    for ep in symbol_endpoints:
                        endpoints.append({
                            "method": ep.method.value,
                            "path": ep.path,
                            "handler": ep.handler_name or "unknown",
                            "file": ep.file.file_path if ep.file else "unknown"
                        })
        
        return endpoints
    
    def _collect_affected_endpoints_for_file(
        self,
        file_id: UUID,
        repository_id: UUID,
        analysis_run_id: Optional[UUID]
    ) -> List[Dict[str, str]]:
        """
        Collect endpoints defined in a file.
        
        Args:
            file_id: File UUID
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            
        Returns:
            List of endpoint info dictionaries
        """
        query = self.db.query(ApiEndpoint).filter(
            ApiEndpoint.file_id == file_id,
            ApiEndpoint.repository_id == repository_id
        )
        
        if analysis_run_id:
            query = query.filter(ApiEndpoint.analysis_run_id == analysis_run_id)
        
        endpoints = query.all()
        
        return [
            {
                "method": ep.method.value,
                "path": ep.path,
                "handler": ep.handler_name or "unknown",
                "file": ep.file.file_path if ep.file else "unknown"
            }
            for ep in endpoints
        ]
    
    def _collect_affected_workflows(
        self,
        target_symbol: Symbol,
        repository_id: UUID,
        analysis_run_id: Optional[UUID],
        depth: int
    ) -> List[Dict[str, Any]]:
        """
        Collect workflows that include the target symbol.
        
        Args:
            target_symbol: Target symbol
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            depth: Maximum depth
            
        Returns:
            List of workflow info dictionaries
        """
        workflows = []
        
        try:
            # Check if symbol is part of any endpoint workflow
            endpoints_with_symbol = self.db.query(ApiEndpoint).filter(
                ApiEndpoint.symbol_id == target_symbol.id
            ).all()
            
            for endpoint in endpoints_with_symbol:
                # Build workflow from this endpoint
                workflow_result = self.workflow_service.build_endpoint_workflow(
                    endpoint.id,
                    repository_id,
                    max_depth=depth
                )
                
                if workflow_result.get("nodes"):
                    workflows.append({
                        "entry_point": f"{endpoint.method.value} {endpoint.path}",
                        "entry_type": "api_endpoint",
                        "node_count": len(workflow_result.get("nodes", [])),
                        "edge_count": len(workflow_result.get("edges", []))
                    })
        
        except Exception as e:
            logger.warning(f"Error collecting workflow information: {e}")
        
        return workflows
    
    def _build_summary(
        self,
        impacts: List[ImpactItem],
        affected_files: List[str],
        affected_endpoints: List[Dict[str, str]],
        affected_workflows: List[Dict[str, Any]],
        max_depth: int
    ) -> ImpactSummary:
        """
        Build impact summary from collected data.
        
        Args:
            impacts: List of impact items
            affected_files: List of affected files
            affected_endpoints: List of affected endpoints
            affected_workflows: List of affected workflows
            max_depth: Maximum depth used
            
        Returns:
            ImpactSummary object
        """
        direct_impacts = len([i for i in impacts if i.depth == 1])
        transitive_impacts = len([i for i in impacts if i.depth > 1])
        
        return ImpactSummary(
            total_impacts=len(impacts),
            direct_impacts=direct_impacts,
            transitive_impacts=transitive_impacts,
            affected_files_count=len(affected_files),
            affected_symbols_count=len([i for i in impacts if i.entity_type == "symbol"]),
            affected_endpoints_count=len(affected_endpoints),
            max_depth_reached=max_depth,
            has_api_impact=len(affected_endpoints) > 0,
            has_workflow_impact=len(affected_workflows) > 0,
            has_test_impact=False  # TODO: Implement test detection
        )
    
    def _empty_result(
        self,
        repository_id: UUID,
        analysis_run_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Return empty impact analysis result.
        
        Args:
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            Empty result dictionary
        """
        return {
            "impacts": [],
            "summary": ImpactSummary(
                total_impacts=0,
                direct_impacts=0,
                transitive_impacts=0,
                affected_files_count=0,
                affected_symbols_count=0,
                affected_endpoints_count=0,
                max_depth_reached=0,
                has_api_impact=False,
                has_workflow_impact=False,
                has_test_impact=False
            ),
            "truncation": TruncationInfo(
                is_truncated=False,
                truncation_reason=None,
                nodes_analyzed=0,
                edges_analyzed=0,
                max_nodes=self.MAX_NODES,
                max_edges=self.MAX_EDGES
            ),
            "affected_files": [],
            "affected_endpoints": [],
            "affected_workflows": []
        }
