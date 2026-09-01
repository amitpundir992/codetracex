"""
Static analysis orchestrator for Phase 3.

This service coordinates the parsing of repository files using language-specific
analyzers and aggregates the results into a unified format.

Architecture:
    Repository Files
           ↓
    Static Analyzer (orchestrator)
           ↓
    ┌──────┴──────┐
    ↓             ↓
Python Analyzer  JavaScript/TypeScript Analyzer
(Python AST)    (Tree-sitter)
    ↓             ↓
    └──────┬──────┘
           ↓
    Unified Results
"""
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from app.services.parsers.python_analyzer import (
    PythonASTAnalyzer,
    PythonAnalysisResult
)
from app.services.parsers.javascript_analyzer import (
    TreeSitterAnalyzer,
    JSAnalysisResult
)
from app.schemas.analysis import Symbol, Import, Call, AnalysisSummary


@dataclass
class FileAnalysisResult:
    """Result of analyzing a single file."""
    file_path: str
    language: str
    success: bool
    error: Optional[str] = None
    symbols: List[Symbol] = None
    imports: List[Import] = None
    calls: List[Call] = None
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = []
        if self.imports is None:
            self.imports = []
        if self.calls is None:
            self.calls = []


@dataclass
class StaticAnalysisResult:
    """Complete static analysis result for a repository."""
    summary: AnalysisSummary
    all_symbols: List[Symbol]
    all_imports: List[Import]
    all_calls: List[Call]
    failed_files: List[Dict[str, str]]  # List of {file, error} dicts


class StaticAnalyzer:
    """
    Orchestrator for static code analysis.
    
    This service:
    1. Receives a list of source files from the file scanner
    2. Determines which files can be analyzed
    3. Routes files to appropriate language-specific analyzers
    4. Aggregates results into a unified format
    5. Handles parsing failures gracefully
    
    Supported languages:
    - Python (.py)
    - JavaScript (.js, .jsx)
    - TypeScript (.ts, .tsx)
    
    Security: This service never executes repository code.
    Only reads and parses source files.
    """
    
    # Supported file extensions mapped to languages
    SUPPORTED_EXTENSIONS = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.jsx': 'JavaScript',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript',
    }
    
    def __init__(self):
        """Initialize the static analyzer with language-specific parsers."""
        self.python_analyzer = PythonASTAnalyzer()
        self.js_analyzer = TreeSitterAnalyzer()
    
    def analyze_repository(
        self,
        repo_root: Path,
        files: List[Path]
    ) -> StaticAnalysisResult:
        """
        Analyze all supported source files in a repository.
        
        This method:
        1. Filters for supported source files
        2. Routes each file to the appropriate analyzer
        3. Converts language-specific results to common format
        4. Aggregates all results
        5. Generates summary statistics
        
        Args:
            repo_root: Repository root directory
            files: List of file paths to analyze
            
        Returns:
            StaticAnalysisResult with all extracted information and statistics
        """
        # DEBUG: Log input files
        print(f"\n=== STATIC ANALYZER DEBUG ===")
        print(f"Total files received: {len(files)}")
        print(f"Repo root: {repo_root}")
        if files:
            print(f"Sample files (first 5):")
            for f in files[:5]:
                print(f"  - {f} (exists: {f.exists()}, suffix: {f.suffix})")
        
        # Filter supported files
        supported_files = [f for f in files if self.is_supported(f)]
        
        print(f"Supported files after filtering: {len(supported_files)}")
        if supported_files:
            print(f"Sample supported files (first 5):")
            for f in supported_files[:5]:
                print(f"  - {f}")
        print(f"=== END DEBUG ===\n")
        
        # Track results
        all_symbols: List[Symbol] = []
        all_imports: List[Import] = []
        all_calls: List[Call] = []
        failed_files: List[Dict[str, str]] = []
        
        analyzed_count = 0
        skipped_count = len(files) - len(supported_files)
        
        # Analyze each supported file
        for idx, file_path in enumerate(supported_files):
            # Only log first 5 files to avoid spam
            if idx < 5:
                print(f"\nAnalyzing file {idx+1}/{len(supported_files)}: {file_path.name}")
            result = self.analyze_file(repo_root, file_path)
            
            if result.success:
                analyzed_count += 1
                
                # Aggregate symbols, imports, and calls
                all_symbols.extend(result.symbols)
                all_imports.extend(result.imports)
                all_calls.extend(result.calls)
            else:
                # Record failure
                failed_files.append({
                    "file": result.file_path,
                    "error": result.error or "Unknown error"
                })
        
        # Generate summary
        summary = self._generate_summary(
            total_files=len(files),
            analyzed_files=analyzed_count,
            skipped_files=skipped_count,
            failed_files=len(failed_files),
            symbols=all_symbols
        )
        
        # DEBUG: Final results summary
        print(f"\n=== FINAL ANALYSIS RESULTS ===")
        print(f"Total files: {len(files)}")
        print(f"Supported files: {len(supported_files)}")
        print(f"Successfully analyzed: {analyzed_count}")
        print(f"Failed files: {len(failed_files)}")
        print(f"\nExtracted data:")
        print(f"  Total symbols: {len(all_symbols)}")
        print(f"  Total imports: {len(all_imports)}")
        print(f"  Total calls: {len(all_calls)}")
        if failed_files:
            print(f"\nFailed files details:")
            for ff in failed_files[:5]:
                print(f"  - {ff['file']}: {ff['error']}")
        print(f"=== END FINAL RESULTS ===\n")
        
        return StaticAnalysisResult(
            summary=summary,
            all_symbols=all_symbols,
            all_imports=all_imports,
            all_calls=all_calls,
            failed_files=failed_files
        )
    
    def is_supported(self, file_path: Path) -> bool:
        """
        Check if a file extension is supported for static analysis.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file can be analyzed, False otherwise
        """
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    def get_language(self, file_path: Path) -> Optional[str]:
        """
        Determine the programming language of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Language name or None if unsupported
        """
        extension = file_path.suffix.lower()
        return self.SUPPORTED_EXTENSIONS.get(extension)
    
    def analyze_file(self, repo_root: Path, file_path: Path) -> FileAnalysisResult:
        """
        Analyze a single source file.
        
        Routes the file to the appropriate language-specific analyzer,
        then converts the result to the common format.
        
        Args:
            repo_root: Repository root directory
            file_path: Path to the file to analyze
            
        Returns:
            FileAnalysisResult with extracted information or error
        """
        language = self.get_language(file_path)
        
        if not language:
            return FileAnalysisResult(
                file_path=str(file_path.relative_to(repo_root)),
                language="Unknown",
                success=False,
                error="Unsupported file type"
            )
        
        # Calculate relative path for result
        relative_path = str(file_path.relative_to(repo_root)).replace('\\', '/')
        
        try:
            # Route to appropriate analyzer
            if language == 'Python':
                result = self.python_analyzer.analyze_file(file_path)
                return self._convert_python_result(relative_path, language, result)
            
            elif language in ['JavaScript', 'TypeScript']:
                result = self.js_analyzer.analyze_file(file_path)
                return self._convert_js_result(relative_path, language, result)
            
            else:
                return FileAnalysisResult(
                    file_path=relative_path,
                    language=language,
                    success=False,
                    error="No analyzer available for this language"
                )
        
        except Exception as e:
            return FileAnalysisResult(
                file_path=relative_path,
                language=language,
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def _convert_python_result(
        self,
        file_path: str,
        language: str,
        result: PythonAnalysisResult
    ) -> FileAnalysisResult:
        """
        Convert Python-specific analysis result to common format.
        
        Args:
            file_path: Relative file path
            language: Language name
            result: Python analyzer result
            
        Returns:
            FileAnalysisResult in common format
        """
        if not result.success:
            return FileAnalysisResult(
                file_path=file_path,
                language=language,
                success=False,
                error=result.error
            )
        
        # Convert symbols
        symbols = [
            Symbol(
                name=s.name,
                type=s.type,
                language=language,
                file=file_path,
                start_line=s.start_line,
                end_line=s.end_line,
                parent=s.parent
            )
            for s in result.symbols
        ]
        
        # Convert imports
        imports = [
            Import(
                file=file_path,
                source=i.source,
                names=i.names,
                line=i.line
            )
            for i in result.imports
        ]
        
        # Convert calls
        calls = [
            Call(
                file=file_path,
                caller=c.caller,
                callee=c.callee,
                line=c.line
            )
            for c in result.calls
        ]
        
        return FileAnalysisResult(
            file_path=file_path,
            language=language,
            success=True,
            symbols=symbols,
            imports=imports,
            calls=calls
        )
    
    def _convert_js_result(
        self,
        file_path: str,
        language: str,
        result: JSAnalysisResult
    ) -> FileAnalysisResult:
        """
        Convert JavaScript/TypeScript-specific analysis result to common format.
        
        Args:
            file_path: Relative file path
            language: Language name
            result: JavaScript analyzer result
            
        Returns:
            FileAnalysisResult in common format
        """
        if not result.success:
            return FileAnalysisResult(
                file_path=file_path,
                language=language,
                success=False,
                error=result.error
            )
        
        # Convert symbols
        symbols = [
            Symbol(
                name=s.name,
                type=s.type,
                language=language,
                file=file_path,
                start_line=s.start_line,
                end_line=s.end_line,
                parent=s.parent
            )
            for s in result.symbols
        ]
        
        # Convert imports
        imports = [
            Import(
                file=file_path,
                source=i.source,
                names=i.names,
                line=i.line
            )
            for i in result.imports
        ]
        
        # Convert calls
        calls = [
            Call(
                file=file_path,
                caller=c.caller,
                callee=c.callee,
                line=c.line
            )
            for c in result.calls
        ]
        
        return FileAnalysisResult(
            file_path=file_path,
            language=language,
            success=True,
            symbols=symbols,
            imports=imports,
            calls=calls
        )
    
    def _generate_summary(
        self,
        total_files: int,
        analyzed_files: int,
        skipped_files: int,
        failed_files: int,
        symbols: List[Symbol]
    ) -> AnalysisSummary:
        """
        Generate summary statistics for the analysis.
        
        Args:
            total_files: Total number of files in repository
            analyzed_files: Files successfully analyzed
            skipped_files: Files skipped (unsupported)
            failed_files: Files that failed parsing
            symbols: All extracted symbols
            
        Returns:
            AnalysisSummary with statistics
        """
        # Count symbols by type
        symbols_by_type: Dict[str, int] = {}
        for symbol in symbols:
            symbol_type = symbol.type
            symbols_by_type[symbol_type] = symbols_by_type.get(symbol_type, 0) + 1
        
        return AnalysisSummary(
            total_files=total_files,
            analyzed_files=analyzed_files,
            skipped_files=skipped_files,
            failed_files=failed_files,
            total_symbols=len(symbols),
            symbols_by_type=symbols_by_type,
            total_imports=0,  # Will be set by caller
            total_calls=0     # Will be set by caller
        )
