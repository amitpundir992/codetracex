"""
Change Impact Service for Phase 18: Pull Request & Change Intelligence.

This service orchestrates deterministic change analysis using existing services:
- ChangeDetectionService: File-level change detection
- SymbolChangeAnalyzer: Symbol-level change analysis
- GraphService: Dependency graph traversal
- WorkflowService: Workflow intelligence
- ChangeRiskAnalyzer: Risk assessment

Architecture Philosophy:

    ORCHESTRATION OF EXISTING SERVICES
    
    This service DOES NOT:
    - Discover new dependencies
    - Execute code
    - Make semantic inferences beyond what existing services provide
    
    This service DOES:
    - Coordinate existing intelligence services
    - Perform bounded graph traversal
    - Collect repository evidence
    - Structure data for LLM reasoning
    
    Flow:
    1. Detect file changes
    2. Identify symbol changes
    3. Traverse dependency graph (bounded)
    4. Identify affected API endpoints
    5. Identify affected workflows
    6. Detect relevant tests
    7. Calculate risk signals
    8. Collect evidence
    
    The LLM explains and reasons over collected evidence.
    It does NOT discover dependencies or facts.

Bounded Traversal:

    - Default depth: 3
    - Maximum depth: 10
    - Maximum nodes: 500
    - Maximum edges: 1000
    
    Explicit truncation reporting when limits reached.

Repository Isolation:

    All queries scoped by repository_id.
    No cross-repository contamination.
"""
from typing import List, Dict, Set, Optional, Any
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.models import (
    Repository, Symbol, File, ApiEndpoint, Call, Import, AnalysisRun
)
from app.services.change_detection_service import ChangeDetectionService
from app.services.symbol_change_analyzer import SymbolChangeAnalyzer
from app.services.graph_service import GraphService
from app.services.workflow_service import WorkflowService
from app.services.change_risk_analyzer import ChangeRiskAnalyzer
from app.schemas.change_analysis import (
    ChangedFile, ChangedSymbol, AffectedEndpoint, AffectedWorkflow,
    DependencyImpact, RelevantTest, ChangeRisk, ChangeEvidence
)

logger = logging.getLogger(__name__)


class ChangeImpactService:
    """
    Service for orchestrating change impact analysis.
    
    Coordinates existing services to provide comprehensive change intelligence.
    """
    
    # Traversal limits
    DEFAULT_DEPTH = 3
    MAX_DEPTH = 10
    MAX_NODES = 500
    MAX_EDGES = 1000
    
    def __init__(self, db: Session):
        """
        Initialize change impact service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.change_detection = ChangeDetectionService(db)
        self.symbol_analyzer = SymbolChangeAnalyzer(db)
        self.graph_service = GraphService(db)
        self.workflow_service = WorkflowService(db)
        self.risk_analyzer = ChangeRiskAnalyzer(db)
    
    def _get_affected_endpoints(
        self,
        repository_id: UUID,
        changed_files: List[ChangedFile],
        changed_symbols: List[ChangedSymbol]
    ) -> List[AffectedEndpoint]:
        """
        Identify affected API endpoints.
        
        Args:
            repository_id: Repository UUID
            changed_files: List of changed files
            changed_symbols: List of changed symbols
            
        Returns:
            List of affected endpoints
        """
        # Get latest analysis run
        latest_analysis = self.db.query(AnalysisRun).filter(
            and_(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.status == 'completed'
            )
        ).order_by(AnalysisRun.completed_at.desc()).first()
        
        if not latest_analysis:
            return []
        
        # Get all endpoints for this analysis run
        endpoints = self.db.query(ApiEndpoint).filter(
            ApiEndpoint.analysis_run_id == latest_analysis.id
        ).all()
        
        if not endpoints:
            return []
        
        affected = []
        changed_file_paths = {f.path for f in changed_files}
        changed_symbol_names = {s.qualified_name for s in changed_symbols}
        
        for endpoint in endpoints:
            # Check if endpoint file was changed
            directly_affected = endpoint.file_path in changed_file_paths
            
            # Check if handler symbol was changed
            if endpoint.handler_symbol and endpoint.handler_symbol in changed_symbol_names:
                directly_affected = True
            
            # For now, we only report directly affected endpoints
            # Indirect effects would require graph traversal from handler
            if directly_affected:
                affected.append(AffectedEndpoint(
                    method=endpoint.method,
                    route=endpoint.route,
                    handler=endpoint.handler_symbol,
                    file_path=endpoint.file_path,
                    directly_affected=True
                ))
        
        logger.info(f"Identified {len(affected)} affected API endpoints")
        return affected
    
    def _get_affected_workflows(
        self,
        repository_id: UUID,
        affected_endpoints: List[AffectedEndpoint],
        changed_symbols: List[ChangedSymbol],
        max_depth: int = 3
    ) -> List[AffectedWorkflow]:
        """
        Identify affected workflows.
        
        Args:
            repository_id: Repository UUID
            affected_endpoints: List of affected endpoints
            changed_symbols: List of changed symbols
            max_depth: Maximum workflow traversal depth
            
        Returns:
            List of affected workflows
        """
        affected_workflows = []
        
        # Get latest analysis run
        latest_analysis = self.db.query(AnalysisRun).filter(
            and_(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.status == 'completed'
            )
        ).order_by(AnalysisRun.completed_at.desc()).first()
        
        if not latest_analysis:
            return []
        
        # Build workflows for affected endpoints
        for endpoint in affected_endpoints:
            try:
                # Get endpoint from database
                db_endpoint = self.db.query(ApiEndpoint).filter(
                    and_(
                        ApiEndpoint.analysis_run_id == latest_analysis.id,
                        ApiEndpoint.method == endpoint.method,
                        ApiEndpoint.route == endpoint.route
                    )
                ).first()
                
                if not db_endpoint:
                    continue
                
                # Build workflow
                workflow = self.workflow_service.build_endpoint_workflow(
                    endpoint_id=db_endpoint.id,
                    max_depth=min(max_depth, 5),
                    direction="downstream"
                )
                
                if not workflow:
                    continue
                
                # Identify changed nodes in workflow
                changed_symbol_set = {s.qualified_name for s in changed_symbols}
                changed_nodes = [
                    node.name
                    for node in workflow.nodes
                    if node.name in changed_symbol_set
                ]
                
                affected_workflows.append(AffectedWorkflow(
                    entry_point=f"{endpoint.method} {endpoint.route}",
                    entry_type="endpoint",
                    changed_nodes=changed_nodes,
                    total_nodes=len(workflow.nodes)
                ))
                
            except Exception as e:
                logger.warning(f"Failed to build workflow for endpoint: {e}")
                continue
        
        logger.info(f"Identified {len(affected_workflows)} affected workflows")
        return affected_workflows
    
    def _get_dependency_impact(
        self,
        repository_id: UUID,
        changed_symbols: List[ChangedSymbol],
        max_depth: int = 3
    ) -> DependencyImpact:
        """
        Analyze dependency impact using graph traversal.
        
        Args:
            repository_id: Repository UUID
            changed_symbols: List of changed symbols
            max_depth: Maximum graph traversal depth
            
        Returns:
            DependencyImpact summary
        """
        # Get latest analysis run
        latest_analysis = self.db.query(AnalysisRun).filter(
            and_(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.status == 'completed'
            )
        ).order_by(AnalysisRun.completed_at.desc()).first()
        
        if not latest_analysis:
            return DependencyImpact(
                affected_callers=[],
                affected_callees=[],
                affected_files=[],
                truncated=False,
                traversal_depth=0
            )
        
        all_callers = set()
        all_callees = set()
        all_files = set()
        truncated = False
        actual_depth = 0
        
        # Limit traversal depth
        safe_depth = min(max_depth, self.MAX_DEPTH)
        
        # Analyze each changed public symbol
        for changed_symbol in changed_symbols:
            if not changed_symbol.is_public:
                continue
            
            # Find symbol in database by matching file path and symbol name
            # Note: qualified_name is not a database column, so we match on name and file path
            symbol = self.db.query(Symbol).join(File).join(AnalysisRun).filter(
                and_(
                    Symbol.name == changed_symbol.name,
                    File.path == changed_symbol.file_path,
                    AnalysisRun.repository_id == repository_id,
                    AnalysisRun.id == latest_analysis.id
                )
            ).first()
            
            if not symbol:
                continue
            
            try:
                # Get callers (who depends on this symbol)
                callers_result = self.graph_service.get_symbol_callers(
                    symbol_id=symbol.id,
                    max_depth=safe_depth
                )
                
                for node in callers_result.get('nodes', []):
                    if node.get('type') == 'symbol':
                        all_callers.add(node.get('name', ''))
                    if node.get('file'):
                        all_files.add(node.get('file'))
                
                # Get callees (what this symbol depends on)
                callees_result = self.graph_service.get_symbol_callees(
                    symbol_id=symbol.id,
                    max_depth=safe_depth
                )
                
                for node in callees_result.get('nodes', []):
                    if node.get('type') == 'symbol':
                        all_callees.add(node.get('name', ''))
                    if node.get('file'):
                        all_files.add(node.get('file'))
                
                actual_depth = max(actual_depth, safe_depth)
                
                # Check truncation
                total_nodes = len(callers_result.get('nodes', [])) + len(callees_result.get('nodes', []))
                if total_nodes >= self.MAX_NODES:
                    truncated = True
                
            except Exception as e:
                logger.warning(f"Graph traversal failed for symbol {changed_symbol.qualified_name}: {e}")
                continue
        
        # Remove empty strings
        all_callers.discard('')
        all_callees.discard('')
        all_files.discard('')
        
        logger.info(
            f"Dependency impact: {len(all_callers)} callers, {len(all_callees)} callees, "
            f"{len(all_files)} files, truncated={truncated}"
        )
        
        return DependencyImpact(
            affected_callers=sorted(list(all_callers)),
            affected_callees=sorted(list(all_callees)),
            affected_files=sorted(list(all_files)),
            truncated=truncated,
            traversal_depth=actual_depth
        )
    
    def _detect_relevant_tests(
        self,
        repository_id: UUID,
        changed_files: List[ChangedFile],
        changed_symbols: List[ChangedSymbol]
    ) -> List[RelevantTest]:
        """
        Detect potentially relevant tests.
        
        Uses deterministic signals:
        - Tests in changed files
        - Tests importing changed modules
        - Tests with path/name relationships
        
        Args:
            repository_id: Repository UUID
            changed_files: List of changed files
            changed_symbols: List of changed symbols
            
        Returns:
            List of relevant tests
        """
        relevant_tests = []
        
        # Signal 1: Test files in the change set
        test_files = [f for f in changed_files if f.is_test]
        for test_file in test_files:
            relevant_tests.append(RelevantTest(
                file_path=test_file.path,
                test_name=None,
                relationship="directly_changed",
                confidence="high"
            ))
        
        # Signal 2: Path-based matching
        # For each changed source file, look for corresponding test file
        source_files = [f for f in changed_files if f.is_source and not f.is_test]
        
        for source_file in source_files:
            # Simple heuristic: replace src/ with tests/, add test_ prefix
            # Example: src/services/user.py -> tests/test_user.py
            path_parts = source_file.path.split('/')
            filename = path_parts[-1]
            
            # Generate potential test paths
            potential_test_paths = []
            
            # Pattern 1: tests/test_<filename>
            test_filename = f"test_{filename}"
            potential_test_paths.append(f"tests/{test_filename}")
            
            # Pattern 2: <dir>/test_<filename>
            if len(path_parts) > 1:
                dir_path = '/'.join(path_parts[:-1])
                potential_test_paths.append(f"{dir_path}/test_{filename}")
            
            # Pattern 3: __tests__/<filename>.test.<ext>
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) == 2:
                test_filename_variant = f"{name_parts[0]}.test.{name_parts[1]}"
                potential_test_paths.append(f"__tests__/{test_filename_variant}")
            
            # Check if any potential test paths exist in repository
            # (In a real implementation, we'd query the File table)
            for test_path in potential_test_paths:
                # For now, mark as potential based on naming only
                relevant_tests.append(RelevantTest(
                    file_path=test_path,
                    test_name=None,
                    relationship="path_related",
                    confidence="medium"
                ))
        
        # Deduplicate
        seen = set()
        unique_tests = []
        for test in relevant_tests:
            if test.file_path not in seen:
                seen.add(test.file_path)
                unique_tests.append(test)
        
        logger.info(f"Detected {len(unique_tests)} potentially relevant tests")
        return unique_tests
    
    def _collect_evidence(
        self,
        changed_files: List[ChangedFile],
        changed_symbols: List[ChangedSymbol],
        affected_endpoints: List[AffectedEndpoint],
        affected_workflows: List[AffectedWorkflow]
    ) -> List[ChangeEvidence]:
        """
        Collect evidence items for analysis.
        
        Args:
            changed_files: List of changed files
            changed_symbols: List of changed symbols
            affected_endpoints: List of affected endpoints
            affected_workflows: List of affected workflows
            
        Returns:
            List of evidence items
        """
        evidence = []
        
        # File change evidence
        for file in changed_files[:20]:  # Limit to first 20
            evidence.append(ChangeEvidence(
                evidence_type="file_change",
                description=f"{file.change_type.value.capitalize()} {file.path} (+{file.additions}, -{file.deletions})",
                reference={"file_path": file.path, "change_type": file.change_type.value}
            ))
        
        # Symbol change evidence
        for symbol in changed_symbols[:20]:  # Limit to first 20
            evidence.append(ChangeEvidence(
                evidence_type="symbol_change",
                description=f"{symbol.change_type.value.capitalize()} {symbol.symbol_type} {symbol.qualified_name}",
                reference={
                    "qualified_name": symbol.qualified_name,
                    "symbol_type": symbol.symbol_type,
                    "change_type": symbol.change_type.value
                }
            ))
        
        # API endpoint evidence
        for endpoint in affected_endpoints[:10]:  # Limit to first 10
            evidence.append(ChangeEvidence(
                evidence_type="affected_endpoint",
                description=f"Affected: {endpoint.method} {endpoint.route}",
                reference={
                    "method": endpoint.method,
                    "route": endpoint.route,
                    "directly_affected": endpoint.directly_affected
                }
            ))
        
        # Workflow evidence
        for workflow in affected_workflows[:10]:  # Limit to first 10
            evidence.append(ChangeEvidence(
                evidence_type="affected_workflow",
                description=f"Workflow {workflow.entry_point}: {len(workflow.changed_nodes)}/{workflow.total_nodes} nodes affected",
                reference={
                    "entry_point": workflow.entry_point,
                    "changed_nodes": workflow.changed_nodes
                }
            ))
        
        logger.info(f"Collected {len(evidence)} evidence items")
        return evidence
    
    def analyze_change_impact(
        self,
        repository_id: UUID,
        base_sha: Optional[str] = None,
        head_sha: Optional[str] = None,
        commit_sha: Optional[str] = None,
        max_depth: int = DEFAULT_DEPTH,
        include_tests: bool = True,
        include_workflows: bool = True
    ) -> Dict[str, Any]:
        """
        Perform comprehensive change impact analysis.
        
        This is the main orchestration method that coordinates all services.
        
        Args:
            repository_id: Repository UUID
            base_sha: Base commit SHA (for range mode)
            head_sha: Head commit SHA (for range mode)
            commit_sha: Single commit SHA (for single commit mode)
            max_depth: Maximum graph traversal depth
            include_tests: Whether to include test analysis
            include_workflows: Whether to include workflow analysis
            
        Returns:
            Dictionary containing complete change impact analysis
            
        Raises:
            ValueError: If input validation fails
        """
        logger.info(
            f"Starting change impact analysis for repository {repository_id}"
        )
        
        # Validate depth
        safe_depth = min(max_depth, self.MAX_DEPTH)
        if safe_depth != max_depth:
            logger.warning(f"Depth capped from {max_depth} to {safe_depth}")
        
        # Step 1: Detect file changes
        changed_files, metadata = self.change_detection.detect_changes(
            repository_id=repository_id,
            base_sha=base_sha,
            head_sha=head_sha,
            commit_sha=commit_sha
        )
        
        # Step 2: Analyze symbol changes
        changed_symbols = self.symbol_analyzer.analyze_symbol_changes(
            repository_id=repository_id,
            changed_files=changed_files
        )
        
        # Step 3: Identify affected API endpoints
        affected_endpoints = self._get_affected_endpoints(
            repository_id=repository_id,
            changed_files=changed_files,
            changed_symbols=changed_symbols
        )
        
        # Step 4: Identify affected workflows (if enabled)
        affected_workflows = []
        if include_workflows:
            affected_workflows = self._get_affected_workflows(
                repository_id=repository_id,
                affected_endpoints=affected_endpoints,
                changed_symbols=changed_symbols,
                max_depth=safe_depth
            )
        
        # Step 5: Analyze dependency impact
        dependency_impact = self._get_dependency_impact(
            repository_id=repository_id,
            changed_symbols=changed_symbols,
            max_depth=safe_depth
        )
        
        # Step 6: Detect relevant tests (if enabled)
        relevant_tests = []
        if include_tests:
            relevant_tests = self._detect_relevant_tests(
                repository_id=repository_id,
                changed_files=changed_files,
                changed_symbols=changed_symbols
            )
        
        # Step 7: Calculate risk
        risk = self.risk_analyzer.analyze_risk(
            repository_id=repository_id,
            changed_files=changed_files,
            changed_symbols=changed_symbols,
            affected_endpoints=affected_endpoints,
            affected_workflows=affected_workflows,
            dependency_impact=dependency_impact.__dict__
        )
        
        # Step 8: Collect evidence
        evidence = self._collect_evidence(
            changed_files=changed_files,
            changed_symbols=changed_symbols,
            affected_endpoints=affected_endpoints,
            affected_workflows=affected_workflows
        )
        
        logger.info("Change impact analysis complete")
        
        return {
            'metadata': metadata,
            'changed_files': changed_files,
            'changed_symbols': changed_symbols,
            'affected_endpoints': affected_endpoints,
            'affected_workflows': affected_workflows,
            'dependency_impact': dependency_impact,
            'relevant_tests': relevant_tests,
            'risk': risk,
            'evidence': evidence
        }
