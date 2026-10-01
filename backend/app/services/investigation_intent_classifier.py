"""
Investigation Intent Classifier for Phase 16.

Classifies investigation questions using deterministic pattern matching.

Architecture:

    Question
        ↓
    Normalize text
        ↓
    Pattern matching (deterministic)
        ↓
    Intent + confidence
        ↓
    [Optional: LLM fallback for complex cases]

Design Principles:

1. DETERMINISTIC FIRST
   - Use keyword/pattern matching for common intents
   - Fast and reliable
   - No LLM required for most questions

2. BOUNDED COMPLEXITY
   - Simple regex/keyword patterns
   - Explicit intent categories
   - Default to UNKNOWN rather than guessing

3. EXTENSIBLE
   - Can add LLM fallback in future
   - Patterns can be refined over time
   - Intent categories are extensible

Security:
    - No code execution
    - Bounded input length
    - Safe pattern matching
"""
import logging
import re
from typing import Optional, Tuple
from uuid import UUID

from app.schemas.investigation import InvestigationIntent

logger = logging.getLogger(__name__)


class InvestigationIntentClassifier:
    """
    Classifies investigation questions into intent categories.
    
    Uses deterministic pattern matching for reliability and speed.
    """
    
    # Keyword patterns for each intent
    INTENT_PATTERNS = {
        InvestigationIntent.SYMBOL_EXPLANATION: [
            r'\b(function|class|method|symbol)\b',
            r'\b(what does|explain|how does)\s+\w+\s+(work|do|function)',
            r'\b(implementation|defined|declared)\b',
        ],
        InvestigationIntent.API_EXPLANATION: [
            r'\b(api|endpoint|route|handler)\b',
            r'\b(GET|POST|PUT|DELETE|PATCH)\s+/',
            r'\b(/api/|/v1/|/v2/)\b',
            r'\b(request|response|payload)\b',
        ],
        InvestigationIntent.WORKFLOW_EXPLANATION: [
            r'\b(workflow|flow|process|execution)\b',
            r'\b(what happens|how does|sequence|pipeline)\b',
            r'\b(after|before|when|then)\b',
            r'\b(request flow|data flow|control flow)\b',
        ],
        InvestigationIntent.DEPENDENCY_QUESTION: [
            r'\b(depend|dependency|import|require)\b',
            r'\b(use|uses|used by|call|calls|called by)\b',
            r'\b(what calls|what uses|who calls)\b',
        ],
        InvestigationIntent.IMPACT_QUESTION: [
            r'\b(impact|affect|change|break|downstream)\b',
            r'\b(what (would )?break|what (would )?fail)\b',
            r'\b(if I change|if I modify|if I update)\b',
            r'\b(affected|impacted|broken)\b',
        ],
        InvestigationIntent.HISTORY_QUESTION: [
            r'\b(history|commit|git|when|why)\b',
            r'\b(introduced|added|changed|modified|removed)\b',
            r'\b(who (wrote|created|added)|author)\b',
            r'\b(previous|original|old version)\b',
        ],
        InvestigationIntent.ARCHITECTURE_QUESTION: [
            r'\b(architecture|structure|design|pattern)\b',
            r'\b(organized|structured|laid out)\b',
            r'\b(how is|how are|overall)\b',
            r'\b(repository|codebase|project)\b.*\b(structured|organized)\b',
        ],
        InvestigationIntent.DATABASE_QUESTION: [
            r'\b(database|db|table|model|schema|query|orm)\b',
            r'\b(sql|postgres|mysql|mongodb)\b',
            r'\b(persist|store|save|retrieve)\b',
        ],
    }
    
    def __init__(self):
        """Initialize the intent classifier."""
        pass
    
    def classify(
        self,
        question: str,
        conversation_context: Optional[dict] = None
    ) -> Tuple[InvestigationIntent, float]:
        """
        Classify an investigation question.
        
        Args:
            question: The investigation question
            conversation_context: Optional previous conversation context
        
        Returns:
            Tuple of (intent, confidence)
        """
        # Normalize question
        normalized = question.lower().strip()
        
        # If question is very short and has conversation context,
        # it might be a contextual reference ("what calls it?", "show me that")
        if len(normalized.split()) <= 4 and conversation_context:
            # Contextual questions often relate to dependencies or details
            if self._matches_contextual_dependency(normalized):
                return InvestigationIntent.DEPENDENCY_QUESTION, 0.7
            if self._matches_contextual_detail(normalized):
                return InvestigationIntent.SYMBOL_EXPLANATION, 0.7
        
        # Score each intent
        intent_scores = {}
        for intent, patterns in self.INTENT_PATTERNS.items():
            score = self._score_intent(normalized, patterns)
            if score > 0:
                intent_scores[intent] = score
        
        # Return highest scoring intent
        if not intent_scores:
            return InvestigationIntent.UNKNOWN, 0.5
        
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        
        # Confidence is the normalized score
        # Max score is number of pattern matches
        confidence = min(best_intent[1] / 2.0, 1.0)  # Cap at 1.0
        
        return best_intent[0], confidence
    
    def _score_intent(self, text: str, patterns: list[str]) -> float:
        """
        Score how well text matches intent patterns.
        
        Args:
            text: Normalized question text
            patterns: List of regex patterns
        
        Returns:
            Score (higher = better match)
        """
        score = 0.0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 1.0
        return score
    
    def _matches_contextual_dependency(self, text: str) -> bool:
        """Check if question is asking about dependencies in context."""
        contextual_dependency_patterns = [
            r'\b(what calls|what uses|who uses|callers|users)\b',
            r'\b(calls it|uses it|depends on it)\b',
            r'\b(called by|used by)\b',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in contextual_dependency_patterns)
    
    def _matches_contextual_detail(self, text: str) -> bool:
        """Check if question is asking for details about previous context."""
        contextual_detail_patterns = [
            r'\b(show|explain|describe|tell me about)\b',
            r'\b(that|this|it)\b',
            r'\b(more details|implementation)\b',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in contextual_detail_patterns)
    
    def supports_llm_fallback(self) -> bool:
        """
        Whether this classifier supports LLM fallback for ambiguous cases.
        
        Returns:
            False (not implemented in Phase 16, can be added later)
        """
        return False
