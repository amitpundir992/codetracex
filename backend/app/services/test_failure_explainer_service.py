"""
Failure explanation service for Phase 20: Test Results & Failure Intelligence.

This service uses Phase 12 LLM infrastructure to generate grounded explanations
of test failures based on explicit evidence.

The LLM receives:
- Test failure information
- Failure classification
- Code correlation evidence
- Historical trends

The LLM does NOT receive:
- Source code (unless explicitly provided as evidence)
- API keys or secrets
- Arbitrary repository access
"""
import logging
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import TestCase, TestRun
from app.services.llm.provider import LLMProvider, LLMRequest, LLMProviderError
from app.services.test_failure_correlation_service import (
    TestFailureCorrelationService,
    FailureCorrelation
)
from app.services.test_historical_trends_service import (
    HistoricalTrendsService,
    TestTrend
)

logger = logging.getLogger(__name__)


class FailureExplanation:
    """LLM-generated explanation of test failure."""
    
    def __init__(
        self,
        test_name: str,
        failure_summary: str,
        potential_causes: str,
        investigation_steps: str,
        related_changes: str,
        uncertainty: str
    ):
        self.test_name = test_name
        self.failure_summary = failure_summary
        self.potential_causes = potential_causes
        self.investigation_steps = investigation_steps
        self.related_changes = related_changes
        self.uncertainty = uncertainty


class TestFailureExplainerService:
    """
    Service for generating LLM-powered test failure explanations.
    
    Reuses Phase 12 LLM infrastructure with grounded prompting.
    """
    
    def __init__(
        self,
        db: Session,
        llm_provider: LLMProvider
    ):
        """
        Initialize service.
        
        Args:
            db: Database session
            llm_provider: LLM provider instance
        """
        self.db = db
        self.llm_provider = llm_provider
        self.correlation_service = TestFailureCorrelationService(db)
        self.trends_service = HistoricalTrendsService(db)
    
    def explain_failure(
        self,
        test_case_id: UUID,
        repository_id: UUID,
        include_correlations: bool = True,
        include_trends: bool = True
    ) -> Optional[FailureExplanation]:
        """
        Generate explanation for a test failure.
        
        Args:
            test_case_id: TestCase UUID
            repository_id: Repository UUID
            include_correlations: Include code change correlations
            include_trends: Include historical trends
            
        Returns:
            FailureExplanation or None
        """
        # Get test case
        test_case = (
            self.db.query(TestCase)
            .join(TestRun)
            .filter(
                TestCase.id == test_case_id,
                TestRun.repository_id == repository_id
            )
            .first()
        )
        
        if not test_case:
            logger.warning(f"Test case {test_case_id} not found")
            return None
        
        if test_case.outcome.value not in ('failed', 'error'):
            logger.warning(f"Test case {test_case_id} did not fail")
            return None
        
        # Gather evidence
        correlations = []
        trends = []
        
        if include_correlations and test_case.test_run.commit_id:
            try:
                correlations = self.correlation_service.correlate_failures_with_commit(
                    test_run_id=test_case.test_run_id,
                    repository_id=repository_id,
                    commit_sha=test_case.test_run.commit.sha,
                    analysis_run_id=test_case.test_run.analysis_run_id
                )
                # Filter to this test
                correlations = [c for c in correlations if c.test_case_id == test_case_id]
            except Exception as e:
                logger.warning(f"Failed to get correlations: {e}")
        
        if include_trends:
            try:
                all_trends = self.trends_service.analyze_trends(
                    repository_id=repository_id,
                    test_run_id=test_case.test_run_id
                )
                # Filter to this test
                trends = [t for t in all_trends if t.test_name == test_case.full_name]
            except Exception as e:
                logger.warning(f"Failed to get trends: {e}")
        
        # Build prompt
        prompt = self._build_prompt(test_case, correlations, trends)
        
        # Generate explanation
        try:
            llm_request = LLMRequest(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3
            )
            
            response = self.llm_provider.generate(llm_request)
            
            if response.is_empty():
                logger.warning("LLM returned empty response")
                return None
            
            # Parse response
            explanation = self._parse_response(test_case.full_name, response.content)
            
            return explanation
        
        except LLMProviderError as e:
            logger.error(f"LLM provider error: {e}")
            return None
    
    def _build_prompt(
        self,
        test_case: TestCase,
        correlations: List[FailureCorrelation],
        trends: List[TestTrend]
    ) -> str:
        """
        Build grounded prompt for LLM.
        
        Args:
            test_case: TestCase instance
            correlations: List of FailureCorrelation
            trends: List of TestTrend
            
        Returns:
            Prompt string
        """
        sections = []
        
        # System instructions
        sections.append("""You are a test failure analysis assistant. Your goal is to explain test failures based ONLY on the evidence provided.

CRITICAL RULES:
- Use ONLY the evidence provided below
- DO NOT invent source code, file contents, or test details
- Distinguish confirmed facts from probable causes
- State when evidence is insufficient
- Do NOT claim to know what the code does unless evidence shows it
- Do NOT recommend fixes unless the evidence supports them""")
        
        sections.append("\n\n## Test Failure Information\n")
        sections.append(f"Test Name: {test_case.full_name}\n")
        sections.append(f"Outcome: {test_case.outcome.value}\n")
        sections.append(f"Suite: {test_case.suite_name}\n")
        
        if test_case.failure_type:
            sections.append(f"Failure Type: {test_case.failure_type}\n")
        
        if test_case.failure_message:
            sections.append(f"\nFailure Message:\n{test_case.failure_message[:500]}\n")
        
        if test_case.failure_classification:
            sections.append(f"\nClassification: {test_case.failure_classification.value}\n")
            sections.append(f"Confidence: {test_case.classification_confidence}\n")
            if test_case.classification_evidence:
                sections.append(f"Evidence: {test_case.classification_evidence}\n")
        
        if test_case.failure_stacktrace:
            sections.append(f"\nStack Trace (truncated):\n{test_case.failure_stacktrace[:1000]}\n")
        
        # Code correlations
        if correlations:
            sections.append("\n\n## Code Change Correlations\n")
            for corr in correlations:
                sections.append(f"\nCorrelation Type: {corr.correlation_type}\n")
                sections.append(f"Confidence: {corr.confidence}\n")
                sections.append(f"Changed Files: {', '.join(corr.changed_files)}\n")
                if corr.changed_symbols:
                    sections.append(f"Changed Symbols: {', '.join(corr.changed_symbols)}\n")
                sections.append("Evidence:\n")
                for evidence in corr.evidence:
                    sections.append(f"- {evidence}\n")
        else:
            sections.append("\n\n## Code Change Correlations\n")
            sections.append("No code change correlations available.\n")
        
        # Historical trends
        if trends:
            sections.append("\n\n## Historical Trends\n")
            for trend in trends:
                sections.append(f"\nTrend: {trend.trend_type}\n")
                sections.append(f"Description: {trend.description}\n")
                sections.append(f"Runs Analyzed: {trend.runs_analyzed}\n")
                sections.append(f"Confidence: {trend.confidence}\n")
                sections.append("Evidence:\n")
                for evidence in trend.evidence:
                    sections.append(f"- {evidence}\n")
        else:
            sections.append("\n\n## Historical Trends\n")
            sections.append("No historical data available.\n")
        
        # Task
        sections.append("\n\n## Task\n")
        sections.append("""Based ONLY on the evidence above, provide:

1. FAILURE SUMMARY: Brief summary of what happened
2. POTENTIAL CAUSES: Possible causes based on evidence (mark speculations clearly)
3. INVESTIGATION STEPS: What to investigate next
4. RELATED CHANGES: How code changes might relate (if correlation evidence exists)
5. UNCERTAINTY: What is unclear or unknown

Format your response as:

FAILURE SUMMARY:
[your summary]

POTENTIAL CAUSES:
[your analysis]

INVESTIGATION STEPS:
[your steps]

RELATED CHANGES:
[your analysis or "None identified"]

UNCERTAINTY:
[what is unclear]""")
        
        return ''.join(sections)
    
    def _parse_response(self, test_name: str, content: str) -> FailureExplanation:
        """
        Parse LLM response into FailureExplanation.
        
        Args:
            test_name: Test name
            content: LLM response content
            
        Returns:
            FailureExplanation
        """
        # Extract sections
        sections = {
            'FAILURE SUMMARY': '',
            'POTENTIAL CAUSES': '',
            'INVESTIGATION STEPS': '',
            'RELATED CHANGES': '',
            'UNCERTAINTY': ''
        }
        
        current_section = None
        lines = content.split('\n')
        
        for line in lines:
            line_upper = line.strip().upper()
            if line_upper.endswith(':'):
                section_name = line_upper[:-1]
                if section_name in sections:
                    current_section = section_name
                    continue
            
            if current_section:
                sections[current_section] += line + '\n'
        
        return FailureExplanation(
            test_name=test_name,
            failure_summary=sections['FAILURE SUMMARY'].strip(),
            potential_causes=sections['POTENTIAL CAUSES'].strip(),
            investigation_steps=sections['INVESTIGATION STEPS'].strip(),
            related_changes=sections['RELATED CHANGES'].strip(),
            uncertainty=sections['UNCERTAINTY'].strip()
        )
