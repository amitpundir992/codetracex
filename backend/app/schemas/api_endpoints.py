"""
Pydantic schemas for API endpoints.

Phase 7: API & Application Structure Intelligence
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ApiEndpointBase(BaseModel):
    """Base schema for API endpoint."""
    method: str = Field(..., description="HTTP method (GET, POST, PUT, etc.)")
    path: str = Field(..., description="Endpoint path as declared in code")
    framework: str = Field(..., description="Web framework (fastapi, flask, express, etc.)")
    handler_name: Optional[str] = Field(None, description="Handler function name")
    start_line: Optional[int] = Field(None, description="Starting line number")
    end_line: Optional[int] = Field(None, description="Ending line number")


class ApiEndpointSummary(ApiEndpointBase):
    """
    API endpoint summary for list views.
    
    Contains essential information for displaying endpoints in lists.
    """
    id: UUID = Field(..., description="Endpoint UUID")
    file_path: str = Field(..., description="Source file path")
    
    class Config:
        from_attributes = True


class SymbolInfo(BaseModel):
    """Symbol information for endpoint details."""
    id: UUID
    name: str
    type: str  # function, class, method, etc.
    file_path: str
    start_line: int
    end_line: int
    
    class Config:
        from_attributes = True


class DependencyNode(BaseModel):
    """Node in dependency graph."""
    id: UUID
    name: str
    type: str  # symbol, file
    file_path: Optional[str] = None


class ApiEndpointDetail(ApiEndpointBase):
    """
    Detailed API endpoint information.
    
    Includes handler resolution, file information, and dependencies.
    """
    id: UUID = Field(..., description="Endpoint UUID")
    repository_id: UUID = Field(..., description="Repository UUID")
    analysis_run_id: UUID = Field(..., description="Analysis run UUID")
    file_id: UUID = Field(..., description="File UUID")
    file_path: str = Field(..., description="Source file path")
    symbol_id: Optional[UUID] = Field(None, description="Handler symbol UUID")
    handler_symbol: Optional[SymbolInfo] = Field(None, description="Resolved handler symbol")
    created_at: datetime = Field(..., description="When endpoint was discovered")
    
    class Config:
        from_attributes = True


class ApiEndpointListResponse(BaseModel):
    """Response for endpoint list API."""
    items: List[ApiEndpointSummary] = Field(..., description="List of endpoints")
    total: int = Field(..., description="Total number of endpoints")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


class ApiEndpointDependenciesResponse(BaseModel):
    """Response for endpoint dependencies."""
    endpoint_id: UUID
    method: str
    path: str
    handler_name: Optional[str]
    dependencies: List[DependencyNode] = Field(
        ...,
        description="Downstream dependencies (services, repositories, etc.)"
    )
    callers: List[DependencyNode] = Field(
        ...,
        description="Upstream callers (other endpoints, functions)"
    )
