"""
Tests for Phase 8 - Workflow & Data-Flow Intelligence.

This test suite covers:
- WorkflowService functionality
- Workflow API endpoints
- Cycle detection
- Depth limits
- Repository isolation
- Edge cases and error handling
"""
import pytest
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import (
    Repository, AnalysisRun, File, Symbol, Call, ApiEndpoint,
    AnalysisStatus, SymbolType, HttpMethod
)
from app.services.workflow_service import WorkflowService


@pytest.fixture
def sample_repository(db: Session):
    """Create a sample repository for testing."""
    repo = Repository(
        id=uuid4(),
        owner="testowner",
        name="testrepo",
        full_name="testowner/testrepo",
        github_url="https://github.com/testowner/testrepo",
        default_branch="main"
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


@pytest.fixture
def sample_analysis(db: Session, sample_repository: Repository):
    """Create a sample analysis run."""
    analysis = AnalysisRun(
        id=uuid4(),
        repository_id=sample_repository.id,
        status=AnalysisStatus.COMPLETED,
        total_files=3,
        analyzed_files=3,
        total_symbols=5,
        total_calls=4,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@pytest.fixture
def sample_files(db: Session, sample_repository: Repository, sample_analysis: AnalysisRun):
    """Create sample files."""
    files = [
        File(
            id=uuid4(),
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis.id,
            path="api/endpoints.py",
            filename="endpoints.py",
            extension=".py",
            language="python",
            size_bytes=1000,
            line_count=50
        ),
        File(
            id=uuid4(),
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis.id,
            path="services/order_service.py",
            filename="order_service.py",
            extension=".py",
            language="python",
            size_bytes=2000,
            line_count=100
        ),
        File(
            id=uuid4(),
            repository_id=sample_repository.id,
            analysis_run_id=sample_analysis.id,
            path="repositories/order_repository.py",
            filename="order_repository.py",
            extension=".py",
            language="python",
            size_bytes=1500,
            line_count=75
        )
    ]
    for file in files:
        db.add(file)
    db.commit()
    for file in files:
        db.refresh(file)
    return files


@pytest.fixture
def sample_symbols(db: Session, sample_analysis: AnalysisRun, sample_files):
    """
    Create sample symbols representing a typical workflow:
    
    create_order (handler)
      ↓
    validate_order
      ↓
    OrderService.create
      ↓
    OrderRepository.save
    """
    symbols = [
        Symbol(
            id=uuid4(),
            file_id=sample_files[0].id,
            analysis_run_id=sample_analysis.id,
            name="create_order",
            symbol_type=SymbolType.FUNCTION,
            language="python",
            start_line=10,
            end_line=20
        ),
        Symbol(
            id=uuid4(),
            file_id=sample_files[0].id,
            analysis_run_id=sample_analysis.id,
            name="validate_order",
            symbol_type=SymbolType.FUNCTION,
            language="python",
            start_line=25,
            end_line=30
        ),
        Symbol(
            id=uuid4(),
            file_id=sample_files[1].id,
            analysis_run_id=sample_analysis.id,
            name="OrderService.create",
            symbol_type=SymbolType.METHOD,
            language="python",
            start_line=40,
            end_line=60
        ),
        Symbol(
            id=uuid4(),
            file_id=sample_files[2].id,
            analysis_run_id=sample_analysis.id,
            name="OrderRepository.save",
            symbol_type=SymbolType.METHOD,
            language="python",
            start_line=30,
            end_line=45
        )
    ]
    for symbol in symbols:
        db.add(symbol)
    db.commit()
    for symbol in symbols:
        db.refresh(symbol)
    return symbols


@pytest.fixture
def sample_calls(db: Session, sample_analysis: AnalysisRun, sample_files, sample_symbols):
    """
    Create sample calls representing execution flow:
    
    create_order → validate_order
    create_order → OrderService.create
    OrderService.create → OrderRepository.save
    """
    calls = [
        Call(
            id=uuid4(),
            file_id=sample_files[0].id,
            analysis_run_id=sample_analysis.id,
            caller_name="create_order",
            callee_name="validate_order",
            line_number=12
        ),
        Call(
            id=uuid4(),
            file_id=sample_files[0].id,
            analysis_run_id=sample_analysis.id,
            caller_name="create_order",
            callee_name="OrderService.create",
            line_number=15
        ),
        Call(
            id=uuid4(),
            file_id=sample_files[1].id,
            analysis_run_id=sample_analysis.id,
            caller_name="OrderService.create",
            callee_name="OrderRepository.save",
            line_number=55
        )
    ]
    for call in calls:
        db.add(call)
    db.commit()
    for call in calls:
        db.refresh(call)
    return calls


@pytest.fixture
def sample_endpoint(db: Session, sample_repository: Repository, sample_analysis: AnalysisRun, sample_files, sample_symbols):
    """Create a sample API endpoint."""
    endpoint = ApiEndpoint(
        id=uuid4(),
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis.id,
        file_id=sample_files[0].id,
        symbol_id=sample_symbols[0].id,  # Links to create_order
        method=HttpMethod.POST,
        path="/api/orders",
        framework="fastapi",
        handler_name="create_order",
        start_line=10,
        end_line=20
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


# WorkflowService Tests

def test_build_endpoint_workflow_basic(db: Session, sample_endpoint, sample_symbols, sample_calls):
    """Test basic endpoint workflow construction."""
    service = WorkflowService(db)
    workflow = service.build_endpoint_workflow(sample_endpoint.id, depth=3)
    
    # Should have endpoint node + handler + callees
    assert workflow.start_node.type == "endpoint"
    assert workflow.start_node.name == "POST /api/orders"
    
    # Should have multiple nodes (endpoint, handler, validate_order, OrderService.create, OrderRepository.save)
    assert len(workflow.nodes) >= 4
    
    # Should have edges
    assert len(workflow.edges) >= 3
    
    # Should not be truncated
    assert workflow.truncated is False
    
    # Start node should be in nodes list
    assert any(node.id == workflow.start_node.id for node in workflow.nodes)


def test_build_symbol_workflow_downstream(db: Session, sample_symbols, sample_calls):
    """Test symbol workflow with downstream traversal."""
    service = WorkflowService(db)
    
    # Start from create_order symbol
    workflow = service.build_symbol_workflow(
        sample_symbols[0].id,
        depth=2,
        direction="downstream"
    )
    
    # Should have create_order as start
    assert workflow.start_node.type == "symbol"
    assert workflow.start_node.name == "create_order"
    
    # Should include callees
    node_names = [node.name for node in workflow.nodes]
    assert "validate_order" in node_names
    assert "OrderService.create" in node_names


def test_build_symbol_workflow_upstream(db: Session, sample_symbols, sample_calls):
    """Test symbol workflow with upstream traversal."""
    service = WorkflowService(db)
    
    # Start from OrderRepository.save (leaf node)
    workflow = service.build_symbol_workflow(
        sample_symbols[3].id,
        depth=2,
        direction="upstream"
    )
    
    # Should have OrderRepository.save as start
    assert workflow.start_node.name == "OrderRepository.save"
    
    # Should include callers
    node_names = [node.name for node in workflow.nodes]
    assert "OrderService.create" in node_names


def test_build_symbol_workflow_both_directions(db: Session, sample_symbols, sample_calls):
    """Test symbol workflow with bidirectional traversal."""
    service = WorkflowService(db)
    
    # Start from OrderService.create (middle node)
    workflow = service.build_symbol_workflow(
        sample_symbols[2].id,
        depth=2,
        direction="both"
    )
    
    # Should have OrderService.create as start
    assert workflow.start_node.name == "OrderService.create"
    
    # Should include both upstream and downstream
    node_names = [node.name for node in workflow.nodes]
    assert "create_order" in node_names  # Upstream
    assert "OrderRepository.save" in node_names  # Downstream


def test_workflow_depth_limit(db: Session, sample_symbols, sample_calls):
    """Test that depth limit is respected."""
    service = WorkflowService(db)
    
    # Workflow with depth 1 should only include immediate callees
    workflow_depth_1 = service.build_symbol_workflow(
        sample_symbols[0].id,
        depth=1,
        direction="downstream"
    )
    
    # Should have create_order + direct callees (validate_order, OrderService.create)
    assert len(workflow_depth_1.nodes) <= 3
    
    # Workflow with depth 2 should include more
    workflow_depth_2 = service.build_symbol_workflow(
        sample_symbols[0].id,
        depth=2,
        direction="downstream"
    )
    
    # Should include OrderRepository.save (called by OrderService.create)
    node_names = [node.name for node in workflow_depth_2.nodes]
    assert "OrderRepository.save" in node_names


def test_workflow_cycle_detection(db: Session, sample_repository, sample_analysis, sample_files):
    """Test that cycles are handled correctly without infinite recursion."""
    # Create symbols with a cycle: A → B → C → A
    symbol_a = Symbol(
        id=uuid4(),
        file_id=sample_files[0].id,
        analysis_run_id=sample_analysis.id,
        name="function_a",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        start_line=1,
        end_line=5
    )
    symbol_b = Symbol(
        id=uuid4(),
        file_id=sample_files[0].id,
        analysis_run_id=sample_analysis.id,
        name="function_b",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        start_line=10,
        end_line=15
    )
    symbol_c = Symbol(
        id=uuid4(),
        file_id=sample_files[0].id,
        analysis_run_id=sample_analysis.id,
        name="function_c",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        start_line=20,
        end_line=25
    )
    
    db.add_all([symbol_a, symbol_b, symbol_c])
    db.commit()
    
    # Create cycle: A → B → C → A
    calls = [
        Call(
            id=uuid4(),
            file_id=sample_files[0].id,
            analysis_run_id=sample_analysis.id,
            caller_name="function_a",
            callee_name="function_b",
            line_number=3
        ),
        Call(
            id=uuid4(),
            file_id=sample_files[0].id,
            analysis_run_id=sample_analysis.id,
            caller_name="function_b",
            callee_name="function_c",
            line_number=12
        ),
        Call(
            id=uuid4(),
            file_id=sample_files[0].id,
            analysis_run_id=sample_analysis.id,
            caller_name="function_c",
            callee_name="function_a",
            line_number=22
        )
    ]
    
    for call in calls:
        db.add(call)
    db.commit()
    
    # Build workflow - should not hang or crash
    service = WorkflowService(db)
    workflow = service.build_symbol_workflow(
        symbol_a.id,
        depth=5,
        direction="downstream"
    )
    
    # Should complete without infinite recursion
    assert workflow is not None
    
    # Should have all three nodes (visited once each)
    assert len(workflow.nodes) == 3
    
    # Should have edges (may have duplicates for cycle)
    assert len(workflow.edges) >= 3


def test_workflow_max_depth_clamping(db: Session, sample_symbols):
    """Test that depth is clamped to MAX_DEPTH."""
    service = WorkflowService(db)
    
    # Request depth > MAX_DEPTH (10)
    workflow = service.build_symbol_workflow(
        sample_symbols[0].id,
        depth=100,  # Way over the limit
        direction="downstream"
    )
    
    # Should be clamped to MAX_DEPTH
    assert workflow.depth == min(100, WorkflowService.MAX_DEPTH)


def test_workflow_repository_isolation(db: Session, sample_repository, sample_analysis, sample_files):
    """Test that workflows are isolated by repository."""
    # Create a second repository
    repo2 = Repository(
        id=uuid4(),
        owner="other",
        name="other-repo",
        full_name="other/other-repo",
        github_url="https://github.com/other/other-repo"
    )
    db.add(repo2)
    db.commit()
    
    analysis2 = AnalysisRun(
        id=uuid4(),
        repository_id=repo2.id,
        status=AnalysisStatus.COMPLETED,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db.add(analysis2)
    db.commit()
    
    file2 = File(
        id=uuid4(),
        repository_id=repo2.id,
        analysis_run_id=analysis2.id,
        path="other.py",
        filename="other.py",
        extension=".py",
        language="python",
        size_bytes=500,
        line_count=25
    )
    db.add(file2)
    db.commit()
    
    symbol2 = Symbol(
        id=uuid4(),
        file_id=file2.id,
        analysis_run_id=analysis2.id,
        name="other_function",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        start_line=1,
        end_line=5
    )
    db.add(symbol2)
    db.commit()
    
    # Build workflow from repo2 symbol
    service = WorkflowService(db)
    workflow = service.build_symbol_workflow(
        symbol2.id,
        depth=3,
        direction="downstream"
    )
    
    # Should only include symbols from repo2
    for node in workflow.nodes:
        # All symbol nodes should be from repo2's analysis run
        if node.type == "symbol":
            # Verify by checking file path
            assert "other.py" in node.file_path


def test_workflow_missing_handler(db: Session, sample_repository, sample_analysis, sample_files):
    """Test endpoint with no resolved handler symbol."""
    endpoint = ApiEndpoint(
        id=uuid4(),
        repository_id=sample_repository.id,
        analysis_run_id=sample_analysis.id,
        file_id=sample_files[0].id,
        symbol_id=None,  # No resolved handler
        method=HttpMethod.GET,
        path="/api/test",
        framework="fastapi",
        handler_name="test_handler",
        start_line=1,
        end_line=5
    )
    db.add(endpoint)
    db.commit()
    
    # Should not crash
    service = WorkflowService(db)
    workflow = service.build_endpoint_workflow(endpoint.id, depth=3)
    
    # Should have endpoint node only
    assert workflow.start_node.type == "endpoint"
    assert len(workflow.nodes) == 1
    assert len(workflow.edges) == 0


def test_workflow_no_calls(db: Session, sample_repository, sample_analysis, sample_files):
    """Test symbol with no downstream calls."""
    # Create a symbol with no calls
    symbol = Symbol(
        id=uuid4(),
        file_id=sample_files[0].id,
        analysis_run_id=sample_analysis.id,
        name="leaf_function",
        symbol_type=SymbolType.FUNCTION,
        language="python",
        start_line=1,
        end_line=5
    )
    db.add(symbol)
    db.commit()
    
    # Build workflow
    service = WorkflowService(db)
    workflow = service.build_symbol_workflow(
        symbol.id,
        depth=3,
        direction="downstream"
    )
    
    # Should have symbol node only
    assert workflow.start_node.name == "leaf_function"
    assert len(workflow.nodes) == 1
    assert len(workflow.edges) == 0
    assert workflow.truncated is False


def test_workflow_node_traceability(db: Session, sample_endpoint, sample_symbols, sample_calls):
    """Test that all workflow nodes have complete traceability."""
    service = WorkflowService(db)
    workflow = service.build_endpoint_workflow(sample_endpoint.id, depth=3)
    
    # All nodes should have required traceability fields
    for node in workflow.nodes:
        assert node.id is not None
        assert node.type is not None
        assert node.name is not None
        
        # Symbol nodes should have file path and line numbers
        if node.type == "symbol":
            assert node.file_path is not None
            assert node.start_line is not None
            assert node.end_line is not None


def test_workflow_to_dict(db: Session, sample_endpoint, sample_symbols, sample_calls):
    """Test workflow serialization to dictionary."""
    service = WorkflowService(db)
    workflow = service.build_endpoint_workflow(sample_endpoint.id, depth=3)
    
    # Convert to dict
    workflow_dict = workflow.to_dict()
    
    # Should have all required fields
    assert "start_node" in workflow_dict
    assert "nodes" in workflow_dict
    assert "edges" in workflow_dict
    assert "truncated" in workflow_dict
    assert "depth" in workflow_dict
    assert "node_count" in workflow_dict
    assert "edge_count" in workflow_dict
    
    # Counts should match
    assert workflow_dict["node_count"] == len(workflow.nodes)
    assert workflow_dict["edge_count"] == len(workflow.edges)


# API Endpoint Tests

def test_get_endpoint_workflow_api(client, db: Session, sample_endpoint, sample_symbols, sample_calls):
    """Test GET /api/repositories/{repo_id}/endpoints/{endpoint_id}/workflow"""
    repo_id = sample_endpoint.repository_id
    endpoint_id = sample_endpoint.id
    
    response = client.get(f"/api/repositories/{repo_id}/endpoints/{endpoint_id}/workflow?depth=3")
    
    assert response.status_code == 200
    
    data = response.json()
    assert "start_node" in data
    assert "nodes" in data
    assert "edges" in data
    assert data["start_node"]["type"] == "endpoint"
    assert len(data["nodes"]) > 0


def test_get_endpoint_workflow_with_callers(client, db: Session, sample_endpoint, sample_symbols, sample_calls):
    """Test endpoint workflow with include_callers parameter."""
    repo_id = sample_endpoint.repository_id
    endpoint_id = sample_endpoint.id
    
    response = client.get(
        f"/api/repositories/{repo_id}/endpoints/{endpoint_id}/workflow"
        f"?depth=2&include_callers=true"
    )
    
    assert response.status_code == 200


def test_get_symbol_workflow_api(client, db: Session, sample_repository, sample_symbols, sample_calls):
    """Test GET /api/repositories/{repo_id}/symbols/{symbol_id}/workflow"""
    repo_id = sample_repository.id
    symbol_id = sample_symbols[0].id
    
    response = client.get(
        f"/api/repositories/{repo_id}/symbols/{symbol_id}/workflow"
        f"?depth=2&direction=downstream"
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert "start_node" in data
    assert data["start_node"]["type"] == "symbol"


def test_workflow_api_depth_validation(client, db: Session, sample_endpoint):
    """Test that API validates depth parameter."""
    repo_id = sample_endpoint.repository_id
    endpoint_id = sample_endpoint.id
    
    # Depth too low
    response = client.get(f"/api/repositories/{repo_id}/endpoints/{endpoint_id}/workflow?depth=0")
    assert response.status_code == 422  # Validation error
    
    # Depth too high
    response = client.get(f"/api/repositories/{repo_id}/endpoints/{endpoint_id}/workflow?depth=11")
    assert response.status_code == 422


def test_workflow_api_invalid_direction(client, db: Session, sample_repository, sample_symbols):
    """Test that API validates direction parameter."""
    repo_id = sample_repository.id
    symbol_id = sample_symbols[0].id
    
    response = client.get(
        f"/api/repositories/{repo_id}/symbols/{symbol_id}/workflow"
        f"?direction=invalid"
    )
    
    assert response.status_code == 422


def test_workflow_api_repository_not_found(client, db: Session):
    """Test workflow API with non-existent repository."""
    fake_repo_id = uuid4()
    fake_endpoint_id = uuid4()
    
    response = client.get(f"/api/repositories/{fake_repo_id}/endpoints/{fake_endpoint_id}/workflow")
    
    assert response.status_code == 404


def test_workflow_api_endpoint_not_found(client, db: Session, sample_repository):
    """Test workflow API with non-existent endpoint."""
    repo_id = sample_repository.id
    fake_endpoint_id = uuid4()
    
    response = client.get(f"/api/repositories/{repo_id}/endpoints/{fake_endpoint_id}/workflow")
    
    assert response.status_code == 404


def test_workflow_api_endpoint_wrong_repository(client, db: Session, sample_endpoint):
    """Test workflow API with endpoint from different repository."""
    wrong_repo_id = uuid4()
    endpoint_id = sample_endpoint.id
    
    response = client.get(f"/api/repositories/{wrong_repo_id}/endpoints/{endpoint_id}/workflow")
    
    assert response.status_code == 404  # Repository not found


def test_workflow_api_symbol_not_found(client, db: Session, sample_repository):
    """Test workflow API with non-existent symbol."""
    repo_id = sample_repository.id
    fake_symbol_id = uuid4()
    
    response = client.get(f"/api/repositories/{repo_id}/symbols/{fake_symbol_id}/workflow")
    
    assert response.status_code == 404
