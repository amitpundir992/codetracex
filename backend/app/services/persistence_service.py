"""
Persistence service for Phase 4.

This service is responsible for persisting Phase 3 static analysis results
into PostgreSQL.

Architecture:
    
    Static Analyzer (Phase 3)
            ↓
    Intermediate Representation (Python objects)
            ↓
    Persistence Service (this module)
            ↓
    SQLAlchemy Models
            ↓
    PostgreSQL
    
Why this separation?
    
    - Decouples static analysis from database
    - Makes analysis logic database-agnostic
    - Allows same analysis result to be used for:
        - PostgreSQL storage
        - Knowledge graph construction
        - Real-time API responses
        - Future: embeddings, RAG
    - Makes testing easier (can test analysis without database)
    
Transaction Handling:
    
    All persistence happens in a single database transaction.
    
    If any step fails:
    - Transaction is rolled back
    - No partial data in database
    - AnalysisRun marked as failed
    
    This ensures data consistency.
"""
from datetime import datetime
from typing import Dict, List, Optional
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Repository, AnalysisRun, File, Symbol, Import, Call, Relationship,
    AnalysisStatus, SymbolType, RelationshipType
)
from app.services.static_analyzer import StaticAnalysisResult
from app.schemas.analysis import Symbol as SymbolSchema, Import as ImportSchema, Call as CallSchema

logger = logging.getLogger(__name__)


class PersistenceService:
    """
    Service for persisting analysis results to PostgreSQL.
    
    This service handles the complete lifecycle of storing analysis data:
    1. Create or retrieve Repository
    2. Create AnalysisRun
    3. Mark status as running
    4. Persist files, symbols, imports, calls
    5. Create relationships
    6. Mark status as completed or failed
    
    All operations are transactional to ensure data consistency.
    """
    
    def __init__(self, db: Session):
        """
        Initialize persistence service with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create_or_get_repository(
        self,
        owner: str,
        name: str,
        github_url: str,
        default_branch: Optional[str] = None,
        description: Optional[str] = None,
        language: Optional[str] = None,
        stars: Optional[int] = None
    ) -> Repository:
        """
        Create a new repository or retrieve existing one.
        
        Repositories are identified by full_name (owner/name).
        If repository exists, it is returned without modification.
        If repository doesn't exist, it is created.
        
        Args:
            owner: GitHub username or organization
            name: Repository name
            github_url: Full GitHub URL
            default_branch: Default branch name
            description: Repository description
            language: Primary language
            stars: Star count
            
        Returns:
            Repository model instance
        """
        full_name = f"{owner}/{name}"
        
        # Try to retrieve existing repository
        repository = self.db.query(Repository).filter(
            Repository.full_name == full_name
        ).first()
        
        if repository:
            logger.info(f"Found existing repository: {full_name}")
            return repository
        
        # Create new repository
        repository = Repository(
            owner=owner,
            name=name,
            full_name=full_name,
            github_url=github_url,
            default_branch=default_branch,
            description=description,
            language=language,
            stars=stars
        )
        
        self.db.add(repository)
        self.db.flush()  # Flush to get ID without committing
        
        logger.info(f"Created new repository: {full_name}")
        return repository
    
    def create_analysis_run(self, repository: Repository) -> AnalysisRun:
        """
        Create a new analysis run for a repository.
        
        Args:
            repository: Repository model instance
            
        Returns:
            AnalysisRun model instance with status=running
        """
        analysis_run = AnalysisRun(
            repository_id=repository.id,
            status=AnalysisStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        self.db.add(analysis_run)
        self.db.flush()
        
        logger.info(f"Created analysis run: {analysis_run.id}")
        return analysis_run
    
    def persist_analysis_result(
        self,
        repository: Repository,
        analysis_run: AnalysisRun,
        static_analysis: StaticAnalysisResult,
        file_metadata: List[Dict],
        api_endpoints: Optional[List] = None  # Optional list of DetectedEndpoint
    ) -> None:
        """
        Persist complete analysis result to database.
        
        This method saves:
        - File metadata
        - Symbols (functions, classes, methods)
        - Imports
        - Calls
        - Relationships
        - API Endpoints (Phase 7)
        
        Args:
            repository: Repository model instance
            analysis_run: AnalysisRun model instance
            static_analysis: Static analysis result from Phase 3
            file_metadata: List of file metadata dicts from file scanner
            api_endpoints: Optional list of DetectedEndpoint from Phase 7
        """
        try:
            # Update analysis run statistics
            analysis_run.total_files = len(file_metadata)
            analysis_run.analyzed_files = static_analysis.summary.analyzed_files
            analysis_run.total_symbols = len(static_analysis.all_symbols)
            analysis_run.total_imports = len(static_analysis.all_imports)
            analysis_run.total_calls = len(static_analysis.all_calls)
            
            # Persist files
            file_map = self._persist_files(repository, analysis_run, file_metadata)
            
            # Persist symbols
            symbol_map = self._persist_symbols(analysis_run, static_analysis.all_symbols, file_map)
            
            # Persist imports
            self._persist_imports(analysis_run, static_analysis.all_imports, file_map)
            
            # Persist calls
            self._persist_calls(analysis_run, static_analysis.all_calls, file_map)
            
            # Create relationships
            self._create_relationships(analysis_run, static_analysis.all_symbols, symbol_map)
            
            # Phase 7: Persist API endpoints
            if api_endpoints:
                self.persist_api_endpoints(repository, analysis_run, api_endpoints, file_map, symbol_map)
            
            # Mark analysis as completed
            analysis_run.status = AnalysisStatus.COMPLETED
            analysis_run.completed_at = datetime.utcnow()
            
            # Commit transaction
            self.db.commit()
            
            logger.info(f"Successfully persisted analysis run: {analysis_run.id}")
            
        except Exception as e:
            # Rollback on error
            self.db.rollback()
            
            # Mark analysis as failed
            analysis_run.status = AnalysisStatus.FAILED
            analysis_run.error_message = str(e)
            analysis_run.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.error(f"Failed to persist analysis run: {analysis_run.id}, error: {str(e)}")
            raise
    
    def _persist_files(
        self,
        repository: Repository,
        analysis_run: AnalysisRun,
        file_metadata: List[Dict]
    ) -> Dict[str, File]:
        """
        Persist file metadata to database.
        
        Args:
            repository: Repository model instance
            analysis_run: AnalysisRun model instance
            file_metadata: List of file metadata dicts
            
        Returns:
            Dict mapping file path to File model instance
        """
        file_map = {}
        
        for file_meta in file_metadata:
            file = File(
                repository_id=repository.id,
                analysis_run_id=analysis_run.id,
                path=file_meta.get('path'),
                filename=file_meta.get('filename'),
                extension=file_meta.get('extension'),
                language=file_meta.get('language'),
                size_bytes=file_meta.get('size_bytes'),
                line_count=file_meta.get('lines'),
                is_sensitive=file_meta.get('is_sensitive', False)
            )
            
            self.db.add(file)
            self.db.flush()
            
            file_map[file.path] = file
        
        logger.info(f"Persisted {len(file_map)} files")
        return file_map
    
    def _persist_symbols(
        self,
        analysis_run: AnalysisRun,
        symbols: List[SymbolSchema],
        file_map: Dict[str, File]
    ) -> Dict[str, Symbol]:
        """
        Persist symbols to database.
        
        Args:
            analysis_run: AnalysisRun model instance
            symbols: List of Symbol schemas from Phase 3
            file_map: Dict mapping file path to File model
            
        Returns:
            Dict mapping symbol key (file:name:type) to Symbol model instance
        """
        symbol_map = {}
        parent_map = {}  # Track parent symbols for methods
        
        # First pass: Create all symbols
        for symbol_schema in symbols:
            file = file_map.get(symbol_schema.file)
            if not file:
                logger.warning(f"File not found for symbol: {symbol_schema.name} in {symbol_schema.file}")
                continue
            
            # Map symbol type string to enum
            symbol_type = self._map_symbol_type(symbol_schema.type)
            
            symbol = Symbol(
                file_id=file.id,
                analysis_run_id=analysis_run.id,
                name=symbol_schema.name,
                symbol_type=symbol_type,
                language=symbol_schema.language,
                start_line=symbol_schema.start_line,
                end_line=symbol_schema.end_line
            )
            
            self.db.add(symbol)
            self.db.flush()
            
            # Create unique key for this symbol
            symbol_key = f"{symbol_schema.file}:{symbol_schema.name}:{symbol_schema.type}"
            symbol_map[symbol_key] = symbol
            
            # Track parent relationship
            if symbol_schema.parent:
                parent_key = f"{symbol_schema.file}:{symbol_schema.parent}:class"
                parent_map[symbol_key] = parent_key
        
        # Second pass: Link parent symbols
        for symbol_key, parent_key in parent_map.items():
            if symbol_key in symbol_map and parent_key in symbol_map:
                symbol_map[symbol_key].parent_symbol_id = symbol_map[parent_key].id
        
        logger.info(f"Persisted {len(symbol_map)} symbols")
        return symbol_map
    
    def _persist_imports(
        self,
        analysis_run: AnalysisRun,
        imports: List[ImportSchema],
        file_map: Dict[str, File]
    ) -> None:
        """
        Persist imports to database.
        
        Args:
            analysis_run: AnalysisRun model instance
            imports: List of Import schemas from Phase 3
            file_map: Dict mapping file path to File model
        """
        for import_schema in imports:
            file = file_map.get(import_schema.file)
            if not file:
                logger.warning(f"File not found for import: {import_schema.source} in {import_schema.file}")
                continue
            
            # Convert list of names to comma-separated string
            imported_names = ",".join(import_schema.names) if import_schema.names else None
            
            import_obj = Import(
                file_id=file.id,
                analysis_run_id=analysis_run.id,
                source=import_schema.source,
                imported_names=imported_names,
                line_number=import_schema.line
            )
            
            self.db.add(import_obj)
        
        logger.info(f"Persisted {len(imports)} imports")
    
    def _persist_calls(
        self,
        analysis_run: AnalysisRun,
        calls: List[CallSchema],
        file_map: Dict[str, File]
    ) -> None:
        """
        Persist calls to database.
        
        Args:
            analysis_run: AnalysisRun model instance
            calls: List of Call schemas from Phase 3
            file_map: Dict mapping file path to File model
        """
        for call_schema in calls:
            file = file_map.get(call_schema.file)
            if not file:
                logger.warning(f"File not found for call: {call_schema.caller} -> {call_schema.callee}")
                continue
            
            call_obj = Call(
                file_id=file.id,
                analysis_run_id=analysis_run.id,
                caller_name=call_schema.caller,
                callee_name=call_schema.callee,
                line_number=call_schema.line
            )
            
            self.db.add(call_obj)
        
        logger.info(f"Persisted {len(calls)} calls")
    
    def _create_relationships(
        self,
        analysis_run: AnalysisRun,
        symbols: List[SymbolSchema],
        symbol_map: Dict[str, Symbol]
    ) -> None:
        """
        Create relationships from symbols.
        
        Currently creates CONTAINS relationships for methods and their parent classes.
        
        Args:
            analysis_run: AnalysisRun model instance
            symbols: List of Symbol schemas from Phase 3
            symbol_map: Dict mapping symbol key to Symbol model instance
        """
        for symbol_schema in symbols:
            if symbol_schema.parent:
                # Create CONTAINS relationship: Class CONTAINS Method
                child_key = f"{symbol_schema.file}:{symbol_schema.name}:{symbol_schema.type}"
                parent_key = f"{symbol_schema.file}:{symbol_schema.parent}:class"
                
                if child_key in symbol_map and parent_key in symbol_map:
                    relationship = Relationship(
                        analysis_run_id=analysis_run.id,
                        relationship_type=RelationshipType.CONTAINS,
                        source_type="symbol",
                        source_id=symbol_map[parent_key].id,
                        target_type="symbol",
                        target_id=symbol_map[child_key].id
                    )
                    
                    self.db.add(relationship)
        
        logger.info(f"Created relationships")
    
    def _map_symbol_type(self, type_str: str) -> SymbolType:
        """
        Map symbol type string to SymbolType enum.
        
        Args:
            type_str: Symbol type string from Phase 3
            
        Returns:
            SymbolType enum value
        """
        mapping = {
            'function': SymbolType.FUNCTION,
            'class': SymbolType.CLASS,
            'method': SymbolType.METHOD,
            'arrow_function': SymbolType.ARROW_FUNCTION,
            'interface': SymbolType.INTERFACE
        }
        return mapping.get(type_str, SymbolType.FUNCTION)
    
    def persist_git_history(
        self,
        repository: Repository,
        commits: List[Dict],
        file_path_to_id: Optional[Dict[str, str]] = None
    ) -> int:
        """
        Persist Git commit history to database.
        
        Phase 6: Git History Intelligence
        
        This method:
        1. Checks for existing commits (by repository_id + commit_hash)
        2. Inserts new commits
        3. Inserts file changes for each commit
        4. Links file changes to existing File records where possible
        
        Duplicate Handling:
            Commits are unique by (repository_id, commit_hash).
            If a commit already exists, it is skipped.
            This allows re-analysis without duplicating history.
        
        File Matching:
            If file_path_to_id is provided, file changes are linked to File records.
            file_path_to_id maps: file_path -> file_id (UUID)
            
            For historical files not in current analysis:
            - file_id is NULL
            - path is preserved
        
        Args:
            repository: Repository model instance
            commits: List of commit dictionaries from GitHistoryService:
                - commit_hash: Full SHA
                - author_name: Author name
                - author_email: Author email
                - commit_message: Full message
                - committed_at: datetime
                - parent_hashes: List of parent SHAs
                - file_changes: List of file change dicts
            file_path_to_id: Optional mapping from file path to UUID
            
        Returns:
            Number of commits persisted (new commits only)
            
        Raises:
            Exception: If persistence fails
        """
        from app.db.models import Commit, CommitFileChange, ChangeType
        
        if not commits:
            logger.info("No commits to persist")
            return 0
        
        # Get existing commit hashes for this repository
        existing_hashes = set(
            row[0] for row in self.db.query(Commit.commit_hash)
            .filter(Commit.repository_id == repository.id)
            .all()
        )
        
        new_commits = 0
        
        for commit_data in commits:
            commit_hash = commit_data['commit_hash']
            
            # Skip if commit already exists
            if commit_hash in existing_hashes:
                logger.debug(f"Skipping existing commit: {commit_hash[:8]}")
                continue
            
            # Create Commit record
            commit = Commit(
                repository_id=repository.id,
                commit_hash=commit_hash,
                author_name=commit_data['author_name'],
                author_email=commit_data['author_email'],
                commit_message=commit_data['commit_message'],
                committed_at=commit_data['committed_at'],
                parent_hashes=','.join(commit_data.get('parent_hashes', []))
            )
            
            self.db.add(commit)
            self.db.flush()  # Get commit.id for file changes
            
            # Create CommitFileChange records
            file_changes = commit_data.get('file_changes', [])
            for change_data in file_changes:
                path = change_data['path']
                
                # Map change_type string to enum
                change_type_str = change_data['change_type']
                change_type = ChangeType[change_type_str.upper()]
                
                # Link to File record if available
                file_id = None
                if file_path_to_id and path in file_path_to_id:
                    file_id = file_path_to_id[path]
                
                file_change = CommitFileChange(
                    commit_id=commit.id,
                    file_id=file_id,
                    path=path,
                    change_type=change_type,
                    additions=change_data.get('additions', 0),
                    deletions=change_data.get('deletions', 0),
                    old_path=change_data.get('old_path'),
                    new_path=change_data.get('new_path')
                )
                
                self.db.add(file_change)
            
            new_commits += 1
        
        # Commit transaction
        self.db.commit()
        
        logger.info(
            f"Persisted {new_commits} new commits out of {len(commits)} total "
            f"({len(commits) - new_commits} already existed)"
        )
        
        return new_commits
        
        return mapping.get(type_str, SymbolType.FUNCTION)
    
    def persist_api_endpoints(
        self,
        repository: Repository,
        analysis_run: AnalysisRun,
        endpoints: List,  # List[DetectedEndpoint] from api_route_analyzer
        file_map: Dict[str, File],
        symbol_map: Dict[str, Symbol]
    ) -> int:
        """
        Persist API endpoints to database.
        
        Phase 7: API & Application Structure Intelligence
        
        This method:
        1. Validates each endpoint
        2. Links endpoint to File record
        3. Attempts to resolve handler to Symbol record
        4. Inserts ApiEndpoint record
        
        Handler Resolution:
            The analyzer extracts handler_name from route definitions.
            We attempt to find a matching Symbol in the symbol_map.
            
            Symbol lookup strategy:
            - Look for function/method with matching name in the same file
            - Match by: file_path:handler_name:function (or method)
            
            If resolution succeeds: symbol_id is set
            If resolution fails: symbol_id remains NULL
            
            This maintains conservative factual reporting.
        
        Duplicate Handling:
            Endpoints are unique by (analysis_run_id, method, path).
            If a duplicate is encountered, it is skipped.
        
        Args:
            repository: Repository model instance
            analysis_run: AnalysisRun model instance
            endpoints: List of DetectedEndpoint from ApiRouteAnalyzer
            file_map: Dict mapping file path to File model
            symbol_map: Dict mapping symbol key to Symbol model
            
        Returns:
            Number of endpoints persisted
            
        Raises:
            Exception: If persistence fails
        """
        from app.db.models import ApiEndpoint, HttpMethod
        
        if not endpoints:
            logger.info("No API endpoints to persist")
            return 0
        
        persisted_count = 0
        
        for endpoint in endpoints:
            # Skip if no file_path (shouldn't happen, but be defensive)
            if not endpoint.file_path:
                logger.warning(f"Endpoint {endpoint.method} {endpoint.path} has no file_path")
                continue
            
            # Find the File record for this endpoint
            file_record = file_map.get(endpoint.file_path)
            if not file_record:
                logger.warning(f"File not found for endpoint: {endpoint.file_path}")
                continue
            
            # Attempt to resolve handler to Symbol
            symbol_id = None
            if endpoint.handler_name:
                # Try to find matching symbol in the same file
                # Symbol map key format: file:name:type
                
                # Try function first
                function_key = f"{endpoint.file_path}:{endpoint.handler_name}:function"
                if function_key in symbol_map:
                    symbol_id = symbol_map[function_key].id
                else:
                    # Try method
                    method_key = f"{endpoint.file_path}:{endpoint.handler_name}:method"
                    if method_key in symbol_map:
                        symbol_id = symbol_map[method_key].id
                    else:
                        # Try arrow function
                        arrow_key = f"{endpoint.file_path}:{endpoint.handler_name}:arrow_function"
                        if arrow_key in symbol_map:
                            symbol_id = symbol_map[arrow_key].id
                
                if symbol_id:
                    logger.debug(f"Resolved handler {endpoint.handler_name} to symbol {symbol_id}")
                else:
                    logger.debug(f"Could not resolve handler {endpoint.handler_name}")
            
            # Map method string to HttpMethod enum
            try:
                http_method = HttpMethod[endpoint.method]
            except KeyError:
                logger.warning(f"Invalid HTTP method: {endpoint.method}")
                continue
            
            # Create ApiEndpoint record
            try:
                api_endpoint = ApiEndpoint(
                    repository_id=repository.id,
                    analysis_run_id=analysis_run.id,
                    file_id=file_record.id,
                    symbol_id=symbol_id,
                    method=http_method,
                    path=endpoint.path,
                    framework=endpoint.framework,
                    handler_name=endpoint.handler_name,
                    start_line=endpoint.start_line,
                    end_line=endpoint.end_line
                )
                
                self.db.add(api_endpoint)
                self.db.flush()
                
                persisted_count += 1
                
            except IntegrityError as e:
                # Duplicate endpoint - skip it
                logger.warning(f"Duplicate endpoint: {endpoint.method} {endpoint.path}")
                self.db.rollback()
                continue
        
        logger.info(f"Persisted {persisted_count} API endpoints")
        
        return persisted_count
    
    def mark_analysis_failed(self, analysis_run: AnalysisRun, error_message: str) -> None:
        """
        Mark an analysis run as failed.
        
        Args:
            analysis_run: AnalysisRun model instance
            error_message: Error message describing the failure
        """
        analysis_run.status = AnalysisStatus.FAILED
        analysis_run.error_message = error_message
        analysis_run.completed_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.error(f"Marked analysis run {analysis_run.id} as failed: {error_message}")
