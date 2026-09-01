"""
Pydantic schemas for repository-related API requests and responses.
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class RepositoryRequest(BaseModel):
    """Request schema for repository ingestion."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://github.com/facebook/react"
            }
        }
    )
    
    url: str = Field(..., description="GitHub repository URL")


class RepositoryResponse(BaseModel):
    """Response schema containing GitHub repository metadata."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "react",
                "full_name": "facebook/react",
                "owner": "facebook",
                "description": "The library for web and native user interfaces.",
                "url": "https://github.com/facebook/react",
                "default_branch": "main",
                "visibility": "public",
                "stars": 100000,
                "forks": 20000,
                "language": "JavaScript",
                "created_at": "2013-05-24T16:15:54Z",
                "updated_at": "2024-08-31T12:00:00Z"
            }
        }
    )
    
    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name (owner/repo)")
    owner: str = Field(..., description="Repository owner username")
    description: str | None = Field(None, description="Repository description")
    url: str = Field(..., description="Repository HTML URL")
    default_branch: str = Field(..., description="Default branch name")
    visibility: str = Field(..., description="Repository visibility (public/private)")
    stars: int = Field(..., description="Number of stars")
    forks: int = Field(..., description="Number of forks")
    language: str | None = Field(None, description="Primary programming language")
    created_at: datetime | None = Field(None, description="Repository creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
