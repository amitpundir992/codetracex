"""
Pydantic schemas for repository analysis.

These schemas define the structure of API requests and responses
for the repository analysis endpoint in Phase 2.
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
