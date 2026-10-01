"""
Investigation Prompt Builder for Phase 16.

Constructs prompts for investigation questions with:
- Grounded claims (confirmed/inferred/uncertain)
- Follow-up question generation
- Explicit evidence citation requirements
- Structured output format

Architecture:

    Investigation Evidence
        ↓
    Structured Prompt
        ↓
    LLM with JSON Schema
        ↓
    Parsed Response
        ↓
    Validated Claims + Follow-ups

Design Principles:

1. EXPLICIT GROUNDING
   - LLM must use only supplied evidence
   - Must distinguish confirmed vs inferred vs uncertain
   - Must cite evidence IDs
   - Must not invent facts

2. STRUCTURED OUTPUT
   - JSON schema for parsing
   - Pydantic validation
   - Clear claim structure
   - Explicit limitations

3. SECURITY
   - No credential exposure
   - Repository content is untrusted
   - Bounded context
   - No code execution instructions
"""
import logging
import json
from typing import List, Dict, Any, Optional

from app.schemas.investigation import (
    InvestigationEvidence,
    InvestigationIntent,
    CertaintyLevel
)

logger = logging.getLogger(__name__)


class InvestigationPromptBuilder:
    """
    Builds investigation prompts with structured output requirements.
    
    Extends basic prompt building with investigation-specific features:
    - Certainty level classification
    - Follow-up question generation
    - Explicit grounding requirements
    """
    
    def __init__(self):
        """Initialize the prompt builder."""
        pass
    
    def build_investigation_prompt(
        self,
        question: str,
        evidence: List[InvestigationEvidence],
        intent: InvestigationIntent,
        conversation_context: Optional[Dict[str, Any]] = None,
        max_follow_ups: int = 5
    ) -> str:
        """
        Build a structured investigation prompt.
        
        Args:
            question: User's investigation question
            evidence: Retrieved evidence items
            intent: Detected question intent
            conversation_context: Previous conversation context if available
            max_follow_ups: Maximum follow-up questions to generate
        
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        # System instructions
        prompt_parts.append(self._build_system_instructions(intent))
        
        # Evidence section
        prompt_parts.append(self._build_evidence_section(evidence))
        
        # Conversation context if available
        if conversation_context:
            prompt_parts.append(self._build_context_section(conversation_context))
        
        # Question
        prompt_parts.append(f"\n## USER QUESTION\n\n{question}")
        
        # Output format requirements
        prompt_parts.append(self._build_output_format(max_follow_ups))
        
        return "\n\n".join(prompt_parts)
    
    def _build_system_instructions(self, intent: InvestigationIntent) -> str:
        """Build system instructions based on intent."""
        base_instructions = """# REPOSITORY INVESTIGATION TASK

You are a repository intelligence assistant. Your job is to answer questions about a codebase using ONLY the provided repository evidence.

## CRITICAL RULES

1. **USE ONLY SUPPLIED EVIDENCE**
   - Do not invent files, functions, classes, or implementation details
   - Do not claim to have inspected code that was not provided
   - Do not fabricate line numbers, commit messages, or Git history
   - If evidence is missing, explicitly state this

2. **DISTINGUISH CERTAINTY LEVELS**
   - CONFIRMED: Direct evidence from static analysis (function calls, imports, definitions)
   - INFERRED: Reasonable inference from evidence (likely behavior based on patterns)
   - UNCERTAIN: Insufficient evidence to confirm (acknowledge gaps)

3. **CITE EVIDENCE**
   - Reference evidence IDs for all claims
   - Link claims to specific files, symbols, or commits
   - Do not make unsupported assertions

4. **ACKNOWLEDGE LIMITATIONS**
   - Static analysis cannot capture runtime behavior
   - Dynamic dispatch and reflection are not resolved
   - External dependencies may not be fully analyzed
   - Missing evidence means uncertain answers

5. **GENERATE USEFUL FOLLOW-UPS**
   - Suggest next investigation questions based on evidence
   - Follow-ups should be grounded in what was found
   - Limit suggestions to genuinely useful next steps"""
        
        # Add intent-specific guidance
        intent_guidance = {
            InvestigationIntent.SYMBOL_EXPLANATION: """
## INTENT: Symbol Explanation

Focus on:
- Symbol definition and implementation
- Parameters and return types
- Direct callers and callees
- File location and context""",
            
            InvestigationIntent.API_EXPLANATION: """
## INTENT: API Endpoint Explanation

Focus on:
- HTTP method and path
- Handler function
- Request/response structure
- Service layer calls
- Authentication/authorization""",
            
            InvestigationIntent.WORKFLOW_EXPLANATION: """
## INTENT: Workflow Explanation

Focus on:
- Execution flow from entry point
- Service/repository calls
- Data transformations
- Control flow logic""",
            
            InvestigationIntent.DEPENDENCY_QUESTION: """
## INTENT: Dependency Question

Focus on:
- Call relationships (who calls who)
- Import dependencies
- Symbol relationships
- Dependency graph structure""",
            
            InvestigationIntent.IMPACT_QUESTION: """
## INTENT: Impact Question

Focus on:
- Downstream callers
- Dependent symbols/files
- Potential breaking changes
- Affected workflows""",
            
            InvestigationIntent.HISTORY_QUESTION: """
## INTENT: History Question

Focus on:
- Git commits if provided
- File/symbol changes over time
- Commit messages and authors
- Historical context""",
        }
        
        specific_guidance = intent_guidance.get(intent, "")
        
        return base_instructions + specific_guidance
    
    def _build_evidence_section(self, evidence: List[InvestigationEvidence]) -> str:
        """Build the evidence section of the prompt."""
        if not evidence:
            return "## REPOSITORY EVIDENCE\n\nNo evidence was retrieved for this question."
        
        evidence_parts = ["## REPOSITORY EVIDENCE"]
        evidence_parts.append(f"\nTotal evidence items: {len(evidence)}\n")
        
        for i, item in enumerate(evidence, 1):
            evidence_parts.append(f"### Evidence #{i} (ID: {item.evidence_id})")
            evidence_parts.append(f"- **Type**: {item.evidence_type.value}")
            evidence_parts.append(f"- **Source**: {item.retrieval_source}")
            
            if item.file_path:
                location = f"{item.file_path}"
                if item.start_line and item.end_line:
                    location += f" (lines {item.start_line}-{item.end_line})"
                evidence_parts.append(f"- **Location**: {location}")
            
            if item.symbol_name:
                evidence_parts.append(f"- **Symbol**: {item.symbol_name} ({item.symbol_type})")
            
            if item.api_endpoint_method and item.api_endpoint_path:
                evidence_parts.append(f"- **Endpoint**: {item.api_endpoint_method} {item.api_endpoint_path}")
            
            if item.retrieval_score:
                evidence_parts.append(f"- **Relevance**: {item.retrieval_score:.2f}")
            
            evidence_parts.append(f"\n**Content**:\n```\n{item.content}\n```\n")
        
        return "\n".join(evidence_parts)
    
    def _build_context_section(self, context: Dict[str, Any]) -> str:
        """Build conversation context section."""
        parts = ["## CONVERSATION CONTEXT"]
        
        if context.get("last_question"):
            parts.append(f"\nPrevious question: {context['last_question']}")
        
        if context.get("last_symbols"):
            symbols = ", ".join([s.get("name", "") for s in context["last_symbols"][:3]])
            parts.append(f"Recently discussed symbols: {symbols}")
        
        if context.get("last_files"):
            files = ", ".join(context["last_files"][:3])
            parts.append(f"Recently discussed files: {files}")
        
        if context.get("last_endpoints"):
            endpoints = ", ".join([
                f"{e.get('method', '')} {e.get('path', '')}"
                for e in context["last_endpoints"][:3]
            ])
            parts.append(f"Recently discussed endpoints: {endpoints}")
        
        return "\n".join(parts)
    
    def _build_output_format(self, max_follow_ups: int) -> str:
        """Build output format requirements."""
        return f"""## OUTPUT FORMAT

Provide your response in the following JSON format:

```json
{{
  "answer": "Your comprehensive answer here",
  "claims": [
    {{
      "claim_text": "Specific claim about the repository",
      "certainty": "confirmed|inferred|uncertain",
      "evidence_ids": ["evidence_id_1", "evidence_id_2"],
      "reasoning": "Why this claim is made"
    }}
  ],
  "limitations": [
    "Explicit limitation or missing evidence"
  ],
  "follow_up_questions": [
    {{
      "question": "Suggested follow-up question",
      "rationale": "Why this is a useful next step",
      "related_evidence_ids": ["evidence_id"]
    }}
  ]
}}
```

## REQUIREMENTS

- **answer**: Comprehensive explanation grounded in evidence
- **claims**: Individual claims with certainty levels (at least 1-5 claims)
- **limitations**: Explicit gaps in evidence or analysis (if any)
- **follow_up_questions**: Useful next investigation steps (maximum {max_follow_ups})

## CERTAINTY LEVELS

- **confirmed**: Direct evidence from static analysis (function definitions, call relationships, imports)
- **inferred**: Reasonable inference from evidence (likely behavior, common patterns)
- **uncertain**: Insufficient evidence to confirm (acknowledge this explicitly)

## EVIDENCE CITATION

Every claim should reference at least one evidence ID. Use the exact evidence IDs provided above (e.g., "evidence_1", "evidence_2").

Begin your response:"""
    
    def parse_investigation_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse structured JSON response from LLM.
        
        Args:
            response_text: Raw LLM response
        
        Returns:
            Parsed dictionary or None if parsing fails
        """
        try:
            # Try to extract JSON from response
            # LLM might wrap it in markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.warning("No JSON found in LLM response")
                    return None
            
            parsed = json.loads(json_str)
            
            # Validate required fields
            required_fields = ["answer", "claims", "limitations", "follow_up_questions"]
            if not all(field in parsed for field in required_fields):
                logger.warning(f"Missing required fields in LLM response: {parsed.keys()}")
                return None
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing LLM response: {e}")
            return None


# Import re for JSON extraction
import re
