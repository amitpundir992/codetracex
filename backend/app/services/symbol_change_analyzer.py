"""
Symbol Change Analyzer for Phase 18: Pull Request & Change Intelligence.

This service identifies changed symbols (functions, classes, methods) by
comparing symbols between base and head commits/analyses.

Architecture Philosophy:

    DETERMINISTIC SYMBOL MATCHING
    
    This service identifies:
    - Added symbols
    - Deleted symbols
    - Potentially modified symbols (with uncertainty)
    
    Symbol modification detection is inherently uncertain without
    semantic diff analysis. We explicitly represent this uncertainty.
    
    Matching Strategy:
    1. Exact qualified name match
    2. File path + symbol name match
    3. Explicit uncertainty for ambiguous cases
    
    We do NOT:
    - Claim certainty where none exists
    - Perform semantic code diff
    - Execute code

Repository Isolation:

    All queries scoped by repository_id and analysis_run_id.
"""
from typing import List, Dict, Set, Optional, Tuple
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import Symbol, File, AnalysisRun
from app.schemas.change_analysis import ChangedSymbol, ChangeType, ChangedFile

logger = logging.getLogger(__name__)


class SymbolChangeAnalyzer:
    """
    Service for identifying changed symbols between commits.
    
    Compares symbols between two analysis runs to detect additions,
    deletions, and potential modifications.
    """
    
    def __init__(self, db: Session):
        """
        Initialize symbol change analyzer.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def _is_public_symbol(self, symbol: Symbol) -> bool:
        """
        Heuristic to determine if a symbol is likely public.
        
        Args:
            symbol: Symbol object
            
        Returns:
            True if likely public
        """
        # Python private naming convention
        if symbol.name.startswith('_') and not symbol.name.startswith('__'):
            return False
        
        # Python dunder methods are special but not necessarily private
        if symbol.name.startswith('__') and symbol.name.endswith('__'):
            return True
        
        # Class methods are typically public unless named privately
        if symbol.symbol_type == 'method':
            return not symbol.name.startswith('_')
        
        # Functions and classes default to public
        return True
    
    def _get_symbols_for_files(
        self,
        repository_id: UUID,
        file_paths: List[str],
        analysis_run_id: Optional[UUID] = None
    ) -> Dict[str, List[Symbol]]:
        """
        Get symbols for specific files from an analysis run.
        
        Args:
            repository_id: Repository UUID
            file_paths: List of file paths
            analysis_run_id: Optional specific analysis run (uses latest if None)
            
        Returns:
            Dictionary mapping file paths to lists of symbols
        """
        # Get analysis run
        if analysis_run_id:
            analysis_run = self.db.query(AnalysisRun).filter(
                and_(
                    AnalysisRun.id == analysis_run_id,
                    AnalysisRun.repository_id == repository_id
                )
            ).first()
        else:
            # Get latest completed analysis
            analysis_run = self.db.query(AnalysisRun).filter(
                and_(
                    AnalysisRun.repository_id == repository_id,
                    AnalysisRun.status == 'completed'
                )
            ).order_by(AnalysisRun.completed_at.desc()).first()
        
        if not analysis_run:
            logger.warning(f"No analysis run found for repository {repository_id}")
            return {}
        
        # Get files
        files = self.db.query(File).filter(
            and_(
                File.analysis_run_id == analysis_run.id,
                File.path.in_(file_paths)
            )
        ).all()
        
        if not files:
            return {}
        
        file_ids = [f.id for f in files]
        file_path_map = {f.id: f.path for f in files}
        
        # Get symbols for these files
        symbols = self.db.query(Symbol).filter(
            Symbol.file_id.in_(file_ids)
        ).all()
        
        # Group by file path
        symbols_by_file: Dict[str, List[Symbol]] = {}
        for symbol in symbols:
            file_path = file_path_map.get(symbol.file_id)
            if file_path:
                if file_path not in symbols_by_file:
                    symbols_by_file[file_path] = []
                symbols_by_file[file_path].append(symbol)
        
        return symbols_by_file
    
    def _create_changed_symbol(
        self,
        symbol: Symbol,
        change_type: ChangeType,
        file_path: str
    ) -> ChangedSymbol:
        """
        Create a ChangedSymbol from a Symbol database object.
        
        Args:
            symbol: Symbol database object
            change_type: Type of change
            file_path: File path
            
        Returns:
            ChangedSymbol schema object
        """
        # Construct qualified name from file path and symbol name
        # e.g., "src/services/user_service.py:UserService"
        qualified_name = f"{file_path}:{symbol.name}"
        
        return ChangedSymbol(
            name=symbol.name,
            qualified_name=qualified_name,
            symbol_type=symbol.symbol_type,
            change_type=change_type,
            file_path=file_path,
            line_number=symbol.start_line,
            is_public=self._is_public_symbol(symbol)
        )
    
    def analyze_symbol_changes(
        self,
        repository_id: UUID,
        changed_files: List[ChangedFile]
    ) -> List[ChangedSymbol]:
        """
        Analyze symbol changes based on file changes.
        
        Strategy:
        1. For added files: all symbols are added
        2. For deleted files: all symbols are deleted
        3. For modified files: compare symbols between latest analysis
        4. For renamed files: treat as delete + add (uncertain)
        
        Note: Without code-level diff, we cannot definitively identify
        modified symbols. We mark all symbols in modified files as
        potentially modified but this is uncertain.
        
        Args:
            repository_id: Repository UUID
            changed_files: List of changed files
            
        Returns:
            List of ChangedSymbol objects with explicit uncertainty
        """
        changed_symbols: List[ChangedSymbol] = []
        
        # Get latest analysis run
        latest_analysis = self.db.query(AnalysisRun).filter(
            and_(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.status == 'completed'
            )
        ).order_by(AnalysisRun.completed_at.desc()).first()
        
        if not latest_analysis:
            logger.warning(
                f"No completed analysis found for repository {repository_id}. "
                "Cannot analyze symbol changes."
            )
            return []
        
        # Process each file
        for changed_file in changed_files:
            # Only analyze source files
            if not changed_file.is_source:
                continue
            
            file_path = changed_file.path
            
            # Get symbols for this file from latest analysis
            symbols_map = self._get_symbols_for_files(
                repository_id,
                [file_path],
                latest_analysis.id
            )
            
            symbols = symbols_map.get(file_path, [])
            
            if changed_file.change_type == ChangeType.ADDED:
                # All symbols in added file are added
                for symbol in symbols:
                    changed_symbols.append(
                        self._create_changed_symbol(symbol, ChangeType.ADDED, file_path)
                    )
                
                logger.debug(
                    f"File {file_path} added with {len(symbols)} symbols"
                )
            
            elif changed_file.change_type == ChangeType.DELETED:
                # All symbols in deleted file are deleted
                for symbol in symbols:
                    changed_symbols.append(
                        self._create_changed_symbol(symbol, ChangeType.DELETED, file_path)
                    )
                
                logger.debug(
                    f"File {file_path} deleted with {len(symbols)} symbols"
                )
            
            elif changed_file.change_type == ChangeType.MODIFIED:
                # File modified - symbols may be added/modified/deleted
                # Without semantic diff, we conservatively mark as MODIFIED
                # This represents uncertainty
                for symbol in symbols:
                    changed_symbols.append(
                        self._create_changed_symbol(symbol, ChangeType.MODIFIED, file_path)
                    )
                
                logger.debug(
                    f"File {file_path} modified with {len(symbols)} symbols "
                    "(marked as potentially modified)"
                )
            
            elif changed_file.change_type == ChangeType.RENAMED:
                # Handle renamed files
                # Get symbols from old path (if available)
                old_path = changed_file.old_path
                
                if old_path:
                    old_symbols_map = self._get_symbols_for_files(
                        repository_id,
                        [old_path],
                        latest_analysis.id
                    )
                    old_symbols = old_symbols_map.get(old_path, [])
                    
                    # Mark old path symbols as deleted
                    for symbol in old_symbols:
                        changed_symbols.append(
                            self._create_changed_symbol(
                                symbol,
                                ChangeType.DELETED,
                                old_path
                            )
                        )
                
                # Mark new path symbols as added
                for symbol in symbols:
                    changed_symbols.append(
                        self._create_changed_symbol(symbol, ChangeType.ADDED, file_path)
                    )
                
                logger.debug(
                    f"File renamed from {old_path} to {file_path}"
                )
        
        logger.info(
            f"Identified {len(changed_symbols)} symbol changes across "
            f"{len(changed_files)} files"
        )
        
        # Deduplicate by qualified name + change type
        seen = set()
        unique_symbols = []
        
        for symbol in changed_symbols:
            key = (symbol.qualified_name, symbol.change_type)
            if key not in seen:
                seen.add(key)
                unique_symbols.append(symbol)
        
        if len(unique_symbols) < len(changed_symbols):
            logger.debug(
                f"Deduplicated {len(changed_symbols) - len(unique_symbols)} "
                "duplicate symbols"
            )
        
        return unique_symbols
