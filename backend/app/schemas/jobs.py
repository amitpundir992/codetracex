"""
Pydantic schemas for background jobs API.

Phase 14: Background Processing
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobCreateResponse(BaseModel):
    """Response when creating a new analysis job."""
    
    job_id: str = Field(..., description="RQ job identifier")
    analysis_run_id: UUID = Field(..., description="Analysis run UUID")
    repository_id: UUID = Field(..., description="Repository UUID")
    status: str = Field(..., description="Initial job status (queued)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "analysis_run_id": "550e8400-e29b-41d4-a716-446655440000",
                "repository_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "status": "queued"
            }
        }


class JobStatusResponse(BaseModel):
    """Response for job status query."""
    
    job_id: Optional[str] = Field(None, description="RQ job identifier")
    analysis_run_id: UUID = Field(..., description="Analysis run UUID")
    repository_id: UUID = Field(..., description="Repository UUID")
    repository_name: str = Field(..., description="Repository full name (owner/name)")
    status: str = Field(..., description="Current job status")
    progress: Optional[int] = Field(None, description="Progress percentage (0-100)")
    current_stage: Optional[str] = Field(None, description="Current pipeline stage")
    
    # Analysis stats
    total_files: int = Field(0, description="Total files scanned")
    analyzed_files: int = Field(0, description="Files successfully analyzed")
    total_symbols: int = Field(0, description="Total symbols extracted")
    
    # Timestamps
    created_at: datetime = Field(..., description="When job was created")
    started_at: Optional[datetime] = Field(None, description="When analysis started")
    completed_at: Optional[datetime] = Field(None, description="When analysis completed")
    
    # Error info
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "analysis_run_id": "550e8400-e29b-41d4-a716-446655440000",
                "repository_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "repository_name": "facebook/react",
                "status": "running",
                "progress": 65,
                "current_stage": "Building semantic chunks",
                "total_files": 1250,
                "analyzed_files": 1200,
                "total_symbols": 3450,
                "created_at": "2026-09-23T10:00:00Z",
                "started_at": "2026-09-23T10:00:05Z",
                "completed_at": None,
                "error_message": None
            }
        }


class JobCancelResponse(BaseModel):
    """Response when cancelling a job."""
    
    job_id: Optional[str] = Field(None, description="RQ job identifier")
    analysis_run_id: UUID = Field(..., description="Analysis run UUID")
    status: str = Field(..., description="Updated job status")
    message: str = Field(..., description="Cancellation message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "analysis_run_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "cancelled",
                "message": "Analysis job cancelled successfully"
            }
        }
