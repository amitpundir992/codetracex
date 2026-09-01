"""
GitHub service for interacting with the GitHub API.

This service handles communication with GitHub's REST API to retrieve
repository information. For Phase 1, we only work with public repositories
and do not require authentication.
"""
import httpx
from typing import Dict, Any


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors."""
    pass


class RepositoryNotFoundError(Exception):
    """Exception raised when a repository does not exist."""
    pass


class GitHubService:
    """Service for interacting with GitHub's REST API."""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self):
        """Initialize the GitHub service."""
        # For Phase 1, we don't use authentication
        # This limits us to 60 requests/hour but is sufficient for initial testing
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeTraceX/0.1.0"
        }
    
    async def get_repository_info(self, owner: str, repository: str) -> Dict[str, Any]:
        """
        Retrieve repository information from GitHub API.
        
        Args:
            owner: Repository owner username
            repository: Repository name
            
        Returns:
            Dictionary containing repository metadata
            
        Raises:
            RepositoryNotFoundError: If the repository does not exist
            GitHubAPIError: If there's an error communicating with GitHub API
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repository}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=10.0)
                
                if response.status_code == 404:
                    raise RepositoryNotFoundError(
                        f"Repository {owner}/{repository} not found on GitHub"
                    )
                
                if response.status_code != 200:
                    raise GitHubAPIError(
                        f"GitHub API returned status code {response.status_code}"
                    )
                
                return response.json()
                
        except httpx.TimeoutException:
            raise GitHubAPIError("GitHub API request timed out")
        except httpx.RequestError as e:
            raise GitHubAPIError(f"Error connecting to GitHub API: {str(e)}")
    
    def extract_repository_metadata(self, github_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant metadata from GitHub API response.
        
        Args:
            github_data: Raw response from GitHub API
            
        Returns:
            Dictionary with extracted and normalized metadata
        """
        return {
            "name": github_data.get("name"),
            "full_name": github_data.get("full_name"),
            "owner": github_data.get("owner", {}).get("login"),
            "description": github_data.get("description"),
            "url": github_data.get("html_url"),
            "default_branch": github_data.get("default_branch"),
            "visibility": github_data.get("visibility", "public"),
            "stars": github_data.get("stargazers_count", 0),
            "forks": github_data.get("forks_count", 0),
            "language": github_data.get("language"),
            "created_at": github_data.get("created_at"),
            "updated_at": github_data.get("updated_at"),
        }
