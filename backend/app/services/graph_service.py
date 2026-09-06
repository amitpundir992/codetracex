"""
Graph service for Phase 5 - Repository Dependency Graph.

This service provides graph traversal operations on top of the PostgreSQL
relationships stored in Phase 4.

Architecture Philosophy:
    
    We use PostgreSQL as the graph storage layer.
    No Neo4j, NetworkX, or graph databases are needed for this phase.
    
    The database already contains structured relationships:
    - Symbol → Symbol (calls, contains)
    - File → File (imports via Import table)
    - Symbol parent/child relationships
    
Graph Concepts:
    
    Nodes:
    - Repository
    - File
    - Symbol (function, class, method)
    
    Edges:
    - CALLS: Symbol calls another Symbol
    - CONTAINS: Class contains Method
    - IMPORTS: File imports another File/Module
    
Traversal Strategy:
    
    - Bounded depth traversal (default: 5, max: 10)
    - Cycle detection using visited set
    - Efficient PostgreSQL queries
    - No loading entire graph into memory
    
Limitations:
    
    - Static analysis only (no runtime information)
    - Name-based matching for calls (not semantic resolution)
    - Cannot resolve dynamic dispatch or reflection
    - External dependencies tracked by name only
"""
from typing import List, Dict, Set, Optional, Tuple
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.db.models import (
    Symbol, File, Import, Call, Relationship,
    RelationshipType, SymbolType
)

logger = logging.getLogger(__name__)


class GraphNode:
    """
    Represents a node in the dependency graph.
    """
    def __init__(
        self,
        id: str,
        name: str,
        type: str,
        file_path: Optional[str] = None,
        language: Optional[str] = None
    ):
        self.id = id
        self.name = name
        self.type = type  # symbol, file
        self.file_path = file_path
        self.language = language
    
    def to_dict(self) -> Dict:
        """Convert node to dictionary representation."""
        result = {
            "id": self.id,
            "name": self.name,
            "type": self.type
        }
        if self.file_path:
            result["file"] = self.file_path
        if self.language:
            result["language"] = self.language
        return result


class GraphEdge:
    """
    Represents an edge in the dependency graph.
    """
    def __init__(
        self,
        source: GraphNode,
        target: GraphNode,
        relationship_type: str,
        line_number: Optional[int] = None
    ):
        self.source = source
        self.target = target
        self.relationship_type = relationship_type
        self.line_number = line_number
    
    def to_dict(self) -> Dict:
        """Convert edge to dictionary representation."""
        result = {
            "type": self.relationship_type,
            "source": self.source.to_dict(),
            "target": self.target.to_dict()
        }
        if self.line_number:
            result["line_number"] = self.line_number
        return result


class GraphService:
    """
    Service for graph traversal and dependency analysis.
    
    Provides operations for querying code dependencies stored in PostgreSQL.
    """
    
    MAX_DEPTH = 10
    DEFAULT_DEPTH = 5
    
    def __init__(self, db: Session):
        """
        Initialize graph service with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def get_symbol_callers(
        self,
        symbol_id: UUID,
        depth: int = 1
    ) -> List[GraphEdge]:
        """
        Get symbols that call the specified symbol.
        
        This performs reverse traversal of the call graph.
        
        Args:
            symbol_id: UUID of the target symbol
            depth: Traversal depth (default: 1 for direct callers)
            
        Returns:
            List of edges representing caller relationships
        """
        depth = min(depth, self.MAX_DEPTH)
        
        target_symbol = self.db.query(Symbol).filter(Symbol.id == symbol_id).first()
        if not target_symbol:
            return []
        
        # Get all calls where callee matches target symbol name
        # Note: Call table stores names, not IDs, due to static analysis limitations
        calls = self.db.query(Call).filter(
            Call.callee_name == target_symbol.name,
            Call.analysis_run_id == target_symbol.analysis_run_id
        ).all()
        
        edges = []
        visited = set([str(symbol_id)])
        
        for call in calls:
            # Find the caller symbol
            caller_symbols = self.db.query(Symbol).filter(
                Symbol.name == call.caller_name,
                Symbol.file_id == call.file_id
            ).all()
            
            for caller_symbol in caller_symbols:
                if str(caller_symbol.id) in visited:
                    continue
                
                visited.add(str(caller_symbol.id))
                
                caller_node = self._symbol_to_node(caller_symbol)
                target_node = self._symbol_to_node(target_symbol)
                
                edge = GraphEdge(
                    source=caller_node,
                    target=target_node,
                    relationship_type="calls",
                    line_number=call.line_number
                )
                edges.append(edge)
                
                # Recursive traversal for depth > 1
                if depth > 1:
                    transitive_edges = self.get_symbol_callers(
                        caller_symbol.id,
                        depth - 1
                    )
                    edges.extend(transitive_edges)
        
        return edges
    
    def get_symbol_callees(
        self,
        symbol_id: UUID,
        depth: int = 1
    ) -> List[GraphEdge]:
        """
        Get symbols that the specified symbol calls.
        
        This performs forward traversal of the call graph.
        
        Args:
            symbol_id: UUID of the source symbol
            depth: Traversal depth (default: 1 for direct callees)
            
        Returns:
            List of edges representing callee relationships
        """
        depth = min(depth, self.MAX_DEPTH)
        
        source_symbol = self.db.query(Symbol).filter(Symbol.id == symbol_id).first()
        if not source_symbol:
            return []
        
        # Get all calls where caller matches source symbol name
        calls = self.db.query(Call).filter(
            Call.caller_name == source_symbol.name,
            Call.file_id == source_symbol.file_id
        ).all()
        
        edges = []
        visited = set([str(symbol_id)])
        
        for call in calls:
            # Find the callee symbol
            callee_symbols = self.db.query(Symbol).filter(
                Symbol.name == call.callee_name,
                Symbol.analysis_run_id == source_symbol.analysis_run_id
            ).all()
            
            for callee_symbol in callee_symbols:
                if str(callee_symbol.id) in visited:
                    continue
                
                visited.add(str(callee_symbol.id))
                
                source_node = self._symbol_to_node(source_symbol)
                target_node = self._symbol_to_node(callee_symbol)
                
                edge = GraphEdge(
                    source=source_node,
                    target=target_node,
                    relationship_type="calls",
                    line_number=call.line_number
                )
                edges.append(edge)
                
                # Recursive traversal for depth > 1
                if depth > 1:
                    transitive_edges = self.get_symbol_callees(
                        callee_symbol.id,
                        depth - 1
                    )
                    edges.extend(transitive_edges)
        
        return edges
    
    def get_symbol_dependencies(
        self,
        symbol_id: UUID,
        depth: int = 1
    ) -> Dict[str, List[GraphEdge]]:
        """
        Get all dependencies of a symbol.
        
        Dependencies include:
        - Direct callees (functions this symbol calls)
        - File imports (modules this symbol's file imports)
        
        Args:
            symbol_id: UUID of the symbol
            depth: Traversal depth
            
        Returns:
            Dictionary with 'calls' and 'imports' keys containing edge lists
        """
        symbol = self.db.query(Symbol).filter(Symbol.id == symbol_id).first()
        if not symbol:
            return {"calls": [], "imports": []}
        
        # Get call dependencies
        call_edges = self.get_symbol_callees(symbol_id, depth)
        
        # Get import dependencies from the file
        import_edges = self._get_file_imports(symbol.file_id)
        
        return {
            "calls": call_edges,
            "imports": import_edges
        }
    
    def get_symbol_dependents(
        self,
        symbol_id: UUID,
        depth: int = 1
    ) -> Dict[str, List[GraphEdge]]:
        """
        Get all dependents of a symbol.
        
        Dependents include:
        - Direct callers (functions that call this symbol)
        - Files that import this symbol's file
        
        Args:
            symbol_id: UUID of the symbol
            depth: Traversal depth
            
        Returns:
            Dictionary with 'callers' and 'imported_by' keys containing edge lists
        """
        symbol = self.db.query(Symbol).filter(Symbol.id == symbol_id).first()
        if not symbol:
            return {"callers": [], "imported_by": []}
        
        # Get caller dependencies
        caller_edges = self.get_symbol_callers(symbol_id, depth)
        
        # Get files that import this symbol's file
        import_edges = self._get_file_imported_by(symbol.file_id)
        
        return {
            "callers": caller_edges,
            "imported_by": import_edges
        }
    
    def get_file_dependencies(
        self,
        file_id: UUID
    ) -> List[GraphEdge]:
        """
        Get files that this file imports.
        
        Args:
            file_id: UUID of the file
            
        Returns:
            List of edges representing import relationships
        """
        return self._get_file_imports(file_id)
    
    def get_file_dependents(
        self,
        file_id: UUID
    ) -> List[GraphEdge]:
        """
        Get files that import this file.
        
        Args:
            file_id: UUID of the file
            
        Returns:
            List of edges representing import relationships
        """
        return self._get_file_imported_by(file_id)
    
    def analyze_symbol_impact(
        self,
        symbol_id: UUID,
        max_depth: int = DEFAULT_DEPTH
    ) -> Dict:
        """
        Analyze the blast radius of changes to a symbol.
        
        This performs multi-level traversal to find all symbols that
        transitively depend on the target symbol.
        
        Args:
            symbol_id: UUID of the symbol
            max_depth: Maximum traversal depth
            
        Returns:
            Dictionary containing:
            - target: The target symbol node
            - direct_callers: Symbols that directly call the target
            - indirect_dependents: All transitive dependents
            - depth_map: Map of symbol IDs to their distance from target
        """
        max_depth = min(max_depth, self.MAX_DEPTH)
        
        target_symbol = self.db.query(Symbol).filter(Symbol.id == symbol_id).first()
        if not target_symbol:
            return {
                "target": None,
                "direct_callers": [],
                "indirect_dependents": [],
                "depth_map": {}
            }
        
        # Get all dependents with full traversal
        all_edges = self.get_symbol_callers(symbol_id, depth=max_depth)
        
        # Separate direct and indirect
        direct_callers = []
        indirect_dependents = []
        depth_map = {}
        
        # Track unique symbols by ID
        seen_symbols = set()
        
        for edge in all_edges:
            symbol_key = edge.source.id
            
            if symbol_key not in seen_symbols:
                seen_symbols.add(symbol_key)
                
                # Categorize as direct or indirect based on whether it directly calls target
                is_direct = edge.target.id == str(symbol_id)
                
                if is_direct:
                    direct_callers.append(edge.source.to_dict())
                    depth_map[symbol_key] = 1
                else:
                    indirect_dependents.append(edge.source.to_dict())
                    # Approximate depth tracking
                    if symbol_key not in depth_map:
                        depth_map[symbol_key] = 2
        
        return {
            "target": self._symbol_to_node(target_symbol).to_dict(),
            "direct_callers": direct_callers,
            "indirect_dependents": indirect_dependents,
            "depth_map": depth_map,
            "total_dependents": len(seen_symbols)
        }
    
    def _get_file_imports(self, file_id: UUID) -> List[GraphEdge]:
        """
        Get files that the specified file imports.
        
        Args:
            file_id: UUID of the source file
            
        Returns:
            List of edges representing import relationships
        """
        source_file = self.db.query(File).filter(File.id == file_id).first()
        if not source_file:
            return []
        
        # Get all imports from this file
        imports = self.db.query(Import).filter(
            Import.file_id == file_id
        ).all()
        
        edges = []
        
        for imp in imports:
            # Try to resolve import to a file in the same analysis run
            # This is heuristic-based for relative imports
            target_files = self._resolve_import_to_file(
                imp.source,
                source_file,
                source_file.analysis_run_id
            )
            
            source_node = self._file_to_node(source_file)
            
            if target_files:
                for target_file in target_files:
                    target_node = self._file_to_node(target_file)
                    edge = GraphEdge(
                        source=source_node,
                        target=target_node,
                        relationship_type="imports",
                        line_number=imp.line_number
                    )
                    edges.append(edge)
            else:
                # External import (cannot resolve to file in repo)
                external_node = GraphNode(
                    id="external",
                    name=imp.source,
                    type="external_module"
                )
                edge = GraphEdge(
                    source=source_node,
                    target=external_node,
                    relationship_type="imports",
                    line_number=imp.line_number
                )
                edges.append(edge)
        
        return edges
    
    def _get_file_imported_by(self, file_id: UUID) -> List[GraphEdge]:
        """
        Get files that import the specified file.
        
        Args:
            file_id: UUID of the target file
            
        Returns:
            List of edges representing import relationships
        """
        target_file = self.db.query(File).filter(File.id == file_id).first()
        if not target_file:
            return []
        
        # Find imports that resolve to this file
        # This is complex due to different import syntaxes across languages
        all_imports = self.db.query(Import).filter(
            Import.analysis_run_id == target_file.analysis_run_id
        ).all()
        
        edges = []
        
        for imp in all_imports:
            resolved_files = self._resolve_import_to_file(
                imp.source,
                self.db.query(File).filter(File.id == imp.file_id).first(),
                target_file.analysis_run_id
            )
            
            if any(f.id == file_id for f in resolved_files):
                source_file = self.db.query(File).filter(File.id == imp.file_id).first()
                source_node = self._file_to_node(source_file)
                target_node = self._file_to_node(target_file)
                
                edge = GraphEdge(
                    source=source_node,
                    target=target_node,
                    relationship_type="imports",
                    line_number=imp.line_number
                )
                edges.append(edge)
        
        return edges
    
    def _resolve_import_to_file(
        self,
        import_source: str,
        from_file: File,
        analysis_run_id: UUID
    ) -> List[File]:
        """
        Attempt to resolve an import statement to actual file(s).
        
        This is heuristic-based and handles:
        - Relative imports (./module, ../module)
        - Absolute imports within the repository
        
        Cannot resolve:
        - External packages (npm, pip packages)
        - Dynamic imports
        
        Args:
            import_source: The import source string
            from_file: The file containing the import
            analysis_run_id: Analysis run ID for scope
            
        Returns:
            List of resolved File models (empty if cannot resolve)
        """
        # Handle relative imports
        if import_source.startswith('./') or import_source.startswith('../'):
            # Resolve relative to from_file's directory
            from_dir = '/'.join(from_file.path.split('/')[:-1])
            
            # Simple path resolution (doesn't handle all edge cases)
            if import_source.startswith('./'):
                resolved_path = f"{from_dir}/{import_source[2:]}"
            else:
                # Count ../ occurrences
                up_levels = import_source.count('../')
                remaining = import_source.split('../')[-1]
                
                # Go up directories
                parts = from_dir.split('/')
                if len(parts) >= up_levels:
                    new_dir = '/'.join(parts[:-up_levels]) if up_levels > 0 else from_dir
                    resolved_path = f"{new_dir}/{remaining}" if new_dir else remaining
                else:
                    return []
            
            # Try to find file with common extensions
            possible_paths = [
                resolved_path,
                f"{resolved_path}.js",
                f"{resolved_path}.ts",
                f"{resolved_path}.jsx",
                f"{resolved_path}.tsx",
                f"{resolved_path}.py",
                f"{resolved_path}/index.js",
                f"{resolved_path}/index.ts"
            ]
            
            files = self.db.query(File).filter(
                File.analysis_run_id == analysis_run_id,
                File.path.in_(possible_paths)
            ).all()
            
            return files
        
        # For non-relative imports, this is likely external or complex
        # Could be enhanced with package.json or import resolution logic
        return []
    
    def _symbol_to_node(self, symbol: Symbol) -> GraphNode:
        """Convert Symbol model to GraphNode."""
        return GraphNode(
            id=str(symbol.id),
            name=symbol.name,
            type=symbol.symbol_type.value,
            file_path=symbol.file.path,
            language=symbol.language
        )
    
    def _file_to_node(self, file: File) -> GraphNode:
        """Convert File model to GraphNode."""
        return GraphNode(
            id=str(file.id),
            name=file.filename,
            type="file",
            file_path=file.path,
            language=file.language
        )
