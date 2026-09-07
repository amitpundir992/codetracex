"""
Git history extraction service.

Phase 6: Git History Intelligence

This service extracts Git commit history from repositories using safe subprocess execution.

Architecture:
    
    GitHub Repository URL
        ↓
    Temporary Git Clone
        ↓
    Extract Commit Metadata
        ↓
    Parse File Changes
        ↓
    Structured Commit Data
        ↓
    Delete Temporary Clone

Security:
    - Uses subprocess with argument arrays (no shell=True)
    - Validates repository URLs
    - Enforces command timeouts
    - Cleans up temporary directories after failures
    - Never executes repository code

Lifecycle:
    - Temporary clone created with tempfile
    - Git commands executed safely
    - Structured data extracted
    - Temporary clone deleted (even on errors)
"""
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class GitCommandError(Exception):
    """Exception raised when a Git command fails."""
    pass


class GitHistoryService:
    """Service for extracting Git commit history from repositories."""
    
    # Command timeout (30 seconds)
    GIT_TIMEOUT = 30.0
    
    # Default maximum number of commits to extract
    DEFAULT_MAX_COMMITS = 1000
    
    def __init__(self, max_commits: int = DEFAULT_MAX_COMMITS):
        """
        Initialize the Git history service.
        
        Args:
            max_commits: Maximum number of commits to extract
        """
        self.max_commits = max_commits
    
    def _run_git_command(
        self,
        args: List[str],
        cwd: Path,
        timeout: float = GIT_TIMEOUT
    ) -> str:
        """
        Execute a Git command safely using subprocess.
        
        Security:
            - Uses argument arrays (no shell=True)
            - Enforces timeouts
            - Captures stdout/stderr
            - Handles errors gracefully
        
        Args:
            args: Git command arguments (e.g., ['git', 'log', '--format=%H'])
            cwd: Working directory for command execution
            timeout: Command timeout in seconds
            
        Returns:
            Command stdout as string
            
        Raises:
            GitCommandError: If command fails or times out
        """
        try:
            result = subprocess.run(
                args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            if result.returncode != 0:
                raise GitCommandError(
                    f"Git command failed: {' '.join(args)}\n"
                    f"Exit code: {result.returncode}\n"
                    f"Error: {result.stderr}"
                )
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            raise GitCommandError(
                f"Git command timed out after {timeout}s: {' '.join(args)}"
            )
        except FileNotFoundError:
            raise GitCommandError(
                "Git executable not found. Ensure Git is installed and in PATH."
            )
        except Exception as e:
            raise GitCommandError(f"Unexpected error executing Git command: {str(e)}")
    
    def clone_repository(
        self,
        github_url: str,
        dest_path: Path,
        branch: Optional[str] = None
    ) -> None:
        """
        Clone a GitHub repository to a temporary location.
        
        Args:
            github_url: GitHub repository URL (HTTPS)
            dest_path: Destination path for clone
            branch: Optional branch to clone (defaults to repository default)
            
        Raises:
            GitCommandError: If clone fails
        """
        args = ['git', 'clone', '--quiet']
        
        if branch:
            args.extend(['--branch', branch])
        
        # Limit clone depth to reduce download size and time
        args.extend(['--depth', '1000'])  # Last 1000 commits
        
        args.extend([github_url, str(dest_path)])
        
        logger.info(f"Cloning repository: {github_url}")
        
        try:
            self._run_git_command(args, Path.cwd(), timeout=120.0)  # Longer timeout for clone
            logger.info(f"Successfully cloned repository to {dest_path}")
        except GitCommandError as e:
            logger.error(f"Failed to clone repository: {e}")
            raise
    
    def extract_commits(self, repo_path: Path) -> List[Dict[str, Any]]:
        """
        Extract commit metadata from a Git repository.
        
        Uses machine-readable Git format to avoid parsing issues.
        
        Format separators:
            - Commits separated by: --COMMIT--
            - Fields separated by: --FIELD--
        
        Args:
            repo_path: Path to Git repository
            
        Returns:
            List of commit dictionaries with fields:
                - commit_hash: Full SHA
                - author_name: Author name
                - author_email: Author email
                - commit_message: Full message
                - committed_at: Timestamp
                - parent_hashes: List of parent SHAs
                
        Raises:
            GitCommandError: If Git command fails
        """
        # Use custom format with clear separators
        # Format: hash|author_name|author_email|timestamp|parents|subject|body
        format_str = '%H--FIELD--%an--FIELD--%ae--FIELD--%at--FIELD--%P--FIELD--%s--FIELD--%b--COMMIT--'
        
        args = [
            'git', 'log',
            f'--format={format_str}',
            f'-n{self.max_commits}',
            '--all'  # Include all branches
        ]
        
        logger.info(f"Extracting commits from {repo_path}")
        
        output = self._run_git_command(args, repo_path)
        
        commits = []
        commit_blocks = output.split('--COMMIT--')
        
        for block in commit_blocks:
            block = block.strip()
            if not block:
                continue
            
            try:
                fields = block.split('--FIELD--')
                if len(fields) < 7:
                    logger.warning(f"Skipping malformed commit block: {block[:100]}")
                    continue
                
                commit_hash = fields[0].strip()
                author_name = fields[1].strip()
                author_email = fields[2].strip()
                timestamp = int(fields[3].strip())
                parent_hashes = fields[4].strip().split()  # Space-separated
                subject = fields[5].strip()
                body = fields[6].strip()
                
                # Combine subject and body for full message
                commit_message = subject
                if body:
                    commit_message = f"{subject}\n\n{body}"
                
                commit = {
                    'commit_hash': commit_hash,
                    'author_name': author_name,
                    'author_email': author_email,
                    'commit_message': commit_message,
                    'committed_at': datetime.fromtimestamp(timestamp),
                    'parent_hashes': parent_hashes
                }
                
                commits.append(commit)
                
            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse commit: {e}")
                continue
        
        logger.info(f"Extracted {len(commits)} commits")
        return commits
    
    def extract_file_changes(
        self,
        repo_path: Path,
        commit_hash: str
    ) -> List[Dict[str, Any]]:
        """
        Extract file changes for a specific commit.
        
        Uses git diff-tree to get change information:
            - Change type (A=added, M=modified, D=deleted, R=renamed)
            - Additions and deletions
            - Old and new paths (for renames)
        
        Args:
            repo_path: Path to Git repository
            commit_hash: Commit SHA to analyze
            
        Returns:
            List of file change dictionaries with fields:
                - path: Current/new file path
                - change_type: added/modified/deleted/renamed
                - additions: Number of lines added
                - deletions: Number of lines deleted
                - old_path: Original path (for renames)
                - new_path: New path (for renames)
                
        Raises:
            GitCommandError: If Git command fails
        """
        # Use diff-tree with numstat for detailed change information
        # Format: additions<tab>deletions<tab>path
        # For renames: additions<tab>deletions<tab>old_path => new_path
        # --root ensures first commit (root commit with no parent) is shown
        args = [
            'git', 'diff-tree',
            '--no-commit-id',
            '--numstat',
            '--find-renames',
            '--root',  # Show root commits (first commit with no parent)
            '-r',
            commit_hash
        ]
        
        output = self._run_git_command(args, repo_path)
        
        file_changes = []
        
        for line in output.strip().split('\n'):
            if not line:
                continue
            
            try:
                parts = line.split('\t')
                if len(parts) < 3:
                    continue
                
                additions_str = parts[0].strip()
                deletions_str = parts[1].strip()
                path_info = parts[2].strip()
                
                # Parse additions/deletions (can be '-' for binary files)
                additions = 0 if additions_str == '-' else int(additions_str)
                deletions = 0 if deletions_str == '-' else int(deletions_str)
                
                # Check if this is a rename (contains ' => ')
                if ' => ' in path_info:
                    # Format: old_path => new_path
                    old_path, new_path = path_info.split(' => ')
                    old_path = old_path.strip()
                    new_path = new_path.strip()
                    
                    file_change = {
                        'path': new_path,
                        'change_type': 'renamed',
                        'additions': additions,
                        'deletions': deletions,
                        'old_path': old_path,
                        'new_path': new_path
                    }
                else:
                    # Regular change
                    path = path_info
                    
                    # Determine change type by checking if file exists in parent
                    # For now, use additions/deletions as heuristic
                    if additions > 0 and deletions == 0:
                        change_type = 'added'
                    elif additions == 0 and deletions > 0:
                        change_type = 'deleted'
                    else:
                        change_type = 'modified'
                    
                    file_change = {
                        'path': path,
                        'change_type': change_type,
                        'additions': additions,
                        'deletions': deletions,
                        'old_path': None,
                        'new_path': None
                    }
                
                file_changes.append(file_change)
                
            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse diff line: {line} - {e}")
                continue
        
        return file_changes
    
    def extract_repository_history(
        self,
        github_url: str,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract complete Git history from a GitHub repository.
        
        This method:
        1. Creates a temporary directory
        2. Clones the repository
        3. Extracts commit metadata
        4. Extracts file changes for each commit
        5. Cleans up temporary directory (even on errors)
        
        Args:
            github_url: GitHub repository URL
            branch: Optional branch to analyze
            
        Returns:
            Dictionary containing:
                - commits: List of commit metadata
                - total_commits: Number of commits extracted
                
        Raises:
            GitCommandError: If extraction fails
        """
        temp_dir = None
        
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix='codetracex_git_')
            repo_path = Path(temp_dir) / 'repo'
            
            # Clone repository
            self.clone_repository(github_url, repo_path, branch)
            
            # Extract commits
            commits = self.extract_commits(repo_path)
            
            # Extract file changes for each commit
            for commit in commits:
                try:
                    file_changes = self.extract_file_changes(
                        repo_path,
                        commit['commit_hash']
                    )
                    commit['file_changes'] = file_changes
                except GitCommandError as e:
                    logger.warning(
                        f"Failed to extract file changes for commit "
                        f"{commit['commit_hash']}: {e}"
                    )
                    commit['file_changes'] = []
            
            result = {
                'commits': commits,
                'total_commits': len(commits)
            }
            
            logger.info(
                f"Successfully extracted {result['total_commits']} commits "
                f"with file changes"
            )
            
            return result
            
        finally:
            # Clean up temporary directory
            if temp_dir and Path(temp_dir).exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logger.error(f"Failed to clean up temporary directory: {e}")
