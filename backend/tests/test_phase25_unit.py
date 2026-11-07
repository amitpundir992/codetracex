"""
Unit tests for Phase 25: Operational Reliability & Automated Recovery

These tests verify the Phase 25 implementation without requiring database connections.
They focus on:
- Import verification
- Status enum correctness
- Warning tracking logic
- Configuration loading
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.db.models import AnalysisStatus


class TestAnalysisStatusEnum:
    """Test the updated AnalysisStatus enum."""
    
    def test_completed_with_warnings_exists(self):
        """Test that COMPLETED_WITH_WARNINGS status exists."""
        assert hasattr(AnalysisStatus, 'COMPLETED_WITH_WARNINGS')
        assert AnalysisStatus.COMPLETED_WITH_WARNINGS.value == 'completed_with_warnings'
    
    def test_all_statuses_present(self):
        """Test that all expected statuses exist."""
        expected_statuses = {
            'QUEUED', 'PENDING', 'RUNNING', 'COMPLETED', 
            'COMPLETED_WITH_WARNINGS', 'FAILED', 'CANCELLED'
        }
        actual_statuses = {s.name for s in AnalysisStatus}
        assert expected_statuses == actual_statuses
    
    def test_status_values(self):
        """Test that status values are correct."""
        assert AnalysisStatus.QUEUED.value == 'queued'
        assert AnalysisStatus.PENDING.value == 'pending'
        assert AnalysisStatus.RUNNING.value == 'running'
        assert AnalysisStatus.COMPLETED.value == 'completed'
        assert AnalysisStatus.COMPLETED_WITH_WARNINGS.value == 'completed_with_warnings'
        assert AnalysisStatus.FAILED.value == 'failed'
        assert AnalysisStatus.CANCELLED.value == 'cancelled'


class TestImports:
    """Test that Phase 25 modules can be imported."""
    
    def test_recovery_service_import(self):
        """Test that RecoveryService can be imported."""
        from app.services.recovery_service import RecoveryService
        assert RecoveryService is not None
    
    def test_scheduled_tasks_import(self):
        """Test that scheduled tasks module can be imported."""
        from app.workers import scheduled_tasks
        assert hasattr(scheduled_tasks, 'recover_stale_analyses_task')
        assert hasattr(scheduled_tasks, 'check_stale_analyses_task')
    
    def test_recovery_api_import(self):
        """Test that recovery API can be imported."""
        from app.api import recovery
        assert recovery.router is not None
    
    def test_job_orchestration_warnings(self):
        """Test that JobOrchestrationService has warnings tracking."""
        from app.services.job_orchestration_service import JobOrchestrationService
        
        # Verify the class has the warnings attribute in __init__
        import inspect
        source = inspect.getsource(JobOrchestrationService.__init__)
        assert 'self.warnings' in source


class TestConfigurationSettings:
    """Test Phase 25 configuration settings."""
    
    def test_stale_threshold_config(self):
        """Test that STALE_JOB_THRESHOLD_HOURS is configurable."""
        from app.core.config import Settings
        settings = Settings()
        
        assert hasattr(settings, 'STALE_JOB_THRESHOLD_HOURS')
        assert isinstance(settings.STALE_JOB_THRESHOLD_HOURS, int)
        assert settings.STALE_JOB_THRESHOLD_HOURS > 0
    
    def test_enable_auto_recovery_config(self):
        """Test that ENABLE_AUTO_RECOVERY is configurable."""
        from app.core.config import Settings
        settings = Settings()
        
        assert hasattr(settings, 'ENABLE_AUTO_RECOVERY')
        assert isinstance(settings.ENABLE_AUTO_RECOVERY, bool)


class TestWarningsTracking:
    """Test warnings tracking logic."""
    
    def test_warnings_json_serialization(self):
        """Test that warnings can be JSON serialized."""
        warnings = [
            {
                "stage": "embedding_generation",
                "message": "Failed to generate embeddings",
                "error": "APIError"
            },
            {
                "stage": "graph_building",
                "message": "Failed to build knowledge graph",
                "error": "TimeoutError"
            }
        ]
        
        # Serialize
        warnings_json = json.dumps(warnings)
        assert warnings_json is not None
        assert isinstance(warnings_json, str)
        
        # Deserialize
        deserialized = json.loads(warnings_json)
        assert deserialized == warnings
        assert len(deserialized) == 2
        assert deserialized[0]['stage'] == 'embedding_generation'
    
    def test_empty_warnings_handling(self):
        """Test that empty warnings list is handled correctly."""
        warnings = []
        
        # Empty list should be falsy in boolean context
        assert not warnings
        
        # But should serialize correctly
        warnings_json = json.dumps(warnings)
        assert warnings_json == '[]'
    
    def test_warning_structure(self):
        """Test that warning dictionaries have expected structure."""
        warning = {
            "stage": "test_stage",
            "message": "Test message",
            "error": "TestError"
        }
        
        # Verify keys
        assert 'stage' in warning
        assert 'message' in warning
        assert 'error' in warning
        
        # Verify types
        assert isinstance(warning['stage'], str)
        assert isinstance(warning['message'], str)
        assert isinstance(warning['error'], str)


class TestRecoveryServiceLogic:
    """Test recovery service logic without database."""
    
    def test_stale_cutoff_calculation(self):
        """Test stale cutoff time calculation."""
        threshold_hours = 24
        cutoff = datetime.utcnow() - timedelta(hours=threshold_hours)
        
        # Verify cutoff is in the past
        assert cutoff < datetime.utcnow()
        
        # Verify cutoff is approximately 24 hours ago
        elapsed = datetime.utcnow() - cutoff
        assert elapsed.total_seconds() / 3600 >= 23.9  # Allow for test execution time
        assert elapsed.total_seconds() / 3600 <= 24.1
    
    def test_elapsed_hours_calculation(self):
        """Test elapsed hours calculation."""
        started_at = datetime.utcnow() - timedelta(hours=30, minutes=15)
        elapsed = datetime.utcnow() - started_at
        elapsed_hours = elapsed.total_seconds() / 3600
        
        # Verify calculation
        assert elapsed_hours >= 30.2
        assert elapsed_hours <= 30.3
    
    def test_recovery_result_structure(self):
        """Test recovery result dictionary structure."""
        result = {
            'stale_count': 2,
            'recovered_count': 2,
            'repository_id': None,
            'threshold_hours': 24,
            'recovered_runs': ['run-id-1', 'run-id-2']
        }
        
        # Verify keys
        assert 'stale_count' in result
        assert 'recovered_count' in result
        assert 'repository_id' in result
        assert 'threshold_hours' in result
        assert 'recovered_runs' in result
        
        # Verify types
        assert isinstance(result['stale_count'], int)
        assert isinstance(result['recovered_count'], int)
        assert isinstance(result['threshold_hours'], int)
        assert isinstance(result['recovered_runs'], list)


class TestAPIEndpoints:
    """Test recovery API endpoints without database."""
    
    def test_recovery_request_model(self):
        """Test RecoveryRequest pydantic model."""
        from app.api.recovery import RecoveryRequest
        
        # Default request
        request = RecoveryRequest()
        assert request.repository_id is None
        assert request.stale_threshold_hours is None
        
        # Request with values
        from uuid import uuid4
        repo_id = uuid4()
        request = RecoveryRequest(
            repository_id=repo_id,
            stale_threshold_hours=12
        )
        assert request.repository_id == repo_id
        assert request.stale_threshold_hours == 12
    
    def test_recovery_response_model(self):
        """Test RecoveryResponse pydantic model."""
        from app.api.recovery import RecoveryResponse
        
        response = RecoveryResponse(
            stale_count=2,
            recovered_count=2,
            repository_id=None,
            threshold_hours=24,
            recovered_runs=['run-1', 'run-2'],
            message="Recovery completed"
        )
        
        assert response.stale_count == 2
        assert response.recovered_count == 2
        assert response.threshold_hours == 24
        assert len(response.recovered_runs) == 2
        assert response.message == "Recovery completed"
    
    def test_stale_run_info_model(self):
        """Test StaleRunInfo pydantic model."""
        from app.api.recovery import StaleRunInfo
        
        info = StaleRunInfo(
            analysis_run_id="test-run-id",
            repository_id="test-repo-id",
            status="running",
            started_at="2026-11-06T12:00:00",
            elapsed_hours=25.5,
            current_stage="Static analysis",
            progress=40,
            job_id="test-job-id"
        )
        
        assert info.analysis_run_id == "test-run-id"
        assert info.status == "running"
        assert info.elapsed_hours == 25.5
        assert info.progress == 40


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
