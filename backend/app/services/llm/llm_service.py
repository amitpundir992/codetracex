"""
LLM Service for Phase 12: LLM Reasoning & Grounded Explanations.

This service orchestrates the complete LLM answer generation pipeline:
1. Generate RAG context using RAGContextService
2. Construct grounded prompt using PromptBuilder
3. Generate answer using LLM provider
4. Parse and validate citations
5. Package grounded answer

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

Design Principles:

1. GROUNDING
   - Answer must reference supplied evidence
   - Citations validated against evidence IDs
   - Insufficient evidence explicitly indicated

2. SECURITY
   - Repository content treated as untrusted data
   - No API key exposure
   - Repository isolation enforced
   - Analysis run isolation supported

3. ERROR HANDLING
   - Provider timeout
   - Authentication failure
   - Malformed response
   - Empty response
   - No evidence

4. TRACEABILITY
   - Evidence → Prompt → Answer → Citations
   - All citations map to chunk UUIDs
"""
import logging
import re
from typing import List, Optional, Dict, Set
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.rag_context_service import RAGContextService
from app.services.llm.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMProviderError,
    LLMTimeoutError,
    LLMAuthenticationError,
)
from app.services.llm.prompt_builder import PromptBuilder
from app.schemas.rag_context import RAGContext
from app.schemas.llm import (
    GroundedAnswer,
    Citation,
    InsufficientEvidenceResponse,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for generating grounded answers using LLM.
    
    This service handles the complete pipeline from question to grounded answer:
    - RAG context generation
    - Prompt construction
    - LLM generation
    - Citation validation
    - Answer packaging
    
    Usage:
        service = LLMService(db, llm_provider)
        answer = service.generate_answer(
            repository_id=repo_id,
            question="How does auth work?",
            top_k=10
        )
    """
    
    def __init__(
        self,
        db: Session,
        llm_provider: LLMProvider,
        timeout_seconds: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        Initialize LLM service.
        
        Args:
            db: Database session
            llm_provider: Configured LLM provider instance
            timeout_seconds: Override default timeout
            temperature: Override default temperature
            max_tokens: Override default max tokens
        """
        self.db = db
        self.llm_provider = llm_provider
        
        # Get settings
        settings = get_settings()
        
        # LLM parameters
        self.timeout_seconds = timeout_seconds or settings.LLM_TIMEOUT
        self.temperature = temperature or settings.LLM_TEMPERATURE
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        
        # Initialize services
        self.rag_service = RAGContextService(db)
        self.prompt_builder = PromptBuilder()
        
        logger.info(
            f"Initialized LLM service with provider: {llm_provider.get_model_name()}, "
            f"timeout: {self.timeout_seconds}s, temperature: {self.temperature}"
        )
    
    def generate_answer(
        self,
        repository_id: UUID,
        question: str,
        top_k: int = 10,
        semantic_weight: float = 0.5,
        keyword_weight: float = 0.5,
        analysis_run_id: Optional[UUID] = None,
    ) -> GroundedAnswer:
        """
        Generate a grounded answer to a question about a repository.
        
        Args:
            repository_id: UUID of the repository
            question: User's question
            top_k: Number of chunks to retrieve
            semantic_weight: Weight for semantic search
            keyword_weight: Weight for keyword search
            analysis_run_id: Optional specific analysis run
            
        Returns:
            Grounded answer with citations
            
        Raises:
            LLMProviderError: If LLM generation fails
            LLMTimeoutError: If LLM request times out
            LLMAuthenticationError: If LLM authentication fails
            ValueError: If repository not found or invalid parameters
        """
        logger.info(
            f"Generating answer for question: '{question[:100]}...' "
            f"on repository: {repository_id}"
        )
        
        # 1. Generate RAG context
        rag_context = self.rag_service.build_context(
            repository_id=repository_id,
            question=question,
            top_k=top_k,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
            analysis_run_id=analysis_run_id,
        )
        
        logger.info(
            f"Retrieved {rag_context.total_evidence_items} evidence items, "
            f"{rag_context.total_characters} characters"
        )
        
        # 2. Check for insufficient evidence
        if not rag_context.evidence:
            logger.warning("No evidence found for question")
            # Return insufficient evidence response as grounded answer
            return GroundedAnswer(
                question=question,
                answer=(
                    "I could not find relevant code or documentation to answer this question. "
                    "The repository may not contain information about this topic, or the "
                    "question may need to be more specific."
                ),
                citations=[],
                is_sufficient_evidence=False,
                confidence_note="No relevant evidence was found in the repository.",
                evidence_count=0,
                repository_id=repository_id,
                analysis_run_id=analysis_run_id,
            )
        
        # 3. Build prompt
        system_prompt, user_prompt, citation_map = self.prompt_builder.build_prompt(rag_context)
        
        # 4. Generate answer using LLM
        llm_request = LLMRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
        )
        
        try:
            llm_response = self.llm_provider.generate(llm_request)
        except (LLMTimeoutError, LLMAuthenticationError, LLMProviderError) as e:
            logger.error(f"LLM generation failed: {e}")
            raise
        
        # Check for empty response
        if llm_response.is_empty:
            logger.error("LLM returned empty response")
            raise LLMProviderError("LLM returned empty response")
        
        logger.info(f"LLM generated {len(llm_response.content)} character response")
        
        # 5. Extract and validate citations
        citations = self._extract_citations(
            llm_response.content,
            citation_map,
            rag_context
        )
        
        logger.info(f"Extracted {len(citations)} citations")
        
        # 6. Determine confidence
        is_sufficient = self._assess_sufficiency(llm_response.content, rag_context)
        confidence_note = None
        
        if not is_sufficient:
            confidence_note = (
                "The available evidence may not fully answer this question. "
                "Consider asking a more specific question or checking if the "
                "repository has been fully analyzed."
            )
        
        # 7. Package grounded answer
        grounded_answer = GroundedAnswer(
            question=question,
            answer=llm_response.content,
            citations=citations,
            is_sufficient_evidence=is_sufficient,
            confidence_note=confidence_note,
            evidence_count=len(rag_context.evidence),
            repository_id=repository_id,
            analysis_run_id=analysis_run_id,
        )
        
        return grounded_answer
    
    def _extract_citations(
        self,
        answer_text: str,
        citation_map: Dict[int, UUID],
        rag_context: RAGContext,
    ) -> List[Citation]:
        """
        Extract and validate citations from LLM answer.
        
        Looks for [Evidence N] patterns and maps them to actual evidence items.
        
        Args:
            answer_text: LLM-generated answer text
            citation_map: Map from evidence number to chunk UUID
            rag_context: Original RAG context with evidence
            
        Returns:
            List of validated citations
        """
        citations = []
        seen_evidence_ids: Set[UUID] = set()
        
        # Find all [Evidence N] references
        pattern = r'\[Evidence (\d+)\]'
        matches = re.finditer(pattern, answer_text)
        
        for match in matches:
            evidence_num = int(match.group(1))
            
            # Validate against citation map
            if evidence_num not in citation_map:
                logger.warning(f"LLM cited non-existent evidence: {evidence_num}")
                continue
            
            chunk_id = citation_map[evidence_num]
            
            # Skip duplicates
            if chunk_id in seen_evidence_ids:
                continue
            
            seen_evidence_ids.add(chunk_id)
            
            # Find the actual evidence item
            evidence_item = None
            for ev in rag_context.evidence:
                if ev.chunk_id == chunk_id:
                    evidence_item = ev
                    break
            
            if not evidence_item:
                logger.warning(f"Could not find evidence item for chunk: {chunk_id}")
                continue
            
            # Create citation
            # Truncate excerpt to 500 chars
            excerpt = evidence_item.content
            if len(excerpt) > 500:
                excerpt = excerpt[:497] + "..."
            
            citation = Citation(
                evidence_id=chunk_id,
                file_path=evidence_item.file_path,
                start_line=evidence_item.start_line,
                end_line=evidence_item.end_line,
                symbol_name=evidence_item.symbol_name,
                symbol_type=evidence_item.symbol_type,
                excerpt=excerpt,
            )
            
            citations.append(citation)
        
        return citations
    
    def _assess_sufficiency(
        self,
        answer_text: str,
        rag_context: RAGContext,
    ) -> bool:
        """
        Assess whether the evidence was sufficient to answer the question.
        
        Uses heuristics to determine if the answer indicates insufficient evidence.
        
        Args:
            answer_text: LLM-generated answer text
            rag_context: Original RAG context
            
        Returns:
            True if evidence appears sufficient, False otherwise
        """
        # Check RAG context flags
        if not rag_context.evidence:
            return False
        
        if rag_context.total_evidence_items < 2:
            return False
        
        # Check answer text for insufficiency indicators
        insufficiency_phrases = [
            "cannot find",
            "no evidence",
            "not enough information",
            "insufficient evidence",
            "unclear from the evidence",
            "not present in the repository",
        ]
        
        answer_lower = answer_text.lower()
        for phrase in insufficiency_phrases:
            if phrase in answer_lower:
                return False
        
        # If we have multiple evidence items and no insufficiency indicators,
        # assume sufficient
        return True
