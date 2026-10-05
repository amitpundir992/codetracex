"""
Change Risk Analyzer for Phase 18: Pull Request & Change Intelligence.

This service calculates deterministic risk signals and scores based on
observable code characteristics.

Architecture Philosophy:

    DETERMINISTIC RISK SIGNALS
    
    Risk assessment is based on MEASURABLE signals:
    - Public API changes
    - High fan-out (many callers)
    - Workflow entry points
    - Security-related patterns
    - Database/model changes
    - Test coverage signals
    
    The risk score is EXPLAINABLE and REPRODUCIBLE.
    
    We do NOT:
    - Let LLM assign risk scores
    - Make subjective judgments
    - Claim absolute certainty
    
    Flow:
    1. Collect risk signals
    2. Calculate weighted score
    3. Assign risk level
    4. Provide evidence for each signal

Risk Levels:
    - low: 0-30
    - medium: 31-60
    - high: 61-85
    - critical: 86-100
"""
from typing import List, Dict, Set, Optional
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.schemas.change_analysis import (
    ChangeRisk, RiskSignal, ChangedFile, ChangedSymbol,
    AffectedEndpoint, AffectedWorkflow, ChangeType
)

logger = logging.getLogger(__name__)


class ChangeRiskAnalyzer:
    """
    Service for calculating deterministic risk signals and scores.
    
    Analyzes changes to produce measurable risk assessment.
    """
    
    # Risk weights (must sum to reasonable total)
    WEIGHT_PUBLIC_API_CHANGE = 25
    WEIGHT_HIGH_FANOUT = 20
    WEIGHT_WORKFLOW_ENTRY = 15
    WEIGHT_SECURITY_CODE = 20
    WEIGHT_DATABASE_CODE = 15
    WEIGHT_MANY_FILES = 10
    WEIGHT_MISSING_TESTS = 15
    WEIGHT_LARGE_CHANGE = 10
    
    # Thresholds
    HIGH_FANOUT_THRESHOLD = 5  # symbols with >5 callers
    MANY_FILES_THRESHOLD = 10  # >10 files changed
    LARGE_CHANGE_THRESHOLD = 500  # >500 line changes
    
    def __init__(self, db: Session):
        """
        Initialize risk analyzer.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def _detect_security_patterns(self, path: str) -> bool:
        """
        Detect security-related code patterns.
        
        Args:
            path: File path
            
        Returns:
            True if file appears security-related
        """
        path_lower = path.lower()
        
        security_patterns = [
            'auth', 'login', 'password', 'token', 'jwt', 'oauth',
            'security', 'permission', 'role', 'access', 'credential',
            'encrypt', 'decrypt', 'hash', 'crypto', 'session'
        ]
        
        return any(pattern in path_lower for pattern in security_patterns)
    
    def _detect_database_patterns(self, path: str) -> bool:
        """
        Detect database-related code patterns.
        
        Args:
            path: File path
            
        Returns:
            True if file appears database-related
        """
        path_lower = path.lower()
        
        database_patterns = [
            'model', 'schema', 'migration', 'database', 'db',
            'query', 'repository', 'dao', 'entity', 'orm',
            'alembic', 'sqlalchemy', 'sequelize', 'prisma'
        ]
        
        return any(pattern in path_lower for pattern in database_patterns)
    
    def _detect_payment_patterns(self, path: str) -> bool:
        """
        Detect payment-related code patterns.
        
        Args:
            path: File path
            
        Returns:
            True if file appears payment-related
        """
        path_lower = path.lower()
        
        payment_patterns = [
            'payment', 'billing', 'invoice', 'checkout', 'cart',
            'stripe', 'paypal', 'transaction', 'charge', 'refund'
        ]
        
        return any(pattern in path_lower for pattern in payment_patterns)
    
    def analyze_risk(
        self,
        repository_id: UUID,
        changed_files: List[ChangedFile],
        changed_symbols: List[ChangedSymbol],
        affected_endpoints: List[AffectedEndpoint],
        affected_workflows: List[AffectedWorkflow],
        dependency_impact: Dict[str, any]
    ) -> ChangeRisk:
        """
        Analyze risk based on deterministic signals.
        
        Args:
            repository_id: Repository UUID
            changed_files: List of changed files
            changed_symbols: List of changed symbols
            affected_endpoints: List of affected API endpoints
            affected_workflows: List of affected workflows
            dependency_impact: Dependency impact data
            
        Returns:
            ChangeRisk with signals and score
        """
        signals: List[RiskSignal] = []
        risk_score = 0
        
        # Signal 1: Public API changes
        public_api_changes = [
            ep for ep in affected_endpoints
            if ep.directly_affected
        ]
        
        if public_api_changes:
            severity = "high" if len(public_api_changes) > 3 else "medium"
            score_contribution = self.WEIGHT_PUBLIC_API_CHANGE
            risk_score += score_contribution
            
            evidence = [
                f"{ep.method} {ep.route}" for ep in public_api_changes[:5]
            ]
            if len(public_api_changes) > 5:
                evidence.append(f"...and {len(public_api_changes) - 5} more")
            
            signals.append(RiskSignal(
                signal_type="public_api_change",
                severity=severity,
                description=f"{len(public_api_changes)} public API endpoint(s) directly affected",
                evidence=evidence
            ))
        
        # Signal 2: High fan-out symbols
        public_symbols = [s for s in changed_symbols if s.is_public]
        
        if public_symbols:
            # In a full implementation, we'd query callers count
            # For now, use public symbol count as proxy
            high_fanout_count = len(public_symbols)
            
            if high_fanout_count >= self.HIGH_FANOUT_THRESHOLD:
                severity = "high" if high_fanout_count > 10 else "medium"
                score_contribution = self.WEIGHT_HIGH_FANOUT
                risk_score += score_contribution
                
                evidence = [
                    s.qualified_name for s in public_symbols[:5]
                ]
                if high_fanout_count > 5:
                    evidence.append(f"...and {high_fanout_count - 5} more")
                
                signals.append(RiskSignal(
                    signal_type="high_fanout_symbol",
                    severity=severity,
                    description=f"{high_fanout_count} public symbol(s) changed",
                    evidence=evidence
                ))
        
        # Signal 3: Workflow entry points
        if affected_workflows:
            severity = "medium"
            score_contribution = self.WEIGHT_WORKFLOW_ENTRY
            risk_score += score_contribution
            
            evidence = [
                f"{w.entry_point} ({len(w.changed_nodes)}/{w.total_nodes} nodes)"
                for w in affected_workflows[:5]
            ]
            if len(affected_workflows) > 5:
                evidence.append(f"...and {len(affected_workflows) - 5} more")
            
            signals.append(RiskSignal(
                signal_type="workflow_entry_affected",
                severity=severity,
                description=f"{len(affected_workflows)} workflow(s) affected",
                evidence=evidence
            ))
        
        # Signal 4: Security-related code
        security_files = [
            f for f in changed_files
            if self._detect_security_patterns(f.path)
        ]
        
        if security_files:
            severity = "high"
            score_contribution = self.WEIGHT_SECURITY_CODE
            risk_score += score_contribution
            
            evidence = [f.path for f in security_files[:5]]
            if len(security_files) > 5:
                evidence.append(f"...and {len(security_files) - 5} more")
            
            signals.append(RiskSignal(
                signal_type="security_code_change",
                severity=severity,
                description=f"{len(security_files)} security-related file(s) changed",
                evidence=evidence
            ))
        
        # Signal 5: Database/model changes
        database_files = [
            f for f in changed_files
            if self._detect_database_patterns(f.path)
        ]
        
        if database_files:
            severity = "medium"
            score_contribution = self.WEIGHT_DATABASE_CODE
            risk_score += score_contribution
            
            evidence = [f.path for f in database_files[:5]]
            if len(database_files) > 5:
                evidence.append(f"...and {len(database_files) - 5} more")
            
            signals.append(RiskSignal(
                signal_type="database_code_change",
                severity=severity,
                description=f"{len(database_files)} database-related file(s) changed",
                evidence=evidence
            ))
        
        # Signal 6: Payment-related changes
        payment_files = [
            f for f in changed_files
            if self._detect_payment_patterns(f.path)
        ]
        
        if payment_files:
            severity = "critical"
            score_contribution = 20  # Extra weight for payment code
            risk_score += score_contribution
            
            evidence = [f.path for f in payment_files]
            
            signals.append(RiskSignal(
                signal_type="payment_code_change",
                severity=severity,
                description=f"{len(payment_files)} payment-related file(s) changed",
                evidence=evidence
            ))
        
        # Signal 7: Many files changed
        if len(changed_files) > self.MANY_FILES_THRESHOLD:
            severity = "medium"
            score_contribution = self.WEIGHT_MANY_FILES
            risk_score += score_contribution
            
            signals.append(RiskSignal(
                signal_type="many_files_changed",
                severity=severity,
                description=f"{len(changed_files)} files changed",
                evidence=[f"Change spans {len(changed_files)} files"]
            ))
        
        # Signal 8: Large change size
        total_lines_changed = sum(f.additions + f.deletions for f in changed_files)
        
        if total_lines_changed > self.LARGE_CHANGE_THRESHOLD:
            severity = "medium"
            score_contribution = self.WEIGHT_LARGE_CHANGE
            risk_score += score_contribution
            
            signals.append(RiskSignal(
                signal_type="large_change_size",
                severity=severity,
                description=f"{total_lines_changed} lines changed",
                evidence=[f"+{sum(f.additions for f in changed_files)} -{sum(f.deletions for f in changed_files)}"]
            ))
        
        # Signal 9: Source changes without nearby tests
        source_files = [f for f in changed_files if f.is_source and not f.is_test]
        test_files = [f for f in changed_files if f.is_test]
        
        if source_files and not test_files:
            severity = "medium"
            score_contribution = self.WEIGHT_MISSING_TESTS
            risk_score += score_contribution
            
            signals.append(RiskSignal(
                signal_type="missing_test_changes",
                severity=severity,
                description=f"{len(source_files)} source file(s) changed but no test files modified",
                evidence=[f"{len(source_files)} source files, {len(test_files)} test files"]
            ))
        
        # Normalize risk score to 0-100 range
        # Cap at 100
        risk_score = min(risk_score, 100)
        
        # Determine risk level
        if risk_score >= 86:
            risk_level = "critical"
        elif risk_score >= 61:
            risk_level = "high"
        elif risk_score >= 31:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        # Generate explanation
        if signals:
            signal_summaries = [
                f"{s.signal_type} ({s.severity})"
                for s in signals
            ]
            explanation = f"Risk assessment based on {len(signals)} signal(s): {', '.join(signal_summaries)}"
        else:
            explanation = "No significant risk signals detected"
        
        logger.info(
            f"Risk analysis complete: level={risk_level}, score={risk_score}, "
            f"signals={len(signals)}"
        )
        
        return ChangeRisk(
            risk_level=risk_level,
            risk_score=risk_score,
            signals=signals,
            explanation=explanation
        )
