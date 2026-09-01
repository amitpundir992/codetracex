"""
Repository download service.

This service handles downloading GitHub repository archives using
streaming downloads with size limits to prevent resource exhaustion.
"""
import httpx
from pathlib import Path
from typing import Optional


class DownloadTooLargeError(Exception):
    """Exception raised when a download exceeds the maximum allowed size."""
    pass


class DownloadError(Exception):
    """Exception raised when there's an error downloading the repository."""
    pass


class RepositoryDownloadService:
    """Service for downloading GitHub repository archives."""
    
    # Chunk size for streaming downloads (1MB)
    CHUNK_SIZE = 1024 * 1024
    
    # Timeout for download requests (30 seconds)
    DOWNLOAD_TIMEOUT = 30.0
    
    def __init__(self, max_size_bytes: int):
        """
        Initialize the download service.
        
        Args:
            max_size_bytes: Maximum allowed download size in bytes
        """
        self.max_size_bytes = max_size_bytes
    
    def get_archive_url(self, owner: str, repository: str, branch: str) -> str:
        """
        Construct the GitHub archive download URL.
        
        GitHub provides ZIP archives of repositories at:
        https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip
        
        This downloads the repository at the specified branch without
        the .git directory or git history.
        
        Args:
            owner: Repository owner username
            repository: Repository name
            branch: Branch name (typically 'main' or 'master')
            
        Returns:
            Complete archive download URL
        """
        return f"https://github.com/{owner}/{repository}/archive/refs/heads/{branch}.zip"
    
    async def download_repository(
        self,
        owner: str,
        repository: str,
        branch: str,
        destination: Path
    ) -> Path:
        """
        Download a GitHub repository archive using streaming.
        
        This method:
        1. Constructs the GitHub archive URL
        2. Starts a streaming HTTP request
        3. Downloads the file in chunks
        4. Tracks total bytes downloaded
        5. Stops if the size limit is exceeded
        6. Saves the archive to the destination
        
        Why streaming?
        - Large repositories could consume excessive memory if loaded all at once
        - Streaming allows us to monitor download progress
        - We can abort early if the file is too large
        
        Args:
            owner: Repository owner
            repository: Repository name
            branch: Branch to download
            destination: Directory where the archive should be saved
            
        Returns:
            Path to the downloaded archive file
            
        Raises:
            DownloadTooLargeError: If the download exceeds max_size_bytes
            DownloadError: If there's an error downloading the repository
        """
        url = self.get_archive_url(owner, repository, branch)
        archive_path = destination / f"{repository}.zip"
        
        try:
            async with httpx.AsyncClient() as client:
                # Start streaming download with timeout
                async with client.stream(
                    "GET",
                    url,
                    follow_redirects=True,
                    timeout=self.DOWNLOAD_TIMEOUT
                ) as response:
                    # Check if the request was successful
                    if response.status_code == 404:
                        raise DownloadError(
                            f"Repository archive not found. Branch '{branch}' may not exist."
                        )
                    
                    if response.status_code != 200:
                        raise DownloadError(
                            f"Failed to download repository. HTTP status: {response.status_code}"
                        )
                    
                    # Check Content-Length header if available
                    content_length = response.headers.get("content-length")
                    if content_length:
                        size = int(content_length)
                        if size > self.max_size_bytes:
                            raise DownloadTooLargeError(
                                f"Repository archive size ({size} bytes) exceeds "
                                f"maximum allowed size ({self.max_size_bytes} bytes)"
                            )
                    
                    # Download the file in chunks
                    total_downloaded = 0
                    
                    with open(archive_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=self.CHUNK_SIZE):
                            # Write chunk to file
                            f.write(chunk)
                            
                            # Track total bytes downloaded
                            total_downloaded += len(chunk)
                            
                            # Check if we've exceeded the size limit
                            if total_downloaded > self.max_size_bytes:
                                # Delete the partial file
                                archive_path.unlink(missing_ok=True)
                                
                                raise DownloadTooLargeError(
                                    f"Repository archive exceeds maximum allowed size "
                                    f"of {self.max_size_bytes} bytes"
                                )
                    
                    return archive_path
                    
        except httpx.TimeoutException:
            raise DownloadError("Repository download timed out")
            
        except httpx.RequestError as e:
            raise DownloadError(f"Error downloading repository: {str(e)}")
            
        except DownloadTooLargeError:
            # Re-raise size limit errors
            raise
            
        except Exception as e:
            # Clean up partial download
            if archive_path.exists():
                archive_path.unlink(missing_ok=True)
            raise DownloadError(f"Unexpected error during download: {str(e)}")
