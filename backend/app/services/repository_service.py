"""
Repository service for URL validation and repository processing.

This service handles the business logic for processing repository URLs,
validating them, extracting owner and repository names, and coordinating
with the GitHub service to retrieve metadata.
"""
import re
from typing import Tuple
from app.services.github_service import GitHubService, GitHubAPIError, RepositoryNotFoundError


class InvalidRepositoryURLError(Exception):
    """Exception raised when a repository URL is invalid."""
    pass


class RepositoryService:
    """Service for processing and validating repository information."""
    
    # Regex pattern for GitHub repository URLs
    # Matches: https://github.com/owner/repository or https://github.com/owner/repository/
    GITHUB_URL_PATTERN = re.compile(
        r'^https://github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)/?$'
    )
    
    def __init__(self):
        """Initialize the repository service."""
        self.github_service = GitHubService()
    
    def parse_github_url(self, url: str) -> Tuple[str, str]:
        """
        Parse and validate a GitHub repository URL.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repository_name)
            
        Raises:
            InvalidRepositoryURLError: If the URL is not a valid GitHub repository URL
        """
        # Strip whitespace
        url = url.strip()
        
        # Check if URL matches the expected pattern
        match = self.GITHUB_URL_PATTERN.match(url)
        
        if not match:
            raise InvalidRepositoryURLError(
                "Invalid GitHub repository URL. Expected format: https://github.com/owner/repository"
            )
        
        owner, repository = match.groups()
        
        return owner, repository
    
    async def get_repository_metadata(self, url: str) -> dict:
        """
        Get repository metadata from a GitHub URL.
        
        This is the main entry point for repository processing. It:
        1. Validates and parses the URL
        2. Retrieves repository information from GitHub
        3. Extracts and normalizes the metadata
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Dictionary containing repository metadata
            
        Raises:
            InvalidRepositoryURLError: If the URL is invalid
            RepositoryNotFoundError: If the repository doesn't exist
            GitHubAPIError: If there's an error with GitHub API
        """
        # Parse and validate the URL
        owner, repository = self.parse_github_url(url)
        
        # Get repository information from GitHub
        github_data = await self.github_service.get_repository_info(owner, repository)
        
        # Extract and normalize metadata
        metadata = self.github_service.extract_repository_metadata(github_data)
        
        return metadata
