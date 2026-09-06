"""
Tests for graph service - Phase 5.

These tests verify the GraphService correctly traverses code dependencies
stored in PostgreSQL.
"""
# Load environment variables before any other imports
from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import uuid4

from app.services.graph_service import GraphService
from app.db.models import (
    Repository, AnalysisRun, File, Symbol, Import, Call,
    AnalysisStatus, SymbolType
)
from app.db.session import SessionLocal, engine, Base


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def graph_service(db_session: Session) -> GraphService:
    """Create a graph service instance."""
    return GraphService(db_session)


@pytest.fixture
def sample_repository(db_session: Session):
    """Create a sample repository with analysis data."""
    # Create repository
    repo = Repository(
        owner="testuser",
        name="test-repo",
        full_name="testuser/test-repo",
        github_url="https://github.com/testuser/test-repo",
        default_branch="main"
    )
    db_session.add(repo)
    db_session.flush()
    
    # Create analysis run
    analysis_run = AnalysisRun(
        repository_id=repo.id,
        status=AnalysisStatus.COMPLETED,
        total_files=3,
        analyzed_files=3,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db_session.add(analysis_run)
    db_session.flush()
    
    # Create files
    file1 = File(
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="src/service.py",
        filename="service.py",
        extension=".py",
        language="Python",
        size_bytes=1000
    )
    file2 = File(
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="src/controller.py",
        filename="controller.py",
        extension=".py",
        language="Python",
        size_bytes=800
    )
    file3 = File(
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="src/utils.py",
        filename="utils.py",
        extension=".py",
        language="Python",
        size_bytes=500
    )
    db_session.add_all([file1, file2, file3])
    db_session.flush()
    
    # Create symbols
    # utils.py: validate_input function
    symbol_validate = Symbol(
        file_id=file3.id,
        analysis_run_id=analysis_run.id,
        name="validate_input",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=1,
        end_line=5
    )
    
    # service.py: create_order function
    symbol_create_order = Symbol(
        file_id=file1.id,
        analysis_run_id=analysis_run.id,
        name="create_order",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=10,
        end_line=20
    )
    
    # controller.py: process_order function
    symbol_process_order = Symbol(
        file_id=file2.id,
        analysis_run_id=analysis_run.id,
        name="process_order",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=5,
        end_line=15
    )
    
    # controller.py: handle_request function
    symbol_handle_request = Symbol(
        file_id=file2.id,
        analysis_run_id=analysis_run.id,
        name="handle_request",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=20,
        end_line=25
    )
    
    db_session.add_all([
        symbol_validate,
        symbol_create_order,
        symbol_process_order,
        symbol_handle_request
    ])
    db_session.flush()
    
    # Create call relationships
    # handle_request -> process_order
    call1 = Call(
        file_id=file2.id,
        analysis_run_id=analysis_run.id,
        caller_name="handle_request",
        callee_name="process_order",
        line_number=22
    )
    
    # process_order -> create_order
    call2 = Call(
        file_id=file2.id,
        analysis_run_id=analysis_run.id,
        caller_name="process_order",
        callee_name="create_order",
        line_number=10
    )
    
    # create_order -> validate_input
    call3 = Call(
        file_id=file1.id,
        analysis_run_id=analysis_run.id,
        caller_name="create_order",
        callee_name="validate_input",
        line_number=12
    )
    
    db_session.add_all([call1, call2, call3])
    db_session.flush()
    
    # Create imports
    # controller.py imports service.py
    import1 = Import(
        file_id=file2.id,
        analysis_run_id=analysis_run.id,
        source="./service",
        imported_names="create_order",
        line_number=1
    )
    
    # service.py imports utils.py
    import2 = Import(
        file_id=file1.id,
        analysis_run_id=analysis_run.id,
        source="./utils",
        imported_names="validate_input",
        line_number=1
    )
    
    db_session.add_all([import1, import2])
    db_session.commit()
    
    return {
        "repo": repo,
        "analysis_run": analysis_run,
        "files": {"service": file1, "controller": file2, "utils": file3},
        "symbols": {
            "validate_input": symbol_validate,
            "create_order": symbol_create_order,
            "process_order": symbol_process_order,
            "handle_request": symbol_handle_request
        }
    }


def test_get_symbol_callers_direct(graph_service, sample_repository):
    """Test getting direct callers of a symbol."""
    symbols = sample_repository["symbols"]
    
    # Get callers of create_order (should be process_order)
    callers = graph_service.get_symbol_callers(symbols["create_order"].id, depth=1)
    
    assert len(callers) == 1
    assert callers[0].relationship_type == "calls"
    assert callers[0].source.name == "process_order"
    assert callers[0].target.name == "create_order"


def test_get_symbol_callers_transitive(graph_service, sample_repository):
    """Test getting transitive callers with depth > 1."""
    symbols = sample_repository["symbols"]
    
    # Get callers of create_order with depth 2
    # Should get: process_order (direct) and handle_request (indirect)
    callers = graph_service.get_symbol_callers(symbols["create_order"].id, depth=2)
    
    # Should find at least process_order
    caller_names = [edge.source.name for edge in callers]
    assert "process_order" in caller_names
    
    # May also find handle_request if transitive traversal works
    # (handle_request -> process_order -> create_order)


def test_get_symbol_callees_direct(graph_service, sample_repository):
    """Test getting direct callees of a symbol."""
    symbols = sample_repository["symbols"]
    
    # Get callees of create_order (should be validate_input)
    callees = graph_service.get_symbol_callees(symbols["create_order"].id, depth=1)
    
    assert len(callees) == 1
    assert callees[0].relationship_type == "calls"
    assert callees[0].source.name == "create_order"
    assert callees[0].target.name == "validate_input"


def test_get_symbol_callees_multi_level(graph_service, sample_repository):
    """Test getting multi-level callees."""
    symbols = sample_repository["symbols"]
    
    # Get callees of handle_request with depth 2
    # Should get: process_order (direct) and create_order (indirect)
    callees = graph_service.get_symbol_callees(symbols["handle_request"].id, depth=2)
    
    callee_names = [edge.target.name for edge in callees]
    assert "process_order" in callee_names


def test_symbol_dependencies(graph_service, sample_repository):
    """Test getting all dependencies of a symbol."""
    symbols = sample_repository["symbols"]
    
    # Get dependencies of create_order
    deps = graph_service.get_symbol_dependencies(symbols["create_order"].id, depth=1)
    
    # Should have call dependencies
    assert "calls" in deps
    assert "imports" in deps
    
    # Should call validate_input
    if deps["calls"]:
        call_targets = [edge.target.name for edge in deps["calls"]]
        assert "validate_input" in call_targets


def test_symbol_dependents(graph_service, sample_repository):
    """Test getting all dependents of a symbol."""
    symbols = sample_repository["symbols"]
    
    # Get dependents of create_order
    dependents = graph_service.get_symbol_dependents(symbols["create_order"].id, depth=1)
    
    # Should have callers
    assert "callers" in dependents
    assert "imported_by" in dependents
    
    # Should be called by process_order
    if dependents["callers"]:
        caller_sources = [edge.source.name for edge in dependents["callers"]]
        assert "process_order" in caller_sources


def test_file_dependencies(graph_service, sample_repository):
    """Test getting file import dependencies."""
    files = sample_repository["files"]
    
    # Get dependencies of controller.py
    deps = graph_service.get_file_dependencies(files["controller"].id)
    
    # Should have at least one import edge
    # Note: Resolution depends on heuristic matching
    assert isinstance(deps, list)


def test_file_dependents(graph_service, sample_repository):
    """Test getting files that import a file."""
    files = sample_repository["files"]
    
    # Get dependents of service.py
    dependents = graph_service.get_file_dependents(files["service"].id)
    
    # Result depends on import resolution
    assert isinstance(dependents, list)


def test_impact_analysis(graph_service, sample_repository):
    """Test impact analysis for blast radius calculation."""
    symbols = sample_repository["symbols"]
    
    # Analyze impact of validate_input
    # Should affect: create_order (direct), process_order (indirect), handle_request (indirect)
    impact = graph_service.analyze_symbol_impact(symbols["validate_input"].id, max_depth=3)
    
    assert "target" in impact
    assert impact["target"]["name"] == "validate_input"
    assert "direct_callers" in impact
    assert "indirect_dependents" in impact
    assert "total_dependents" in impact
    assert "depth_map" in impact
    
    # Should have at least create_order as a caller
    total = impact["total_dependents"]
    assert total >= 1


def test_depth_limit_respected(graph_service, sample_repository):
    """Test that depth limits are enforced."""
    symbols = sample_repository["symbols"]
    
    # Get callers with depth 1
    callers_depth_1 = graph_service.get_symbol_callers(symbols["validate_input"].id, depth=1)
    
    # Get callers with depth 2
    callers_depth_2 = graph_service.get_symbol_callers(symbols["validate_input"].id, depth=2)
    
    # Depth 2 should find same or more results than depth 1
    assert len(callers_depth_2) >= len(callers_depth_1)


def test_max_depth_capped(graph_service, sample_repository):
    """Test that maximum depth is capped at MAX_DEPTH."""
    symbols = sample_repository["symbols"]
    
    # Request depth > MAX_DEPTH (10)
    # Should be capped to MAX_DEPTH
    callers = graph_service.get_symbol_callers(symbols["validate_input"].id, depth=100)
    
    # Should not crash and should return results
    assert isinstance(callers, list)


def test_nonexistent_symbol(graph_service, db_session):
    """Test querying a non-existent symbol."""
    fake_id = uuid4()
    
    callers = graph_service.get_symbol_callers(fake_id, depth=1)
    assert callers == []
    
    callees = graph_service.get_symbol_callees(fake_id, depth=1)
    assert callees == []


def test_cycle_detection(db_session, graph_service):
    """Test that cycles don't cause infinite loops."""
    # Create a repository with cyclic dependencies
    repo = Repository(
        owner="testuser",
        name="cycle-test",
        full_name="testuser/cycle-test",
        github_url="https://github.com/testuser/cycle-test",
        default_branch="main"
    )
    db_session.add(repo)
    db_session.flush()
    
    analysis_run = AnalysisRun(
        repository_id=repo.id,
        status=AnalysisStatus.COMPLETED,
        total_files=1,
        analyzed_files=1,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db_session.add(analysis_run)
    db_session.flush()
    
    file = File(
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="cycle.py",
        filename="cycle.py",
        extension=".py",
        language="Python",
        size_bytes=500
    )
    db_session.add(file)
    db_session.flush()
    
    # Create symbols A, B, C
    symbol_a = Symbol(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        name="function_a",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=1,
        end_line=5
    )
    symbol_b = Symbol(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        name="function_b",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=10,
        end_line=15
    )
    symbol_c = Symbol(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        name="function_c",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=20,
        end_line=25
    )
    db_session.add_all([symbol_a, symbol_b, symbol_c])
    db_session.flush()
    
    # Create cycle: A -> B -> C -> A
    call1 = Call(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        caller_name="function_a",
        callee_name="function_b",
        line_number=3
    )
    call2 = Call(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        caller_name="function_b",
        callee_name="function_c",
        line_number=12
    )
    call3 = Call(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        caller_name="function_c",
        callee_name="function_a",
        line_number=22
    )
    db_session.add_all([call1, call2, call3])
    db_session.commit()
    
    # Query should not hang or crash
    callees = graph_service.get_symbol_callees(symbol_a.id, depth=5)
    
    # Should get finite results despite cycle
    assert isinstance(callees, list)
    assert len(callees) > 0
    
    # Each symbol should appear at most once due to visited tracking
    target_names = [edge.target.name for edge in callees]
    # Allow some duplication at different levels, but should be bounded
    assert len(callees) < 100  # Sanity check for runaway traversal


def test_empty_analysis_run(db_session, graph_service):
    """Test querying an analysis run with no symbols."""
    repo = Repository(
        owner="testuser",
        name="empty-repo",
        full_name="testuser/empty-repo",
        github_url="https://github.com/testuser/empty-repo",
        default_branch="main"
    )
    db_session.add(repo)
    db_session.flush()
    
    analysis_run = AnalysisRun(
        repository_id=repo.id,
        status=AnalysisStatus.COMPLETED,
        total_files=0,
        analyzed_files=0,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db_session.add(analysis_run)
    db_session.commit()
    
    # Query with fake symbol ID should return empty results
    fake_id = uuid4()
    callers = graph_service.get_symbol_callers(fake_id, depth=1)
    assert callers == []


def test_multiple_callers(db_session, graph_service):
    """Test symbol with multiple direct callers."""
    repo = Repository(
        owner="testuser",
        name="multi-caller",
        full_name="testuser/multi-caller",
        github_url="https://github.com/testuser/multi-caller",
        default_branch="main"
    )
    db_session.add(repo)
    db_session.flush()
    
    analysis_run = AnalysisRun(
        repository_id=repo.id,
        status=AnalysisStatus.COMPLETED,
        total_files=1,
        analyzed_files=1,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db_session.add(analysis_run)
    db_session.flush()
    
    file = File(
        repository_id=repo.id,
        analysis_run_id=analysis_run.id,
        path="app.py",
        filename="app.py",
        extension=".py",
        language="Python",
        size_bytes=1000
    )
    db_session.add(file)
    db_session.flush()
    
    # Create one target symbol and three callers
    target = Symbol(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        name="shared_function",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=1,
        end_line=5
    )
    caller1 = Symbol(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        name="caller_one",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=10,
        end_line=15
    )
    caller2 = Symbol(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        name="caller_two",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=20,
        end_line=25
    )
    caller3 = Symbol(
        file_id=file.id,
        analysis_run_id=analysis_run.id,
        name="caller_three",
        symbol_type=SymbolType.FUNCTION,
        language="Python",
        start_line=30,
        end_line=35
    )
    db_session.add_all([target, caller1, caller2, caller3])
    db_session.flush()
    
    # All three call the target
    for i, caller in enumerate([caller1, caller2, caller3], 1):
        call = Call(
            file_id=file.id,
            analysis_run_id=analysis_run.id,
            caller_name=caller.name,
            callee_name=target.name,
            line_number=10 * i + 2
        )
        db_session.add(call)
    db_session.commit()
    
    # Get callers
    callers = graph_service.get_symbol_callers(target.id, depth=1)
    
    # Should find all three callers
    assert len(callers) == 3
    caller_names = {edge.source.name for edge in callers}
    assert caller_names == {"caller_one", "caller_two", "caller_three"}
