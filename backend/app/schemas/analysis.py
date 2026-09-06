"""
Pydantic schemas for repository analysis.

Phase 2: File scanning and metadata collection
Phase 3: Static code analysis with symbol extraction
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional


class FileInfo(BaseModel):
    """Information about a single file in the repository."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "path": "src/components/Button.tsx",
                "filename": "Button.tsx",
                "extension": ".tsx",
                "size_bytes": 2450,
                "language": "TypeScript",
                "lines": 82,
                "is_sensitive": False
            }
        }
    )
    
    path: str = Field(..., description="Relative path from repository root")
    filename: str = Field(..., description="File name")
    extension: str = Field(..., description="File extension including dot")
    size_bytes: int = Field(..., description="File size in bytes")
    language: Optional[str] = Field(None, description="Detected programming language")
    lines: Optional[int] = Field(None, description="Number of lines in the file")
    is_sensitive: bool = Field(..., description="Whether file might contain sensitive data")


# ============================================================================
# Phase 3: Static Code Analysis Schemas
# ============================================================================


class Symbol(BaseModel):
    """
    Represents a code symbol extracted through static analysis.
    
    A symbol is a named entity in source code such as:
    - function
    - class
    - method
    - interface
    - variable (when relevant)
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "create_order",
                "type": "function",
                "language": "Python",
                "file": "app/services/order.py",
                "start_line": 10,
                "end_line": 25,
                "parent": None
            }
        }
    )
    
    name: str = Field(..., description="Symbol name")
    type: str = Field(..., description="Symbol type: function, class, method, interface, etc.")
    language: str = Field(..., description="Programming language: Python, JavaScript, TypeScript")
    file: str = Field(..., description="File path where symbol is defined")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    parent: Optional[str] = Field(None, description="Parent symbol name (e.g., class containing a method)")


class Import(BaseModel):
    """
    Represents an import/require statement extracted from source code.
    
    Examples:
    - Python: from app.services import OrderService
    - JavaScript: import UserService from './services/UserService'
    - TypeScript: import { useState } from 'react'
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file": "app/controllers/order.py",
                "source": "app.services.order",
                "names": ["OrderService"],
                "line": 3
            }
        }
    )
    
    file: str = Field(..., description="File containing the import")
    source: str = Field(..., description="Module/file being imported from")
    names: List[str] = Field(..., description="Names being imported (empty for default imports)")
    line: int = Field(..., description="Line number of the import statement")


class Call(BaseModel):
    """
    Represents a function/method call extracted from source code.
    
    Note: This is syntactic information only. Static analysis cannot always
    determine which specific definition a call refers to, especially with:
    - Dynamic dispatch
    - Reflection
    - Runtime-generated code
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file": "app/controllers/order.py",
                "caller": "create_order_endpoint",
                "callee": "create_order",
                "line": 15
            }
        }
    )
    
    file: str = Field(..., description="File containing the call")
    caller: str = Field(..., description="Function/method making the call")
    callee: str = Field(..., description="Function/method being called")
    line: int = Field(..., description="Line number of the call")


class AnalysisSummary(BaseModel):
    """
    Summary statistics for static code analysis.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_files": 120,
                "analyzed_files": 80,
                "skipped_files": 40,
                "failed_files": 0,
                "total_symbols": 450,
                "symbols_by_type": {
                    "function": 250,
                    "class": 40,
                    "method": 160
                },
                "total_imports": 600,
                "total_calls": 900
            }
        }
    )
    
    total_files: int = Field(..., description="Total files in repository")
    analyzed_files: int = Field(..., description="Files successfully analyzed")
    skipped_files: int = Field(..., description="Files skipped (unsupported language, binary, etc.)")
    failed_files: int = Field(..., description="Files that failed parsing")
    total_symbols: int = Field(..., description="Total symbols extracted")
    symbols_by_type: Dict[str, int] = Field(..., description="Symbol count by type")
    total_imports: int = Field(..., description="Total import statements")
    total_calls: int = Field(..., description="Total function calls")


class RepositoryAnalysisResponse(BaseModel):
    """Response schema for repository analysis."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "repository": "facebook/react",
                "status": "completed",
                "total_files": 1200,
                "total_size_bytes": 12845678,
                "languages": {
                    "JavaScript": 450,
                    "TypeScript": 300,
                    "JSON": 100,
                    "Markdown": 50
                },
                "files": [
                    {
                        "path": "src/index.js",
                        "filename": "index.js",
                        "extension": ".js",
                        "size_bytes": 1523,
                        "language": "JavaScript",
                        "lines": 45,
                        "is_sensitive": False
                    }
                ],
                "files_returned": 100,
                "note": "Showing first 100 files out of 1200 total files"
            }
        }
    )
    
    repository: str = Field(..., description="Repository identifier (owner/name)")
    status: str = Field(..., description="Analysis status")
    total_files: int = Field(..., description="Total number of files scanned")
    total_size_bytes: int = Field(..., description="Total size of all scanned files")
    languages: Dict[str, int] = Field(..., description="Language distribution (language -> file count)")
    files: List[FileInfo] = Field(..., description="List of scanned files")
    files_returned: int = Field(..., description="Number of files included in this response")
    note: Optional[str] = Field(None, description="Additional information about the response")
    
    # Phase 3: Static Analysis Results
    analysis_summary: Optional[AnalysisSummary] = Field(None, description="Static analysis summary")
    symbols: Optional[List[Symbol]] = Field(None, description="Extracted symbols (limited preview)")
    imports: Optional[List[Import]] = Field(None, description="Extracted imports (limited preview)")
    calls: Optional[List[Call]] = Field(None, description="Extracted calls (limited preview)")
    
    # Phase 4: Database Persistence IDs
    repository_id: Optional[str] = Field(None, description="UUID of persisted repository record")
    analysis_run_id: Optional[str] = Field(None, description="UUID of persisted analysis run")


# ============================================================================
# Phase 5: Graph Query Schemas
# ============================================================================


class GraphNode(BaseModel):
    """
    Represents a node in the dependency graph.
    
    Nodes can represent:
    - Symbol (function, class, method)
    - File
    - External module
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "create_order",
                "type": "function",
                "file": "app/services/order.py",
                "language": "Python"
            }
        }
    )
    
    id: str = Field(..., description="Node ID (UUID for internal nodes, 'external' for external dependencies)")
    name: str = Field(..., description="Node name")
    type: str = Field(..., description="Node type: function, class, method, file, external_module")
    file: Optional[str] = Field(None, description="File path for symbols")
    language: Optional[str] = Field(None, description="Programming language")


class GraphEdge(BaseModel):
    """
    Represents an edge (relationship) in the dependency graph.
    
    Edges represent:
    - calls: Function A calls Function B
    - imports: File A imports File B
    - contains: Class A contains Method B
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "calls",
                "source": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "process_order",
                    "type": "function",
                    "file": "app/controllers/order.py",
                    "language": "Python"
                },
                "target": {
                    "id": "223e4567-e89b-12d3-a456-426614174001",
                    "name": "create_order",
                    "type": "function",
                    "file": "app/services/order.py",
                    "language": "Python"
                },
                "line_number": 15
            }
        }
    )
    
    type: str = Field(..., description="Relationship type: calls, imports, contains")
    source: GraphNode = Field(..., description="Source node")
    target: GraphNode = Field(..., description="Target node")
    line_number: Optional[int] = Field(None, description="Line number where relationship occurs")


class SymbolCallersResponse(BaseModel):
    """Response schema for symbol callers query."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol_id": "123e4567-e89b-12d3-a456-426614174000",
                "symbol_name": "create_order",
                "depth": 2,
                "callers": [
                    {
                        "type": "calls",
                        "source": {"id": "...", "name": "process_order", "type": "function"},
                        "target": {"id": "...", "name": "create_order", "type": "function"}
                    }
                ],
                "total_callers": 3
            }
        }
    )
    
    symbol_id: str = Field(..., description="UUID of the target symbol")
    symbol_name: str = Field(..., description="Name of the target symbol")
    depth: int = Field(..., description="Traversal depth")
    callers: List[GraphEdge] = Field(..., description="List of caller relationships")
    total_callers: int = Field(..., description="Total number of unique callers")


class SymbolCalleesResponse(BaseModel):
    """Response schema for symbol callees query."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol_id": "123e4567-e89b-12d3-a456-426614174000",
                "symbol_name": "process_order",
                "depth": 2,
                "callees": [
                    {
                        "type": "calls",
                        "source": {"id": "...", "name": "process_order", "type": "function"},
                        "target": {"id": "...", "name": "create_order", "type": "function"}
                    }
                ],
                "total_callees": 5
            }
        }
    )
    
    symbol_id: str = Field(..., description="UUID of the source symbol")
    symbol_name: str = Field(..., description="Name of the source symbol")
    depth: int = Field(..., description="Traversal depth")
    callees: List[GraphEdge] = Field(..., description="List of callee relationships")
    total_callees: int = Field(..., description="Total number of unique callees")


class SymbolDependenciesResponse(BaseModel):
    """Response schema for symbol dependencies query."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol_id": "123e4567-e89b-12d3-a456-426614174000",
                "symbol_name": "OrderService",
                "depth": 1,
                "calls": [],
                "imports": [],
                "total_dependencies": 10
            }
        }
    )
    
    symbol_id: str = Field(..., description="UUID of the symbol")
    symbol_name: str = Field(..., description="Name of the symbol")
    depth: int = Field(..., description="Traversal depth")
    calls: List[GraphEdge] = Field(..., description="Functions/methods this symbol calls")
    imports: List[GraphEdge] = Field(..., description="Modules this symbol's file imports")
    total_dependencies: int = Field(..., description="Total dependencies")


class SymbolDependentsResponse(BaseModel):
    """Response schema for symbol dependents query."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol_id": "123e4567-e89b-12d3-a456-426614174000",
                "symbol_name": "create_order",
                "depth": 2,
                "callers": [],
                "imported_by": [],
                "total_dependents": 8
            }
        }
    )
    
    symbol_id: str = Field(..., description="UUID of the symbol")
    symbol_name: str = Field(..., description="Name of the symbol")
    depth: int = Field(..., description="Traversal depth")
    callers: List[GraphEdge] = Field(..., description="Symbols that call this symbol")
    imported_by: List[GraphEdge] = Field(..., description="Files that import this symbol's file")
    total_dependents: int = Field(..., description="Total dependents")


class FileDependenciesResponse(BaseModel):
    """Response schema for file dependencies query."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_path": "app/services/order.py",
                "imports": [],
                "total_dependencies": 5
            }
        }
    )
    
    file_id: str = Field(..., description="UUID of the file")
    file_path: str = Field(..., description="File path")
    imports: List[GraphEdge] = Field(..., description="Files/modules this file imports")
    total_dependencies: int = Field(..., description="Total dependencies")


class FileDependentsResponse(BaseModel):
    """Response schema for file dependents query."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_path": "app/services/order.py",
                "imported_by": [],
                "total_dependents": 3
            }
        }
    )
    
    file_id: str = Field(..., description="UUID of the file")
    file_path: str = Field(..., description="File path")
    imported_by: List[GraphEdge] = Field(..., description="Files that import this file")
    total_dependents: int = Field(..., description="Total dependents")


class ImpactAnalysisResponse(BaseModel):
    """
    Response schema for blast radius / impact analysis.
    
    Shows what would be affected by changes to a symbol.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "create_order",
                    "type": "function",
                    "file": "app/services/order.py"
                },
                "direct_callers": [
                    {"id": "...", "name": "process_order", "type": "function"}
                ],
                "indirect_dependents": [
                    {"id": "...", "name": "OrderController", "type": "class"}
                ],
                "total_dependents": 5,
                "depth_map": {
                    "uuid1": 1,
                    "uuid2": 2
                },
                "max_depth": 5
            }
        }
    )
    
    target: GraphNode = Field(..., description="The target symbol being analyzed")
    direct_callers: List[Dict] = Field(..., description="Symbols that directly call the target")
    indirect_dependents: List[Dict] = Field(..., description="Symbols that transitively depend on the target")
    total_dependents: int = Field(..., description="Total number of affected symbols")
    depth_map: Dict[str, int] = Field(..., description="Map of symbol IDs to their distance from target")
    max_depth: int = Field(..., description="Maximum traversal depth used")
