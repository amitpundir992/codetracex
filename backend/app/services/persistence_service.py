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
        file_metadata: List[Dict]
    ) -> None:
        """
        Persist complete analysis result to database.
        
        This method saves:
        - File metadata
        - Symbols (functions, classes, methods)
        - Imports
        - Calls
        - Relationships
        
        Args:
            repository: Repository model instance
            analysis_run: AnalysisRun model instance
            static_analysis: Static analysis result from Phase 3
            file_metadata: List of file metadata dicts from file scanner
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
    
    def mark_analysis_failed(self, analysis_run: AnalysisRun, error_message: str) -> None:
        """
        Mark an analysis run as failed.
        
        Args:
            analysis_run: AnalysisRun model instance
            error_message: Error message describing the failure
        """
        analysis_run.status = AnalysisStatus.failed
        analysis_run.error_message = error_message
        analysis_run.completed_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.error(f"Marked analysis run {analysis_run.id} as failed: {error_message}")
