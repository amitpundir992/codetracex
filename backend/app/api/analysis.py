"""
API endpoint for repository analysis.

This module provides the Phase 2, Phase 3, and Phase 4 endpoint for analyzing GitHub repositories.
It coordinates downloading, extracting, scanning, static code analysis, and database persistence.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.schemas.repository import RepositoryRequest
from app.schemas.analysis import (
    RepositoryAnalysisResponse,
    FileInfo,
    Symbol,
    Import,
    Call
)
from app.services.analysis_service import RepositoryAnalysisService
from app.services.repository_service import InvalidRepositoryURLError
from app.services.github_service import GitHubAPIError, RepositoryNotFoundError
from app.services.download_service import DownloadTooLargeError, DownloadError
from app.services.scanner_service import TooManyFilesError
from app.utils.zip_utils import UnsafeZipError, InvalidZipError
from app.db import get_db


router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.post("/analyze", response_model=RepositoryAnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_repository(request: RepositoryRequest, db: Session = Depends(get_db)):
    """
    Analyze a GitHub repository.
    
    This endpoint performs a complete analysis of a GitHub repository:
    1. Validates the repository URL
    2. Downloads the repository archive (without .git history)
    3. Extracts the archive safely with path traversal protection
    4. Scans all files and collects metadata (Phase 2)
    5. Performs static code analysis on source files (Phase 3)
    6. Persists results to PostgreSQL database (Phase 4)
    7. Returns file statistics, language distribution, and code symbols
    8. Automatically cleans up temporary files
    
    The repository is downloaded into a temporary workspace and deleted
    after analysis. Structured intelligence is persisted to PostgreSQL.
    
    **Phase 3: Static Code Analysis**
    - Extracts functions, classes, methods from Python, JavaScript, TypeScript
    - Identifies import statements and dependencies
    - Maps function calls (syntactically)
    - Uses Python AST for .py files
    - Uses Tree-sitter for .js, .jsx, .ts, .tsx files
    - Never executes repository code (security)
    
    **Phase 4: PostgreSQL Persistence**
    - Repository metadata saved to database
    - Analysis run created with unique ID
    - Files, symbols, imports, calls persisted
    - Relationships between symbols tracked
    - Transaction-based persistence (all-or-nothing)
    
    **Size Limits:**
    - Maximum repository download size: configured in MAX_REPOSITORY_SIZE_MB
    - Maximum files to scan: configured in MAX_REPOSITORY_FILES
    
    **Security:**
    - ZIP archives are validated for path traversal attacks
    - Binary files are automatically skipped
    - Sensitive files (.env, credentials) are flagged but not exposed
    - Source code is parsed but never executed
    
    Args:
        request: Repository request containing the GitHub URL
        db: Database session (injected by FastAPI)
        
    Returns:
        Repository analysis results including:
        - Total file count and size
        - Language distribution
        - List of scanned files with metadata
        - Static analysis summary (symbols, imports, calls)
        - Preview of extracted symbols
        - Analysis run ID (Phase 4)
        - Repository ID (Phase 4)
        
    Raises:
        400 Bad Request: Invalid GitHub URL
        404 Not Found: Repository doesn't exist on GitHub
        413 Payload Too Large: Repository exceeds size or file limits
        500 Internal Server Error: Other errors during processing
    """
    print(f"\n=== ENDPOINT CALLED ===\nAnalyzing: {request.url}\n")
    
    # Create analysis service with database session (Phase 4)
    analysis_service = RepositoryAnalysisService(db=db)
    
    try:
        # Perform the complete analysis workflow
        result = await analysis_service.analyze_repository(request.url)
        
        # Extract results
        repository = result["repository"]
        scan_result = result["scan_result"]
        static_analysis = result["static_analysis"]
        
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
        
        # Limit static analysis results for API response
        # Return preview of symbols (top 50), imports (top 50), calls (top 50)
        symbols_preview = static_analysis.all_symbols[:50]
        imports_preview = static_analysis.all_imports[:50]
        calls_preview = static_analysis.all_calls[:50]
        
        return RepositoryAnalysisResponse(
            repository=repository,
            status="completed",
            total_files=scan_result.total_files,
            total_size_bytes=scan_result.total_size_bytes,
            languages=scan_result.languages,
            files=files,
            files_returned=len(files),
            note=note,
            # Phase 3: Static analysis results
            analysis_summary=static_analysis.summary,
            symbols=symbols_preview,
            imports=imports_preview,
            calls=calls_preview
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
