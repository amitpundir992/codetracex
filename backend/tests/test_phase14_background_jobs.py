"""
Tests for Phase 14: Background Processing & Job Queue.

Tests cover:
- Job creation
- Job lifecycle (queued → running → completed)
- Job failure handling
- Job cancellation
- Duplicate job protection
- Progress tracking
- Repository isolation
- Cleanup on error
"""
import pytest
import time
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Repository, AnalysisRun, AnalysisStatus
from app.workers.tasks import analyze_repository_task, cancel_analysis_task
from app.services.job_orchestration_service import JobOrchestrationService


class TestJobAPI:
    """Test job API endpoints."""
    
    def test_start_analysis_async(self, client, db):
        """Test starting asynchronous analysis."""
        # Mock GitHub API response
        with patch('app.services.repository_service.RepositoryService.get_repository_metadata') as mock_get_metadata:
            mock_get_metadata.return_value = {
                "owner": "testowner",
                "name": "testrepo",
                "full_name": "testowner/testrepo",
                "url": "https://github.com/testowner/testrepo",
                "default_branch": "main",
                "description": "Test repository",
                "language": "Python",
                "stars": 100
            }
            
            # Mock Redis queue
            with patch('app.api.jobs.get_analysis_queue') as mock_queue:
                mock_job = Mock()
                mock_job.id = "test-job-123"
                mock_queue.return_value.enqueue.return_value = mock_job
                
                response = client.post(
                    "/api/repositories/analyze-async",
                    json={"url": "https://github.com/testowner/testrepo"}
                )
                
                assert response.status_code == 202
                data = response.json()
                assert data["status"] == "queued"
                assert "job_id" in data
                assert "analysis_run_id" in data
                assert "repository_id" in data
    
    def test_start_analysis_async_duplicate(self, client, db):
        """Test duplicate job protection."""
        # Create repository
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        # Create active analysis run
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.RUNNING,
            progress=50,
            current_stage="Running"
        )
        db.add(analysis_run)
        db.commit()
        
        # Mock GitHub API
        with patch('app.services.repository_service.RepositoryService.get_repository_metadata') as mock_get_metadata:
            mock_get_metadata.return_value = {
                "owner": "testowner",
                "name": "testrepo",
                "full_name": "testowner/testrepo",
                "url": "https://github.com/testowner/testrepo",
                "default_branch": "main"
            }
            
            # Try to start another analysis
            response = client.post(
                "/api/repositories/analyze-async",
                json={"url": "https://github.com/testowner/testrepo"}
            )
            
            # Should return 409 Conflict
            assert response.status_code == 409
            assert "already in progress" in response.json()["detail"].lower()
    
    def test_get_job_status(self, client, db):
        """Test retrieving job status."""
        # Create repository and analysis run
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.RUNNING,
            job_id="test-job-123",
            progress=65,
            current_stage="Building semantic chunks",
            total_files=1200,
            total_symbols=3400
        )
        db.add(analysis_run)
        db.commit()
        
        # Get job status
        response = client.get(f"/api/jobs/{analysis_run.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["progress"] == 65
        assert data["current_stage"] == "Building semantic chunks"
        assert data["total_files"] == 1200
        assert data["total_symbols"] == 3400
    
    def test_get_job_status_not_found(self, client, db):
        """Test retrieving non-existent job."""
        fake_id = uuid4()
        response = client.get(f"/api/jobs/{fake_id}")
        
        assert response.status_code == 404
    
    def test_cancel_job(self, client, db):
        """Test job cancellation."""
        # Create repository and analysis run
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.RUNNING,
            job_id="test-job-123",
            progress=30,
            current_stage="Analyzing code"
        )
        db.add(analysis_run)
        db.commit()
        
        # Mock RQ job
        with patch('app.api.jobs.get_analysis_queue') as mock_queue:
            mock_job = Mock()
            mock_job.cancel = Mock()
            with patch('app.api.jobs.Job.fetch', return_value=mock_job):
                # Cancel job
                response = client.post(f"/api/jobs/{analysis_run.id}/cancel")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "cancelled"
                
                # Verify analysis run is marked as cancelled
                db.refresh(analysis_run)
                assert analysis_run.status == AnalysisStatus.CANCELLED
    
    def test_cancel_completed_job(self, client, db):
        """Test cancelling already completed job."""
        # Create repository and completed analysis run
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.COMPLETED,
            progress=100,
            current_stage="Completed"
        )
        db.add(analysis_run)
        db.commit()
        
        # Try to cancel
        response = client.post(f"/api/jobs/{analysis_run.id}/cancel")
        
        # Should return 409 Conflict
        assert response.status_code == 409
    
    def test_get_latest_job_for_repository(self, client, db):
        """Test retrieving latest job for repository."""
        # Create repository
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        # Create older analysis run
        old_analysis = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.COMPLETED,
            started_at=datetime(2026, 1, 1)
        )
        db.add(old_analysis)
        
        # Create newer analysis run
        new_analysis = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.RUNNING,
            progress=50,
            started_at=datetime(2026, 9, 23)
        )
        db.add(new_analysis)
        db.commit()
        
        # Get latest job
        response = client.get(f"/api/repositories/{repo.id}/latest-job")
        
        assert response.status_code == 200
        data = response.json()
        assert data["analysis_run_id"] == str(new_analysis.id)
        assert data["status"] == "running"


class TestJobOrchestration:
    """Test job orchestration service."""
    
    def test_update_progress(self, db):
        """Test progress tracking."""
        # Create repository and analysis run
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.QUEUED
        )
        db.add(analysis_run)
        db.commit()
        
        # Create orchestration service
        orchestrator = JobOrchestrationService(db, analysis_run)
        
        # Update progress
        orchestrator.update_progress("Testing", 42)
        
        # Verify
        db.refresh(analysis_run)
        assert analysis_run.current_stage == "Testing"
        assert analysis_run.progress == 42
    
    def test_mark_running(self, db):
        """Test marking analysis as running."""
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.QUEUED
        )
        db.add(analysis_run)
        db.commit()
        
        orchestrator = JobOrchestrationService(db, analysis_run)
        orchestrator.mark_running()
        
        db.refresh(analysis_run)
        assert analysis_run.status == AnalysisStatus.RUNNING
        assert analysis_run.progress == 0
        assert analysis_run.current_stage == "Starting analysis"
    
    def test_mark_completed(self, db):
        """Test marking analysis as completed."""
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.RUNNING
        )
        db.add(analysis_run)
        db.commit()
        
        orchestrator = JobOrchestrationService(db, analysis_run)
        orchestrator.mark_completed()
        
        db.refresh(analysis_run)
        assert analysis_run.status == AnalysisStatus.COMPLETED
        assert analysis_run.progress == 100
        assert analysis_run.current_stage == "Completed"
        assert analysis_run.completed_at is not None
    
    def test_mark_failed(self, db):
        """Test marking analysis as failed."""
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.RUNNING
        )
        db.add(analysis_run)
        db.commit()
        
        orchestrator = JobOrchestrationService(db, analysis_run)
        orchestrator.mark_failed("Test error message")
        
        db.refresh(analysis_run)
        assert analysis_run.status == AnalysisStatus.FAILED
        assert analysis_run.error_message == "Test error message"
        assert analysis_run.completed_at is not None
    
    def test_safe_error_message(self, db):
        """Test safe error message generation."""
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.RUNNING
        )
        db.add(analysis_run)
        db.commit()
        
        orchestrator = JobOrchestrationService(db, analysis_run)
        
        # Test various error types
        from app.services.repository_service import InvalidRepositoryURLError
        from app.services.github_service import RepositoryNotFoundError
        from app.services.download_service import DownloadTooLargeError
        
        # Invalid URL
        error = InvalidRepositoryURLError("Invalid URL")
        safe_msg = orchestrator._get_safe_error_message(error)
        assert safe_msg == "Invalid repository URL"
        
        # Repository not found
        error = RepositoryNotFoundError("Not found")
        safe_msg = orchestrator._get_safe_error_message(error)
        assert safe_msg == "Repository not found on GitHub"
        
        # Too large
        error = DownloadTooLargeError("Too big")
        safe_msg = orchestrator._get_safe_error_message(error)
        assert safe_msg == "Repository exceeds maximum size limit"
        
        # Generic error (should remove file paths)
        error = Exception("Error at /home/user/secret/path: failed")
        safe_msg = orchestrator._get_safe_error_message(error)
        assert "/home/user/secret/path" not in safe_msg
        assert "[path]" in safe_msg


class TestWorkerTasks:
    """Test worker task handlers."""
    
    def test_analyze_repository_task_success(self, db):
        """Test successful repository analysis task."""
        # Create repository
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        # Create analysis run
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.QUEUED
        )
        db.add(analysis_run)
        db.commit()
        analysis_run_id = str(analysis_run.id)
        
        # Mock the orchestration service execution
        with patch('app.workers.tasks.JobOrchestrationService') as MockOrchestrator:
            mock_instance = MockOrchestrator.return_value
            mock_instance.execute_analysis.return_value = {
                "status": "completed",
                "repository_id": str(repo.id),
                "analysis_run_id": analysis_run_id,
                "total_files": 100,
                "total_symbols": 500
            }
            
            # Run task
            result = analyze_repository_task(
                analysis_run_id,
                "https://github.com/testowner/testrepo"
            )
            
            assert result["status"] == "completed"
            assert result["analysis_run_id"] == analysis_run_id
    
    def test_analyze_repository_task_not_found(self):
        """Test task with non-existent analysis run."""
        fake_id = str(uuid4())
        
        with pytest.raises(ValueError, match="AnalysisRun not found"):
            analyze_repository_task(fake_id, "https://github.com/test/repo")
    
    def test_cancel_analysis_task(self, db):
        """Test analysis cancellation task."""
        # Create repository and analysis run
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.RUNNING,
            progress=40
        )
        db.add(analysis_run)
        db.commit()
        analysis_run_id = str(analysis_run.id)
        
        # Run cancellation task
        result = cancel_analysis_task(analysis_run_id)
        
        assert result["status"] == "cancelled"
        assert result["analysis_run_id"] == analysis_run_id
        
        # Verify analysis run is cancelled
        db.refresh(analysis_run)
        assert analysis_run.status == AnalysisStatus.CANCELLED


class TestRedisConnection:
    """Test Redis connection utilities."""
    
    def test_get_redis_connection(self):
        """Test Redis connection creation."""
        with patch('app.workers.redis_connection.redis.from_url') as mock_from_url:
            from app.workers.redis_connection import get_redis_connection
            
            get_redis_connection()
            
            # Verify Redis connection was created
            mock_from_url.assert_called_once()
    
    def test_get_queue(self):
        """Test queue creation."""
        with patch('app.workers.redis_connection.get_redis_connection') as mock_conn:
            with patch('app.workers.redis_connection.Queue') as MockQueue:
                from app.workers.redis_connection import get_queue
                
                queue = get_queue("test-queue")
                
                # Verify Queue was created with correct name
                MockQueue.assert_called_once_with("test-queue", connection=mock_conn.return_value)
    
    def test_get_analysis_queue(self):
        """Test analysis queue retrieval."""
        with patch('app.workers.redis_connection.get_queue') as mock_get_queue:
            from app.workers.redis_connection import get_analysis_queue
            
            get_analysis_queue()
            
            # Verify correct queue name
            mock_get_queue.assert_called_once_with("analysis")


class TestDatabaseModels:
    """Test Phase 14 database model changes."""
    
    def test_analysis_run_job_fields(self, db):
        """Test new job tracking fields in AnalysisRun."""
        repo = Repository(
            owner="testowner",
            name="testrepo",
            full_name="testowner/testrepo",
            github_url="https://github.com/testowner/testrepo",
            default_branch="main"
        )
        db.add(repo)
        db.commit()
        
        # Create analysis run with job fields
        analysis_run = AnalysisRun(
            repository_id=repo.id,
            status=AnalysisStatus.RUNNING,
            job_id="test-job-123",
            progress=55,
            current_stage="Analyzing code"
        )
        db.add(analysis_run)
        db.commit()
        
        # Verify fields are persisted
        db.refresh(analysis_run)
        assert analysis_run.job_id == "test-job-123"
        assert analysis_run.progress == 55
        assert analysis_run.current_stage == "Analyzing code"
    
    def test_analysis_status_enum(self):
        """Test AnalysisStatus enum includes new values."""
        assert AnalysisStatus.QUEUED.value == "queued"
        assert AnalysisStatus.CANCELLED.value == "cancelled"
        assert AnalysisStatus.PENDING.value == "pending"
        assert AnalysisStatus.RUNNING.value == "running"
        assert AnalysisStatus.COMPLETED.value == "completed"
        assert AnalysisStatus.FAILED.value == "failed"
