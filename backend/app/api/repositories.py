"""
API endpoints for repository operations.
"""
from fastapi import APIRouter, HTTPException, status
from app.schemas.repository import RepositoryRequest, RepositoryResponse
from app.services.repository_service import (
    RepositoryService,
    InvalidRepositoryURLError
)
from app.services.github_service import (
    GitHubAPIError,
    RepositoryNotFoundError
)

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_200_OK)
async def ingest_repository(request: RepositoryRequest):
    """
    Ingest a GitHub repository and retrieve its metadata.
    
    This endpoint accepts a GitHub repository URL, validates it,
    and retrieves basic metadata from the GitHub API.
    
    Args:
        request: Repository request containing the GitHub URL
        
    Returns:
        Repository metadata including name, owner, description, etc.
        
    Raises:
        400 Bad Request: If the URL is invalid
        404 Not Found: If the repository doesn't exist on GitHub
        500 Internal Server Error: If there's an error communicating with GitHub
    """
    repository_service = RepositoryService()
    
    try:
        metadata = await repository_service.get_repository_metadata(request.url)
        return RepositoryResponse(**metadata)
        
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
        
    except GitHubAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error communicating with GitHub API"
        )
        
    except Exception as e:
        # Catch any unexpected errors without exposing internal details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
