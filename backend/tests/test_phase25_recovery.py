"""
Tests for Phase 25: Operational Reliability & Automated Recovery

This test suite verifies the recovery and reliability improvements implemented in Phase 25:
- Automated stale analysis recovery
- Partial failure handling (completed_with_warnings status)
- Recovery service safety guarantees
- Repository isolation
- Idempotent recovery operations
"""
# Load environment variables before any other imports
from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
import json
from datetime import datetime, timedelta, UTC
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock

from app.db.models import Repository, AnalysisRun, AnalysisStatus
from app.db.session import SessionLocal, engine, Base
from app.services.recovery_service import RecoveryService
from app.services.job_orchestration_service import JobOrchestrationService
from app.services.persistence_service import PersistenceService


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def recovery_service(db_session: Session) -> RecoveryService:
    """Create a recovery service instance."""
    return RecoveryService(db_session)


@pytest.fixture
def sample_repository(db_session: Session) -> Repository:
    """Create a sample repository."""
    repo = Repository(
        owner="test",
        name="test-repo",
        full_name="test/test-repo",
        github_url="https://github.com/test/test-repo",
        default_branch="main"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


@pytest.fixture
def second_repository(db_session: Session) -> Repository:
    """Create a second repository for isolation tests."""
    repo = Repository(
        owner="test2",
        name="test-repo2",
        full_name="test2/test-repo2",
        github_url="https://github.com/test2/test-repo2",
        default_branch="main"
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


class TestStaleAnalysisRecovery:
    """Tests for automated stale analysis recovery."""
    
    def test_recover_stale_running_analysis(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test recovering a stale RUNNING analysis run."""
        # Create analysis run that started 25 hours ago
        stale_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=25),
            progress=50,
            current_stage="Analyzing code"
        )
        db_session.add(stale_run)
        db_session.commit()
        db_session.refresh(stale_run)
        
        # Run recovery with 24 hour threshold
        result = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Verify recovery occurred
        assert result['stale_count'] == 1
        assert result['recovered_count'] == 1
        assert str(stale_run.id) in result['recovered_runs']
        
        # Verify status updated
        db_session.refresh(stale_run)
        assert stale_run.status == AnalysisStatus.FAILED
        assert stale_run.completed_at is not None
        assert "stale" in stale_run.error_message.lower()
        assert "RUNNING" in stale_run.error_message  # Original status preserved
        
        # Verify progress not reset (helps debugging)
        assert stale_run.progress == 50
    
    def test_recover_stale_queued_analysis(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test recovering a stale QUEUED analysis run."""
        # Create analysis run that was queued 25 hours ago
        stale_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.QUEUED,
            started_at=datetime.utcnow() - timedelta(hours=25),
            progress=0,
            current_stage="Queued"
        )
        db_session.add(stale_run)
        db_session.commit()
        db_session.refresh(stale_run)
        
        # Run recovery
        result = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Verify recovery occurred
        assert result['stale_count'] == 1
        assert result['recovered_count'] == 1
        
        # Verify status updated
        db_session.refresh(stale_run)
        assert stale_run.status == AnalysisStatus.FAILED
        assert "QUEUED" in stale_run.error_message
    
    def test_dont_recover_recent_running_analysis(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that recent RUNNING analysis runs are not marked as stale."""
        # Create analysis run that started 1 hour ago
        recent_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=1),
            progress=30,
            current_stage="Scanning files"
        )
        db_session.add(recent_run)
        db_session.commit()
        db_session.refresh(recent_run)
        
        # Run recovery with 24 hour threshold
        result = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Verify no recovery occurred
        assert result['stale_count'] == 0
        assert result['recovered_count'] == 0
        
        # Verify status unchanged
        db_session.refresh(recent_run)
        assert recent_run.status == AnalysisStatus.RUNNING
        assert recent_run.completed_at is None
    
    def test_dont_recover_completed_analysis(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that completed analysis runs are never marked as stale."""
        # Create completed analysis run from 30 hours ago
        completed_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(hours=30),
            completed_at=datetime.utcnow() - timedelta(hours=29),
            progress=100,
            current_stage="Completed"
        )
        db_session.add(completed_run)
        db_session.commit()
        db_session.refresh(completed_run)
        
        # Run recovery
        result = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Verify no recovery occurred
        assert result['stale_count'] == 0
        assert result['recovered_count'] == 0
        
        # Verify status unchanged
        db_session.refresh(completed_run)
        assert completed_run.status == AnalysisStatus.COMPLETED
    
    def test_dont_recover_failed_analysis(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that already-failed analysis runs are not touched."""
        # Create failed analysis run from 30 hours ago
        failed_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.FAILED,
            started_at=datetime.utcnow() - timedelta(hours=30),
            completed_at=datetime.utcnow() - timedelta(hours=29),
            error_message="Some error"
        )
        db_session.add(failed_run)
        db_session.commit()
        db_session.refresh(failed_run)
        
        # Run recovery
        result = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Verify no recovery occurred
        assert result['stale_count'] == 0
        
        # Verify status and error message unchanged
        db_session.refresh(failed_run)
        assert failed_run.status == AnalysisStatus.FAILED
        assert failed_run.error_message == "Some error"
    
    def test_dont_recover_cancelled_analysis(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that cancelled analysis runs are not touched."""
        # Create cancelled analysis run
        cancelled_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.CANCELLED,
            started_at=datetime.utcnow() - timedelta(hours=30),
            completed_at=datetime.utcnow() - timedelta(hours=29)
        )
        db_session.add(cancelled_run)
        db_session.commit()
        
        # Run recovery
        result = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Verify no recovery occurred
        assert result['stale_count'] == 0


class TestRepositoryIsolation:
    """Tests for repository isolation in recovery."""
    
    def test_recover_stale_for_specific_repository(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository,
        second_repository: Repository
    ):
        """Test that recovery can be scoped to a specific repository."""
        # Create stale run for repo1
        stale_run_repo1 = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=25)
        )
        db_session.add(stale_run_repo1)
        
        # Create stale run for repo2
        stale_run_repo2 = AnalysisRun(
            repository_id=second_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=25)
        )
        db_session.add(stale_run_repo2)
        db_session.commit()
        db_session.refresh(stale_run_repo1)
        db_session.refresh(stale_run_repo2)
        
        # Run recovery for repo1 only
        result = recovery_service.recover_stale_analyses(
            repository_id=str(sample_repository.id),
            stale_threshold_hours=24
        )
        
        # Verify only repo1 run was recovered
        assert result['stale_count'] == 1
        assert result['recovered_count'] == 1
        assert result['repository_id'] == str(sample_repository.id)
        
        # Verify repo1 run marked failed
        db_session.refresh(stale_run_repo1)
        assert stale_run_repo1.status == AnalysisStatus.FAILED
        
        # Verify repo2 run unchanged
        db_session.refresh(stale_run_repo2)
        assert stale_run_repo2.status == AnalysisStatus.RUNNING
    
    def test_recover_all_repositories(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository,
        second_repository: Repository
    ):
        """Test that recovery without repository_id affects all repositories."""
        # Create stale runs for both repos
        stale_run_repo1 = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=25)
        )
        stale_run_repo2 = AnalysisRun(
            repository_id=second_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=25)
        )
        db_session.add_all([stale_run_repo1, stale_run_repo2])
        db_session.commit()
        
        # Run recovery for all repositories
        result = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Verify both runs recovered
        assert result['stale_count'] == 2
        assert result['recovered_count'] == 2
        assert result['repository_id'] is None
        
        # Verify both marked failed
        db_session.refresh(stale_run_repo1)
        db_session.refresh(stale_run_repo2)
        assert stale_run_repo1.status == AnalysisStatus.FAILED
        assert stale_run_repo2.status == AnalysisStatus.FAILED


class TestIdempotentRecovery:
    """Tests for idempotent recovery operations."""
    
    def test_repeated_recovery_is_safe(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that running recovery multiple times is safe."""
        # Create stale run
        stale_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=25)
        )
        db_session.add(stale_run)
        db_session.commit()
        db_session.refresh(stale_run)
        
        # Run recovery first time
        result1 = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        assert result1['recovered_count'] == 1
        
        # Run recovery second time
        result2 = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Verify no additional recovery (already failed)
        assert result2['stale_count'] == 0
        assert result2['recovered_count'] == 0
        
        # Verify status still failed
        db_session.refresh(stale_run)
        assert stale_run.status == AnalysisStatus.FAILED
    
    def test_recovery_during_active_processing(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that recovery doesn't affect actively processing jobs."""
        # Create a job that just started (not stale)
        active_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(minutes=30),
            progress=10,
            current_stage="Downloading repository"
        )
        db_session.add(active_run)
        db_session.commit()
        
        # Run recovery
        result = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Verify no recovery
        assert result['stale_count'] == 0
        
        # Verify job still running
        db_session.refresh(active_run)
        assert active_run.status == AnalysisStatus.RUNNING


class TestCheckStaleRuns:
    """Tests for read-only stale run checking."""
    
    def test_check_stale_runs_without_modifying(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that check_stale_runs is read-only."""
        # Create stale run
        stale_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=25),
            progress=40,
            current_stage="Static analysis",
            job_id="test-job-123"
        )
        db_session.add(stale_run)
        db_session.commit()
        db_session.refresh(stale_run)
        
        # Check for stale runs
        stale_list = recovery_service.check_stale_runs(stale_threshold_hours=24)
        
        # Verify detection
        assert len(stale_list) == 1
        stale_info = stale_list[0]
        assert stale_info['analysis_run_id'] == str(stale_run.id)
        assert stale_info['status'] == 'running'
        assert stale_info['progress'] == 40
        assert stale_info['current_stage'] == "Static analysis"
        assert stale_info['job_id'] == "test-job-123"
        assert 'elapsed_hours' in stale_info
        assert stale_info['elapsed_hours'] > 24
        
        # Verify status NOT modified
        db_session.refresh(stale_run)
        assert stale_run.status == AnalysisStatus.RUNNING
        assert stale_run.completed_at is None
    
    def test_check_stale_runs_empty(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that check_stale_runs returns empty list when no stale runs."""
        # Create recent run
        recent_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(recent_run)
        db_session.commit()
        
        # Check for stale runs
        stale_list = recovery_service.check_stale_runs(stale_threshold_hours=24)
        
        # Verify empty
        assert len(stale_list) == 0


class TestPartialFailureHandling:
    """Tests for partial analysis failure handling (completed_with_warnings)."""
    
    def test_completed_with_warnings_status(
        self,
        db_session: Session,
        sample_repository: Repository
    ):
        """Test that completed_with_warnings status is stored correctly."""
        # Create analysis run with warnings
        analysis_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.COMPLETED_WITH_WARNINGS,
            started_at=datetime.utcnow() - timedelta(hours=1),
            completed_at=datetime.utcnow(),
            progress=100,
            warnings=json.dumps([
                {"stage": "embedding_generation", "message": "Failed to generate embeddings", "error": "APIError"}
            ])
        )
        db_session.add(analysis_run)
        db_session.commit()
        db_session.refresh(analysis_run)
        
        # Verify status stored
        assert analysis_run.status == AnalysisStatus.COMPLETED_WITH_WARNINGS
        
        # Verify warnings stored
        warnings = json.loads(analysis_run.warnings)
        assert len(warnings) == 1
        assert warnings[0]['stage'] == 'embedding_generation'
        
        # Query back
        queried_run = db_session.query(AnalysisRun).filter_by(id=analysis_run.id).first()
        assert queried_run.status == AnalysisStatus.COMPLETED_WITH_WARNINGS
        assert queried_run.warnings is not None
    
    def test_orchestrator_tracks_warnings(
        self,
        db_session: Session,
        sample_repository: Repository
    ):
        """Test that JobOrchestrationService tracks warnings."""
        # Create analysis run
        analysis_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.QUEUED
        )
        db_session.add(analysis_run)
        db_session.commit()
        db_session.refresh(analysis_run)
        
        # Create orchestrator
        orchestrator = JobOrchestrationService(db_session, analysis_run)
        
        # Verify warnings list exists
        assert hasattr(orchestrator, 'warnings')
        assert orchestrator.warnings == []
        
        # Add a warning
        orchestrator.warnings.append({
            "stage": "test_stage",
            "message": "Test warning",
            "error": "TestError"
        })
        
        # Mark completed
        orchestrator.mark_completed()
        
        # Verify status and warnings persisted
        db_session.refresh(analysis_run)
        assert analysis_run.status == AnalysisStatus.COMPLETED_WITH_WARNINGS
        assert analysis_run.warnings is not None
        
        warnings = json.loads(analysis_run.warnings)
        assert len(warnings) == 1
        assert warnings[0]['stage'] == 'test_stage'
    
    def test_orchestrator_completed_without_warnings(
        self,
        db_session: Session,
        sample_repository: Repository
    ):
        """Test that JobOrchestrationService uses COMPLETED when no warnings."""
        # Create analysis run
        analysis_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.QUEUED
        )
        db_session.add(analysis_run)
        db_session.commit()
        db_session.refresh(analysis_run)
        
        # Create orchestrator
        orchestrator = JobOrchestrationService(db_session, analysis_run)
        
        # Mark completed without warnings
        orchestrator.mark_completed()
        
        # Verify status is COMPLETED (not COMPLETED_WITH_WARNINGS)
        db_session.refresh(analysis_run)
        assert analysis_run.status == AnalysisStatus.COMPLETED
        assert analysis_run.warnings is None or analysis_run.warnings == 'null'


class TestConfigurableThreshold:
    """Tests for configurable stale threshold."""
    
    def test_custom_threshold(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that custom stale threshold is respected."""
        # Create run that started 13 hours ago
        run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=13)
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)
        
        # Recovery with 24 hour threshold: should not recover
        result1 = recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        assert result1['stale_count'] == 0
        
        # Recovery with 12 hour threshold: should recover
        result2 = recovery_service.recover_stale_analyses(stale_threshold_hours=12)
        assert result2['stale_count'] == 1
        assert result2['threshold_hours'] == 12
        
        # Verify marked failed
        db_session.refresh(run)
        assert run.status == AnalysisStatus.FAILED


class TestRecoveryLogging:
    """Tests for recovery logging and error messages."""
    
    def test_error_message_includes_details(
        self,
        db_session: Session,
        recovery_service: RecoveryService,
        sample_repository: Repository
    ):
        """Test that recovery error message includes useful details."""
        # Create stale run
        stale_run = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=30)
        )
        db_session.add(stale_run)
        db_session.commit()
        
        # Run recovery
        recovery_service.recover_stale_analyses(stale_threshold_hours=24)
        
        # Check error message
        db_session.refresh(stale_run)
        assert stale_run.error_message is not None
        error_msg = stale_run.error_message.lower()
        
        # Verify key information present
        assert "stale" in error_msg
        assert "running" in error_msg  # Original status
        assert "24" in error_msg or "exceeded" in error_msg  # Threshold
        
        # Should mention possible causes
        assert any(word in error_msg for word in ["crash", "timeout", "resource"])
