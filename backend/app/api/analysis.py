"""
API endpoint for repository analysis.

This module provides the Phase 2 endpoint for analyzing GitHub repositories.
It coordinates downloading, extracting, and scanning repositories to collect
file metadata.
"""
from fastapi import APIRouter, HTTPException, status

from app.schemas.repository import RepositoryRequest
from app.schemas.analysis import RepositoryAnalysisResponse, FileInfo
from app.services.analysis_service import RepositoryAnalysisService
from app.services.repository_service import InvalidRepositoryURLError
from app.services.github_service import GitHubAPIError, RepositoryNotFoundError
from app.services.download_service import DownloadTooLargeError, DownloadError
from app.services.scanner_service import TooManyFilesError
from app.utils.zip_utils import UnsafeZipError, InvalidZipError


router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.post("/analyze", response_model=RepositoryAnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_repository(request: RepositoryRequest):
    """
    Analyze a GitHub repository.
    
    This endpoint performs a complete analysis of a GitHub repository:
    1. Validates the repository URL
    2. Downloads the repository archive (without .git history)
    3. Extracts the archive safely with path traversal protection
    4. Scans all files and collects metadata
    5. Returns file statistics and language distribution
    6. Automatically cleans up temporary files
    
    The repository is downloaded into a temporary workspace and deleted
    after analysis. No repository data is permanently stored on the server.
    
    **Size Limits:**
    - Maximum repository download size: configured in MAX_REPOSITORY_SIZE_MB
    - Maximum files to scan: configured in MAX_REPOSITORY_FILES
    
    **Security:**
    - ZIP archives are validated for path traversal attacks
    - Binary files are automatically skipped
    - Sensitive files (.env, credentials) are flagged but not exposed
    
    Args:
        request: Repository request containing the GitHub URL
        
    Returns:
        Repository analysis results including:
        - Total file count and size
        - Language distribution
        - List of scanned files with metadata
        
    Raises:
        400 Bad Request: Invalid GitHub URL
        404 Not Found: Repository doesn't exist on GitHub
        413 Payload Too Large: Repository exceeds size or file limits
        500 Internal Server Error: Other errors during processing
    """
    analysis_service = RepositoryAnalysisService()
    
    try:
        # Perform the complete analysis workflow
        result = await analysis_service.analyze_repository(request.url)
        
        # Extract results
        repository = result["repository"]
        scan_result = result["scan_result"]
        
        # Convert file metadata to response format
        # Limit the number of files returned in the response
        # (Full scan happens, but API returns a subset for practicality)
        files_to_return = analysis_service.scanner_service.get_top_files(
            scan_result,
            limit=100
        )
        
        files = [
            FileInfo(
                path=f.path,
                filename=f.filename,
                extension=f.extension,
                size_bytes=f.size_bytes,
                language=f.language,
                lines=f.lines,
                is_sensitive=f.is_sensitive
            )
            for f in files_to_return
        ]
        
        # Create note if we're returning fewer files than scanned
        note = None
        if len(files) < scan_result.total_files:
            note = f"Showing first {len(files)} files out of {scan_result.total_files} total files"
        
        return RepositoryAnalysisResponse(
            repository=repository,
            status="completed",
            total_files=scan_result.total_files,
            total_size_bytes=scan_result.total_size_bytes,
            languages=scan_result.languages,
            files=files,
            files_returned=len(files),
            note=note
        )
        
    except InvalidRepositoryURLError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    except RepositoryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub repository not found"
        )
        
    except DownloadTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e)
        )
        
    except TooManyFilesError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e)
        )
        
    except (UnsafeZipError, InvalidZipError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unsafe repository archive: {str(e)}"
        )
        
    except (DownloadError, GitHubAPIError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error communicating with GitHub"
        )
        
    except Exception as e:
        # Catch any unexpected errors without exposing internal details
        # Log the error server-side for debugging
        print(f"Unexpected error during repository analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during repository analysis"
        )
