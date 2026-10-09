"""
Test Intelligence Explainer for Phase 19: CI & Test Intelligence.

This service provides LLM-powered explanations of test intelligence findings.

Architecture Philosophy:

    GROUNDED TEST EXPLANATIONS
    
    This service generates human-readable explanations of:
    - Why tests are affected
    - Why coverage gaps exist
    - What CI checks will run
    - What to test locally
    - What reviewers should focus on
    
    It does NOT:
    - Invent test relationships
    - Suggest test implementations
    - Make up CI behavior
    
    All explanations are grounded in deterministic evidence.
    
    Flow:
    1. Receive test intelligence data (deterministic)
    2. Build context from evidence
    3. Generate prompt with evidence
    4. Get LLM explanation
    5. Validate against evidence

Grounding Contract:

    The LLM MUST only explain evidence provided.
    The LLM MUST NOT invent tests, CI jobs, or commands.
    The LLM MUST indicate uncertainty when evidence is lacking.
"""
import logging
from typing import List, Optional
from uuid import UUID

from app.schemas.test_intelligence import (
    TestIntelligenceResponse,
    TestExplainResponse,
    AffectedTest,
    UncoveredArea,
    RelevantCICheck,
    LocalTestRecommendation
)
from app.services.llm.provider import LLMProvider, LLMRequest, LLMProviderError
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TestIntelligenceExplainer:
    """
    Service for generating LLM explanations of test intelligence.
    
    Generates grounded explanations of test impact, coverage, and recommendations.
    """
    
    def __init__(self, llm_provider: LLMProvider):
        """
        Initialize test intelligence explainer.
        
        Args:
            llm_provider: LLM provider for generation
        """
        self.llm_provider = llm_provider
        self.settings = get_settings()
    
    def explain_test_intelligence(
        self,
        test_intelligence: TestIntelligenceResponse,
        changed_files: List[str],
        focus_area: Optional[str] = None
    ) -> TestExplainResponse:
        """
        Generate LLM explanation of test intelligence.
        
        Args:
            test_intelligence: Test intelligence data
            changed_files: List of changed file paths
            focus_area: Optional specific area to focus on
            
        Returns:
            Test explanation response
        """
        # Build context from evidence
        context = self._build_context(
            test_intelligence,
            changed_files
        )
        
        # Build prompt
        prompt = self._build_prompt(
            context,
            test_intelligence,
            focus_area
        )
        
        # Generate explanation
        try:
            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for factual explanations
                max_tokens=2000
            )
            
            response = self.llm_provider.generate(request)
            
            # Parse response into sections
            sections = self._parse_response(response.text)
            
            return TestExplainResponse(
                test_impact_summary=sections.get('impact', ''),
                affected_tests_explanation=sections.get('affected_tests', ''),
                coverage_gaps_explanation=sections.get('coverage_gaps', ''),
                ci_recommendations=sections.get('ci_recommendations', ''),
                local_testing_guidance=sections.get('local_testing', ''),
                reviewer_testing_focus=sections.get('reviewer_focus', ''),
                uncertainty=sections.get('uncertainty', '')
            )
        
        except LLMProviderError as e:
            logger.error(f"LLM provider error in test intelligence explainer: {e}")
            # Return fallback response
            return self._fallback_response(test_intelligence)
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt for test intelligence explanation.
        
        Returns:
            System prompt string
        """
        return """You are a test intelligence expert analyzing code changes and test coverage.

Your task is to explain test impact, coverage, and recommendations based ONLY on the evidence provided.

CRITICAL RULES:
1. Only reference tests, files, and CI checks explicitly provided in the evidence
2. Do NOT invent test names, file paths, or CI workflows
3. If evidence is insufficient, explicitly state uncertainty
4. Use technical language appropriate for developers
5. Be concise but thorough

Provide explanations in these sections:
- IMPACT: High-level summary of test impact
- AFFECTED_TESTS: Why specific tests are affected
- COVERAGE_GAPS: Why certain areas lack test coverage
- CI_RECOMMENDATIONS: What CI checks will run and why
- LOCAL_TESTING: Specific commands to run locally
- REVIEWER_FOCUS: What reviewers should pay attention to
- UNCERTAINTY: Areas where evidence is insufficient

Format your response with section headers like:
## IMPACT
... content ...

## AFFECTED_TESTS
... content ...
"""
    
    def _build_context(
        self,
        test_intelligence: TestIntelligenceResponse,
        changed_files: List[str]
    ) -> str:
        """
        Build context string from test intelligence data.
        
        Args:
            test_intelligence: Test intelligence data
            changed_files: Changed file paths
            
        Returns:
            Context string
        """
        lines = []
        
        # Changed files
        lines.append("## CHANGED FILES")
        for file_path in changed_files[:10]:  # Limit to 10
            lines.append(f"- {file_path}")
        if len(changed_files) > 10:
            lines.append(f"... and {len(changed_files) - 10} more files")
        lines.append("")
        
        # Affected tests
        if test_intelligence.affected_tests:
            lines.append("## AFFECTED TESTS")
            for test in test_intelligence.affected_tests[:15]:  # Limit to 15
                lines.append(f"- Test: {test.test_file}")
                if test.test_name:
                    lines.append(f"  Function: {test.test_name}")
                lines.append(f"  Coverage Type: {test.coverage_type.value}")
                lines.append(f"  Confidence: {test.confidence}")
                if test.evidence:
                    lines.append(f"  Evidence: {'; '.join(test.evidence[:2])}")
                if test.changed_symbols:
                    lines.append(f"  Changed Symbols: {', '.join(test.changed_symbols[:3])}")
            if len(test_intelligence.affected_tests) > 15:
                lines.append(f"... and {len(test_intelligence.affected_tests) - 15} more tests")
            lines.append("")
        
        # Uncovered areas
        if test_intelligence.uncovered_areas:
            lines.append("## UNCOVERED AREAS")
            for area in test_intelligence.uncovered_areas[:10]:
                lines.append(f"- File: {area.file_path}")
                lines.append(f"  Severity: {area.severity}")
                lines.append(f"  Symbols: {', '.join(area.changed_symbols[:5])}")
                lines.append(f"  Explanation: {area.explanation}")
            if len(test_intelligence.uncovered_areas) > 10:
                lines.append(f"... and {len(test_intelligence.uncovered_areas) - 10} more uncovered areas")
            lines.append("")
        
        # CI checks
        if test_intelligence.relevant_ci_checks:
            lines.append("## RELEVANT CI CHECKS")
            for check in test_intelligence.relevant_ci_checks[:10]:
                lines.append(f"- Workflow: {check.workflow_file}")
                lines.append(f"  Job: {check.job_name}")
                lines.append(f"  Relevance: {check.relevance}")
                lines.append(f"  Confidence: {check.confidence}")
                if check.evidence:
                    lines.append(f"  Evidence: {'; '.join(check.evidence[:2])}")
            lines.append("")
        
        # Local recommendations
        if test_intelligence.local_test_recommendations:
            lines.append("## LOCAL TEST RECOMMENDATIONS")
            for rec in test_intelligence.local_test_recommendations[:10]:
                lines.append(f"- Command: {rec.command}")
                lines.append(f"  Priority: {rec.priority}")
                lines.append(f"  Reason: {rec.reason}")
            lines.append("")
        
        # Summary statistics
        lines.append("## STATISTICS")
        lines.append(f"- Total test files in repository: {test_intelligence.total_test_files}")
        lines.append(f"- Affected tests: {len(test_intelligence.affected_tests)}")
        lines.append(f"- Uncovered areas: {len(test_intelligence.uncovered_areas)}")
        lines.append(f"- Relevant CI checks: {len(test_intelligence.relevant_ci_checks)}")
        
        return '\n'.join(lines)
    
    def _build_prompt(
        self,
        context: str,
        test_intelligence: TestIntelligenceResponse,
        focus_area: Optional[str]
    ) -> str:
        """
        Build prompt for LLM.
        
        Args:
            context: Context string
            test_intelligence: Test intelligence data
            focus_area: Optional focus area
            
        Returns:
            Prompt string
        """
        lines = []
        
        lines.append("Analyze the following test intelligence data and provide a comprehensive explanation.")
        lines.append("")
        lines.append("EVIDENCE:")
        lines.append(context)
        lines.append("")
        
        if focus_area:
            lines.append(f"FOCUS AREA: Pay special attention to {focus_area}")
            lines.append("")
        
        lines.append("Provide your analysis in the structured format specified in the system prompt.")
        lines.append("Remember: Only reference evidence provided above. Do not invent tests, files, or CI workflows.")
        
        return '\n'.join(lines)
    
    def _parse_response(self, response_text: str) -> dict:
        """
        Parse LLM response into sections.
        
        Args:
            response_text: LLM response text
            
        Returns:
            Dictionary mapping section names to content
        """
        sections = {}
        
        # Define section mappings
        section_patterns = {
            'impact': r'##\s*IMPACT\s*\n(.*?)(?=##|$)',
            'affected_tests': r'##\s*AFFECTED[_\s]TESTS\s*\n(.*?)(?=##|$)',
            'coverage_gaps': r'##\s*COVERAGE[_\s]GAPS\s*\n(.*?)(?=##|$)',
            'ci_recommendations': r'##\s*CI[_\s]RECOMMENDATIONS\s*\n(.*?)(?=##|$)',
            'local_testing': r'##\s*LOCAL[_\s]TESTING\s*\n(.*?)(?=##|$)',
            'reviewer_focus': r'##\s*REVIEWER[_\s]FOCUS\s*\n(.*?)(?=##|$)',
            'uncertainty': r'##\s*UNCERTAINTY\s*\n(.*?)(?=##|$)'
        }
        
        import re
        
        for key, pattern in section_patterns.items():
            match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                sections[key] = content
            else:
                sections[key] = ""
        
        return sections
    
    def _fallback_response(
        self,
        test_intelligence: TestIntelligenceResponse
    ) -> TestExplainResponse:
        """
        Generate fallback response when LLM fails.
        
        Args:
            test_intelligence: Test intelligence data
            
        Returns:
            Fallback explanation
        """
        return TestExplainResponse(
            test_impact_summary=test_intelligence.summary,
            affected_tests_explanation=f"{len(test_intelligence.affected_tests)} tests affected by changes",
            coverage_gaps_explanation=f"{len(test_intelligence.uncovered_areas)} areas without obvious test coverage",
            ci_recommendations=f"{len(test_intelligence.relevant_ci_checks)} CI checks will run",
            local_testing_guidance="Run affected tests before opening PR",
            reviewer_testing_focus="Review test coverage for changed areas",
            uncertainty="LLM explanation unavailable; showing deterministic analysis only"
        )
