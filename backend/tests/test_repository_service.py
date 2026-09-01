"""
Tests for repository service URL validation and parsing.
"""
import pytest
from app.services.repository_service import RepositoryService, InvalidRepositoryURLError


class TestRepositoryServiceURLValidation:
    """Tests for GitHub URL validation and parsing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = RepositoryService()
    
    def test_valid_url_without_trailing_slash(self):
        """Test parsing a valid GitHub URL without trailing slash."""
        url = "https://github.com/facebook/react"
        owner, repo = self.service.parse_github_url(url)
        
        assert owner == "facebook"
        assert repo == "react"
    
    def test_valid_url_with_trailing_slash(self):
        """Test parsing a valid GitHub URL with trailing slash."""
        url = "https://github.com/facebook/react/"
        owner, repo = self.service.parse_github_url(url)
        
        assert owner == "facebook"
        assert repo == "react"
    
    def test_valid_url_with_dashes(self):
        """Test parsing a URL with dashes in owner/repo names."""
        url = "https://github.com/some-owner/some-repo"
        owner, repo = self.service.parse_github_url(url)
        
        assert owner == "some-owner"
        assert repo == "some-repo"
    
    def test_valid_url_with_underscores(self):
        """Test parsing a URL with underscores in owner/repo names."""
        url = "https://github.com/some_owner/some_repo"
        owner, repo = self.service.parse_github_url(url)
        
        assert owner == "some_owner"
        assert repo == "some_repo"
    
    def test_valid_url_with_dots_in_repo(self):
        """Test parsing a URL with dots in repository name."""
        url = "https://github.com/owner/repo.name"
        owner, repo = self.service.parse_github_url(url)
        
        assert owner == "owner"
        assert repo == "repo.name"
    
    def test_invalid_url_non_github(self):
        """Test that non-GitHub URLs are rejected."""
        url = "https://google.com/test"
        
        with pytest.raises(InvalidRepositoryURLError) as exc_info:
            self.service.parse_github_url(url)
        
        assert "Invalid GitHub repository URL" in str(exc_info.value)
    
    def test_invalid_url_not_url(self):
        """Test that non-URL strings are rejected."""
        url = "not-a-url"
        
        with pytest.raises(InvalidRepositoryURLError):
            self.service.parse_github_url(url)
    
    def test_invalid_url_github_root(self):
        """Test that GitHub root URL is rejected."""
        url = "https://github.com/"
        
        with pytest.raises(InvalidRepositoryURLError):
            self.service.parse_github_url(url)
    
    def test_invalid_url_only_owner(self):
        """Test that URL with only owner is rejected."""
        url = "https://github.com/owner"
        
        with pytest.raises(InvalidRepositoryURLError):
            self.service.parse_github_url(url)
    
    def test_invalid_url_extra_path(self):
        """Test that URL with extra path segments is rejected."""
        url = "https://github.com/owner/repo/extra/path"
        
        with pytest.raises(InvalidRepositoryURLError):
            self.service.parse_github_url(url)
    
    def test_invalid_url_http_instead_of_https(self):
        """Test that HTTP URLs are rejected (only HTTPS is supported)."""
        url = "http://github.com/owner/repo"
        
        with pytest.raises(InvalidRepositoryURLError):
            self.service.parse_github_url(url)
    
    def test_url_with_whitespace(self):
        """Test that URLs with surrounding whitespace are handled correctly."""
        url = "  https://github.com/facebook/react  "
        owner, repo = self.service.parse_github_url(url)
        
        assert owner == "facebook"
        assert repo == "react"
    
    def test_empty_url(self):
        """Test that empty URL is rejected."""
        url = ""
        
        with pytest.raises(InvalidRepositoryURLError):
            self.service.parse_github_url(url)
    
    def test_url_with_query_params(self):
        """Test that URLs with query parameters are rejected."""
        url = "https://github.com/owner/repo?tab=readme"
        
        with pytest.raises(InvalidRepositoryURLError):
            self.service.parse_github_url(url)
