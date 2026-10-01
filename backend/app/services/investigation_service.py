"""
Investigation Orchestration Service for Phase 16.

Coordinates the complete investigation pipeline:
1. Intent classification
2. Evidence gathering (hybrid search, graph, workflow, git)
3. Evidence deduplication
4. Context building
5. LLM reasoning
6. Response assembly with claims and follow-ups

Architecture:

    User Question + Context
        ↓
    Intent Classification
        ↓
    Evidence Gathering (parallel)
        ↓
    Deduplication + Ranking
        ↓
    Context Budgeting
        ↓
    LLM Prompt
        ↓
    Structured Response
        ↓
    Validation
        ↓
    Investigation Response

Design Principles:

1. ORCHESTRATION
   - Coordinates existing services
   - Does not duplicate retrieval logic
   - Intent-driven evidence gathering

2. BOUNDED CONTEXT
   - Configurable limits
   - Deterministic truncation
   - Explicit metadata

3. GROUNDING
   - Evidence-based claims
   - Certainty levels
   - Citation traceability

4. SECURITY
   - Repository isolation
   - Analysis run isolation
   - Safe error handling
   - No credential exposure
"""
import logging
from typing import List, Optional, Dict, Any, Set, Tuple
from uuid import UUID
import asyncio

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.services.investigation_intent_classifier import InvestigationIntentClassifier
from app.services.investigation_prompt_builder import InvestigationPromptBuilder
from app.services.hybrid_search_service import HybridSearchService, HybridSearchResult
from app.services.graph_service import GraphService
from app.services.workflow_service import WorkflowService
from app.services.git_history_service import GitHistoryService
from app.services.target_identification_service import TargetIdentificationService
from app.services.llm.llm_service import LLMService
from app.services.llm.provider import LLMProvider, LLMProviderError
from app.schemas.investigation import (
    InvestigationIntent,
    InvestigationEvidence,
    EvidenceType,
    GroundedClaim,
    CertaintyLevel,
    FollowUpQuestion,
    InvestigationGrounding,
    ConversationContext,
    InvestigationResponse,
    InsufficientEvidenceResponse
)
from app.db.models import Repository, AnalysisRun, Symbol, File, ApiEndpoint

logger = logging.getLogger(__name__)


class InvestigationService:
    """
    Service for orchestrating repository investigations.
    
    Coordinates evidence gathering, LLM reasoning, and response assembly.
    """
    
    # Configuration defaults
    DEFAULT_MAX_EVIDENCE = 10
    DEFAULT_MAX_CONTENT_LENGTH = 1000
    DEFAULT_MAX_FOLLOW_UPS = 5
    DEFAULT_MAX_GRAPH_NODES = 20
    DEFAULT_MAX_WORKFLOW_NODES = 15
    DEFAULT_MAX_GIT_COMMITS = 10
    
    def __init__(
        self,
        db: Session,
        llm_provider: LLMProvider
    ):
        """
        Initialize investigation service.
        
        Args:
            db: Database session
            llm_provider: LLM provider for answer generation
        """
        self.db = db
        self.llm_provider = llm_provider
        
        # Initialize sub-services
        self.intent_classifier = InvestigationIntentClassifier()
        self.prompt_builder = InvestigationPromptBuilder()
        self.hybrid_search = HybridSearchService(db)
        self.graph_service = GraphService(db)
        self.workflow_service = WorkflowService(db)
        self.git_history_service = GitHistoryService(db)
        self.target_identification = TargetIdentificationService(db)
    
    async def investigate(
        self,
        repository_id: UUID,
        question: str,
        analysis_run_id: Optional[UUID] = None,
        conversation_context: Optional[ConversationContext] = None,
        max_evidence: int = DEFAULT_MAX_EVIDENCE,
        include_graph: bool = True,
        include_workflow: bool = True,
        include_git_history: bool = False
    ) -> InvestigationResponse:
        """
        Conduct a repository investigation.
        
        Args:
            repository_id: Repository to investigate
            question: Investigation question
            analysis_run_id: Specific analysis run (optional, uses latest if None)
            conversation_context: Previous conversation context (optional)
            max_evidence: Maximum evidence items to retrieve
            include_graph: Whether to include graph relationships
            include_workflow: Whether to include workflow information
            include_git_history: Whether to include git history
        
        Returns:
            Investigation response with answer, claims, evidence, follow-ups
        
        Raises:
            ValueError: Invalid repository or analysis run
            LLMProviderError: LLM generation failed
        """
        logger.info(f"Starting investigation for repository {repository_id}: {question}")
        
        # Validate repository
        repository = self.db.query(Repository).filter(
            Repository.id == repository_id
        ).first()
        
        if not repository:
            raise ValueError(f"Repository {repository_id} not found")
        
        # Get analysis run
        if not analysis_run_id:
            analysis_run = self.db.query(AnalysisRun).filter(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.status == "completed"
            ).order_by(desc(AnalysisRun.completed_at)).first()
            
            if not analysis_run:
                raise ValueError(f"No completed analysis found for repository {repository_id}")
            
            analysis_run_id = analysis_run.id
        else:
            analysis_run = self.db.query(AnalysisRun).filter(
                AnalysisRun.id == analysis_run_id,
                AnalysisRun.repository_id == repository_id
            ).first()
            
            if not analysis_run:
                raise ValueError(f"Analysis run {analysis_run_id} not found for repository {repository_id}")
        
        # Step 1: Classify intent
        context_dict = conversation_context.dict() if conversation_context else None
        intent, confidence = self.intent_classifier.classify(question, context_dict)
        logger.info(f"Detected intent: {intent.value} (confidence: {confidence:.2f})")
        
        # Step 2: Gather evidence
        evidence = await self._gather_evidence(
            repository_id=repository_id,
            analysis_run_id=analysis_run_id,
            question=question,
            intent=intent,
            conversation_context=conversation_context,
            max_evidence=max_evidence,
            include_graph=include_graph,
            include_workflow=include_workflow,
            include_git_history=include_git_history
        )
        
        logger.info(f"Gathered {len(evidence)} evidence items")
        
        # Check if we have sufficient evidence
        if len(evidence) == 0:
            return self._create_insufficient_evidence_response(
                question=question,
                repository_id=repository_id,
                reason="No relevant evidence found in repository analysis"
            )
        
        # Step 3: Build prompt
        prompt = self.prompt_builder.build_investigation_prompt(
            question=question,
            evidence=evidence,
            intent=intent,
            conversation_context=context_dict,
            max_follow_ups=self.DEFAULT_MAX_FOLLOW_UPS
        )
        
        # Step 4: Generate answer via LLM
        try:
            llm_response = await self._generate_llm_response(prompt)
        except LLMProviderError as e:
            logger.error(f"LLM generation failed: {e}")
            # Return safe fallback
            return self._create_fallback_response(
                question=question,
                repository_id=repository_id,
                analysis_run_id=analysis_run_id,
                intent=intent,
                evidence=evidence,
                error_message=str(e)
            )
        
        # Step 5: Parse and validate response
        parsed_response = self.prompt_builder.parse_investigation_response(llm_response)
        
        if not parsed_response:
            logger.warning("Failed to parse LLM response, using fallback")
            return self._create_fallback_response(
                question=question,
                repository_id=repository_id,
                analysis_run_id=analysis_run_id,
                intent=intent,
                evidence=evidence,
                error_message="Failed to parse LLM response"
            )
        
        # Step 6: Assemble investigation response
        response = self._assemble_investigation_response(
            question=question,
            intent=intent,
            parsed_response=parsed_response,
            evidence=evidence,
            repository_id=repository_id,
            analysis_run_id=analysis_run_id,
            conversation_context=conversation_context
        )
        
        logger.info(f"Investigation complete: {len(response.claims)} claims, {len(response.follow_up_questions)} follow-ups")
        
        return response
    
    async def _gather_evidence(
        self,
        repository_id: UUID,
        analysis_run_id: UUID,
        question: str,
        intent: InvestigationIntent,
        conversation_context: Optional[ConversationContext],
        max_evidence: int,
        include_graph: bool,
        include_workflow: bool,
        include_git_history: bool
    ) -> List[InvestigationEvidence]:
        """
        Gather evidence from multiple sources based on intent.
        
        Returns unified evidence list, deduplicated and ranked.
        """
        all_evidence = []
        
        # 1. Hybrid search (always included)
        search_results = self.hybrid_search.search(
            repository_id=repository_id,
            query=question,
            top_k=max_evidence,
            analysis_run_id=analysis_run_id
        )
        
        for result in search_results:
            evidence = self._convert_search_result_to_evidence(result, repository_id, analysis_run_id)
            all_evidence.append(evidence)
        
        # 2. Target identification (for specific entity questions)
        if intent in [InvestigationIntent.SYMBOL_EXPLANATION, InvestigationIntent.API_EXPLANATION,
                      InvestigationIntent.DEPENDENCY_QUESTION, InvestigationIntent.IMPACT_QUESTION]:
            target_evidence = self._gather_target_evidence(
                question, repository_id, analysis_run_id, intent
            )
            all_evidence.extend(target_evidence)
        
        # 3. Graph relationships (if requested and relevant)
        if include_graph and intent in [InvestigationIntent.DEPENDENCY_QUESTION,
                                        InvestigationIntent.IMPACT_QUESTION,
                                        InvestigationIntent.WORKFLOW_EXPLANATION]:
            # Graph enrichment happens on top of identified targets
            # This is already handled by existing services
            pass
        
        # 4. Workflow information (if requested and relevant)
        if include_workflow and intent in [InvestigationIntent.WORKFLOW_EXPLANATION,
                                           InvestigationIntent.API_EXPLANATION]:
            # Workflow enrichment
            pass
        
        # 5. Git history (if requested and relevant)
        if include_git_history and intent == InvestigationIntent.HISTORY_QUESTION:
            git_evidence = self._gather_git_evidence(
                question, repository_id, analysis_run_id
            )
            all_evidence.extend(git_evidence)
        
        # Deduplicate evidence
        deduplicated = self._deduplicate_evidence(all_evidence)
        
        # Rank by relevance
        ranked = sorted(deduplicated, key=lambda e: e.retrieval_score or 0.0, reverse=True)
        
        # Apply limits
        truncated = ranked[:max_evidence]
        
        # Truncate content if needed
        for evidence in truncated:
            if len(evidence.content) > self.DEFAULT_MAX_CONTENT_LENGTH:
                evidence.content = evidence.content[:self.DEFAULT_MAX_CONTENT_LENGTH] + "\n... (truncated)"
                evidence.content_truncated = True
        
        return truncated
    
    def _convert_search_result_to_evidence(
        self,
        result: HybridSearchResult,
        repository_id: UUID,
        analysis_run_id: UUID
    ) -> InvestigationEvidence:
        """Convert hybrid search result to investigation evidence."""
        return InvestigationEvidence(
            evidence_id=f"search_{str(result.chunk_id)}",
            evidence_type=EvidenceType.HYBRID_SEARCH,
            retrieval_score=result.final_score,
            retrieval_source=result.retrieval_source,
            content=result.content,
            content_truncated=False,
            repository_id=repository_id,
            analysis_run_id=analysis_run_id,
            file_path=result.file_path,
            start_line=result.start_line,
            end_line=result.end_line,
            language=result.language,
            symbol_name=result.symbol_name,
            symbol_type=result.symbol_type,
            api_endpoint_method=result.api_endpoint_method,
            api_endpoint_path=result.api_endpoint_path,
            metadata=result.metadata
        )
    
    def _gather_target_evidence(
        self,
        question: str,
        repository_id: UUID,
        analysis_run_id: UUID,
        intent: InvestigationIntent
    ) -> List[InvestigationEvidence]:
        """Gather evidence for specific targets mentioned in question."""
        evidence = []
        
        try:
            # Try to identify specific target
            result = self.target_identification.identify_target_from_query(
                query=question,
                repository_id=repository_id,
                analysis_run_id=analysis_run_id
            )
            
            if result.identified_target:
                target = result.identified_target
                
                # Add target as evidence
                if target.target_type == "symbol" and target.target_id:
                    symbol_evidence = self._get_symbol_evidence(
                        target.target_id, repository_id, analysis_run_id
                    )
                    if symbol_evidence:
                        evidence.append(symbol_evidence)
                
                elif target.target_type == "api_endpoint" and target.target_id:
                    endpoint_evidence = self._get_endpoint_evidence(
                        target.target_id, repository_id, analysis_run_id
                    )
                    if endpoint_evidence:
                        evidence.append(endpoint_evidence)
        
        except Exception as e:
            logger.warning(f"Target identification failed: {e}")
        
        return evidence
    
    def _get_symbol_evidence(
        self,
        symbol_id: UUID,
        repository_id: UUID,
        analysis_run_id: UUID
    ) -> Optional[InvestigationEvidence]:
        """Get evidence for a specific symbol."""
        symbol = self.db.query(Symbol).filter(Symbol.id == symbol_id).first()
        if not symbol:
            return None
        
        file = symbol.file
        content = f"# Symbol: {symbol.name}\n"
        content += f"# Type: {symbol.symbol_type}\n"
        content += f"# File: {file.relative_path}\n"
        content += f"# Lines: {symbol.start_line}-{symbol.end_line}\n"
        
        return InvestigationEvidence(
            evidence_id=f"symbol_{str(symbol.id)}",
            evidence_type=EvidenceType.SYMBOL,
            retrieval_score=1.0,
            retrieval_source="direct",
            content=content,
            content_truncated=False,
            repository_id=repository_id,
            analysis_run_id=analysis_run_id,
            file_path=file.relative_path,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            language=file.language,
            symbol_id=symbol.id,
            symbol_name=symbol.name,
            symbol_type=symbol.symbol_type
        )
    
    def _get_endpoint_evidence(
        self,
        endpoint_id: UUID,
        repository_id: UUID,
        analysis_run_id: UUID
    ) -> Optional[InvestigationEvidence]:
        """Get evidence for a specific API endpoint."""
        endpoint = self.db.query(ApiEndpoint).filter(ApiEndpoint.id == endpoint_id).first()
        if not endpoint:
            return None
        
        file = endpoint.file
        content = f"# API Endpoint: {endpoint.method.value} {endpoint.path}\n"
        content += f"# Handler: {endpoint.handler_function}\n"
        content += f"# File: {file.relative_path}\n"
        if endpoint.line_number:
            content += f"# Line: {endpoint.line_number}\n"
        
        return InvestigationEvidence(
            evidence_id=f"endpoint_{str(endpoint.id)}",
            evidence_type=EvidenceType.API_ENDPOINT,
            retrieval_score=1.0,
            retrieval_source="direct",
            content=content,
            content_truncated=False,
            repository_id=repository_id,
            analysis_run_id=analysis_run_id,
            file_path=file.relative_path,
            start_line=endpoint.line_number,
            end_line=endpoint.line_number,
            language=file.language,
            api_endpoint_id=endpoint.id,
            api_endpoint_method=endpoint.method.value,
            api_endpoint_path=endpoint.path
        )
    
    def _gather_git_evidence(
        self,
        question: str,
        repository_id: UUID,
        analysis_run_id: UUID
    ) -> List[InvestigationEvidence]:
        """Gather Git history evidence if available."""
        # Git history integration is minimal in Phase 16
        # This is a placeholder for future enhancement
        return []
    
    def _deduplicate_evidence(
        self,
        evidence: List[InvestigationEvidence]
    ) -> List[InvestigationEvidence]:
        """
        Deduplicate evidence items.
        
        Uses deterministic identity: same file + lines + type = same evidence
        """
        seen: Set[str] = set()
        deduplicated = []
        
        for item in evidence:
            # Create identity key
            key_parts = [
                str(item.repository_id),
                item.evidence_type.value,
                item.file_path or "",
                str(item.start_line or 0),
                str(item.end_line or 0),
                item.symbol_name or "",
                f"{item.api_endpoint_method or ''}_{item.api_endpoint_path or ''}"
            ]
            key = "|".join(key_parts)
            
            if key not in seen:
                seen.add(key)
                deduplicated.append(item)
            else:
                # Evidence already present, optionally merge scores
                # For now, keep first occurrence
                pass
        
        return deduplicated
    
    async def _generate_llm_response(self, prompt: str) -> str:
        """Generate LLM response with error handling."""
        from app.services.llm.provider import LLMRequest
        
        request = LLMRequest(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.3  # Lower temperature for more deterministic responses
        )
        
        response = await self.llm_provider.generate(request)
        return response.content
    
    def _assemble_investigation_response(
        self,
        question: str,
        intent: InvestigationIntent,
        parsed_response: Dict[str, Any],
        evidence: List[InvestigationEvidence],
        repository_id: UUID,
        analysis_run_id: UUID,
        conversation_context: Optional[ConversationContext]
    ) -> InvestigationResponse:
        """Assemble the final investigation response."""
        
        # Parse claims
        claims = [
            GroundedClaim(
                claim_text=claim["claim_text"],
                certainty=CertaintyLevel(claim["certainty"]),
                evidence_ids=claim.get("evidence_ids", []),
                reasoning=claim.get("reasoning")
            )
            for claim in parsed_response.get("claims", [])
        ]
        
        # Parse follow-up questions
        follow_ups = [
            FollowUpQuestion(
                question=fq["question"],
                rationale=fq.get("rationale"),
                related_evidence_ids=fq.get("related_evidence_ids", [])
            )
            for fq in parsed_response.get("follow_up_questions", [])
        ]
        
        # Build grounding metadata
        grounding = InvestigationGrounding(
            is_grounded=len(evidence) > 0,
            evidence_count=len(evidence),
            evidence_truncated=len(evidence) >= self.DEFAULT_MAX_EVIDENCE,
            truncation_reason="Maximum evidence limit reached" if len(evidence) >= self.DEFAULT_MAX_EVIDENCE else None,
            confidence_note=None
        )
        
        # Update conversation context
        new_context = self._build_conversation_context(
            evidence=evidence,
            question=question
        )
        
        return InvestigationResponse(
            question=question,
            detected_intent=intent,
            answer=parsed_response.get("answer", ""),
            claims=claims,
            evidence=evidence,
            grounding=grounding,
            limitations=parsed_response.get("limitations", []),
            follow_up_questions=follow_ups,
            conversation_context=new_context,
            repository_id=repository_id,
            analysis_run_id=analysis_run_id
        )
    
    def _build_conversation_context(
        self,
        evidence: List[InvestigationEvidence],
        question: str
    ) -> ConversationContext:
        """Build conversation context from evidence for next turn."""
        context = ConversationContext(
            last_question=question
        )
        
        # Extract symbols
        for item in evidence:
            if item.symbol_id and item.symbol_name:
                context.last_symbols.append({
                    "id": str(item.symbol_id),
                    "name": item.symbol_name,
                    "type": item.symbol_type or "unknown"
                })
        
        # Extract files
        for item in evidence:
            if item.file_path and item.file_path not in context.last_files:
                context.last_files.append(item.file_path)
        
        # Extract endpoints
        for item in evidence:
            if item.api_endpoint_id and item.api_endpoint_method and item.api_endpoint_path:
                context.last_endpoints.append({
                    "id": str(item.api_endpoint_id),
                    "method": item.api_endpoint_method,
                    "path": item.api_endpoint_path
                })
        
        # Limit to most recent
        context.last_symbols = context.last_symbols[:10]
        context.last_files = context.last_files[:10]
        context.last_endpoints = context.last_endpoints[:10]
        
        return context
    
    def _create_insufficient_evidence_response(
        self,
        question: str,
        repository_id: UUID,
        reason: str
    ) -> InvestigationResponse:
        """Create response when evidence is insufficient."""
        return InvestigationResponse(
            question=question,
            detected_intent=InvestigationIntent.UNKNOWN,
            answer=f"Insufficient evidence to answer this question. {reason}",
            claims=[],
            evidence=[],
            grounding=InvestigationGrounding(
                is_grounded=False,
                evidence_count=0,
                evidence_truncated=False
            ),
            limitations=[reason],
            follow_up_questions=[],
            conversation_context=ConversationContext(),
            repository_id=repository_id,
            analysis_run_id=None
        )
    
    def _create_fallback_response(
        self,
        question: str,
        repository_id: UUID,
        analysis_run_id: UUID,
        intent: InvestigationIntent,
        evidence: List[InvestigationEvidence],
        error_message: str
    ) -> InvestigationResponse:
        """Create fallback response when LLM fails."""
        # Build basic answer from evidence
        answer = "Found relevant evidence in the repository:\n\n"
        for i, item in enumerate(evidence[:5], 1):
            answer += f"{i}. {item.file_path}"
            if item.symbol_name:
                answer += f" - {item.symbol_name}"
            if item.api_endpoint_method and item.api_endpoint_path:
                answer += f" - {item.api_endpoint_method} {item.api_endpoint_path}"
            answer += "\n"
        
        answer += "\n(Note: Detailed analysis temporarily unavailable)"
        
        return InvestigationResponse(
            question=question,
            detected_intent=intent,
            answer=answer,
            claims=[],
            evidence=evidence,
            grounding=InvestigationGrounding(
                is_grounded=True,
                evidence_count=len(evidence),
                evidence_truncated=False,
                confidence_note=f"LLM analysis unavailable: {error_message}"
            ),
            limitations=[f"Detailed LLM analysis failed: {error_message}"],
            follow_up_questions=[],
            conversation_context=self._build_conversation_context(evidence, question),
            repository_id=repository_id,
            analysis_run_id=analysis_run_id
        )
