"""
Change Detection Service for Phase 18: Pull Request & Change Intelligence.

This service provides deterministic change detection between commits using
the existing Git history infrastructure.

Architecture Philosophy:

    DETERMINISTIC CHANGE DETECTION
    
    This service analyzes Git commits to identify:
    - Added files
    - Modified files
    - Deleted files
    - Renamed files
    - Line changes (insertions/deletions)
    
    It does NOT:
    - Invent changes
    - Guess at semantic meaning
    - Execute code
    
    Flow:
    1. Validate commits exist in database
    2. Extract file changes from Git history
    3. Classify files (source/test/other)
    4. Detect languages
    5. Structure for downstream analysis

Repository Isolation:

    All queries scoped by repository_id.
    Cross-repository contamination prevented.
"""
from typing import List, Dict, Optional, Any, Tuple
from uuid import UUID
import logging
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import Repository, Commit, CommitFileChange, ChangeType as DBChangeType
from app.schemas.change_analysis import ChangedFile, ChangeType
from app.utils.scanner_config import detect_language

logger = logging.getLogger(__name__)


class ChangeDetectionService:
    """
    Service for detecting file changes between commits.
    
    Uses existing Git history data from the database.
    """
    
    def __init__(self, db: Session):
        """
        Initialize change detection service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def _is_test_file(self, path: str) -> bool:
        """
        Determine if a file is likely a test file.
        
        Uses heuristics based on path and filename patterns.
        
        Args:
            path: File path
            
        Returns:
            True if likely a test file
        """
        path_lower = path.lower()
        parts = Path(path).parts
        
        # Common test directory patterns
        test_dirs = {'test', 'tests', '__tests__', 'spec', 'specs', 'test_', 'e2e', 'integration'}
        if any(part.lower() in test_dirs for part in parts):
            return True
        
        # Common test file patterns
        filename = Path(path).name.lower()
        test_patterns = ['test_', '_test', '.test.', '.spec.', '_spec']
        if any(pattern in filename for pattern in test_patterns):
            return True
        
        return False
    
    def _is_source_file(self, path: str, language: Optional[str]) -> bool:
        """
        Determine if a file is a source file.
        
        Args:
            path: File path
            language: Detected language
            
        Returns:
            True if likely a source file
        """
        if not language:
            return False
        
        # Exclude documentation and configuration
        path_lower = path.lower()
        non_source_patterns = [
            '.md', '.txt', '.json', '.yaml', '.yml', '.toml',
            '.xml', '.ini', '.cfg', '.conf', 'license', 'readme',
            'dockerfile', '.dockerignore', '.gitignore'
        ]
        
        if any(pattern in path_lower for pattern in non_source_patterns):
            return False
        
        # Consider files with detected programming language as source
        programming_languages = {
            'Python', 'JavaScript', 'TypeScript', 'Java', 'Go',
            'Rust', 'C', 'C++', 'C#', 'Ruby', 'PHP', 'Swift', 'Kotlin'
        }
        
        return language in programming_languages
    
    def _map_change_type(self, db_change_type: str) -> ChangeType:
        """
        Map database change type to schema change type.
        
        Args:
            db_change_type: Database ChangeType enum value
            
        Returns:
            Schema ChangeType enum value
        """
        type_mapping = {
            DBChangeType.ADDED.value: ChangeType.ADDED,
            DBChangeType.MODIFIED.value: ChangeType.MODIFIED,
            DBChangeType.DELETED.value: ChangeType.DELETED,
            DBChangeType.RENAMED.value: ChangeType.RENAMED,
        }
        
        return type_mapping.get(db_change_type, ChangeType.UNKNOWN)
    
    def get_commit_file_changes(
        self,
        repository_id: UUID,
        commit_sha: str
    ) -> List[ChangedFile]:
        """
        Get file changes for a single commit.
        
        Args:
            repository_id: Repository UUID
            commit_sha: Commit SHA (full or abbreviated)
            
        Returns:
            List of ChangedFile objects
            
        Raises:
            ValueError: If commit not found
        """
        # Find commit (handle abbreviated SHAs)
        commit = self.db.query(Commit).filter(
            and_(
                Commit.repository_id == repository_id,
                Commit.commit_hash.like(f"{commit_sha}%")
            )
        ).first()
        
        if not commit:
            raise ValueError(f"Commit {commit_sha} not found in repository")
        
        # Get file changes
        file_changes = self.db.query(CommitFileChange).filter(
            CommitFileChange.commit_id == commit.id
        ).all()
        
        changed_files = []
        
        for change in file_changes:
            language = detect_language(change.path)
            is_test = self._is_test_file(change.path)
            is_source = self._is_source_file(change.path, language)
            
            changed_file = ChangedFile(
                path=change.path,
                change_type=self._map_change_type(change.change_type),
                old_path=change.old_path,
                additions=change.additions,
                deletions=change.deletions,
                is_test=is_test,
                is_source=is_source,
                language=language
            )
            
            changed_files.append(changed_file)
        
        logger.info(
            f"Found {len(changed_files)} file changes in commit {commit_sha[:8]}"
        )
        
        return changed_files
    
    def get_commit_range_changes(
        self,
        repository_id: UUID,
        base_sha: str,
        head_sha: str
    ) -> Tuple[List[ChangedFile], Dict[str, Any]]:
        """
        Get aggregated file changes between two commits.
        
        This method finds all commits between base and head and aggregates
        their file changes. For files changed multiple times, uses the latest
        state.
        
        Args:
            repository_id: Repository UUID
            base_sha: Base commit SHA
            head_sha: Head commit SHA
            
        Returns:
            Tuple of (changed_files, metadata)
            
        Raises:
            ValueError: If commits not found
        """
        # Find commits
        base_commit = self.db.query(Commit).filter(
            and_(
                Commit.repository_id == repository_id,
                Commit.commit_hash.like(f"{base_sha}%")
            )
        ).first()
        
        head_commit = self.db.query(Commit).filter(
            and_(
                Commit.repository_id == repository_id,
                Commit.commit_hash.like(f"{head_sha}%")
            )
        ).first()
        
        if not base_commit:
            raise ValueError(f"Base commit {base_sha} not found in repository")
        if not head_commit:
            raise ValueError(f"Head commit {head_sha} not found in repository")
        
        # Get commits between base and head (inclusive of head, exclusive of base)
        # Simplified approach: get all commits newer than base up to head
        commits_in_range = self.db.query(Commit).filter(
            and_(
                Commit.repository_id == repository_id,
                Commit.committed_at > base_commit.committed_at,
                Commit.committed_at <= head_commit.committed_at
            )
        ).order_by(Commit.committed_at.asc()).all()
        
        logger.info(
            f"Found {len(commits_in_range)} commits between "
            f"{base_sha[:8]} and {head_sha[:8]}"
        )
        
        # Aggregate file changes
        # Use a dict to track the latest state of each file
        file_changes_map: Dict[str, CommitFileChange] = {}
        total_insertions = 0
        total_deletions = 0
        
        for commit in commits_in_range:
            changes = self.db.query(CommitFileChange).filter(
                CommitFileChange.commit_id == commit.id
            ).all()
            
            for change in changes:
                # Track cumulative stats
                total_insertions += change.additions
                total_deletions += change.deletions
                
                # Update file state (latest change wins)
                file_changes_map[change.path] = change
        
        # Convert to ChangedFile objects
        changed_files = []
        
        for file_path, change in file_changes_map.items():
            language = detect_language(change.path)
            is_test = self._is_test_file(change.path)
            is_source = self._is_source_file(change.path, language)
            
            changed_file = ChangedFile(
                path=change.path,
                change_type=self._map_change_type(change.change_type),
                old_path=change.old_path,
                additions=change.additions,
                deletions=change.deletions,
                is_test=is_test,
                is_source=is_source,
                language=language
            )
            
            changed_files.append(changed_file)
        
        metadata = {
            'base_sha': base_commit.commit_hash,
            'head_sha': head_commit.commit_hash,
            'files_changed': len(changed_files),
            'insertions': total_insertions,
            'deletions': total_deletions,
            'commits_in_range': len(commits_in_range)
        }
        
        logger.info(
            f"Aggregated {metadata['files_changed']} file changes "
            f"(+{total_insertions}, -{total_deletions})"
        )
        
        return changed_files, metadata
    
    def detect_changes(
        self,
        repository_id: UUID,
        base_sha: Optional[str] = None,
        head_sha: Optional[str] = None,
        commit_sha: Optional[str] = None
    ) -> Tuple[List[ChangedFile], Dict[str, Any]]:
        """
        Detect changes based on input mode.
        
        Supports two modes:
        1. Commit range: base_sha + head_sha
        2. Single commit: commit_sha
        
        Args:
            repository_id: Repository UUID
            base_sha: Base commit SHA (for range mode)
            head_sha: Head commit SHA (for range mode)
            commit_sha: Single commit SHA (for single commit mode)
            
        Returns:
            Tuple of (changed_files, metadata)
            
        Raises:
            ValueError: If input validation fails or commits not found
        """
        if commit_sha:
            # Single commit mode
            changed_files = self.get_commit_file_changes(repository_id, commit_sha)
            
            # Get commit for metadata
            commit = self.db.query(Commit).filter(
                and_(
                    Commit.repository_id == repository_id,
                    Commit.commit_hash.like(f"{commit_sha}%")
                )
            ).first()
            
            total_insertions = sum(f.additions for f in changed_files)
            total_deletions = sum(f.deletions for f in changed_files)
            
            metadata = {
                'base_sha': commit.commit_hash,  # Single commit uses same for base/head
                'head_sha': commit.commit_hash,
                'files_changed': len(changed_files),
                'insertions': total_insertions,
                'deletions': total_deletions,
                'commits_in_range': 1
            }
            
            return changed_files, metadata
        
        elif base_sha and head_sha:
            # Commit range mode
            return self.get_commit_range_changes(repository_id, base_sha, head_sha)
        
        else:
            raise ValueError(
                "Must provide either commit_sha OR both base_sha and head_sha"
            )
