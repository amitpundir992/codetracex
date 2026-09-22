"""
Tests for Impact Analysis Service (Phase 13).

Tests deterministic impact analysis with bounded traversal.
"""
import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from app.services.impact_analysis_service import ImpactAnalysisService
from app.db.models import (
    Repository, AnalysisRun, File, Symbol, Call,
    SymbolType, AnalysisStatus
)


@pytest.fixture
def sample_graph(db: Session):
    """Create a sample dependency graph for testing."""
    repo = Repository(
        id=uuid4(),
        name="test-repo",
        full_name="test/test-repo",
        owner="test",
        github_url="https://github.com/test/test-repo",
        default_branch="main",
        description="Test repository"
    )
    db.add(repo)
    
    analysis_run = AnalysisRun(
        id=uuid4(),
        repository_id=repo.id,
        status=AnalysisStatus.COMPLETED,
        commit_sha="abc123"
    )
    db.add(analysis_run)
    
    # Create files
    service_file = File(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="src/service.py",
        filename="service.py",
        language="python",
        size_bytes=1000
    )
    db.add(service_file)
    
    controller_file = File(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="src/controller.py",
        filename="controller.py",
        language="python",
        size_bytes=800
    )
    db.add(controller_file)
    
    # Create symbols forming a call chain
    # target -> caller1 -> caller2
    target_symbol = Symbol(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=service_file.id,
        name="process_data",
        symbol_type=SymbolType.FUNCTION,
        start_line=10,
        end_line=20
    )
    db.add(target_symbol)
    
    caller1_symbol = Symbol(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=service_file.id,
        name="handle_request",
        symbol_type=SymbolType.FUNCTION,
        start_line=25,
        end_line=35
    )
    db.add(caller1_symbol)
    
    caller2_symbol = Symbol(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=controller_file.id,
        name="endpoint_handler",
        symbol_type=SymbolType.FUNCTION,
        start_line=10,
        end_line=20
    )
    db.add(caller2_symbol)
    
    # Create call relationships
    call1 = Call(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=service_file.id,
        caller_name="handle_request",
        callee_name="process_data",
        line_number=30
    )
    db.add(call1)
    
    call2 = Call(
        id=uuid4(),
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        file_id=controller_file.id,
        caller_name="endpoint_handler",
        callee_name="handle_request",
        line_number=15
    )
    db.add(call2)
    
    db.commit()
    
    return {
        "repository": repo,
        "analysis_run": analysis_run,
        "target_symbol": target_symbol,
        "caller1_symbol": caller1_symbol,
        "caller2_symbol": caller2_symbol,
        "service_file": service_file,
        "controller_file": controller_file
    }


class TestImpactAnalysisService:
    """Tests for impact analysis service."""
    
    def test_analyze_symbol_direct_callers(self, db: Session, sample_graph):
        """Test analyzing direct callers only."""
        service = ImpactAnalysisService(db)
        target = sample_graph["target_symbol"]
        repo = sample_graph["repository"]
        
        result = service.analyze_symbol_impact(
            symbol_id=target.id,
            repository_id=repo.id,
            depth=1
        )
        
        assert result is not None
        assert "impacts" in result
        assert "summary" in result
        
        # Should find handle_request as direct caller
        direct_callers = [i for i in result["impacts"] if i.impact_category == "direct_caller"]
        assert len(direct_callers) >= 1
        assert any(i.entity_name == "handle_request" for i in direct_callers)
        
        # Should NOT find endpoint_handler at depth 1
        assert not any(i.entity_name == "endpoint_handler" for i in result["impacts"])
    
    def test_analyze_symbol_transitive_callers(self, db: Session, sample_graph):
        """Test analyzing transitive callers."""
        service = ImpactAnalysisService(db)
        target = sample_graph["target_symbol"]
        repo = sample_graph["repository"]
        
        result = service.analyze_symbol_impact(
            symbol_id=target.id,
            repository_id=repo.id,
            depth=3
        )
        
        assert result is not None
        
        # Should find both direct and transitive callers
        all_callers = [i for i in result["impacts"] 
                      if "caller" in i.impact_category]
        assert len(all_callers) >= 2
        
        # Should include endpoint_handler as transitive caller
        assert any(i.entity_name == "endpoint_handler" for i in all_callers)
    
    def test_impact_summary(self, db: Session, sample_graph):
        """Test impact summary generation."""
        service = ImpactAnalysisService(db)
        target = sample_graph["target_symbol"]
        repo = sample_graph["repository"]
        
        result = service.analyze_symbol_impact(
            symbol_id=target.id,
            repository_id=repo.id,
            depth=3
        )
        
        summary = result["summary"]
        assert summary.total_impacts >= 2
        assert summary.direct_impacts >= 1
        assert summary.affected_files_count >= 2
        assert summary.max_depth_reached <= 3
    
    def test_truncation_not_triggered_small_graph(self, db: Session, sample_graph):
        """Test that truncation is not triggered for small graphs."""
        service = ImpactAnalysisService(db)
        target = sample_graph["target_symbol"]
        repo = sample_graph["repository"]
        
        result = service.analyze_symbol_impact(
            symbol_id=target.id,
            repository_id=repo.id,
            depth=3
        )
        
        truncation = result["truncation"]
        assert not truncation.is_truncated
        assert truncation.nodes_analyzed < service.MAX_NODES
        assert truncation.edges_analyzed < service.MAX_EDGES
    
    def test_repository_isolation(self, db: Session, sample_graph):
        """Test repository isolation enforcement."""
        service = ImpactAnalysisService(db)
        target = sample_graph["target_symbol"]
        wrong_repo_id = uuid4()
        
        result = service.analyze_symbol_impact(
            symbol_id=target.id,
            repository_id=wrong_repo_id,
            depth=3
        )
        
        # Should return empty result for wrong repository
        assert result["summary"].total_impacts == 0
    
    def test_analysis_run_isolation(self, db: Session, sample_graph):
        """Test analysis run isolation enforcement."""
        service = ImpactAnalysisService(db)
        target = sample_graph["target_symbol"]
        repo = sample_graph["repository"]
        wrong_run_id = uuid4()
        
        result = service.analyze_symbol_impact(
            symbol_id=target.id,
            repository_id=repo.id,
            analysis_run_id=wrong_run_id,
            depth=3
        )
        
        # Should return empty result for wrong analysis run
        assert result["summary"].total_impacts == 0
    
    def test_depth_limit_enforcement(self, db: Session, sample_graph):
        """Test that depth limits are enforced."""
        service = ImpactAnalysisService(db)
        target = sample_graph["target_symbol"]
        repo = sample_graph["repository"]
        
        # Request depth > MAX_DEPTH
        result = service.analyze_symbol_impact(
            symbol_id=target.id,
            repository_id=repo.id,
            depth=100  # Way over limit
        )
        
        # Should be capped at MAX_DEPTH
        summary = result["summary"]
        assert summary.max_depth_reached <= service.MAX_DEPTH
    
    def test_affected_files_collection(self, db: Session, sample_graph):
        """Test affected files are correctly collected."""
        service = ImpactAnalysisService(db)
        target = sample_graph["target_symbol"]
        repo = sample_graph["repository"]
        
        result = service.analyze_symbol_impact(
            symbol_id=target.id,
            repository_id=repo.id,
            depth=3
        )
        
        affected_files = result["affected_files"]
        assert len(affected_files) >= 2
        assert "src/service.py" in affected_files
        assert "src/controller.py" in affected_files
    
    def test_analyze_file_impact(self, db: Session, sample_graph):
        """Test file impact analysis."""
        service = ImpactAnalysisService(db)
        file = sample_graph["service_file"]
        repo = sample_graph["repository"]
        
        result = service.analyze_file_impact(
            file_id=file.id,
            repository_id=repo.id,
            depth=2
        )
        
        assert result is not None
        assert "impacts" in result
        assert "summary" in result
        
        # Should have some impacts from symbols in the file
        assert result["summary"].total_impacts >= 0
    
    def test_empty_result_nonexistent_symbol(self, db: Session, sample_graph):
        """Test empty result for nonexistent symbol."""
        service = ImpactAnalysisService(db)
        repo = sample_graph["repository"]
        fake_symbol_id = uuid4()
        
        result = service.analyze_symbol_impact(
            symbol_id=fake_symbol_id,
            repository_id=repo.id,
            depth=3
        )
        
        assert result["summary"].total_impacts == 0
        assert len(result["impacts"]) == 0
        assert len(result["affected_files"]) == 0
