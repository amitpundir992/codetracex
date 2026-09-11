"""
Pydantic schemas for Phase 8 - Workflow & Data-Flow Intelligence.

These schemas define the API request/response structures for workflow endpoints.
"""
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional, List
from datetime import datetime


class WorkflowNodeSchema(BaseModel):
    """
    Schema for a workflow node.
    
    Represents a component in the application workflow with
    full traceability to source code.
    """
    id: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type: endpoint, symbol, file, external_module")
    name: str = Field(..., description="Display name")
    file_path: Optional[str] = Field(None, description="Source file path")
    start_line: Optional[int] = Field(None, description="Starting line number")
    end_line: Optional[int] = Field(None, description="Ending line number")
    language: Optional[str] = Field(None, description="Programming language")
    symbol_type: Optional[str] = Field(None, description="Symbol type: function, class, method")
    method: Optional[str] = Field(None, description="HTTP method (for endpoint nodes)")
    path: Optional[str] = Field(None, description="Endpoint path (for endpoint nodes)")
    
    class Config:
        from_attributes = True


class WorkflowEdgeSchema(BaseModel):
    """
    Schema for a workflow edge.
    
    Represents a relationship between two workflow nodes.
    """
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Edge type: handles, calls, returns")
    line_number: Optional[int] = Field(None, description="Line number where relationship occurs")
    
    class Config:
        from_attributes = True


class WorkflowResponse(BaseModel):
    """
    Response schema for workflow queries.
    
    Contains the complete workflow graph with metadata.
    """
    start_node: WorkflowNodeSchema = Field(..., description="Starting node of the workflow")
    nodes: List[WorkflowNodeSchema] = Field(..., description="All nodes in the workflow")
    edges: List[WorkflowEdgeSchema] = Field(..., description="All edges in the workflow")
    node_count: int = Field(..., description="Total number of nodes")
    edge_count: int = Field(..., description="Total number of edges")
    depth: int = Field(..., description="Maximum traversal depth used")
    truncated: bool = Field(..., description="Whether workflow was truncated due to limits")
    truncation_reason: Optional[str] = Field(None, description="Reason for truncation if applicable")
    
    class Config:
        from_attributes = True


class EndpointWorkflowRequest(BaseModel):
    """
    Request schema for endpoint workflow queries.
    
    Optional query parameters for customizing workflow traversal.
    """
    depth: int = Field(5, ge=1, le=10, description="Traversal depth (1-10)")
    include_callers: bool = Field(False, description="Include upstream callers")


class SymbolWorkflowRequest(BaseModel):
    """
    Request schema for symbol workflow queries.
    
    Optional query parameters for customizing workflow traversal.
    """
    depth: int = Field(5, ge=1, le=10, description="Traversal depth (1-10)")
    direction: str = Field("downstream", description="Direction: downstream, upstream, both")
