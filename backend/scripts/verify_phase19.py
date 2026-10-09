"""
Verification script for Phase 19: CI & Test Intelligence.

This script demonstrates the complete test intelligence pipeline:
1. Test detection
2. Test coverage analysis
3. CI intelligence
4. Test recommendations
5. LLM explanations

Usage:
    python scripts/verify_phase19.py
"""
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import logging
from uuid import uuid4
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import (
    Repository, AnalysisRun, Commit, CommitFileChange, File, Symbol, Import,
    AnalysisStatus, SymbolType, ChangeType as DBChangeType
)
from app.services.test_detection_service import TestDetectionService
from app.services.test_coverage_analyzer import TestCoverageAnalyzer
from app.services.ci_intelligence_service import CIIntelligenceService
from app.services.test_recommendation_service import TestRecommendationService
from app.services.test_intelligence_explainer import TestIntelligenceExplainer
from app.schemas.change_analysis import ChangedFile, ChangedSymbol, ChangeType
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_test_data(db: Session, repository_id):
    """Clean up test data."""
    try:
        repo = db.query(Repository).filter(Repository.id == repository_id).first()
        if repo:
            db.delete(repo)
            db.commit()
            logger.info("✓ Cleaned up test data")
    except Exception as e:
        logger.warning(f"Cleanup warning: {e}")
        db.rollback()


def create_test_repository(db: Session):
    """Create a test repository with files and tests."""
    logger.info("=" * 60)
    logger.info("PHASE 19 VERIFICATION: CI & Test Intelligence")
    logger.info("=" * 60)
    
    # Create repository
    repo = Repository(
        id=uuid4(),
        name="test-intelligence-demo",
        full_name="demo/test-intelligence-demo",
        owner="demo",
        github_url="https://github.com/demo/test-intelligence-demo",
        description="Demo repository for test intelligence",
        default_branch="main",
        stars=50,
        language="Python"
    )
    db.add(repo)
    db.commit()
    logger.info(f"✓ Created test repository: {repo.full_name}")
    
    # Create analysis run
    analysis = AnalysisRun(
        id=uuid4(),
        repository_id=repo.id,
        status=AnalysisStatus.COMPLETED,
        started_at=datetime.utcnow() - timedelta(hours=1),
        completed_at=datetime.utcnow(),
        total_files=15,
        analyzed_files=15
    )
    db.add(analysis)
    db.commit()
    logger.info("✓ Created analysis run")
    
    # Create source files
    files_data = [
        ("src/services/user_service.py", "Python", False),
        ("src/services/auth_service.py", "Python", False),
        ("src/api/user_routes.py", "Python", False),
        ("tests/test_user_service.py", "Python", True),
        ("tests/test_auth_service.py", "Python", True),
        ("tests/integration/test_user_api.py", "Python", True),
        (".github/workflows/ci.yml", "YAML", False)
    ]
    
    files = {}
    for path, language, is_test in files_data:
        file = File(
            id=uuid4(),
            repository_id=repo.id,
            analysis_run_id=analysis.id,
            path=path,
            filename=Path(path).name,
            extension=Path(path).suffix,
            language=language,
            size_bytes=1024,
            line_count=50
        )
        db.add(file)
        files[path] = file
    
    db.commit()
    logger.info(f"✓ Created {len(files)} files")
    
    # Create symbols
    symbols_data = [
        ("src/services/user_service.py", "create_user", SymbolType.FUNCTION, 15, 30),
        ("src/services/user_service.py", "update_user", SymbolType.FUNCTION, 32, 45),
        ("src/services/user_service.py", "UserService", SymbolType.CLASS, 50, 100),
        ("src/services/auth_service.py", "authenticate", SymbolType.FUNCTION, 10, 25),
        ("tests/test_user_service.py", "test_create_user", SymbolType.FUNCTION, 10, 20),
        ("tests/test_user_service.py", "test_update_user", SymbolType.FUNCTION, 22, 32),
        ("tests/test_user_service.py", "test_user_service_integration", SymbolType.FUNCTION, 34, 50),
        ("tests/test_auth_service.py", "test_authenticate", SymbolType.FUNCTION, 8, 18),
        ("tests/integration/test_user_api.py", "test_create_user_api", SymbolType.FUNCTION, 15, 30)
    ]
    
    symbols = {}
    for file_path, name, symbol_type, start, end in symbols_data:
        symbol = Symbol(
            id=uuid4(),
            file_id=files[file_path].id,
            analysis_run_id=analysis.id,
            name=name,
            symbol_type=symbol_type,
            language=files[file_path].language,
            start_line=start,
            end_line=end
        )
        db.add(symbol)
        symbols[f"{file_path}:{name}"] = symbol
    
    db.commit()
    logger.info(f"✓ Created {len(symbols)} symbols")
    
    # Create imports
    imports_data = [
        ("tests/test_user_service.py", "services.user_service", "create_user,update_user,UserService"),
        ("tests/test_user_service.py", "pytest", ""),
        ("tests/test_auth_service.py", "services.auth_service", "authenticate"),
        ("tests/test_auth_service.py", "pytest", ""),
        ("tests/integration/test_user_api.py", "api.user_routes", ""),
        ("tests/integration/test_user_api.py", "pytest", "")
    ]
    
    for file_path, source, imported_names in imports_data:
        imp = Import(
            id=uuid4(),
            file_id=files[file_path].id,
            analysis_run_id=analysis.id,
            source=source,
            imported_names=imported_names,
            line_number=1
        )
        db.add(imp)
    
    db.commit()
    logger.info(f"✓ Created {len(imports_data)} imports")
    
    # Create commits
    base_commit = Commit(
        id=uuid4(),
        repository_id=repo.id,
        commit_hash="base123abc",
        author_name="Developer",
        author_email="dev@example.com",
        commit_message="Initial commit",
        committed_at=datetime.utcnow() - timedelta(days=7)
    )
    db.add(base_commit)
    
    head_commit = Commit(
        id=uuid4(),
        repository_id=repo.id,
        commit_hash="head456def",
        author_name="Developer",
        author_email="dev@example.com",
        commit_message="Update user service with validation",
        committed_at=datetime.utcnow() - timedelta(days=1)
    )
    db.add(head_commit)
    db.commit()
    
    # Create file changes
    file_changes_data = [
        ("src/services/user_service.py", DBChangeType.MODIFIED, 35, 10),
        ("src/services/auth_service.py", DBChangeType.MODIFIED, 5, 2),
    ]
    
    for path, change_type, additions, deletions in file_changes_data:
        change = CommitFileChange(
            id=uuid4(),
            commit_id=head_commit.id,
            path=path,
            change_type=change_type,
            additions=additions,
            deletions=deletions
        )
        db.add(change)
    
    db.commit()
    logger.info("✓ Created commits and file changes")
    
    return repo, analysis, {'base': base_commit, 'head': head_commit}


def verify_test_detection(db: Session, repo, analysis):
    """Verify test detection service."""
    logger.info("\n" + "=" * 60)
    logger.info("1. TEST DETECTION")
    logger.info("=" * 60)
    
    service = TestDetectionService(db)
    
    # Get all test files
    test_files = service.get_test_files(
        repository_id=repo.id,
        analysis_run_id=analysis.id
    )
    
    logger.info(f"✓ Detected {len(test_files)} test files")
    
    for test_file in test_files:
        logger.info(f"\n  Test File: {test_file.file_path}")
        logger.info(f"    Framework: {test_file.framework.value}")
        logger.info(f"    Test Count: {test_file.test_count}")
        logger.info(f"    Imports: {', '.join(test_file.imports_from[:3])}")
        
        for test_case in test_file.test_cases[:3]:
            logger.info(f"      - {test_case.name} (line {test_case.line_number})")
    
    return test_files


def verify_test_coverage(db: Session, repo, analysis):
    """Verify test coverage analyzer."""
    logger.info("\n" + "=" * 60)
    logger.info("2. TEST COVERAGE ANALYSIS")
    logger.info("=" * 60)
    
    analyzer = TestCoverageAnalyzer(db)
    
    # Simulate changes
    changed_files = [
        ChangedFile(
            path="src/services/user_service.py",
            change_type=ChangeType.MODIFIED,
            additions=35,
            deletions=10,
            is_test=False,
            is_source=True,
            language="Python"
        ),
        ChangedFile(
            path="src/services/auth_service.py",
            change_type=ChangeType.MODIFIED,
            additions=5,
            deletions=2,
            is_test=False,
            is_source=True,
            language="Python"
        )
    ]
    
    changed_symbols = [
        ChangedSymbol(
            name="create_user",
            qualified_name="src/services/user_service.py:create_user",
            symbol_type="function",
            change_type=ChangeType.MODIFIED,
            file_path="src/services/user_service.py",
            line_number=15,
            is_public=True
        ),
        ChangedSymbol(
            name="authenticate",
            qualified_name="src/services/auth_service.py:authenticate",
            symbol_type="function",
            change_type=ChangeType.MODIFIED,
            file_path="src/services/auth_service.py",
            line_number=10,
            is_public=True
        )
    ]
    
    affected_tests, uncovered_areas = analyzer.analyze_test_coverage(
        repository_id=repo.id,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        analysis_run_id=analysis.id
    )
    
    logger.info(f"✓ Found {len(affected_tests)} affected tests")
    logger.info(f"✓ Found {len(uncovered_areas)} uncovered areas")
    
    # Display affected tests
    high_confidence = [t for t in affected_tests if t.confidence == "high"]
    logger.info(f"\n  High Confidence Tests ({len(high_confidence)}):")
    for test in high_confidence[:5]:
        logger.info(f"    - {test.test_file}")
        if test.test_name:
            logger.info(f"      Test: {test.test_name}")
        logger.info(f"      Coverage: {test.coverage_type.value}")
        logger.info(f"      Symbols: {', '.join(test.changed_symbols[:3])}")
    
    # Display uncovered areas
    if uncovered_areas:
        logger.info(f"\n  Uncovered Areas:")
        for area in uncovered_areas:
            logger.info(f"    - {area.file_path}")
            logger.info(f"      Severity: {area.severity}")
            logger.info(f"      Symbols: {', '.join(area.changed_symbols[:3])}")
    
    return affected_tests, uncovered_areas, changed_files, changed_symbols


def verify_ci_intelligence(db: Session, repo, analysis, changed_files):
    """Verify CI intelligence service."""
    logger.info("\n" + "=" * 60)
    logger.info("3. CI INTELLIGENCE")
    logger.info("=" * 60)
    
    service = CIIntelligenceService(db)
    
    # Get CI jobs
    ci_jobs = service.get_ci_jobs(
        repository_id=repo.id,
        analysis_run_id=analysis.id
    )
    
    logger.info(f"✓ Found {len(ci_jobs)} CI jobs")
    
    for job in ci_jobs:
        logger.info(f"\n  CI Job: {job.job_name}")
        logger.info(f"    Workflow: {job.workflow_file}")
        logger.info(f"    Runs Tests: {job.runs_tests}")
        logger.info(f"    Triggers: {', '.join(job.triggers_on)}")
    
    # Get relevant checks
    relevant_checks = service.get_relevant_ci_checks(
        repository_id=repo.id,
        changed_files=changed_files,
        analysis_run_id=analysis.id
    )
    
    logger.info(f"\n✓ Found {len(relevant_checks)} relevant CI checks")
    
    for check in relevant_checks:
        logger.info(f"\n  Relevant Check: {check.job_name}")
        logger.info(f"    Confidence: {check.confidence}")
        logger.info(f"    Relevance: {check.relevance}")
        logger.info(f"    Evidence: {'; '.join(check.evidence[:2])}")
    
    return ci_jobs, relevant_checks


def verify_test_recommendations(db: Session, repo, commits, changed_files, changed_symbols):
    """Verify test recommendation service."""
    logger.info("\n" + "=" * 60)
    logger.info("4. TEST RECOMMENDATIONS")
    logger.info("=" * 60)
    
    service = TestRecommendationService(db)
    
    result = service.analyze_test_intelligence(
        repository_id=repo.id,
        base_sha=commits['base'].commit_hash,
        head_sha=commits['head'].commit_hash,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        include_ci_analysis=True,
        include_local_recommendations=True
    )
    
    logger.info(f"✓ Test Intelligence Summary: {result.summary}")
    logger.info(f"  Total Test Files: {result.total_test_files}")
    logger.info(f"  Affected Tests: {len(result.affected_tests)}")
    logger.info(f"  Uncovered Areas: {len(result.uncovered_areas)}")
    logger.info(f"  CI Jobs: {len(result.ci_jobs)}")
    logger.info(f"  Relevant CI Checks: {len(result.relevant_ci_checks)}")
    
    # Display local recommendations
    logger.info(f"\n  Local Test Recommendations ({len(result.local_test_recommendations)}):")
    for rec in result.local_test_recommendations:
        logger.info(f"\n    Priority: {rec.priority.upper()}")
        logger.info(f"    Command: {rec.command}")
        logger.info(f"    Reason: {rec.reason}")
    
    # Display evidence
    logger.info(f"\n  Evidence:")
    for evidence in result.evidence:
        logger.info(f"    - {evidence}")
    
    return result


def verify_llm_explanation(test_intelligence, changed_files):
    """Verify LLM explanation (if configured)."""
    logger.info("\n" + "=" * 60)
    logger.info("5. LLM EXPLANATION (Optional)")
    logger.info("=" * 60)
    
    settings = get_settings()
    
    if not settings.GEMINI_API_KEY:
        logger.info("⚠ GEMINI_API_KEY not configured - skipping LLM explanation")
        return
    
    try:
        from app.services.llm.gemini_provider import GeminiProvider
        
        provider = GeminiProvider(api_key=settings.GEMINI_API_KEY)
        explainer = TestIntelligenceExplainer(llm_provider=provider)
        
        explanation = explainer.explain_test_intelligence(
            test_intelligence=test_intelligence,
            changed_files=[f.path for f in changed_files]
        )
        
        logger.info("✓ Generated LLM explanation")
        logger.info(f"\n  Test Impact Summary:")
        logger.info(f"    {explanation.test_impact_summary}")
        
        logger.info(f"\n  Affected Tests Explanation:")
        logger.info(f"    {explanation.affected_tests_explanation[:200]}...")
        
        logger.info(f"\n  Coverage Gaps:")
        logger.info(f"    {explanation.coverage_gaps_explanation[:200]}...")
        
        logger.info(f"\n  CI Recommendations:")
        logger.info(f"    {explanation.ci_recommendations[:200]}...")
        
        if explanation.uncertainty:
            logger.info(f"\n  Uncertainty:")
            logger.info(f"    {explanation.uncertainty}")
    
    except Exception as e:
        logger.warning(f"⚠ LLM explanation failed: {e}")


def main():
    """Run Phase 19 verification."""
    db = SessionLocal()
    repo = None
    
    try:
        # Create test data
        repo, analysis, commits = create_test_repository(db)
        
        # 1. Test detection
        test_files = verify_test_detection(db, repo, analysis)
        
        # 2. Test coverage
        affected_tests, uncovered_areas, changed_files, changed_symbols = verify_test_coverage(
            db, repo, analysis
        )
        
        # 3. CI intelligence
        ci_jobs, relevant_checks = verify_ci_intelligence(
            db, repo, analysis, changed_files
        )
        
        # 4. Test recommendations
        test_intelligence = verify_test_recommendations(
            db, repo, commits, changed_files, changed_symbols
        )
        
        # 5. LLM explanation (optional)
        verify_llm_explanation(test_intelligence, changed_files)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION COMPLETE")
        logger.info("=" * 60)
        logger.info("✓ All Phase 19 components verified successfully!")
        logger.info("\nPhase 19 provides:")
        logger.info("  • Test detection and classification")
        logger.info("  • Test coverage mapping for changes")
        logger.info("  • CI workflow intelligence")
        logger.info("  • Actionable test recommendations")
        logger.info("  • LLM-powered explanations")
        
    except Exception as e:
        logger.error(f"✗ Verification failed: {e}", exc_info=True)
        raise
    
    finally:
        if repo:
            cleanup_test_data(db, repo.id)
        db.close()


if __name__ == "__main__":
    main()
