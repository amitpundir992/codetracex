"""
Tests for Phase 24: Repository Intelligence Quality & Analysis Reliability

This test suite verifies the reliability improvements implemented in Phase 24:
- File content fingerprinting (content_hash)
- Stale analysis run detection and cleanup
- Performance timing measurements
- File hash utility functions
"""
# Load environment variables before any other imports
from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
import tempfile
from datetime import datetime, timedelta, UTC
from sqlalchemy.orm import Session

from app.db.models import Repository, AnalysisRun, File, AnalysisStatus
from app.db.session import SessionLocal, engine, Base
from app.services.persistence_service import PersistenceService
from app.services.scanner_service import FileScannerService, FileMetadata
from app.utils.file_hash import compute_file_hash, compute_content_hash
from app.utils.timing import StageTiming, timed_stage


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def persistence_service(db_session: Session) -> PersistenceService:
    """Create a persistence service instance."""
    return PersistenceService(db_session)


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


class TestFileContentFingerprinting:
    """Tests for file content fingerprinting (content_hash)."""
    
    def test_compute_file_hash(self):
        """Test computing SHA-256 hash of file content."""
        # Create temporary file with known content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Hello, World!")
            temp_path = Path(f.name)
        
        try:
            # Compute hash
            file_hash = compute_file_hash(temp_path)
            
            # Verify it's a valid SHA-256 hex digest (64 characters)
            assert file_hash is not None
            assert len(file_hash) == 64
            assert all(c in '0123456789abcdef' for c in file_hash)
            
            # Verify deterministic: same content = same hash
            file_hash2 = compute_file_hash(temp_path)
            assert file_hash == file_hash2
            
        finally:
            temp_path.unlink()
    
    def test_compute_file_hash_different_content(self):
        """Test that different content produces different hashes."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f1:
            f1.write("Content A")
            path1 = Path(f1.name)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f2:
            f2.write("Content B")
            path2 = Path(f2.name)
        
        try:
            hash1 = compute_file_hash(path1)
            hash2 = compute_file_hash(path2)
            
            assert hash1 != hash2
            
        finally:
            path1.unlink()
            path2.unlink()
    
    def test_compute_file_hash_nonexistent_file(self):
        """Test that compute_file_hash returns None for nonexistent file."""
        nonexistent_path = Path("/nonexistent/file.txt")
        file_hash = compute_file_hash(nonexistent_path)
        assert file_hash is None
    
    def test_compute_content_hash(self):
        """Test computing SHA-256 hash of string content."""
        content = "Hello, World!"
        content_hash = compute_content_hash(content)
        
        # Verify it's a valid SHA-256 hex digest
        assert len(content_hash) == 64
        assert all(c in '0123456789abcdef' for c in content_hash)
        
        # Verify deterministic
        content_hash2 = compute_content_hash(content)
        assert content_hash == content_hash2
    
    def test_scanner_includes_content_hash(self):
        """Test that FileScannerService includes content_hash in FileMetadata."""
        # Create temporary directory with test file
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            test_file = repo_root / "test.py"
            test_file.write_text("def hello():\n    print('Hello')\n")
            
            # Scan directory
            scanner = FileScannerService(max_files=1000)
            result = scanner.scan_directory(repo_root)
            
            # Verify content_hash is populated
            assert len(result.files) == 1
            file_meta = result.files[0]
            assert isinstance(file_meta, FileMetadata)
            assert file_meta.content_hash is not None
            assert len(file_meta.content_hash) == 64
    
    def test_file_model_stores_content_hash(
        self,
        db_session: Session,
        persistence_service: PersistenceService,
        sample_repository: Repository
    ):
        """Test that File model stores content_hash in database."""
        # Create analysis run
        analysis_run = persistence_service.create_analysis_run(sample_repository)
        
        # Create file with content_hash
        file = File(
            repository_id=sample_repository.id,
            analysis_run_id=analysis_run.id,
            path="src/app.py",
            filename="app.py",
            extension=".py",
            language="Python",
            size_bytes=1000,
            line_count=50,
            is_sensitive=False,
            content_hash="a" * 64  # Mock hash
        )
        
        db_session.add(file)
        db_session.commit()
        db_session.refresh(file)
        
        # Verify stored
        assert file.content_hash == "a" * 64
        
        # Query back
        queried_file = db_session.query(File).filter_by(id=file.id).first()
        assert queried_file.content_hash == "a" * 64


class TestStaleAnalysisDetection:
    """Tests for stale analysis run detection and cleanup."""
    
    def test_mark_stale_runs_as_failed(
        self,
        db_session: Session,
        persistence_service: PersistenceService,
        sample_repository: Repository
    ):
        """Test marking stale RUNNING analysis runs as failed."""
        # Create analysis run that started 25 hours ago
        old_analysis = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=25)
        )
        db_session.add(old_analysis)
        db_session.commit()
        db_session.refresh(old_analysis)
        
        # Mark stale runs
        count = persistence_service.mark_stale_runs_as_failed(stale_threshold_hours=24)
        
        # Verify marked as failed
        assert count == 1
        db_session.refresh(old_analysis)
        assert old_analysis.status == AnalysisStatus.FAILED
        assert "stale" in old_analysis.error_message.lower()
        assert old_analysis.completed_at is not None
    
    def test_mark_stale_queued_runs(
        self,
        db_session: Session,
        persistence_service: PersistenceService,
        sample_repository: Repository
    ):
        """Test marking stale QUEUED analysis runs as failed."""
        # Create queued run from 30 hours ago
        old_queued = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.QUEUED,
            started_at=datetime.utcnow() - timedelta(hours=30)
        )
        db_session.add(old_queued)
        db_session.commit()
        
        # Mark stale
        count = persistence_service.mark_stale_runs_as_failed(stale_threshold_hours=24)
        
        # Verify
        assert count == 1
        db_session.refresh(old_queued)
        assert old_queued.status == AnalysisStatus.FAILED
    
    def test_dont_mark_recent_running_as_stale(
        self,
        db_session: Session,
        persistence_service: PersistenceService,
        sample_repository: Repository
    ):
        """Test that recent RUNNING analysis runs are not marked as stale."""
        # Create analysis that started 1 hour ago
        recent_analysis = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(recent_analysis)
        db_session.commit()
        
        # Try to mark stale
        count = persistence_service.mark_stale_runs_as_failed(stale_threshold_hours=24)
        
        # Verify not marked
        assert count == 0
        db_session.refresh(recent_analysis)
        assert recent_analysis.status == AnalysisStatus.RUNNING
    
    def test_dont_mark_completed_runs_as_stale(
        self,
        db_session: Session,
        persistence_service: PersistenceService,
        sample_repository: Repository
    ):
        """Test that completed runs are never marked as stale."""
        # Create old completed analysis
        old_completed = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(hours=48),
            completed_at=datetime.utcnow() - timedelta(hours=47)
        )
        db_session.add(old_completed)
        db_session.commit()
        
        # Try to mark stale
        count = persistence_service.mark_stale_runs_as_failed(stale_threshold_hours=24)
        
        # Verify not marked
        assert count == 0
        db_session.refresh(old_completed)
        assert old_completed.status == AnalysisStatus.COMPLETED
    
    def test_mark_stale_for_specific_repository(
        self,
        db_session: Session,
        persistence_service: PersistenceService
    ):
        """Test marking stale runs for a specific repository only."""
        # Create two repositories
        repo1 = Repository(
            owner="test",
            name="repo1",
            full_name="test/repo1",
            github_url="https://github.com/test/repo1",
            default_branch="main"
        )
        repo2 = Repository(
            owner="test",
            name="repo2",
            full_name="test/repo2",
            github_url="https://github.com/test/repo2",
            default_branch="main"
        )
        db_session.add_all([repo1, repo2])
        db_session.commit()
        
        # Create stale runs for both
        stale1 = AnalysisRun(
            repository_id=repo1.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=30)
        )
        stale2 = AnalysisRun(
            repository_id=repo2.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(hours=30)
        )
        db_session.add_all([stale1, stale2])
        db_session.commit()
        
        # Mark stale for repo1 only
        count = persistence_service.mark_stale_runs_as_failed(
            repository_id=str(repo1.id),
            stale_threshold_hours=24
        )
        
        # Verify only repo1 marked
        assert count == 1
        db_session.refresh(stale1)
        db_session.refresh(stale2)
        assert stale1.status == AnalysisStatus.FAILED
        assert stale2.status == AnalysisStatus.RUNNING  # Not marked


class TestLatestSuccessfulAnalysis:
    """Tests for retrieving latest successful analysis."""
    
    def test_get_latest_successful_analysis(
        self,
        db_session: Session,
        persistence_service: PersistenceService,
        sample_repository: Repository
    ):
        """Test retrieving the most recent successful analysis."""
        # Create multiple analysis runs
        old_completed = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=2),
            completed_at=datetime.utcnow() - timedelta(days=2)
        )
        recent_completed = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=1),
            completed_at=datetime.utcnow() - timedelta(days=1)
        )
        failed = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.FAILED,
            started_at=datetime.utcnow() - timedelta(hours=1),
            completed_at=datetime.utcnow() - timedelta(hours=1)
        )
        
        db_session.add_all([old_completed, recent_completed, failed])
        db_session.commit()
        
        # Get latest successful
        latest = persistence_service.get_latest_successful_analysis(str(sample_repository.id))
        
        # Verify it's the most recent completed one
        assert latest is not None
        assert latest.id == recent_completed.id
        assert latest.status == AnalysisStatus.COMPLETED
    
    def test_get_latest_no_successful_analysis(
        self,
        db_session: Session,
        persistence_service: PersistenceService,
        sample_repository: Repository
    ):
        """Test get_latest_successful_analysis returns None when no successful analysis exists."""
        # Create only failed analysis
        failed = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.FAILED,
            started_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(failed)
        db_session.commit()
        
        # Get latest successful
        latest = persistence_service.get_latest_successful_analysis(str(sample_repository.id))
        
        # Verify None
        assert latest is None


class TestPerformanceTiming:
    """Tests for performance timing measurements."""
    
    def test_stage_timing_record(self):
        """Test recording stage timing."""
        timing = StageTiming()
        
        timing.record_stage("Download", 1.5)
        timing.record_stage("Parse", 3.2)
        
        assert timing.stages["Download"] == 1.5
        assert timing.stages["Parse"] == 3.2
    
    def test_stage_timing_total_duration(self):
        """Test setting total duration."""
        timing = StageTiming()
        
        timing.set_total_duration(10.5)
        
        assert timing.total_duration == 10.5
    
    def test_stage_timing_summary(self):
        """Test getting timing summary."""
        timing = StageTiming()
        
        timing.record_stage("Stage1", 1.234)
        timing.record_stage("Stage2", 2.567)
        timing.set_total_duration(5.678)
        
        summary = timing.get_summary()
        
        assert summary['total_duration_seconds'] == 5.68  # Rounded
        assert summary['stages']['Stage1'] == 1.23
        assert summary['stages']['Stage2'] == 2.57
    
    def test_timed_stage_context_manager(self):
        """Test timed_stage context manager."""
        import time
        
        timing = StageTiming()
        
        with timed_stage("Test Stage", timing):
            time.sleep(0.1)  # Sleep for 100ms
        
        # Verify stage was recorded
        assert "Test Stage" in timing.stages
        duration = timing.stages["Test Stage"]
        
        # Duration should be approximately 0.1 seconds (allow 50ms tolerance)
        assert 0.05 < duration < 0.2
    
    def test_timed_stage_without_timing_object(self):
        """Test timed_stage without StageTiming object (just logs)."""
        import time
        
        # Should not raise exception
        with timed_stage("Test Stage"):
            time.sleep(0.05)


class TestReanalysisScenarios:
    """Tests for reanalysis scenarios and data integrity."""
    
    def test_multiple_analysis_runs_same_repository(
        self,
        db_session: Session,
        persistence_service: PersistenceService,
        sample_repository: Repository
    ):
        """Test that multiple analysis runs can exist for same repository."""
        # Create first analysis
        analysis1 = persistence_service.create_analysis_run(sample_repository)
        analysis1.status = AnalysisStatus.COMPLETED
        analysis1.completed_at = datetime.utcnow()
        db_session.commit()
        
        # Create second analysis
        analysis2 = persistence_service.create_analysis_run(sample_repository)
        
        # Verify both exist
        all_runs = db_session.query(AnalysisRun).filter_by(
            repository_id=sample_repository.id
        ).all()
        
        assert len(all_runs) == 2
        assert analysis1.id != analysis2.id
    
    def test_files_associated_with_correct_analysis_run(
        self,
        db_session: Session,
        sample_repository: Repository
    ):
        """Test that files are correctly isolated by analysis_run_id."""
        # Create two analysis runs
        run1 = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.COMPLETED,
            started_at=datetime.utcnow()
        )
        run2 = AnalysisRun(
            repository_id=sample_repository.id,
            status=AnalysisStatus.COMPLETED,
            started_at=datetime.utcnow()
        )
        db_session.add_all([run1, run2])
        db_session.commit()
        
        # Add files to first run
        file1 = File(
            repository_id=sample_repository.id,
            analysis_run_id=run1.id,
            path="src/app.py",
            filename="app.py",
            extension=".py"
        )
        
        # Add files to second run
        file2 = File(
            repository_id=sample_repository.id,
            analysis_run_id=run2.id,
            path="src/app.py",  # Same path
            filename="app.py",
            extension=".py",
            content_hash="different_hash"  # Different content
        )
        
        db_session.add_all([file1, file2])
        db_session.commit()
        
        # Query files for each run
        run1_files = db_session.query(File).filter_by(analysis_run_id=run1.id).all()
        run2_files = db_session.query(File).filter_by(analysis_run_id=run2.id).all()
        
        # Verify isolation
        assert len(run1_files) == 1
        assert len(run2_files) == 1
        assert run1_files[0].id != run2_files[0].id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
