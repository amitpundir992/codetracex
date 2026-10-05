"""
API endpoints for Phase 18: Pull Request & Change Intelligence.

This module provides REST API endpoints for analyzing code changes,
pull requests, and commit ranges.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Repository
from app.schemas.change_analysis import (
    ChangeAnalysisRequest,
    ChangeAnalysisResponse,
    InsufficientEvidenceResponse,
    ChangeSummaryMetadata,
    ChangeInputType,
    PRMetadata
)
from app.services.github_service import GitHubService, GitHubAPIError, RepositoryNotFoundError
from app.services.change_impact_service import ChangeImpactService
from app.services.change_prompt_builder import ChangePromptBuilder
from app.services.llm.llm_service import LLMService
from app.services.llm.llm_service import LLMProviderError
from app.core.config import get_settings
from app.middleware.error_handlers import SafeAPIError

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()


def _get_llm_service() -> Optional[LLMService]:
    """
    Get LLM service if configured.
    
    Returns:
        LLMService instance or None if not configured
    """
    try:
        from app.services.llm.gemini_provider import GeminiProvider
        
        if not settings.GEMINI_API_KEY:
            return None
        
        provider = GeminiProvider(api_key=settings.GEMINI_API_KEY)
        return LLMService(provider=provider)
    except Exception as e:
        logger.warning(f"Failed to initialize LLM service: {e}")
        return None


def _validate_input_mode(request: ChangeAnalysisRequest) -> ChangeInputType:
    """
    Validate that exactly one input mode is provided.
    
    Args:
        request: Change analysis request
        
    Returns:
        Detected input type
        
    Raises:
        HTTPException: If validation fails
    """
    modes_provided = sum([
        request.pull_request_number is not None,
        (request.base_sha is not None and request.head_sha is not None),
        request.commit_sha is not None
    ])
    
    if modes_provided == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide pull_request_number, base_sha+head_sha, or commit_sha"
        )
    
    if modes_provided > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide only one input mode: pull_request_number OR base_sha+head_sha OR commit_sha"
        )
    
    if request.pull_request_number is not None:
        return ChangeInputType.PULL_REQUEST
    elif request.base_sha and request.head_sha:
        return ChangeInputType.COMMIT_RANGE
    else:
        return ChangeInputType.SINGLE_COMMIT


async def _get_pr_metadata_if_available(
    repository: Repository,
    pr_number: Optional[int]
) -> Optional[PRMetadata]:
    """
    Fetch PR metadata from GitHub if PR number provided.
    
    Args:
        repository: Repository database object
        pr_number: Optional PR number
        
    Returns:
        PRMetadata or None if not applicable or failed
    """
    if not pr_number:
        return None
    
    try:
        github_service = GitHubService()
        
        # Parse owner and repo name from full_name
        if not repository.full_name or '/' not in repository.full_name:
            logger.warning(f"Invalid repository full_name: {repository.full_name}")
            return None
        
        owner, repo_name = repository.full_name.split('/', 1)
        
        # Fetch PR metadata
        pr_data = await github_service.get_pull_request(owner, repo_name, pr_number)
        
        return PRMetadata(
            number=pr_data['number'],
            title=pr_data['title'],
            body=pr_data.get('body', ''),
            author=pr_data['author'],
            state=pr_data['state'],
            merged=pr_data['merged'],
            base_ref=pr_data['base_ref'],
            head_ref=pr_data['head_ref'],
            created_at=pr_data.get('created_at')
        )
    
    except RepositoryNotFoundError:
        logger.warning(f"PR #{pr_number} not found in {repository.full_name}")
        return None
    except GitHubAPIError as e:
        logger.warning(f"Failed to fetch PR metadata: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching PR metadata: {e}")
        return None


@router.post(
    "/repositories/{repository_id}/change-analysis",
    response_model=ChangeAnalysisResponse,
    responses={
        200: {"model": ChangeAnalysisResponse},
        400: {"description": "Invalid request"},
        404: {"description": "Repository not found"},
        500: {"description": "Internal server error"}
    },
    tags=["change_analysis"]
)
async def analyze_change(
    repository_id: UUID,
    request: ChangeAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze a pull request or commit range for changes and impact.
    
    This endpoint performs comprehensive change analysis including:
    - File and symbol change detection
    - API impact analysis
    - Workflow impact analysis
    - Dependency graph traversal
    - Test relevance detection
    - Risk assessment
    - LLM-based change explanation (if configured)
    
    **Input Modes:**
    
    1. Pull Request: Provide `pull_request_number`
    2. Commit Range: Provide `base_sha` + `head_sha`
    3. Single Commit: Provide `commit_sha`
    
    **Requirements:**
    
    - Repository must exist and have been analyzed
    - Commits must exist in Git history
    - For PR mode: PR must be publicly accessible
    
    **Limitations:**
    
    - Symbol modification detection has uncertainty
    - Graph traversal is bounded (max depth: 10)
    - Results may be truncated for large changes
    - No authentication (public repositories only)
    
    **Security:**
    
    - Repository isolation enforced
    - No cross-repository contamination
    - Safe error handling
    - No secret exposure
    """
    logger.info(
        f"Change analysis request for repository {repository_id}"
    )
    
    try:
        # Validate input mode
        input_type = _validate_input_mode(request)
        
        # Validate repository exists
        repository = db.query(Repository).filter(
            Repository.id == repository_id
        ).first()
        
        if not repository:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository {repository_id} not found"
            )
        
        # Determine base and head SHAs based on input mode
        base_sha = None
        head_sha = None
        commit_sha = None
        pr_metadata = None
        
        if input_type == ChangeInputType.PULL_REQUEST:
            # Fetch PR metadata to get base/head SHAs
            pr_metadata = await _get_pr_metadata_if_available(
                repository,
                request.pull_request_number
            )
            
            if not pr_metadata:
                raise SafeAPIError(
                    message=f"Failed to fetch PR #{request.pull_request_number}. "
                            "Ensure it's a public PR in a public repository.",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            base_sha = pr_metadata.base_ref  # Use branch refs for now
            head_sha = pr_metadata.head_ref
            
            # Note: In production, we'd map branch refs to commit SHAs
            # For now, we'll try to use the SHAs from PR metadata if available
            # This is a simplified implementation
            logger.warning(
                "PR mode currently uses branch refs. Full SHA resolution not implemented."
            )
        
        elif input_type == ChangeInputType.COMMIT_RANGE:
            base_sha = request.base_sha
            head_sha = request.head_sha
        
        else:  # SINGLE_COMMIT
            commit_sha = request.commit_sha
        
        # Initialize services
        change_impact_service = ChangeImpactService(db)
        prompt_builder = ChangePromptBuilder()
        llm_service = _get_llm_service()
        
        # Perform change impact analysis
        try:
            impact_data = change_impact_service.analyze_change_impact(
                repository_id=repository_id,
                base_sha=base_sha,
                head_sha=head_sha,
                commit_sha=commit_sha,
                max_depth=request.max_depth,
                include_tests=request.include_tests,
                include_workflows=request.include_workflows
            )
        except ValueError as e:
            raise SafeAPIError(
                message=f"Change detection failed: {str(e)}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Build metadata
        metadata = ChangeSummaryMetadata(
            input_type=input_type,
            base_sha=impact_data['metadata']['base_sha'],
            head_sha=impact_data['metadata']['head_sha'],
            files_changed=impact_data['metadata']['files_changed'],
            symbols_changed=len(impact_data['changed_symbols']),
            insertions=impact_data['metadata']['insertions'],
            deletions=impact_data['metadata']['deletions']
        )
        
        # Generate LLM explanation if available
        summary = ""
        technical_changes = ""
        reviewer_attention = ""
        testing_considerations = ""
        potential_impact = ""
        uncertainty = ""
        
        if llm_service:
            try:
                # Build grounded prompt
                prompt = prompt_builder.build_change_prompt(
                    pr_metadata=pr_metadata,
                    changed_files=impact_data['changed_files'],
                    changed_symbols=impact_data['changed_symbols'],
                    affected_endpoints=impact_data['affected_endpoints'],
                    affected_workflows=impact_data['affected_workflows'],
                    dependency_impact=impact_data['dependency_impact'],
                    relevant_tests=impact_data['relevant_tests'],
                    risk=impact_data['risk']
                )
                
                # Generate LLM response
                from app.services.llm.provider import LLMRequest
                
                llm_request = LLMRequest(
                    prompt=prompt,
                    max_tokens=2000,
                    temperature=0.3
                )
                
                llm_response = llm_service.provider.generate(llm_request)
                
                if not llm_response.is_empty():
                    # Parse LLM response
                    # For now, use the full response as summary
                    # In production, we'd parse structured sections
                    full_response = llm_response.content
                    
                    # Simple section extraction
                    sections = {
                        'summary': '',
                        'technical_changes': '',
                        'reviewer_attention': '',
                        'testing_considerations': '',
                        'potential_impact': '',
                        'uncertainty': ''
                    }
                    
                    # Parse sections from markdown-style headings
                    current_section = None
                    for line in full_response.split('\n'):
                        line_lower = line.lower().strip()
                        if line_lower.startswith('### summary'):
                            current_section = 'summary'
                        elif line_lower.startswith('### technical changes'):
                            current_section = 'technical_changes'
                        elif line_lower.startswith('### reviewer attention'):
                            current_section = 'reviewer_attention'
                        elif line_lower.startswith('### testing considerations'):
                            current_section = 'testing_considerations'
                        elif line_lower.startswith('### potential impact'):
                            current_section = 'potential_impact'
                        elif line_lower.startswith('### uncertainty'):
                            current_section = 'uncertainty'
                        elif current_section and line.strip():
                            sections[current_section] += line + '\n'
                    
                    summary = sections['summary'].strip()
                    technical_changes = sections['technical_changes'].strip()
                    reviewer_attention = sections['reviewer_attention'].strip()
                    testing_considerations = sections['testing_considerations'].strip()
                    potential_impact = sections['potential_impact'].strip()
                    uncertainty = sections['uncertainty'].strip()
                    
                    logger.info("LLM change explanation generated successfully")
            
            except LLMProviderError as e:
                logger.warning(f"LLM generation failed: {e}")
                uncertainty = "LLM-based explanation unavailable due to generation error."
            except Exception as e:
                logger.error(f"Unexpected error in LLM generation: {e}")
                uncertainty = "LLM-based explanation unavailable due to unexpected error."
        else:
            logger.info("LLM service not configured, skipping explanation generation")
            uncertainty = "LLM-based explanation not available (LLM not configured)."
        
        # Build response
        response = ChangeAnalysisResponse(
            metadata=metadata,
            pr_metadata=pr_metadata,
            files=impact_data['changed_files'],
            symbols=impact_data['changed_symbols'],
            affected_apis=impact_data['affected_endpoints'],
            affected_workflows=impact_data['affected_workflows'],
            dependency_impact=impact_data['dependency_impact'],
            relevant_tests=impact_data['relevant_tests'],
            risk=impact_data['risk'],
            evidence=impact_data['evidence'],
            summary=summary,
            technical_changes=technical_changes,
            reviewer_attention=reviewer_attention,
            testing_considerations=testing_considerations,
            potential_impact=potential_impact,
            uncertainty=uncertainty
        )
        
        logger.info(
            f"Change analysis complete: {metadata.files_changed} files, "
            f"{metadata.symbols_changed} symbols, risk={impact_data['risk'].risk_level}"
        )
        
        return response
    
    except HTTPException:
        raise
    except SafeAPIError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in change analysis: {e}", exc_info=True)
        raise SafeAPIError(
            message="An unexpected error occurred during change analysis",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
