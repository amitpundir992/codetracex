"""
Investigation API endpoints for Phase 16.

Provides repository investigation capabilities with:
- Intent-based evidence gathering
- Grounded answers with claims
- Follow-up question generation
- Conversation context support

Security:
    - Repository isolation enforced
    - Analysis run isolation enforced
    - Bounded inputs (max question length, max evidence)
    - Safe error handling
    - No credential exposure
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.investigation_service import InvestigationService
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.provider import LLMProviderError, LLMTimeoutError, LLMAuthenticationError
from app.schemas.investigation import (
    InvestigationRequest,
    InvestigationResponse,
    InsufficientEvidenceResponse
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


def get_investigation_service(db: Session = Depends(get_db)) -> InvestigationService:
    """
    Dependency to create investigation service with LLM provider.
    
    Returns:
        Configured InvestigationService
    """
    settings = get_settings()
    
    # Initialize LLM provider
    llm_provider = GeminiProvider(
        api_key=settings.GEMINI_API_KEY,
        model=settings.LLM_MODEL
    )
    
    return InvestigationService(db=db, llm_provider=llm_provider)


@router.post(
    "/repositories/{repository_id}/investigate",
    response_model=InvestigationResponse,
    status_code=status.HTTP_200_OK,
    summary="Investigate repository question",
    description="""
    Conduct an advanced repository investigation with grounded answers.
    
    This endpoint:
    - Classifies investigation intent
    - Gathers relevant evidence (hybrid search, graph, workflow, git)
    - Generates grounded answer with LLM reasoning
    - Provides claims with certainty levels (confirmed/inferred/uncertain)
    - Suggests follow-up investigation questions
    - Maintains lightweight conversation context
    
    The answer is grounded in repository evidence with full traceability.
    
    **Security:**
    - Repository isolation enforced (can only query specified repository)
    - Analysis run isolation enforced (if specified)
    - Bounded inputs to prevent resource exhaustion
    - Safe error handling without credential exposure
    
    **Evidence Sources:**
    - Hybrid semantic + keyword search
    - Graph relationships (if include_graph=true)
    - Workflow analysis (if include_workflow=true)
    - Git history (if include_git_history=true)
    
    **Conversation Context:**
    - Supports lightweight contextual references ("that function", "this endpoint")
    - Maintains last N symbols/files/endpoints for reference
    - No persistent chat history (stateless per request)
    
    **Examples:**
    ```
    {
      "question": "How does authentication work?",
      "max_evidence": 10,
      "include_graph": true,
      "include_workflow": true,
      "include_git_history": false
    }
    ```
    
    **Response includes:**
    - Grounded answer with certainty levels
    - Individual claims with evidence citations
    - Retrieved evidence with source traceability
    - Explicit limitations when evidence is missing
    - Suggested follow-up questions
    - Updated conversation context
    """
)
async def investigate_repository(
    repository_id: UUID,
    request: InvestigationRequest,
    investigation_service: InvestigationService = Depends(get_investigation_service)
) -> InvestigationResponse:
    """
    Investigate a repository question with grounded reasoning.
    
    Args:
        repository_id: Repository to investigate
        request: Investigation request
        investigation_service: Investigation service dependency
    
    Returns:
        Investigation response with answer, claims, evidence, follow-ups
    
    Raises:
        HTTPException 404: Repository or analysis run not found
        HTTPException 400: Invalid request
        HTTPException 500: Internal error
    """
    try:
        logger.info(f"Investigation request for repository {repository_id}: {request.question}")
        
        response = await investigation_service.investigate(
            repository_id=repository_id,
            question=request.question,
            analysis_run_id=request.analysis_run_id,
            conversation_context=request.conversation_context,
            max_evidence=request.max_evidence or 10,
            include_graph=request.include_graph if request.include_graph is not None else True,
            include_workflow=request.include_workflow if request.include_workflow is not None else True,
            include_git_history=request.include_git_history or False
        )
        
        logger.info(f"Investigation complete: {len(response.evidence)} evidence, {len(response.claims)} claims")
        
        return response
    
    except ValueError as e:
        # Repository or analysis run not found
        logger.warning(f"Investigation validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    except LLMAuthenticationError as e:
        # LLM API key invalid
        logger.error(f"LLM authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM service authentication failed"
        )
    
    except LLMTimeoutError as e:
        # LLM timeout
        logger.error(f"LLM timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM service timeout"
        )
    
    except LLMProviderError as e:
        # Other LLM errors
        logger.error(f"LLM provider error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM service error"
        )
    
    except Exception as e:
        # Unexpected errors
        logger.error(f"Investigation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Investigation failed"
        )


@router.get(
    "/repositories/{repository_id}/investigation-info",
    summary="Get investigation information",
    description="""
    Get information about investigation capabilities for a repository.
    
    Returns:
    - Whether repository has completed analysis
    - Available evidence sources
    - Supported investigation intents
    """
)
async def get_investigation_info(
    repository_id: UUID,
    db: Session = Depends(get_db)
) -> dict:
    """
    Get investigation capabilities for a repository.
    
    Args:
        repository_id: Repository to check
        db: Database session
    
    Returns:
        Investigation info
    
    Raises:
        HTTPException 404: Repository not found
    """
    from app.db.models import Repository, AnalysisRun
    from sqlalchemy import desc
    
    try:
        # Check repository exists
        repository = db.query(Repository).filter(
            Repository.id == repository_id
        ).first()
        
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository {repository_id} not found"
            )
        
        # Check for completed analysis
        latest_analysis = db.query(AnalysisRun).filter(
            AnalysisRun.repository_id == repository_id,
            AnalysisRun.status == "completed"
        ).order_by(desc(AnalysisRun.completed_at)).first()
        
        has_analysis = latest_analysis is not None
        
        # Count evidence sources
        evidence_sources = {
            "hybrid_search": has_analysis,
            "graph_relationships": has_analysis,
            "workflow_analysis": has_analysis,
            "git_history": False  # Not yet fully implemented
        }
        
        return {
            "repository_id": str(repository_id),
            "repository_name": repository.name,
            "has_completed_analysis": has_analysis,
            "latest_analysis_id": str(latest_analysis.id) if latest_analysis else None,
            "evidence_sources": evidence_sources,
            "supported_intents": [
                "general_repository_question",
                "symbol_explanation",
                "api_explanation",
                "workflow_explanation",
                "dependency_question",
                "impact_question",
                "history_question",
                "architecture_question",
                "database_question"
            ],
            "conversation_context_supported": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get investigation info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve investigation information"
        )
