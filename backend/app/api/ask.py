"""
API endpoints for Phase 12: LLM Reasoning & Grounded Explanations.

These endpoints expose the Ask functionality that generates grounded answers
to user questions about repositories using LLM.

Architecture:
    User Question
        ↓
    RAGContextService (retrieve evidence)
        ↓
    PromptBuilder (construct prompt)
        ↓
    LLMProvider (generate answer)
        ↓
    Citation validation
        ↓
    Grounded Answer

Security:
    - Repository isolation enforced
    - Analysis run isolation supported
    - No API key exposure
    - Repository content treated as untrusted data
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Body
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Repository
from app.services.llm import (
    LLMService,
    GeminiProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMAuthenticationError,
    LLMRateLimitError,
)
from app.schemas.llm import (
    AskRequest,
    AskResponse,
    GroundedAnswer,
)
from app.core.config import get_settings

router = APIRouter(prefix="/api/repositories", tags=["llm"])


def _get_llm_provider():
    """
    Get configured LLM provider.
    
    Returns:
        Configured LLM provider instance
        
    Raises:
        HTTPException: If LLM is not configured or provider unavailable
    """
    settings = get_settings()
    
    # Check if LLM is configured
    if not settings.LLM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is not configured. Please set LLM_API_KEY in environment."
        )
    
    # Create provider based on configuration
    if settings.LLM_PROVIDER.lower() == "gemini":
        try:
            return GeminiProvider(
                api_key=settings.LLM_API_KEY,
                model=settings.LLM_MODEL,
            )
        except LLMProviderError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to initialize LLM provider: {str(e)}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"LLM provider '{settings.LLM_PROVIDER}' is not implemented"
        )


@router.post("/{repository_id}/ask", response_model=AskResponse)
def ask_repository_question(
    repository_id: UUID,
    request: AskRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Ask a question about a repository and get a grounded answer.
    
    This endpoint orchestrates the complete Phase 12 LLM reasoning pipeline:
    
    1. **RAG Context**: Retrieves relevant evidence using hybrid search
    2. **Prompt Construction**: Builds structured prompt with grounding instructions
    3. **LLM Generation**: Generates answer using configured LLM provider
    4. **Citation Validation**: Validates citations against supplied evidence
    5. **Answer Packaging**: Returns grounded answer with citations
    
    **What This Endpoint Returns:**
    - Grounded answer based on repository evidence
    - Citations referencing actual source code
    - Confidence indicators
    - Insufficient evidence handling
    
    **What This Endpoint Does NOT Return:**
    - Unsupported claims without evidence
    - Fabricated code or file paths
    - Opinions or recommendations
    
    **Repository Isolation:**
    - Only searches the specified repository
    - No cross-repository contamination
    - Optional analysis run filtering
    
    **Security:**
    - API keys never exposed to client
    - Repository content treated as untrusted data
    - Bounded resource usage (timeouts, limits)
    
    **Error Handling:**
    - LLM timeout (503)
    - LLM authentication failure (503)
    - LLM rate limit (429)
    - Repository not found (404)
    - No analysis runs (404)
    - Invalid request (422)
    
    Args:
        repository_id: UUID of the repository to query
        request: Ask request with question and retrieval parameters
        db: Database session (injected)
        
    Returns:
        Grounded answer with citations and metadata
        
    Raises:
        HTTPException 404: Repository not found or no analysis runs
        HTTPException 422: Invalid request parameters
        HTTPException 429: LLM rate limit exceeded
        HTTPException 503: LLM service unavailable or failed
    """
    # 1. Validate repository exists
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # 2. Parse analysis_run_id if provided
    analysis_run_id_uuid: Optional[UUID] = None
    if request.analysis_run_id:
        try:
            analysis_run_id_uuid = UUID(request.analysis_run_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid analysis_run_id format: {request.analysis_run_id}"
            )
    
    # 3. Get LLM provider
    try:
        llm_provider = _get_llm_provider()
    except HTTPException:
        raise
    
    # 4. Initialize LLM service
    llm_service = LLMService(db, llm_provider)
    
    # 5. Generate grounded answer
    try:
        grounded_answer = llm_service.generate_answer(
            repository_id=repository_id,
            question=request.question,
            top_k=request.top_k,
            semantic_weight=request.semantic_weight,
            keyword_weight=request.keyword_weight,
            analysis_run_id=analysis_run_id_uuid,
        )
    except LLMTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"LLM request timed out: {str(e)}"
        )
    except LLMAuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM authentication failed: {str(e)}"
        )
    except LLMRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"LLM rate limit exceeded: {str(e)}"
        )
    except LLMProviderError as e:
        # Generic error message to avoid leaking sensitive information
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service failed. Please check configuration and try again."
        )
    except ValueError as e:
        # Repository or analysis run validation errors
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        # Unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
    
    # 6. Return grounded answer
    return AskResponse(answer=grounded_answer)
