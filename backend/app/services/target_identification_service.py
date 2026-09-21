"""
Target Identification Service for Phase 13: AI Impact Analysis.

This service identifies repository entities (symbols, files, or API endpoints)
from user queries using deterministic matching.

Architecture Philosophy:

    DO NOT use LLM as sole source of truth for target identification.
    
    Use deterministic matching where possible:
    - Exact symbol name
    - Qualified symbol name
    - Exact file path
    - API method + route
    - Fuzzy matching with confidence scores
    
    If multiple candidates exist:
    - Return ambiguity information
    - Let user select target
    - Never silently pick arbitrary target

Matching Strategy:

    1. Exact matches (ID, full name, full path)
    2. Qualified name matches (module.Class.method)
    3. Partial matches with ranking
    4. API endpoint matching (method + path)
    
Limitations:

    - Static analysis only
    - Name-based matching
    - Cannot resolve ambiguity without user input
    - External references cannot be matched to internal entities
"""
from typing import List, Optional, Tuple
from uuid import UUID
import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import joinedload

from app.db.models import Symbol, File, ApiEndpoint, HttpMethod
from app.schemas.impact_analysis import (
    ImpactTarget,
    TargetCandidate,
    TargetIdentificationResult
)

logger = logging.getLogger(__name__)


class TargetIdentificationService:
    """
    Service for identifying impact analysis targets from user queries.
    
    Uses deterministic matching with confidence scoring for ambiguous cases.
    """
    
    def __init__(self, db: Session):
        """
        Initialize target identification service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def identify_target_from_query(
        self,
        query: str,
        repository_id: UUID,
        analysis_run_id: Optional[UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[UUID] = None
    ) -> TargetIdentificationResult:
        """
        Identify the target entity from a user query.
        
        If target_id is provided, retrieve it directly.
        Otherwise, parse the query to identify the target.
        
        Args:
            query: User's natural language query
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            target_type: Optional explicit target type hint
            target_id: Optional explicit target ID
            
        Returns:
            TargetIdentificationResult with status and candidates
        """
        # Explicit target ID provided
        if target_id:
            return self._identify_by_id(
                target_id,
                repository_id,
                analysis_run_id,
                target_type
            )
        
        # Parse query for entity references
        candidates: List[TargetCandidate] = []
        
        # Try symbol identification
        if not target_type or target_type == "symbol":
            symbol_candidates = self._identify_symbols(
                query,
                repository_id,
                analysis_run_id
            )
            candidates.extend(symbol_candidates)
        
        # Try file identification
        if not target_type or target_type == "file":
            file_candidates = self._identify_files(
                query,
                repository_id,
                analysis_run_id
            )
            candidates.extend(file_candidates)
        
        # Try API endpoint identification
        if not target_type or target_type == "api_endpoint":
            endpoint_candidates = self._identify_endpoints(
                query,
                repository_id,
                analysis_run_id
            )
            candidates.extend(endpoint_candidates)
        
        # Sort by match score descending
        candidates.sort(key=lambda c: c.match_score, reverse=True)
        
        # Determine result
        if not candidates:
            return TargetIdentificationResult(
                status="not_found",
                message=f"No matching symbol, file, or endpoint found for query: {query}"
            )
        
        # Single high-confidence match
        if len(candidates) == 1 and candidates[0].match_score >= 0.9:
            return TargetIdentificationResult(
                status="found",
                target=candidates[0].target
            )
        
        # Multiple candidates or low confidence
        if len(candidates) > 1 or candidates[0].match_score < 0.9:
            # Check if top candidate is significantly better
            if len(candidates) > 1:
                score_diff = candidates[0].match_score - candidates[1].match_score
                if score_diff >= 0.3:
                    return TargetIdentificationResult(
                        status="found",
                        target=candidates[0].target
                    )
            
            return TargetIdentificationResult(
                status="ambiguous",
                candidates=candidates[:5],  # Return top 5
                message=f"Found {len(candidates)} potential matches. Please specify the target."
            )
        
        # Single candidate
        return TargetIdentificationResult(
            status="found",
            target=candidates[0].target
        )
    
    def _identify_by_id(
        self,
        target_id: UUID,
        repository_id: UUID,
        analysis_run_id: Optional[UUID],
        target_type: Optional[str]
    ) -> TargetIdentificationResult:
        """
        Identify target by explicit ID.
        
        Args:
            target_id: Target entity UUID
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            target_type: Optional target type hint
            
        Returns:
            TargetIdentificationResult
        """
        # Try symbol
        if not target_type or target_type == "symbol":
            symbol = self.db.query(Symbol).options(
                joinedload(Symbol.file)
            ).filter(
                Symbol.id == target_id,
                Symbol.repository_id == repository_id
            ).first()
            
            if symbol:
                if analysis_run_id and symbol.analysis_run_id != analysis_run_id:
                    return TargetIdentificationResult(
                        status="not_found",
                        message="Symbol found but belongs to different analysis run"
                    )
                
                target = self._symbol_to_target(symbol)
                return TargetIdentificationResult(
                    status="found",
                    target=target
                )
        
        # Try file
        if not target_type or target_type == "file":
            file = self.db.query(File).filter(
                File.id == target_id,
                File.repository_id == repository_id
            ).first()
            
            if file:
                if analysis_run_id and file.analysis_run_id != analysis_run_id:
                    return TargetIdentificationResult(
                        status="not_found",
                        message="File found but belongs to different analysis run"
                    )
                
                target = self._file_to_target(file)
                return TargetIdentificationResult(
                    status="found",
                    target=target
                )
        
        # Try API endpoint
        if not target_type or target_type == "api_endpoint":
            endpoint = self.db.query(ApiEndpoint).options(
                joinedload(ApiEndpoint.file)
            ).filter(
                ApiEndpoint.id == target_id,
                ApiEndpoint.repository_id == repository_id
            ).first()
            
            if endpoint:
                if analysis_run_id and endpoint.analysis_run_id != analysis_run_id:
                    return TargetIdentificationResult(
                        status="not_found",
                        message="Endpoint found but belongs to different analysis run"
                    )
                
                target = self._endpoint_to_target(endpoint)
                return TargetIdentificationResult(
                    status="found",
                    target=target
                )
        
        return TargetIdentificationResult(
            status="not_found",
            message=f"No entity found with ID {target_id}"
        )
    
    def _identify_symbols(
        self,
        query: str,
        repository_id: UUID,
        analysis_run_id: Optional[UUID]
    ) -> List[TargetCandidate]:
        """
        Identify symbol candidates from query.
        
        Uses exact matching, qualified name matching, and partial matching.
        
        Args:
            query: User query
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            
        Returns:
            List of TargetCandidate objects
        """
        candidates: List[TargetCandidate] = []
        
        # Extract potential symbol names from query
        # Look for patterns like: ClassName.method_name, function_name, etc.
        symbol_patterns = [
            r'\b([A-Z][a-zA-Z0-9_]*\.[a-z_][a-zA-Z0-9_]*)\b',  # Class.method
            r'\b([a-z_][a-zA-Z0-9_]*\.[a-z_][a-zA-Z0-9_]*)\b',  # module.function
            r'\b([A-Z][a-zA-Z0-9_]*)\b',  # ClassName
            r'\b([a-z_][a-zA-Z0-9_]{2,})\b',  # function_name
        ]
        
        potential_names = set()
        for pattern in symbol_patterns:
            matches = re.findall(pattern, query)
            potential_names.update(matches)
        
        # Query database for matching symbols
        base_query = self.db.query(Symbol).options(
            joinedload(Symbol.file)
        ).filter(
            Symbol.repository_id == repository_id
        )
        
        if analysis_run_id:
            base_query = base_query.filter(Symbol.analysis_run_id == analysis_run_id)
        
        for name in potential_names:
            # Exact name match
            symbols = base_query.filter(
                Symbol.name == name
            ).all()
            
            for symbol in symbols:
                score = 1.0  # Exact match
                candidates.append(TargetCandidate(
                    target=self._symbol_to_target(symbol),
                    match_score=score,
                    match_reason=f"Exact symbol name match: {name}"
                ))
            
            # Qualified name match (Class.method)
            if '.' in name:
                parts = name.split('.')
                if len(parts) == 2:
                    class_name, method_name = parts
                    
                    # Find methods with matching name in matching class
                    methods = base_query.filter(
                        Symbol.name == method_name,
                        Symbol.parent_symbol_name == class_name
                    ).all()
                    
                    for method in methods:
                        score = 1.0  # Qualified match
                        candidates.append(TargetCandidate(
                            target=self._symbol_to_target(method),
                            match_score=score,
                            match_reason=f"Qualified name match: {name}"
                        ))
            
            # Partial match (case-insensitive)
            if not symbols:
                partial_symbols = base_query.filter(
                    func.lower(Symbol.name).like(f"%{name.lower()}%")
                ).limit(10).all()
                
                for symbol in partial_symbols:
                    # Calculate similarity score
                    score = self._calculate_name_similarity(name, symbol.name)
                    if score >= 0.5:
                        candidates.append(TargetCandidate(
                            target=self._symbol_to_target(symbol),
                            match_score=score * 0.8,  # Reduce score for partial matches
                            match_reason=f"Partial symbol name match: {symbol.name}"
                        ))
        
        return candidates
    
    def _identify_files(
        self,
        query: str,
        repository_id: UUID,
        analysis_run_id: Optional[UUID]
    ) -> List[TargetCandidate]:
        """
        Identify file candidates from query.
        
        Args:
            query: User query
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            
        Returns:
            List of TargetCandidate objects
        """
        candidates: List[TargetCandidate] = []
        
        # Extract potential file paths
        # Look for patterns with file extensions or path separators
        file_patterns = [
            r'[\w/\\.-]+\.(py|js|ts|tsx|jsx|java|go|rb|php|cs)',  # Full path with extension
            r'[\w.-]+\.(py|js|ts|tsx|jsx|java|go|rb|php|cs)',  # Filename with extension
        ]
        
        potential_paths = set()
        for pattern in file_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            potential_paths.update([m[0] if isinstance(m, tuple) else m for m in matches])
        
        # Query database
        base_query = self.db.query(File).filter(
            File.repository_id == repository_id
        )
        
        if analysis_run_id:
            base_query = base_query.filter(File.analysis_run_id == analysis_run_id)
        
        for path in potential_paths:
            # Exact path match
            files = base_query.filter(File.file_path == path).all()
            
            for file in files:
                candidates.append(TargetCandidate(
                    target=self._file_to_target(file),
                    match_score=1.0,
                    match_reason=f"Exact file path match: {path}"
                ))
            
            # Partial path match (ends with)
            if not files:
                partial_files = base_query.filter(
                    File.file_path.like(f"%{path}")
                ).limit(10).all()
                
                for file in partial_files:
                    score = self._calculate_path_similarity(path, file.file_path)
                    if score >= 0.5:
                        candidates.append(TargetCandidate(
                            target=self._file_to_target(file),
                            match_score=score * 0.85,
                            match_reason=f"Partial file path match: {file.file_path}"
                        ))
        
        return candidates
    
    def _identify_endpoints(
        self,
        query: str,
        repository_id: UUID,
        analysis_run_id: Optional[UUID]
    ) -> List[TargetCandidate]:
        """
        Identify API endpoint candidates from query.
        
        Args:
            query: User query
            repository_id: Repository UUID
            analysis_run_id: Optional analysis run filter
            
        Returns:
            List of TargetCandidate objects
        """
        candidates: List[TargetCandidate] = []
        
        # Extract HTTP method and path
        # Look for patterns like: GET /api/users, POST /orders, etc.
        method_pattern = r'\b(GET|POST|PUT|PATCH|DELETE)\s+([/\w{}-]+)'
        matches = re.findall(method_pattern, query, re.IGNORECASE)
        
        base_query = self.db.query(ApiEndpoint).options(
            joinedload(ApiEndpoint.file)
        ).filter(
            ApiEndpoint.repository_id == repository_id
        )
        
        if analysis_run_id:
            base_query = base_query.filter(ApiEndpoint.analysis_run_id == analysis_run_id)
        
        for method, path in matches:
            method_enum = method.upper()
            
            # Exact match
            endpoints = base_query.filter(
                ApiEndpoint.method == method_enum,
                ApiEndpoint.path == path
            ).all()
            
            for endpoint in endpoints:
                candidates.append(TargetCandidate(
                    target=self._endpoint_to_target(endpoint),
                    match_score=1.0,
                    match_reason=f"Exact endpoint match: {method} {path}"
                ))
            
            # Method match with partial path
            if not endpoints:
                partial_endpoints = base_query.filter(
                    ApiEndpoint.method == method_enum,
                    ApiEndpoint.path.like(f"%{path}%")
                ).limit(10).all()
                
                for endpoint in partial_endpoints:
                    score = self._calculate_path_similarity(path, endpoint.path)
                    if score >= 0.5:
                        candidates.append(TargetCandidate(
                            target=self._endpoint_to_target(endpoint),
                            match_score=score * 0.9,
                            match_reason=f"Partial endpoint match: {endpoint.method.value} {endpoint.path}"
                        ))
        
        # Also try path-only matches (without explicit method)
        path_pattern = r'/[\w/{}-]+'
        path_matches = re.findall(path_pattern, query)
        
        for path in path_matches:
            if len(path) > 3:  # Ignore very short paths
                endpoints = base_query.filter(
                    ApiEndpoint.path == path
                ).all()
                
                for endpoint in endpoints:
                    candidates.append(TargetCandidate(
                        target=self._endpoint_to_target(endpoint),
                        match_score=0.85,
                        match_reason=f"Path match: {endpoint.path}"
                    ))
        
        return candidates
    
    def _symbol_to_target(self, symbol: Symbol) -> ImpactTarget:
        """Convert Symbol model to ImpactTarget schema."""
        qualified_name = symbol.name
        if symbol.parent_symbol_name:
            qualified_name = f"{symbol.parent_symbol_name}.{symbol.name}"
        
        return ImpactTarget(
            target_type="symbol",
            target_id=symbol.id,
            name=symbol.name,
            symbol_type=symbol.symbol_type.value,
            qualified_name=qualified_name,
            file_path=symbol.file.file_path if symbol.file else None,
            language=symbol.file.language if symbol.file else None
        )
    
    def _file_to_target(self, file: File) -> ImpactTarget:
        """Convert File model to ImpactTarget schema."""
        return ImpactTarget(
            target_type="file",
            target_id=file.id,
            name=file.file_path,
            file_path=file.file_path,
            language=file.language
        )
    
    def _endpoint_to_target(self, endpoint: ApiEndpoint) -> ImpactTarget:
        """Convert ApiEndpoint model to ImpactTarget schema."""
        return ImpactTarget(
            target_type="api_endpoint",
            target_id=endpoint.id,
            name=f"{endpoint.method.value} {endpoint.path}",
            http_method=endpoint.method.value,
            endpoint_path=endpoint.path,
            framework=endpoint.framework,
            handler_name=endpoint.handler_name,
            file_path=endpoint.file.file_path if endpoint.file else None
        )
    
    def _calculate_name_similarity(self, query_name: str, actual_name: str) -> float:
        """
        Calculate similarity score between two names.
        
        Uses simple Levenshtein-like approach.
        
        Args:
            query_name: Name from query
            actual_name: Actual symbol name
            
        Returns:
            Similarity score 0-1
        """
        query_lower = query_name.lower()
        actual_lower = actual_name.lower()
        
        # Exact match
        if query_lower == actual_lower:
            return 1.0
        
        # Contains
        if query_lower in actual_lower or actual_lower in query_lower:
            # Calculate ratio
            shorter = min(len(query_lower), len(actual_lower))
            longer = max(len(query_lower), len(actual_lower))
            return shorter / longer
        
        # Simple character overlap
        common_chars = set(query_lower) & set(actual_lower)
        total_chars = set(query_lower) | set(actual_lower)
        
        if total_chars:
            return len(common_chars) / len(total_chars)
        
        return 0.0
    
    def _calculate_path_similarity(self, query_path: str, actual_path: str) -> float:
        """
        Calculate similarity score between two paths.
        
        Args:
            query_path: Path from query
            actual_path: Actual file path
            
        Returns:
            Similarity score 0-1
        """
        # Normalize paths
        query_norm = query_path.replace('\\', '/').lower()
        actual_norm = actual_path.replace('\\', '/').lower()
        
        # Exact match
        if query_norm == actual_norm:
            return 1.0
        
        # Ends with (most specific)
        if actual_norm.endswith(query_norm):
            return 0.95
        
        # Contains
        if query_norm in actual_norm:
            return 0.8
        
        # Compare path segments
        query_segments = query_norm.split('/')
        actual_segments = actual_norm.split('/')
        
        matching_segments = sum(1 for q, a in zip(reversed(query_segments), reversed(actual_segments)) if q == a)
        max_segments = max(len(query_segments), len(actual_segments))
        
        if max_segments > 0:
            return matching_segments / max_segments
        
        return 0.0
