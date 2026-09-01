"""
Repository analysis service.

This service orchestrates the complete repository analysis workflow:
1. Validate repository URL
2. Get repository metadata
3. Download repository archive
4. Extract archive safely
5. Scan files and collect metadata
6. Clean up temporary files

This is the main entry point for Phase 2 functionality.
"""
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

from app.core.config import get_settings
from app.services.repository_service import RepositoryService
from app.services.download_service import RepositoryDownloadService
from app.services.scanner_service import FileScannerService
from app.utils.zip_utils import safe_extract, find_repository_root


class RepositoryAnalysisService:
    """Service for analyzing GitHub repositories."""
    
    def __init__(self):
        """Initialize the analysis service with required dependencies."""
        settings = get_settings()
        
        self.repository_service = RepositoryService()
        self.download_service = RepositoryDownloadService(
            max_size_bytes=settings.max_repository_size_bytes
        )
        self.scanner_service = FileScannerService(
            max_files=settings.MAX_REPOSITORY_FILES
        )
    
    async def analyze_repository(self, url: str) -> Dict[str, Any]:
        """
        Analyze a GitHub repository from start to finish.
        
        This method orchestrates the complete workflow:
        1. Parse and validate the GitHub URL
        2. Retrieve repository metadata from GitHub API
        3. Create a temporary workspace
        4. Download the repository archive
        5. Extract the archive safely
        6. Find the repository root
        7. Scan all files and collect metadata
        8. Clean up temporary files (even if errors occur)
        9. Return structured analysis results
        
        The temporary workspace is automatically cleaned up using a context manager,
        ensuring cleanup happens even if an exception occurs during processing.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Dictionary containing:
                - repository: Repository identifier (owner/name)
                - metadata: Repository metadata from GitHub
                - scan_result: File scanning results with metadata
                
        Raises:
            InvalidRepositoryURLError: If URL is invalid
            RepositoryNotFoundError: If repository doesn't exist
            DownloadTooLargeError: If repository exceeds size limit
            DownloadError: If download fails
            UnsafeZipError: If archive contains unsafe paths
            InvalidZipError: If archive is corrupted
            TooManyFilesError: If repository exceeds file limit
        """
        # Step 1 & 2: Validate URL and get repository metadata
        metadata = await self.repository_service.get_repository_metadata(url)
        
        owner = metadata["owner"]
        repository_name = metadata["name"]
        default_branch = metadata["default_branch"]
        repository_id = f"{owner}/{repository_name}"
        
        # Step 3-8: Use temporary directory for download and extraction
        # The 'with' statement ensures cleanup happens automatically
        with tempfile.TemporaryDirectory(prefix="codetracex_") as temp_dir:
            temp_path = Path(temp_dir)
            
            # Step 4: Download repository archive
            archive_path = await self.download_service.download_repository(
                owner=owner,
                repository=repository_name,
                branch=default_branch,
                destination=temp_path
            )
            
            # Step 5: Extract archive safely
            extract_path = temp_path / "extracted"
            safe_extract(archive_path, extract_path)
            
            # Step 6: Find repository root
            repo_root = find_repository_root(extract_path)
            
            # Step 7: Scan files
            scan_result = self.scanner_service.scan_directory(repo_root)
        
        # Temporary directory is automatically deleted here
        
        # Step 9: Return structured results
        return {
            "repository": repository_id,
            "metadata": metadata,
            "scan_result": scan_result
        }
