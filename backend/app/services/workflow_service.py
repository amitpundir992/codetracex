"""
Workflow Service for Phase 8 - Workflow & Data-Flow Intelligence.

This service constructs deterministic application workflows from existing
static analysis data. It builds on GraphService to provide higher-level
workflow representations.

Architecture Philosophy:
    
    Workflows are DERIVED from existing database facts.
    No workflow-specific tables are needed.
    
    Foundation:
    - ApiEndpoint (Phase 7)
    - Symbol (Phase 3)
    - Call (Phase 3)
    - GraphService (Phase 5)
    
    Workflow = structured representation of application execution flow
    
Workflow Types:
    
    1. Endpoint-originated workflow:
       API endpoint → handler → service → repository → model
    
    2. Symbol-originated workflow:
       Symbol → downstream callees
    
    3. Reverse workflow:
       Symbol → upstream callers
    
Limitations:
    
    This is STATIC ANALYSIS, not runtime tracing.
    
    Cannot resolve:
    - Dynamic dispatch
    - Reflection
    - Dependency injection
    - Runtime route registration
    - Event-driven execution
    - Message queues
    
    Workflows represent POSSIBLE execution paths based on syntactic evidence.
    They do NOT guarantee actual runtime execution order.
"""
from typing import List, Dict, Set, Optional, Tuple
from uuid import UUID
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Symbol, File, Call, ApiEndpoint, AnalysisRun
)
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)


@dataclass
class WorkflowNode:
    """
    Represents a node in an application workflow.
    
    Nodes are normalized representations of application components
    with traceability back to source code.
    """
    id: str  # UUID or composite identifier
    type: str  # endpoint, symbol, file, external_module
    name: str  # Display name
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    language: Optional[str] = None
    symbol_type: Optional[str] = None  # function, class, method
    method: Optional[str] = None  # For endpoint nodes: GET, POST, etc.
    path: Optional[str] = None  # For endpoint nodes: /api/users
    
    def to_dict(self) -> Dict:
        """Convert node to dictionary representation."""
        result = {
            "id": self.id,
            "type": self.type,
            "name": self.name
        }
        
        if self.file_path:
            result["file_path"] = self.file_path
        if self.start_line is not None:
            result["start_line"] = self.start_line
        if self.end_line is not None:
            result["end_line"] = self.end_line
        if self.language:
            result["language"] = self.language
        if self.symbol_type:
            result["symbol_type"] = self.symbol_type
        if self.method:
            result["method"] = self.method
        if self.path:
            result["path"] = self.path
        
        return result
    
    def __hash__(self):
        """Make node hashable for set operations."""
        return hash(self.id)
    
    def __eq__(self, other):
        """Node equality based on ID."""
        if not isinstance(other, WorkflowNode):
            return False
        return self.id == other.id


@dataclass
class WorkflowEdge:
    """
    Represents an edge in an application workflow.
    
    Edges connect workflow nodes with typed relationships.
    """
    source_id: str
    target_id: str
    type: str  # handles, calls, returns
    line_number: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert edge to dictionary representation."""
        result = {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.type
        }
        
        if self.line_number:
            result["line_number"] = self.line_number
        
        return result


@dataclass
class WorkflowPath:
    """
    Represents a single execution path through the workflow.
    
    A path is an ordered sequence of nodes connected by edges.
    """
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert path to dictionary representation."""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges]
        }


@dataclass
class Workflow:
    """
    Represents a complete application workflow.
    
    A workflow consists of:
    - A start node (endpoint or symbol)
    - All nodes reachable from the start
    - All edges connecting the nodes
    - Optional: individual paths through the workflow
    """
    start_node: WorkflowNode
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    truncated: bool = False
    truncation_reason: Optional[str] = None
    depth: int = 0
    
    def to_dict(self) -> Dict:
        """Convert workflow to dictionary representation."""
        result = {
            "start_node": self.start_node.to_dict(),
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "truncated": self.truncated,
            "depth": self.depth,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges)
        }
        
        if self.truncation_reason:
            result["truncation_reason"] = self.truncation_reason
        
        return result


class WorkflowService:
    """
    Service for constructing application workflows from static analysis data.
    
    This service builds on GraphService to provide workflow-specific
    representations of application execution flow.
    """
    
    # Traversal limits for safety
    MAX_DEPTH = 10
    DEFAULT_DEPTH = 5
    MAX_NODES = 100
    MAX_EDGES = 200
    
    def __init__(self, db: Session):
        """
        Initialize workflow service with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.graph_service = GraphService(db)
    
    def build_endpoint_workflow(
        self,
        endpoint_id: UUID,
        depth: int = DEFAULT_DEPTH,
        include_callers: bool = False
    ) -> Workflow:
        """
        Build workflow starting from an API endpoint.
        
        This constructs the execution flow:
        API endpoint → handler → downstream calls
        
        Args:
            endpoint_id: UUID of the API endpoint
            depth: Maximum traversal depth (default: 5, max: 10)
            include_callers: Whether to include upstream callers
            
        Returns:
            Workflow instance containing nodes and edges
        """
        depth = min(depth, self.MAX_DEPTH)
        
        # Load endpoint with relationships
        endpoint = (
            self.db.query(ApiEndpoint)
            .options(joinedload(ApiEndpoint.file))
            .options(joinedload(ApiEndpoint.symbol))
            .filter(ApiEndpoint.id == endpoint_id)
            .first()
        )
        
        if not endpoint:
            logger.warning(f"Endpoint not found: {endpoint_id}")
            # Return empty workflow
            empty_node = WorkflowNode(
                id=str(endpoint_id),
                type="endpoint",
                name="Unknown endpoint"
            )
            return Workflow(start_node=empty_node, nodes=[], edges=[])
        
        # Create endpoint node
        endpoint_node = self._endpoint_to_node(endpoint)
        
        # Initialize workflow
        workflow = Workflow(
            start_node=endpoint_node,
            nodes=[endpoint_node],
            edges=[],
            depth=depth
        )
        
        # Track visited nodes to prevent cycles
        visited: Set[str] = {endpoint_node.id}
        
        # If endpoint has resolved handler symbol, traverse from there
        if endpoint.symbol:
            handler_node = self._symbol_to_node(endpoint.symbol)
            
            # Add handler node
            if handler_node.id not in visited:
                workflow.nodes.append(handler_node)
                visited.add(handler_node.id)
                
                # Add endpoint -> handler edge
                workflow.edges.append(WorkflowEdge(
                    source_id=endpoint_node.id,
                    target_id=handler_node.id,
                    type="handles"
                ))
            
            # Traverse downstream calls
            self._traverse_downstream(
                symbol=endpoint.symbol,
                workflow=workflow,
                visited=visited,
                current_depth=1,
                max_depth=depth
            )
            
            # Optionally traverse upstream callers
            if include_callers:
                self._traverse_upstream(
                    symbol=endpoint.symbol,
                    workflow=workflow,
                    visited=visited,
                    current_depth=1,
                    max_depth=min(depth, 3)  # Limit upstream depth
                )
        
        # Check if workflow was truncated
        if len(workflow.nodes) >= self.MAX_NODES:
            workflow.truncated = True
            workflow.truncation_reason = "max_nodes_reached"
        elif len(workflow.edges) >= self.MAX_EDGES:
            workflow.truncated = True
            workflow.truncation_reason = "max_edges_reached"
        
        return workflow
    
    def build_symbol_workflow(
        self,
        symbol_id: UUID,
        depth: int = DEFAULT_DEPTH,
        direction: str = "downstream"
    ) -> Workflow:
        """
        Build workflow starting from a symbol.
        
        Directions:
        - downstream: symbol → functions it calls
        - upstream: symbol → functions that call it
        - both: bidirectional
        
        Args:
            symbol_id: UUID of the symbol
            depth: Maximum traversal depth
            direction: Traversal direction (downstream, upstream, both)
            
        Returns:
            Workflow instance containing nodes and edges
        """
        depth = min(depth, self.MAX_DEPTH)
        
        # Load symbol with file
        symbol = (
            self.db.query(Symbol)
            .options(joinedload(Symbol.file))
            .filter(Symbol.id == symbol_id)
            .first()
        )
        
        if not symbol:
            logger.warning(f"Symbol not found: {symbol_id}")
            empty_node = WorkflowNode(
                id=str(symbol_id),
                type="symbol",
                name="Unknown symbol"
            )
            return Workflow(start_node=empty_node, nodes=[], edges=[])
        
        # Create symbol node
        symbol_node = self._symbol_to_node(symbol)
        
        # Initialize workflow
        workflow = Workflow(
            start_node=symbol_node,
            nodes=[symbol_node],
            edges=[],
            depth=depth
        )
        
        # Track visited nodes
        visited: Set[str] = {symbol_node.id}
        
        # Traverse based on direction
        if direction in ("downstream", "both"):
            self._traverse_downstream(
                symbol=symbol,
                workflow=workflow,
                visited=visited,
                current_depth=1,
                max_depth=depth
            )
        
        if direction in ("upstream", "both"):
            self._traverse_upstream(
                symbol=symbol,
                workflow=workflow,
                visited=visited,
                current_depth=1,
                max_depth=depth
            )
        
        # Check truncation
        if len(workflow.nodes) >= self.MAX_NODES:
            workflow.truncated = True
            workflow.truncation_reason = "max_nodes_reached"
        elif len(workflow.edges) >= self.MAX_EDGES:
            workflow.truncated = True
            workflow.truncation_reason = "max_edges_reached"
        
        return workflow
    
    def _traverse_downstream(
        self,
        symbol: Symbol,
        workflow: Workflow,
        visited: Set[str],
        current_depth: int,
        max_depth: int
    ):
        """
        Traverse downstream calls recursively.
        
        Args:
            symbol: Current symbol
            workflow: Workflow being built
            visited: Set of visited node IDs
            current_depth: Current recursion depth
            max_depth: Maximum recursion depth
        """
        # Check depth limit
        if current_depth > max_depth:
            return
        
        # Check node/edge limits
        if len(workflow.nodes) >= self.MAX_NODES or len(workflow.edges) >= self.MAX_EDGES:
            return
        
        # Get calls from this symbol
        calls = (
            self.db.query(Call)
            .filter(
                Call.caller_name == symbol.name,
                Call.file_id == symbol.file_id,
                Call.analysis_run_id == symbol.analysis_run_id
            )
            .all()
        )
        
        source_node = self._symbol_to_node(symbol)
        
        for call in calls:
            # Check limits again
            if len(workflow.nodes) >= self.MAX_NODES or len(workflow.edges) >= self.MAX_EDGES:
                break
            
            # Find callee symbol(s)
            callee_symbols = (
                self.db.query(Symbol)
                .options(joinedload(Symbol.file))
                .filter(
                    Symbol.name == call.callee_name,
                    Symbol.analysis_run_id == symbol.analysis_run_id
                )
                .all()
            )
            
            for callee_symbol in callee_symbols:
                callee_node = self._symbol_to_node(callee_symbol)
                
                # Add node if not visited
                if callee_node.id not in visited:
                    workflow.nodes.append(callee_node)
                    visited.add(callee_node.id)
                    
                    # Recurse
                    self._traverse_downstream(
                        symbol=callee_symbol,
                        workflow=workflow,
                        visited=visited,
                        current_depth=current_depth + 1,
                        max_depth=max_depth
                    )
                
                # Add edge (even if node was already visited, to show multiple paths)
                workflow.edges.append(WorkflowEdge(
                    source_id=source_node.id,
                    target_id=callee_node.id,
                    type="calls",
                    line_number=call.line_number
                ))
    
    def _traverse_upstream(
        self,
        symbol: Symbol,
        workflow: Workflow,
        visited: Set[str],
        current_depth: int,
        max_depth: int
    ):
        """
        Traverse upstream callers recursively.
        
        Args:
            symbol: Current symbol
            workflow: Workflow being built
            visited: Set of visited node IDs
            current_depth: Current recursion depth
            max_depth: Maximum recursion depth
        """
        # Check depth limit
        if current_depth > max_depth:
            return
        
        # Check node/edge limits
        if len(workflow.nodes) >= self.MAX_NODES or len(workflow.edges) >= self.MAX_EDGES:
            return
        
        # Get calls to this symbol
        calls = (
            self.db.query(Call)
            .filter(
                Call.callee_name == symbol.name,
                Call.analysis_run_id == symbol.analysis_run_id
            )
            .all()
        )
        
        target_node = self._symbol_to_node(symbol)
        
        for call in calls:
            # Check limits
            if len(workflow.nodes) >= self.MAX_NODES or len(workflow.edges) >= self.MAX_EDGES:
                break
            
            # Find caller symbol(s)
            caller_symbols = (
                self.db.query(Symbol)
                .options(joinedload(Symbol.file))
                .filter(
                    Symbol.name == call.caller_name,
                    Symbol.file_id == call.file_id
                )
                .all()
            )
            
            for caller_symbol in caller_symbols:
                caller_node = self._symbol_to_node(caller_symbol)
                
                # Add node if not visited
                if caller_node.id not in visited:
                    workflow.nodes.append(caller_node)
                    visited.add(caller_node.id)
                    
                    # Recurse
                    self._traverse_upstream(
                        symbol=caller_symbol,
                        workflow=workflow,
                        visited=visited,
                        current_depth=current_depth + 1,
                        max_depth=max_depth
                    )
                
                # Add edge
                workflow.edges.append(WorkflowEdge(
                    source_id=caller_node.id,
                    target_id=target_node.id,
                    type="calls",
                    line_number=call.line_number
                ))
    
    def _endpoint_to_node(self, endpoint: ApiEndpoint) -> WorkflowNode:
        """
        Convert ApiEndpoint model to WorkflowNode.
        
        Args:
            endpoint: ApiEndpoint instance
            
        Returns:
            WorkflowNode representation
        """
        return WorkflowNode(
            id=f"endpoint:{endpoint.id}",
            type="endpoint",
            name=f"{endpoint.method.value} {endpoint.path}",
            file_path=endpoint.file.path,
            start_line=endpoint.start_line,
            end_line=endpoint.end_line,
            method=endpoint.method.value,
            path=endpoint.path
        )
    
    def _symbol_to_node(self, symbol: Symbol) -> WorkflowNode:
        """
        Convert Symbol model to WorkflowNode.
        
        Args:
            symbol: Symbol instance
            
        Returns:
            WorkflowNode representation
        """
        return WorkflowNode(
            id=f"symbol:{symbol.id}",
            type="symbol",
            name=symbol.name,
            file_path=symbol.file.path,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            language=symbol.language,
            symbol_type=symbol.symbol_type.value
        )
