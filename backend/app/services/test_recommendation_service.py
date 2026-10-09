"""
Test Recommendation Service for Phase 19: CI & Test Intelligence.

This service orchestrates test detection, coverage analysis, and CI intelligence
to provide actionable test recommendations.

Architecture Philosophy:

    EVIDENCE-BASED TEST RECOMMENDATIONS
    
    This service combines:
    - Test Detection (which tests exist)
    - Coverage Analysis (which tests are affected)
    - CI Intelligence (which workflows run tests)
    
    To provide:
    - Tests to run locally
    - Expected CI checks
    - Coverage gaps
    - Prioritized recommendations
    
    It does NOT:
    - Invent tests
    - Suggest test implementation
    - Generate test code
    
    Flow:
    1. Detect all tests in repository
    2. Map changes to affected tests
    3. Analyze CI workflows
    4. Build recommendations with evidence
    5. Prioritize by confidence/impact

Repository Isolation:

    All operations scoped by repository_id.
    Recommendations are deterministic.
"""
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from app.schemas.change_analysis import ChangedFile, ChangedSymbol
from app.schemas.test_intelligence import (
    TestIntelligenceResponse,
    AffectedTest,
    UncoveredArea,
    LocalTestRecommendation,
    CIJob,
    RelevantCICheck,
    TestCoverageType
)
from app.services.test_detection_service import TestDetectionService
from app.services.test_coverage_analyzer import TestCoverageAnalyzer
from app.services.ci_intelligence_service import CIIntelligenceService

logger = logging.getLogger(__name__)


class TestRecommendationService:
    """
    Service for building test recommendations with evidence.
    
    Orchestrates test intelligence components.
    """
    
    def __init__(self, db: Session):
        """
        Initialize test recommendation service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.test_detector = TestDetectionService(db)
        self.coverage_analyzer = TestCoverageAnalyzer(db)
        self.ci_intelligence = CIIntelligenceService(db)
    
    def analyze_test_intelligence(
        self,
        repository_id: UUID,
        base_sha: str,
        head_sha: str,
        changed_files: List[ChangedFile],
        changed_symbols: List[ChangedSymbol],
        include_ci_analysis: bool = True,
        include_local_recommendations: bool = True,
        analysis_run_id: Optional[UUID] = None
    ) -> TestIntelligenceResponse:
        """
        Comprehensive test intelligence analysis.
        
        Args:
            repository_id: Repository UUID
            base_sha: Base commit SHA
            head_sha: Head commit SHA
            changed_files: List of changed files
            changed_symbols: List of changed symbols
            include_ci_analysis: Include CI workflow analysis
            include_local_recommendations: Include local test recommendations
            analysis_run_id: Optional analysis run UUID
            
        Returns:
            Complete test intelligence response
        """
        # Detect all test files
        all_test_files = self.test_detector.get_test_files(
            repository_id,
            analysis_run_id
        )
        total_test_files = len(all_test_files)
        
        # Analyze test coverage
        affected_tests, uncovered_areas = self.coverage_analyzer.analyze_test_coverage(
            repository_id,
            changed_files,
            changed_symbols,
            analysis_run_id
        )
        
        # CI analysis
        ci_jobs = []
        relevant_ci_checks = []
        if include_ci_analysis:
            ci_analysis = self.ci_intelligence.analyze_ci_for_changes(
                repository_id,
                changed_files,
                analysis_run_id
            )
            ci_jobs = ci_analysis['ci_jobs']
            relevant_ci_checks = ci_analysis['relevant_ci_checks']
        
        # Local test recommendations
        local_recommendations = []
        if include_local_recommendations:
            local_recommendations = self._build_local_recommendations(
                affected_tests,
                changed_files
            )
        
        # Build evidence
        evidence = self._collect_evidence(
            affected_tests,
            uncovered_areas,
            relevant_ci_checks
        )
        
        # Generate summary
        summary = self._generate_summary(
            affected_tests,
            uncovered_areas,
            relevant_ci_checks
        )
        
        return TestIntelligenceResponse(
            base_sha=base_sha,
            head_sha=head_sha,
            total_test_files=total_test_files,
            affected_tests=affected_tests,
            uncovered_areas=uncovered_areas,
            ci_jobs=ci_jobs,
            relevant_ci_checks=relevant_ci_checks,
            local_test_recommendations=local_recommendations,
            evidence=evidence,
            summary=summary
        )
    
    def _build_local_recommendations(
        self,
        affected_tests: List[AffectedTest],
        changed_files: List[ChangedFile]
    ) -> List[LocalTestRecommendation]:
        """
        Build local test recommendations.
        
        Args:
            affected_tests: Affected tests
            changed_files: Changed files
            
        Returns:
            List of local test recommendations
        """
        recommendations = []
        
        # Group tests by file and priority
        high_priority_tests = []
        medium_priority_tests = []
        low_priority_tests = []
        
        for test in affected_tests:
            if test.confidence == "high":
                if test.coverage_type == TestCoverageType.DIRECT_IMPORT:
                    high_priority_tests.append(test)
                else:
                    medium_priority_tests.append(test)
            else:
                low_priority_tests.append(test)
        
        # Build recommendations for high priority
        test_files_covered = set()
        
        if high_priority_tests:
            test_files = sorted(set(t.test_file for t in high_priority_tests))
            
            for test_file in test_files:
                # Determine command based on file extension
                command = self._suggest_test_command(test_file)
                
                # Get changed symbols for this test
                relevant_symbols = [
                    t.changed_symbols for t in high_priority_tests
                    if t.test_file == test_file
                ]
                flat_symbols = [s for sublist in relevant_symbols for s in sublist]
                
                if flat_symbols:
                    reason = f"Tests symbols directly modified: {', '.join(flat_symbols[:3])}"
                else:
                    reason = "Tests code directly affected by changes"
                
                recommendations.append(LocalTestRecommendation(
                    command=command,
                    reason=reason,
                    priority="high",
                    test_files=[test_file]
                ))
                
                test_files_covered.add(test_file)
        
        # Build recommendations for medium priority (grouped)
        if medium_priority_tests:
            medium_test_files = sorted(set(
                t.test_file for t in medium_priority_tests
                if t.test_file not in test_files_covered
            ))
            
            # Group by language/framework
            grouped = self._group_test_files_by_type(medium_test_files)
            
            for test_type, files in grouped.items():
                command = self._suggest_batch_test_command(files, test_type)
                
                recommendations.append(LocalTestRecommendation(
                    command=command,
                    reason=f"Tests modules affected by changes",
                    priority="medium",
                    test_files=files[:5]  # Limit listed files
                ))
        
        # Add general test recommendation if no specific tests found
        if not recommendations and changed_files:
            # Suggest running all tests
            source_languages = {f.language for f in changed_files if f.is_source and f.language}
            
            if 'Python' in source_languages:
                recommendations.append(LocalTestRecommendation(
                    command="pytest tests/ -v",
                    reason="No specific test coverage detected; run full test suite",
                    priority="medium",
                    test_files=[]
                ))
            
            if 'JavaScript' in source_languages or 'TypeScript' in source_languages:
                recommendations.append(LocalTestRecommendation(
                    command="npm test",
                    reason="No specific test coverage detected; run full test suite",
                    priority="medium",
                    test_files=[]
                ))
        
        return recommendations
    
    def _suggest_test_command(self, test_file: str) -> str:
        """
        Suggest test command for a file.
        
        Args:
            test_file: Test file path
            
        Returns:
            Suggested command
        """
        ext = test_file.split('.')[-1].lower()
        
        if ext == 'py':
            return f"pytest {test_file} -v"
        elif ext in ['js', 'ts', 'jsx', 'tsx']:
            return f"npm test {test_file}"
        elif ext == 'go':
            return f"go test {test_file}"
        elif ext == 'rs':
            return f"cargo test --test {test_file}"
        elif ext == 'java':
            return f"mvn test -Dtest={test_file}"
        else:
            return f"# Run tests in {test_file}"
    
    def _suggest_batch_test_command(
        self,
        test_files: List[str],
        test_type: str
    ) -> str:
        """
        Suggest batch test command.
        
        Args:
            test_files: List of test files
            test_type: Test file type
            
        Returns:
            Suggested batch command
        """
        if test_type == 'python':
            if len(test_files) <= 3:
                return f"pytest {' '.join(test_files)} -v"
            else:
                # Get common directory
                common_dir = self._find_common_directory(test_files)
                return f"pytest {common_dir} -v"
        
        elif test_type == 'javascript':
            return "npm test"
        
        elif test_type == 'typescript':
            return "npm test"
        
        else:
            return f"# Run {len(test_files)} test files"
    
    def _group_test_files_by_type(
        self,
        test_files: List[str]
    ) -> Dict[str, List[str]]:
        """
        Group test files by type/language.
        
        Args:
            test_files: List of test file paths
            
        Returns:
            Dictionary mapping type to files
        """
        grouped = defaultdict(list)
        
        for file_path in test_files:
            ext = file_path.split('.')[-1].lower()
            
            if ext == 'py':
                grouped['python'].append(file_path)
            elif ext in ['js', 'jsx']:
                grouped['javascript'].append(file_path)
            elif ext in ['ts', 'tsx']:
                grouped['typescript'].append(file_path)
            elif ext == 'go':
                grouped['go'].append(file_path)
            elif ext == 'rs':
                grouped['rust'].append(file_path)
            else:
                grouped['other'].append(file_path)
        
        return dict(grouped)
    
    def _find_common_directory(self, file_paths: List[str]) -> str:
        """
        Find common directory for file paths.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Common directory path
        """
        if not file_paths:
            return ""
        
        # Split paths into parts
        parts_list = [path.split('/') for path in file_paths]
        
        # Find common prefix
        common = []
        for parts in zip(*parts_list):
            if len(set(parts)) == 1:
                common.append(parts[0])
            else:
                break
        
        if common:
            return '/'.join(common) + '/'
        else:
            return 'tests/'
    
    def _collect_evidence(
        self,
        affected_tests: List[AffectedTest],
        uncovered_areas: List[UncoveredArea],
        relevant_ci_checks: List[RelevantCICheck]
    ) -> List[str]:
        """
        Collect evidence for test intelligence.
        
        Args:
            affected_tests: Affected tests
            uncovered_areas: Uncovered areas
            relevant_ci_checks: Relevant CI checks
            
        Returns:
            List of evidence strings
        """
        evidence = []
        
        # Test coverage evidence
        high_confidence_tests = [t for t in affected_tests if t.confidence == "high"]
        if high_confidence_tests:
            evidence.append(
                f"{len(high_confidence_tests)} tests with high-confidence direct impact"
            )
        
        medium_confidence_tests = [t for t in affected_tests if t.confidence == "medium"]
        if medium_confidence_tests:
            evidence.append(
                f"{len(medium_confidence_tests)} tests with medium-confidence indirect impact"
            )
        
        # Coverage gaps
        if uncovered_areas:
            high_severity = [u for u in uncovered_areas if u.severity == "high"]
            if high_severity:
                evidence.append(
                    f"{len(high_severity)} changed areas with high-severity coverage gaps"
                )
        
        # CI evidence
        high_confidence_ci = [c for c in relevant_ci_checks if c.confidence == "high"]
        if high_confidence_ci:
            evidence.append(
                f"{len(high_confidence_ci)} CI workflows will definitely run affected tests"
            )
        
        return evidence
    
    def _generate_summary(
        self,
        affected_tests: List[AffectedTest],
        uncovered_areas: List[UncoveredArea],
        relevant_ci_checks: List[RelevantCICheck]
    ) -> str:
        """
        Generate summary of test intelligence.
        
        Args:
            affected_tests: Affected tests
            uncovered_areas: Uncovered areas
            relevant_ci_checks: Relevant CI checks
            
        Returns:
            Summary string
        """
        parts = []
        
        if affected_tests:
            parts.append(f"{len(affected_tests)} tests affected")
        else:
            parts.append("No tests directly affected")
        
        if uncovered_areas:
            parts.append(f"{len(uncovered_areas)} uncovered areas")
        
        if relevant_ci_checks:
            parts.append(f"{len(relevant_ci_checks)} relevant CI checks")
        
        return ", ".join(parts) if parts else "No test impact detected"
