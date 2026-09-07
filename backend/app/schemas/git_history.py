"""
Git history schemas for API responses.

Phase 6: Git History Intelligence

These schemas define the structure of Git history data returned by APIs.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class CommitFileChangeSchema(BaseModel):
    """
    File change in a commit.
    
    Represents one file that was changed in a commit.
    """
    id: UUID
    commit_id: UUID
    file_id: Optional[UUID] = None
    path: str
    change_type: str  # added, modified, deleted, renamed
    additions: int = 0
    deletions: int = 0
    old_path: Optional[str] = None
    new_path: Optional[str] = None
    
    class Config:
        from_attributes = True


class CommitSummarySchema(BaseModel):
    """
    Summary of a commit for list views.
    
    Contains essential commit information without file changes.
    """
    id: UUID
    repository_id: UUID
    commit_hash: str
    short_hash: str = Field(description="First 8 characters of commit hash")
    author_name: str
    author_email: str
    commit_message: str
    subject: str = Field(description="First line of commit message")
    committed_at: datetime
    parent_count: int = Field(description="Number of parent commits")
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_commit(cls, commit):
        """
        Create CommitSummarySchema from Commit model.
        
        Args:
            commit: Commit model instance
            
        Returns:
            CommitSummarySchema instance
        """
        # Extract subject (first line of commit message)
        subject = commit.commit_message.split('\n')[0] if commit.commit_message else ''
        
        # Count parent commits
        parent_count = len(commit.parent_hashes.split(',')) if commit.parent_hashes else 0
        
        return cls(
            id=commit.id,
            repository_id=commit.repository_id,
            commit_hash=commit.commit_hash,
            short_hash=commit.commit_hash[:8],
            author_name=commit.author_name,
            author_email=commit.author_email,
            commit_message=commit.commit_message,
            subject=subject,
            committed_at=commit.committed_at,
            parent_count=parent_count
        )


class CommitDetailSchema(BaseModel):
    """
    Detailed commit information with file changes.
    
    Used for single commit detail views.
    """
    id: UUID
    repository_id: UUID
    commit_hash: str
    short_hash: str
    author_name: str
    author_email: str
    commit_message: str
    subject: str
    committed_at: datetime
    parent_hashes: List[str] = Field(description="List of parent commit SHAs")
    file_changes: List[CommitFileChangeSchema]
    total_additions: int = Field(description="Total lines added across all files")
    total_deletions: int = Field(description="Total lines deleted across all files")
    files_changed: int = Field(description="Number of files changed")
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_commit(cls, commit):
        """
        Create CommitDetailSchema from Commit model.
        
        Args:
            commit: Commit model instance with file_changes loaded
            
        Returns:
            CommitDetailSchema instance
        """
        # Extract subject
        subject = commit.commit_message.split('\n')[0] if commit.commit_message else ''
        
        # Parse parent hashes
        parent_hashes = commit.parent_hashes.split(',') if commit.parent_hashes else []
        
        # Convert file changes
        file_changes = [
            CommitFileChangeSchema.from_orm(fc)
            for fc in commit.file_changes
        ]
        
        # Calculate totals
        total_additions = sum(fc.additions or 0 for fc in commit.file_changes)
        total_deletions = sum(fc.deletions or 0 for fc in commit.file_changes)
        
        return cls(
            id=commit.id,
            repository_id=commit.repository_id,
            commit_hash=commit.commit_hash,
            short_hash=commit.commit_hash[:8],
            author_name=commit.author_name,
            author_email=commit.author_email,
            commit_message=commit.commit_message,
            subject=subject,
            committed_at=commit.committed_at,
            parent_hashes=parent_hashes,
            file_changes=file_changes,
            total_additions=total_additions,
            total_deletions=total_deletions,
            files_changed=len(file_changes)
        )


class CommitListResponse(BaseModel):
    """
    Paginated list of commits.
    
    Used for commit listing endpoints.
    """
    items: List[CommitSummarySchema]
    total: int
    page: int
    page_size: int
    total_pages: int


class FileHistorySchema(BaseModel):
    """
    Commit information for file history.
    
    Simplified commit info focused on file-specific changes.
    """
    commit_id: UUID
    commit_hash: str
    short_hash: str
    author_name: str
    author_email: str
    subject: str
    committed_at: datetime
    change_type: str
    additions: int
    deletions: int
    
    class Config:
        from_attributes = True


class FileHistoryResponse(BaseModel):
    """
    File history response.
    
    Lists all commits that modified a specific file.
    """
    file_id: UUID
    file_path: str
    commits: List[FileHistorySchema]
    total_commits: int


class CoChangeFileSchema(BaseModel):
    """
    File that frequently changes together with target file.
    
    Represents co-change analysis results.
    """
    file_id: Optional[UUID] = None
    file_path: str
    shared_commits: int = Field(description="Number of commits where both files changed")
    last_shared_commit: datetime = Field(description="Most recent shared commit")


class CoChangeResponse(BaseModel):
    """
    Co-change analysis response.
    
    Shows files that frequently change together with the target file.
    """
    file_id: UUID
    file_path: str
    co_changed_files: List[CoChangeFileSchema]
    total_files: int
