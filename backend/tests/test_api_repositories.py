"""
Tests for repository API endpoint.

These tests use mocking to avoid making real network requests to GitHub,
ensuring deterministic test execution.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.services.github_service import GitHubAPIError, RepositoryNotFoundError
from app.services.repository_service import InvalidRepositoryURLError


client = TestClient(app)


class TestRepositoryAPI:
    """Tests for POST /api/repositories endpoint."""
    
    @patch('app.services.repository_service.RepositoryService.get_repository_metadata')
    @pytest.mark.asyncio
    async def test_successful_repository_ingestion(self, mock_get_metadata):
        """Test successful repository ingestion with valid URL."""
        # Mock the repository metadata response
        mock_get_metadata.return_value = {
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
        
        response = client.post(
            "/api/repositories",
            json={"url": "https://github.com/facebook/react"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "react"
        assert data["full_name"] == "facebook/react"
        assert data["owner"] == "facebook"
        assert data["visibility"] == "public"
    
    @patch('app.services.repository_service.RepositoryService.get_repository_metadata')
    @pytest.mark.asyncio
    async def test_invalid_url(self, mock_get_metadata):
        """Test API response for invalid GitHub URL."""
        # Mock raising InvalidRepositoryURLError
        mock_get_metadata.side_effect = InvalidRepositoryURLError(
            "Invalid GitHub repository URL. Expected format: https://github.com/owner/repository"
        )
        
        response = client.post(
            "/api/repositories",
            json={"url": "https://google.com/test"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid GitHub repository URL" in data["detail"]
    
    @patch('app.services.repository_service.RepositoryService.get_repository_metadata')
    @pytest.mark.asyncio
    async def test_repository_not_found(self, mock_get_metadata):
        """Test API response when repository doesn't exist on GitHub."""
        # Mock raising RepositoryNotFoundError
        mock_get_metadata.side_effect = RepositoryNotFoundError(
            "Repository does-not-exist/fake-repo not found on GitHub"
        )
        
        response = client.post(
            "/api/repositories",
            json={"url": "https://github.com/does-not-exist/fake-repo"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    @patch('app.services.repository_service.RepositoryService.get_repository_metadata')
    @pytest.mark.asyncio
    async def test_github_api_error(self, mock_get_metadata):
        """Test API response when GitHub API fails."""
        # Mock raising GitHubAPIError
        mock_get_metadata.side_effect = GitHubAPIError(
            "GitHub API returned status code 500"
        )
        
        response = client.post(
            "/api/repositories",
            json={"url": "https://github.com/facebook/react"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "GitHub API" in data["detail"]
    
    def test_missing_url_field(self):
        """Test API response when URL field is missing."""
        response = client.post(
            "/api/repositories",
            json={}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_empty_request_body(self):
        """Test API response with empty request body."""
        response = client.post(
            "/api/repositories",
            json=None
        )
        
        assert response.status_code == 422  # Validation error
    
    @patch('app.services.repository_service.RepositoryService.get_repository_metadata')
    @pytest.mark.asyncio
    async def test_repository_with_null_description(self, mock_get_metadata):
        """Test handling of repository with no description."""
        # Some repositories don't have descriptions
        mock_get_metadata.return_value = {
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "owner": "owner",
            "description": None,  # No description
            "url": "https://github.com/owner/test-repo",
            "default_branch": "main",
            "visibility": "public",
            "stars": 10,
            "forks": 2,
            "language": None,  # No primary language
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z"
        }
        
        response = client.post(
            "/api/repositories",
            json={"url": "https://github.com/owner/test-repo"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["description"] is None
        assert data["language"] is None
