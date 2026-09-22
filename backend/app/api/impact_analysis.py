"""
API endpoints for Phase 13: AI Impact Analysis + Change Planning.

These endpoints expose impact analysis functionality that combines deterministic
static analysis with LLM-powered explanations and implementation planning.

Architecture:
    User Question
        ↓
    Target Identification (deterministic)
        ↓
    Impact Analysis (deterministic graph traversal)
        ↓
    Evidence Collection (graph + history + search)
        ↓
    LLM Reasoning (explanation + planning)
        ↓
    Grounded Impact Analysis + Implementation Plan

Security:
    - Repository isolation enforced
    - Analysis run isolation supported
    - No API key exposure
    - Repository content treated as untrusted data
    - No arbitrary code execution
    - No file modification
"""
from typing import Optional
from uuid import UUID
import logging

from fastapi import APIRouter, HTTPException, status, Depends, Body
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Repository, AnalysisRun
from app.services.target_identification_service import TargetIdentificationService
from app.services.impact_analysis_service import ImpactAnalysisService
from app.services.impact_prompt_builder import ImpactPromptBuilder
from app.services.llm import (
    LLMService,
    GeminiProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMAuthenticationError,
    LLMRateLimitError,
)
from app.schemas.impact_analysis import (
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    ImpactTarget,
    ImpactSummary,
    ImplementationPlan,
    ImplementationStep,
)
from app.core.config import get_settings

router = APIRouter(prefix="/api/repositories", tags=["impact-analysis"])
logger = logging.getLogger(__name__)


def _get_llm_provider():
    """
    Get configured LLM provider for impact analysis.
    
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


@router.post("/{repository_id}/impact-analysis", response_model=ImpactAnalysisResponse)
def analyze_change_impact(
    repository_id: UUID,
    request: ImpactAnalysisRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Analyze the impact of a potential change and generate an implementation plan.
    
    This endpoint orchestrates the complete Phase 13 impact analysis pipeline:
    1. Verify repository exists
    2. Identify target entity from question
    3. Perform deterministic impact analysis
    4. Collect additional evidence (history, code search)
    5. Generate LLM explanation and implementation plan
    6. Return grounded impact analysis
    
    Args:
        repository_id: Repository UUID
        request: Impact analysis request with question and optional target
        db: Database session
        
    Returns:
        Complete impact analysis with explanation and implementation plan
        
    Raises:
        HTTPException: Various error conditions
    """
    # Verify repository exists
    repository = db.query(Repository).filter(
        Repository.id == repository_id
    ).first()
    
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found"
        )
    
    # Verify analysis run if provided
    analysis_run_id_uuid: Optional[UUID] = None
    if request.analysis_run_id:
        try:
            analysis_run_id_uuid = UUID(request.analysis_run_id)
            
            analysis_run = db.query(AnalysisRun).filter(
                AnalysisRun.id == analysis_run_id_uuid,
                AnalysisRun.repository_id == repository_id
            ).first()
            
            if not analysis_run:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Analysis run {request.analysis_run_id} not found for repository {repository_id}"
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid analysis_run_id format"
            )
    
    # Initialize services
    target_service = TargetIdentificationService(db)
    impact_service = ImpactAnalysisService(db)
    prompt_builder = ImpactPromptBuilder()
    
    # Step 1: Identify target
    try:
        target_id_uuid: Optional[UUID] = None
        if request.target_id:
            try:
                target_id_uuid = UUID(request.target_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid target_id format"
                )
        
        target_result = target_service.identify_target_from_query(
            query=request.question,
            repository_id=repository_id,
            analysis_run_id=analysis_run_id_uuid,
            target_type=request.target_type,
            target_id=target_id_uuid
        )
        
        # Handle ambiguous or not found
        if target_result.status == "not_found":
            return ImpactAnalysisResponse(
                status="target_not_found",
                question=request.question,
                target=None,
                target_identification=target_result,
                summary=None,
                impacts=[],
                affected_files=[],
                affected_endpoints=[],
                affected_workflows=[],
                historical_evidence=[],
                explanation=None,
                implementation_plan=None,
                citations=[],
                confidence_note=target_result.message,
                truncation=None,
                analysis_run_id=analysis_run_id_uuid,
                repository_id=repository_id
            )
        
        if target_result.status == "ambiguous":
            return ImpactAnalysisResponse(
                status="ambiguous_target",
                question=request.question,
                target=None,
                target_identification=target_result,
                summary=None,
                impacts=[],
                affected_files=[],
                affected_endpoints=[],
                affected_workflows=[],
                historical_evidence=[],
                explanation=None,
                implementation_plan=None,
                citations=[],
                confidence_note=target_result.message,
                truncation=None,
                analysis_run_id=analysis_run_id_uuid,
                repository_id=repository_id
            )
        
        # Target found
        target = target_result.target
        
    except Exception as e:
        logger.error(f"Target identification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Target identification failed: {str(e)}"
        )
    
    # Step 2: Perform deterministic impact analysis
    try:
        if target.target_type == "symbol":
            impact_result = impact_service.analyze_symbol_impact(
                symbol_id=target.target_id,
                repository_id=repository_id,
                analysis_run_id=analysis_run_id_uuid,
                depth=request.depth
            )
        elif target.target_type == "file":
            impact_result = impact_service.analyze_file_impact(
                file_id=target.target_id,
                repository_id=repository_id,
                analysis_run_id=analysis_run_id_uuid,
                depth=request.depth
            )
        elif target.target_type == "api_endpoint":
            impact_result = impact_service.analyze_endpoint_impact(
                endpoint_id=target.target_id,
                repository_id=repository_id,
                analysis_run_id=analysis_run_id_uuid,
                depth=request.depth
            )
        else:
            raise ValueError(f"Unsupported target type: {target.target_type}")
        
        impacts = impact_result["impacts"]
        summary = impact_result["summary"]
        truncation = impact_result["truncation"]
        affected_files = impact_result["affected_files"]
        affected_endpoints = impact_result["affected_endpoints"]
        affected_workflows = impact_result["affected_workflows"]
        
    except Exception as e:
        logger.error(f"Impact analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impact analysis failed: {str(e)}"
        )
    
    # Step 3: Check if we have enough impact data
    if summary.total_impacts == 0:
        return ImpactAnalysisResponse(
            status="insufficient_evidence",
            question=request.question,
            target=target,
            target_identification=None,
            summary=summary,
            impacts=[],
            affected_files=affected_files,
            affected_endpoints=affected_endpoints,
            affected_workflows=affected_workflows,
            historical_evidence=[],
            explanation="No impacts were detected for this target. This could mean the target is not called or used by other code, or it may be at the leaf of the dependency graph.",
            implementation_plan=None,
            citations=[],
            confidence_note="Static analysis did not find any dependent code.",
            truncation=truncation,
            analysis_run_id=analysis_run_id_uuid,
            repository_id=repository_id
        )
    
    # Step 4: Collect additional evidence (optional - Git history)
    # For Phase 13, we'll skip Git history and code search to keep it focused
    # These can be added in future iterations
    historical_evidence = []
    code_snippets = []
    
    # Step 5: Generate LLM explanation and implementation plan
    try:
        # Build prompt
        system_prompt, user_prompt = prompt_builder.build_impact_prompt(
            question=request.question,
            target=target,
            impacts=impacts,
            summary=summary,
            truncation=truncation,
            affected_files=affected_files,
            affected_endpoints=affected_endpoints,
            affected_workflows=affected_workflows,
            historical_evidence=historical_evidence,
            code_snippets=code_snippets,
            include_implementation_plan=request.include_implementation_plan
        )
        
        # Get LLM provider
        llm_provider = _get_llm_provider()
        llm_service = LLMService(llm_provider)
        
        # Generate response
        llm_response = llm_service.generate_grounded_answer(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        
        # Parse LLM response
        # For now, treat entire response as explanation
        # In a more sophisticated version, we would parse structured output
        explanation = llm_response
        
        # Extract implementation plan if requested
        # For this version, we'll return a simple plan based on the impacts
        implementation_plan = None
        if request.include_implementation_plan:
            implementation_plan = _create_implementation_plan(
                target=target,
                impacts=impacts,
                affected_files=affected_files,
                affected_endpoints=affected_endpoints,
                summary=summary
            )
        
    except LLMAuthenticationError as e:
        logger.error(f"LLM authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="LLM authentication failed. Please check API key configuration."
        )
    except LLMRateLimitError as e:
        logger.error(f"LLM rate limit exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="LLM rate limit exceeded. Please try again later."
        )
    except LLMTimeoutError as e:
        logger.error(f"LLM request timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM request timed out. Please try again."
        )
    except LLMProviderError as e:
        logger.error(f"LLM provider error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during LLM generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate impact explanation: {str(e)}"
        )
    
    # Step 6: Return complete response
    return ImpactAnalysisResponse(
        status="success",
        question=request.question,
        target=target,
        target_identification=None,
        summary=summary,
        impacts=impacts,
        affected_files=affected_files,
        affected_endpoints=affected_endpoints,
        affected_workflows=affected_workflows,
        historical_evidence=historical_evidence,
        explanation=explanation,
        implementation_plan=implementation_plan,
        citations=[],  # TODO: Extract citations from LLM response
        confidence_note=None if not truncation.is_truncated else f"Analysis was truncated: {truncation.truncation_reason}",
        truncation=truncation,
        analysis_run_id=analysis_run_id_uuid,
        repository_id=repository_id
    )


def _create_implementation_plan(
    target: ImpactTarget,
    impacts: list,
    affected_files: list,
    affected_endpoints: list,
    summary: ImpactSummary
) -> ImplementationPlan:
    """
    Create a basic implementation plan from impact analysis.
    
    This is a simple version that creates steps based on deterministic impacts.
    The LLM will provide more detailed reasoning in the explanation.
    
    Args:
        target: Target entity
        impacts: List of impact items
        affected_files: List of affected files
        affected_endpoints: List of affected endpoints
        summary: Impact summary
        
    Returns:
        ImplementationPlan object
    """
    steps = []
    step_num = 1
    
    # Step 1: Update target
    steps.append(ImplementationStep(
        step_number=step_num,
        action=f"Update {target.name}",
        target_files=[target.file_path] if target.file_path else [],
        target_symbols=[target.name],
        reason="Primary target of the change",
        evidence_references=["Target entity identified by user"],
        depends_on_steps=[],
        risk_level="medium",
        uncertainty_note=None
    ))
    step_num += 1
    
    # Step 2: Update direct callers
    direct_callers = [i for i in impacts if i.impact_category == "direct_caller"]
    if direct_callers:
        caller_files = list(set(i.file_path for i in direct_callers if i.file_path))[:5]
        caller_names = list(set(i.entity_name for i in direct_callers))[:5]
        
        steps.append(ImplementationStep(
            step_number=step_num,
            action=f"Update {len(direct_callers)} direct caller(s)",
            target_files=caller_files,
            target_symbols=caller_names,
            reason="These symbols directly call the target and may need signature updates",
            evidence_references=[f"{len(direct_callers)} direct callers found in dependency graph"],
            depends_on_steps=[1],
            risk_level="high" if len(direct_callers) > 10 else "medium",
            uncertainty_note="Actual changes depend on the nature of the modification" if len(direct_callers) > 5 else None
        ))
        step_num += 1
    
    # Step 3: Update affected API endpoints
    if affected_endpoints:
        endpoint_files = list(set(ep.get("file", "") for ep in affected_endpoints if ep.get("file")))[:5]
        
        steps.append(ImplementationStep(
            step_number=step_num,
            action=f"Review and update {len(affected_endpoints)} affected API endpoint(s)",
            target_files=endpoint_files,
            target_symbols=[],
            reason="API contracts may need to be updated or versioned",
            evidence_references=[f"{len(affected_endpoints)} endpoints found in API analysis"],
            depends_on_steps=[1],
            risk_level="high",
            uncertainty_note="API changes may affect external clients"
        ))
        step_num += 1
    
    # Step 4: Update tests
    if summary.has_test_impact:
        steps.append(ImplementationStep(
            step_number=step_num,
            action="Update affected tests",
            target_files=[],
            target_symbols=[],
            reason="Tests may need to be updated for new behavior",
            evidence_references=["Test impact detected"],
            depends_on_steps=list(range(1, step_num)),
            risk_level="low",
            uncertainty_note=None
        ))
        step_num += 1
    
    # Determine overall risk
    overall_risk = "medium"
    if summary.affected_endpoints_count > 0:
        overall_risk = "high"
    elif summary.total_impacts > 20:
        overall_risk = "high"
    elif summary.total_impacts == 0:
        overall_risk = "low"
    
    # Assumptions
    assumptions = [
        "Static analysis captured all relevant dependencies",
        "No runtime/dynamic dispatch affects the impact",
        "External service dependencies are handled separately"
    ]
    
    # Limitations
    limitations = [
        "Cannot detect dynamic dispatch or reflection-based calls",
        "Does not analyze runtime behavior",
        "External API clients not analyzed"
    ]
    
    if summary.transitive_impacts > 0:
        limitations.append("Transitive impacts may require cascading changes")
    
    return ImplementationPlan(
        summary=f"Update {target.name} and {summary.total_impacts} affected component(s)",
        steps=steps,
        estimated_files_affected=len(affected_files),
        overall_risk=overall_risk,
        assumptions=assumptions,
        limitations=limitations
    )
