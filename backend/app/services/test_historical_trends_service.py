"""
Historical trends analysis service for Phase 20: Test Results & Failure Intelligence.

This service analyzes test run history to identify:
- Repeated failures across runs
- Tests that changed from passing to failing
- Tests that changed from failing to passing
- Duration changes
- Potentially flaky tests (with sufficient evidence)
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import TestRun, TestCase, TestOutcome

logger = logging.getLogger(__name__)


class TestTrend:
    """Represents a historical trend for a test."""
    
    def __init__(
        self,
        test_name: str,
        trend_type: str,
        description: str,
        runs_analyzed: int,
        evidence: List[str],
        confidence: str
    ):
        self.test_name = test_name
        self.trend_type = trend_type
        self.description = description
        self.runs_analyzed = runs_analyzed
        self.evidence = evidence
        self.confidence = confidence


class HistoricalTrendsService:
    """
    Service for analyzing historical test trends.
    
    Compares test outcomes across multiple runs to identify patterns.
    """
    
    # Minimum runs required for flaky test detection
    MIN_RUNS_FOR_FLAKY_DETECTION = 5
    
    # Flaky threshold: must have both passes and failures
    FLAKY_THRESHOLD = 0.2  # At least 20% of each outcome
    
    def __init__(self, db: Session):
        """
        Initialize service.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def analyze_trends(
        self,
        repository_id: UUID,
        test_run_id: UUID,
        lookback_days: int = 30,
        max_historical_runs: int = 50
    ) -> List[TestTrend]:
        """
        Analyze historical trends for a test run.
        
        Args:
            repository_id: Repository UUID
            test_run_id: Current test run UUID
            lookback_days: Days to look back (default 30)
            max_historical_runs: Maximum historical runs to analyze
            
        Returns:
            List of TestTrend objects
        """
        # Get current test run
        current_run = (
            self.db.query(TestRun)
            .filter(
                TestRun.id == test_run_id,
                TestRun.repository_id == repository_id
            )
            .first()
        )
        
        if not current_run:
            logger.warning(f"Test run {test_run_id} not found")
            return []
        
        # Get historical runs (excluding current)
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        historical_runs = (
            self.db.query(TestRun)
            .filter(
                TestRun.repository_id == repository_id,
                TestRun.id != test_run_id,
                TestRun.imported_at >= cutoff_date
            )
            .order_by(TestRun.imported_at.desc())
            .limit(max_historical_runs)
            .all()
        )
        
        if not historical_runs:
            logger.info(f"No historical runs found for repository {repository_id}")
            return []
        
        logger.info(f"Analyzing {len(historical_runs)} historical runs")
        
        # Get test cases for current run
        current_cases = (
            self.db.query(TestCase)
            .filter(TestCase.test_run_id == test_run_id)
            .all()
        )
        
        # Get test cases for historical runs
        historical_run_ids = [r.id for r in historical_runs]
        historical_cases = (
            self.db.query(TestCase)
            .filter(TestCase.test_run_id.in_(historical_run_ids))
            .all()
        )
        
        # Build history map: test_name -> list of (run_id, outcome, duration)
        history_map = self._build_history_map(historical_cases)
        
        # Analyze each current test case
        trends = []
        
        for current_case in current_cases:
            test_trends = self._analyze_test_history(
                current_case=current_case,
                history=history_map.get(current_case.full_name, []),
                total_runs=len(historical_runs)
            )
            trends.extend(test_trends)
        
        logger.info(f"Found {len(trends)} trends")
        
        return trends
    
    def _build_history_map(
        self,
        historical_cases: List[TestCase]
    ) -> Dict[str, List[tuple]]:
        """
        Build map of test name to historical outcomes.
        
        Args:
            historical_cases: List of historical TestCase instances
            
        Returns:
            Dict mapping test_name to list of (run_id, outcome, duration_ms)
        """
        history_map = {}
        
        for case in historical_cases:
            if case.full_name not in history_map:
                history_map[case.full_name] = []
            
            history_map[case.full_name].append((
                case.test_run_id,
                case.outcome,
                case.duration_ms
            ))
        
        return history_map
    
    def _analyze_test_history(
        self,
        current_case: TestCase,
        history: List[tuple],
        total_runs: int
    ) -> List[TestTrend]:
        """
        Analyze history for a single test.
        
        Args:
            current_case: Current TestCase
            history: List of (run_id, outcome, duration_ms) tuples
            total_runs: Total number of historical runs analyzed
            
        Returns:
            List of TestTrend objects
        """
        trends = []
        
        if not history:
            # New test
            if current_case.outcome == TestOutcome.FAILED:
                trends.append(TestTrend(
                    test_name=current_case.full_name,
                    trend_type="new_test_failure",
                    description="New test failed on first appearance",
                    runs_analyzed=1,
                    evidence=["Test not seen in historical runs"],
                    confidence="medium"
                ))
            return trends
        
        # Count outcomes
        outcome_counts = {}
        recent_outcomes = []
        durations = []
        
        for run_id, outcome, duration in history:
            outcome_str = outcome.value if hasattr(outcome, 'value') else str(outcome)
            outcome_counts[outcome_str] = outcome_counts.get(outcome_str, 0) + 1
            recent_outcomes.append(outcome_str)
            if duration:
                durations.append(duration)
        
        # Check for repeated failures
        if current_case.outcome in (TestOutcome.FAILED, TestOutcome.ERROR):
            failed_count = outcome_counts.get('failed', 0) + outcome_counts.get('error', 0)
            
            if failed_count >= 2:
                trends.append(TestTrend(
                    test_name=current_case.full_name,
                    trend_type="repeated_failure",
                    description=f"Test failed in {failed_count + 1} of last {len(history) + 1} runs",
                    runs_analyzed=len(history) + 1,
                    evidence=[f"Failed in current run and {failed_count} historical runs"],
                    confidence="high"
                ))
        
        # Check for status transitions
        if len(recent_outcomes) > 0:
            most_recent = recent_outcomes[0]  # Most recent historical outcome
            current_outcome = current_case.outcome.value
            
            if most_recent == 'passed' and current_outcome in ('failed', 'error'):
                trends.append(TestTrend(
                    test_name=current_case.full_name,
                    trend_type="regression",
                    description="Test changed from passing to failing",
                    runs_analyzed=len(history) + 1,
                    evidence=[f"Previously passed, now {current_outcome}"],
                    confidence="high"
                ))
            
            elif most_recent in ('failed', 'error') and current_outcome == 'passed':
                trends.append(TestTrend(
                    test_name=current_case.full_name,
                    trend_type="fixed",
                    description="Test changed from failing to passing",
                    runs_analyzed=len(history) + 1,
                    evidence=[f"Previously {most_recent}, now passed"],
                    confidence="high"
                ))
        
        # Check for flaky tests (requires sufficient history)
        if len(history) >= self.MIN_RUNS_FOR_FLAKY_DETECTION:
            passed_count = outcome_counts.get('passed', 0)
            failed_count = outcome_counts.get('failed', 0) + outcome_counts.get('error', 0)
            total_outcomes = passed_count + failed_count
            
            if total_outcomes >= self.MIN_RUNS_FOR_FLAKY_DETECTION:
                passed_ratio = passed_count / total_outcomes
                failed_ratio = failed_count / total_outcomes
                
                # Test is potentially flaky if it has significant both outcomes
                if passed_ratio >= self.FLAKY_THRESHOLD and failed_ratio >= self.FLAKY_THRESHOLD:
                    trends.append(TestTrend(
                        test_name=current_case.full_name,
                        trend_type="potentially_flaky",
                        description=f"Test has inconsistent outcomes: {passed_count}P/{failed_count}F",
                        runs_analyzed=len(history),
                        evidence=[
                            f"Passed {passed_count} times ({passed_ratio:.0%})",
                            f"Failed {failed_count} times ({failed_ratio:.0%})"
                        ],
                        confidence="medium"
                    ))
        
        # Check for duration changes (if current test passed and has duration)
        if current_case.outcome == TestOutcome.PASSED and current_case.duration_ms and durations:
            # Compare with median historical duration
            durations.sort()
            median_duration = durations[len(durations) // 2]
            
            if current_case.duration_ms > median_duration * 2:
                trends.append(TestTrend(
                    test_name=current_case.full_name,
                    trend_type="duration_increase",
                    description=f"Test duration increased significantly: {current_case.duration_ms}ms vs {median_duration}ms median",
                    runs_analyzed=len(durations),
                    evidence=[f"Current: {current_case.duration_ms}ms, Median: {median_duration}ms"],
                    confidence="medium"
                ))
        
        return trends
