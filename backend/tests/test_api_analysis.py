"""
Tests for repository analysis API endpoint.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.scanner_service import ScanResult, FileMetadata
from app.services.repository_service import InvalidRepositoryURLError
from app.services.github_service import RepositoryNotFoundError, GitHubAPIError
from app.services.download_service import DownloadTooLargeError, DownloadError
from app.services.scanner_service import TooManyFilesError
from app.utils.zip_utils import UnsafeZipError, InvalidZipError


client = TestClient(app)


@pytest.fixture
def mock_analysis_result():
    """Create a mock analysis result."""
    return {
        "repository": "facebook/react",
        "metadata": {
            "name": "react",
            "full_name": "facebook/react",
            "owner": "facebook",
            "description": "A JavaScript library",
            "url": "https://github.com/facebook/react",
            "default_branch": "main",
            "visibility": "public",
            "stars": 100000,
            "forks": 20000,
            "language": "JavaScript",
            "created_at": "2013-05-24T16:15:54Z",
            "updated_at": "2024-08-31T12:00:00Z"
        },
        "scan_result": ScanResult(
            total_files=150,
            total_size_bytes=1234567,
            files=[
                FileMetadata(
                    path="src/index.js",
                    filename="index.js",
                    extension=".js",
                    size_bytes=1523,
                    language="JavaScript",
                    lines=45,
                    is_sensitive=False
                ),
                FileMetadata(
                    path="src/App.tsx",
                    filename="App.tsx",
                    extension=".tsx",
                    size_bytes=2850,
                    language="TypeScript",
                    lines=102,
                    is_sensitive=False
                ),
            ],
            languages={"JavaScript": 80, "TypeScript": 70}
        )
    }


class TestAnalyzeRepositoryEndpoint:
    """Tests for POST /api/repositories/analyze endpoint."""
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_analyze_repository_success(self, mock_analyze, mock_analysis_result):
        """Test successful repository analysis."""
        mock_analyze.return_value = mock_analysis_result
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/facebook/react"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["repository"] == "facebook/react"
        assert data["status"] == "completed"
        assert data["total_files"] == 150
        assert data["total_size_bytes"] == 1234567
        assert "JavaScript" in data["languages"]
        assert "TypeScript" in data["languages"]
        assert len(data["files"]) == 2
        assert data["files_returned"] == 2
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_analyze_repository_with_many_files(self, mock_analyze):
        """Test that API limits returned files even when many are scanned."""
        # Create result with 200 files
        many_files = [
            FileMetadata(
                path=f"src/file_{i}.py",
                filename=f"file_{i}.py",
                extension=".py",
                size_bytes=100,
                language="Python",
                lines=10,
                is_sensitive=False
            )
            for i in range(200)
        ]
        
        mock_analyze.return_value = {
            "repository": "test/repo",
            "metadata": {},
            "scan_result": ScanResult(
                total_files=200,
                total_size_bytes=20000,
                files=many_files,
                languages={"Python": 200}
            )
        }
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/test/repo"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_files"] == 200
        assert data["files_returned"] == 100  # Limited to 100
        assert data["note"] is not None
        assert "Showing first 100 files out of 200" in data["note"]
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_invalid_url(self, mock_analyze):
        """Test that invalid GitHub URL returns 400."""
        mock_analyze.side_effect = InvalidRepositoryURLError("Invalid URL")
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "not-a-valid-url"}
        )
        
        assert response.status_code == 400
        assert "detail" in response.json()
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_repository_not_found(self, mock_analyze):
        """Test that non-existent repository returns 404."""
        mock_analyze.side_effect = RepositoryNotFoundError("Not found")
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/nonexistent/repository"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_repository_too_large(self, mock_analyze):
        """Test that oversized repository returns 413."""
        mock_analyze.side_effect = DownloadTooLargeError(
            "Repository exceeds maximum size"
        )
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/huge/repository"}
        )
        
        assert response.status_code == 413
        assert "exceeds" in response.json()["detail"].lower()
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_too_many_files(self, mock_analyze):
        """Test that repository with too many files returns 413."""
        mock_analyze.side_effect = TooManyFilesError(
            "Repository contains more than 10000 files"
        )
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/huge/repository"}
        )
        
        assert response.status_code == 413
        assert "files" in response.json()["detail"].lower()
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_unsafe_zip_archive(self, mock_analyze):
        """Test that unsafe ZIP archive returns 400."""
        mock_analyze.side_effect = UnsafeZipError(
            "ZIP contains unsafe paths"
        )
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/malicious/repository"}
        )
        
        assert response.status_code == 400
        assert "unsafe" in response.json()["detail"].lower()
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_invalid_zip_archive(self, mock_analyze):
        """Test that invalid ZIP archive returns 400."""
        mock_analyze.side_effect = InvalidZipError(
            "Corrupted ZIP file"
        )
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/broken/repository"}
        )
        
        assert response.status_code == 400
        assert "Invalid or unsafe" in response.json()["detail"]
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_download_error(self, mock_analyze):
        """Test that download errors return 500."""
        mock_analyze.side_effect = DownloadError(
            "Failed to download repository"
        )
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/test/repository"}
        )
        
        assert response.status_code == 500
        assert "GitHub" in response.json()["detail"]
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_github_api_error(self, mock_analyze):
        """Test that GitHub API errors return 500."""
        mock_analyze.side_effect = GitHubAPIError(
            "GitHub API is unavailable"
        )
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/test/repository"}
        )
        
        assert response.status_code == 500
        assert "GitHub" in response.json()["detail"]
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_unexpected_error(self, mock_analyze):
        """Test that unexpected errors return 500 without exposing details."""
        mock_analyze.side_effect = Exception("Internal server error")
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/test/repository"}
        )
        
        assert response.status_code == 500
        # Should not expose the actual exception message
        assert "unexpected error" in response.json()["detail"].lower()
        assert "Internal server error" not in response.json()["detail"]


class TestFileInfoSchema:
    """Tests for FileInfo response schema."""
    
    @patch('app.services.analysis_service.RepositoryAnalysisService.analyze_repository')
    def test_file_info_includes_all_fields(self, mock_analyze, mock_analysis_result):
        """Test that FileInfo includes all required fields."""
        mock_analyze.return_value = mock_analysis_result
        
        response = client.post(
            "/api/repositories/analyze",
            json={"url": "https://github.com/facebook/react"}
        )
        
        assert response.status_code == 200
        files = response.json()["files"]
        
        assert len(files) > 0
        file_info = files[0]
        
        assert "path" in file_info
        assert "filename" in file_info
        assert "extension" in file_info
        assert "size_bytes" in file_info
        assert "language" in file_info
        assert "lines" in file_info
        assert "is_sensitive" in file_info
