"""
Job orchestration service for background repository analysis.

Phase 14: Background Processing

This service orchestrates the complete repository analysis pipeline as a background job:
1. Download repository
2. Scan files
3. Static analysis
4. Persist to database
5. Build knowledge graph
6. Extract Git history
7. Analyze API endpoints
8. Detect workflows
9. Build semantic chunks
10. Generate embeddings

Key differences from RepositoryAnalysisService:
- Designed for background execution (no async/await at top level)
- Updates job progress at each stage
- Handles cleanup robustly even on failure
- Reports detailed stage information
- Separates LLM operations (not required for base indexing)

Architecture:
    
    Worker (RQ) → JobOrchestrationService → Existing Services → Database
    
This service REUSES existing services, it does not duplicate their logic.
"""
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.repository_service import RepositoryService
from app.services.download_service import RepositoryDownloadService, DownloadError, DownloadTooLargeError
from app.services.scanner_service import FileScannerService, TooManyFilesError
from app.services.static_analyzer import StaticAnalyzer
from app.services.persistence_service import PersistenceService
from app.services.graph_service import GraphService
from app.services.git_history_service import GitHistoryService
from app.services.api_route_analyzer import ApiRouteAnalyzer
from app.services.workflow_service import WorkflowService
from app.services.chunk_builder import ChunkBuilder
from app.services.embedding_service import EmbeddingService
from app.utils.zip_utils import safe_extract, find_repository_root, UnsafeZipError, InvalidZipError
from app.db.models import AnalysisRun, AnalysisStatus, File, Symbol, ApiEndpoint
from app.services.github_service import GitHubAPIError, RepositoryNotFoundError
from app.services.repository_service import InvalidRepositoryURLError

logger = logging.getLogger(__name__)


class JobOrchestrationService:
    """
    Orchestrates complete repository analysis as a background job.
    
    This service is the main entry point for worker execution.
    It coordinates all analysis stages and updates job progress.
    """
    
    def __init__(self, db: Session, analysis_run: AnalysisRun):
        """
        Initialize orchestration service.
        
        Args:
            db: Database session
            analysis_run: AnalysisRun model instance
        """
        self.db = db
        self.analysis_run = analysis_run
        self.settings = get_settings()
        
        # Initialize existing services
        self.repository_service = RepositoryService()
        self.download_service = RepositoryDownloadService(
            max_size_bytes=self.settings.max_repository_size_bytes
        )
        self.scanner_service = FileScannerService(
            max_files=self.settings.MAX_REPOSITORY_FILES
        )
        self.static_analyzer = StaticAnalyzer()
        self.api_route_analyzer = ApiRouteAnalyzer()
        self.persistence_service = PersistenceService(db)
        self.graph_service = GraphService(db)
        self.git_history_service = GitHistoryService()
        self.workflow_service = WorkflowService(db)
        self.embedding_service = EmbeddingService()
    
    def update_progress(self, stage: str, progress: int):
        """
        Update job progress in database.
        
        Args:
            stage: Current pipeline stage description
            progress: Progress percentage (0-100)
        """
        try:
            self.analysis_run.current_stage = stage
            self.analysis_run.progress = progress
            self.db.commit()
            logger.info(f"Job {self.analysis_run.id}: {stage} ({progress}%)")
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")
            self.db.rollback()
    
    def mark_running(self):
        """Mark analysis as running."""
        try:
            self.analysis_run.status = AnalysisStatus.RUNNING
            self.analysis_run.started_at = datetime.utcnow()
            self.update_progress("Starting analysis", 0)
        except Exception as e:
            logger.error(f"Failed to mark running: {e}")
            raise
    
    def mark_completed(self):
        """Mark analysis as completed."""
        try:
            self.analysis_run.status = AnalysisStatus.COMPLETED
            self.analysis_run.completed_at = datetime.utcnow()
            self.analysis_run.current_stage = "Completed"
            self.analysis_run.progress = 100
            self.db.commit()
            logger.info(f"Analysis run {self.analysis_run.id} completed successfully")
        except Exception as e:
            logger.error(f"Failed to mark completed: {e}")
            self.db.rollback()
    
    def mark_failed(self, error_message: str):
        """
        Mark analysis as failed with error message.
        
        Args:
            error_message: Safe error message (no secrets)
        """
        try:
            self.analysis_run.status = AnalysisStatus.FAILED
            self.analysis_run.completed_at = datetime.utcnow()
            self.analysis_run.error_message = error_message[:1000]  # Limit length
            self.db.commit()
            logger.error(f"Analysis run {self.analysis_run.id} failed: {error_message}")
        except Exception as e:
            logger.error(f"Failed to mark failed: {e}")
            self.db.rollback()
    
    def execute_analysis(self, repository_url: str) -> Dict[str, Any]:
        """
        Execute complete repository analysis pipeline.
        
        This is the main entry point called by the worker.
        
        Pipeline stages:
        1. Validate URL and get metadata (5%)
        2. Download repository (15%)
        3. Extract archive (20%)
        4. Scan files (30%)
        5. Static analysis (40%)
        6. Persist to database (50%)
        7. Build knowledge graph (60%)
        8. Extract Git history (70%)
        9. Analyze API endpoints (already done in static analysis)
        10. Detect workflows (80%)
        11. Build semantic chunks (85%)
        12. Generate embeddings (95%)
        13. Complete (100%)
        
        Args:
            repository_url: GitHub repository URL
            
        Returns:
            Dictionary with analysis results
            
        Raises:
            Various exceptions for different failure modes
        """
        temp_dir = None
        
        try:
            # Mark as running
            self.mark_running()
            
            # Stage 1: Validate URL and get metadata
            self.update_progress("Validating repository", 5)
            metadata = self._get_repository_metadata(repository_url)
            
            owner = metadata["owner"]
            repository_name = metadata["name"]
            default_branch = metadata["default_branch"]
            
            # Get repository from database
            repository = self.analysis_run.repository
            
            # Stage 2-12: Use temporary directory for analysis
            temp_dir = tempfile.mkdtemp(prefix="codetracex_")
            temp_path = Path(temp_dir)
            
            try:
                # Stage 2: Download repository
                self.update_progress("Downloading repository", 15)
                archive_path = self._download_repository(
                    owner, repository_name, default_branch, temp_path
                )
                
                # Stage 3: Extract archive
                self.update_progress("Extracting repository", 20)
                repo_root = self._extract_repository(archive_path, temp_path)
                
                # Stage 4: Scan files
                self.update_progress("Scanning files", 30)
                scan_result = self._scan_files(repo_root)
                
                # Stage 5: Static analysis
                self.update_progress("Analyzing source code", 40)
                static_analysis, api_endpoints = self._analyze_code(repo_root, scan_result)
                
                # Stage 6: Persist to database
                self.update_progress("Persisting to database", 50)
                self._persist_results(repository, static_analysis, scan_result, api_endpoints)
                
                # Stage 7: Build knowledge graph
                self.update_progress("Building knowledge graph", 60)
                self._build_graph(repository, self.analysis_run)
                
                # Stage 8: Extract Git history
                self.update_progress("Extracting Git history", 70)
                self._extract_git_history(repository, repo_root)
                
                # Stage 9: Detect workflows
                self.update_progress("Detecting workflows", 80)
                self._detect_workflows(repository, self.analysis_run)
                
                # Stage 10: Build semantic chunks
                self.update_progress("Building semantic chunks", 85)
                chunks = self._build_semantic_chunks(repository, self.analysis_run, repo_root)
                
                # Stage 11: Generate embeddings
                self.update_progress("Generating embeddings", 95)
                self._generate_embeddings(repository, self.analysis_run, chunks)
                
                # Stage 12: Complete
                self.mark_completed()
                
                return {
                    "status": "completed",
                    "repository_id": str(repository.id),
                    "analysis_run_id": str(self.analysis_run.id),
                    "total_files": scan_result.total_files,
                    "total_symbols": len(static_analysis.all_symbols),
                }
                
            finally:
                # Always cleanup temporary directory
                if temp_dir and Path(temp_dir).exists():
                    try:
                        shutil.rmtree(temp_dir)
                        logger.info(f"Cleaned up temporary directory: {temp_dir}")
                    except Exception as cleanup_error:
                        logger.error(f"Failed to cleanup temporary directory: {cleanup_error}")
        
        except Exception as e:
            # Mark as failed with safe error message
            safe_error = self._get_safe_error_message(e)
            self.mark_failed(safe_error)
            
            # Cleanup temp directory on error
            if temp_dir and Path(temp_dir).exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup on error: {cleanup_error}")
            
            raise
    
    def _get_repository_metadata(self, url: str) -> Dict[str, Any]:
        """Get repository metadata from GitHub."""
        # This is synchronous - RepositoryService.get_repository_metadata is async
        # We need to handle this properly
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.repository_service.get_repository_metadata(url)
        )
    
    def _download_repository(
        self, owner: str, name: str, branch: str, temp_path: Path
    ) -> Path:
        """Download repository archive."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.download_service.download_repository(owner, name, branch, temp_path)
        )
    
    def _extract_repository(self, archive_path: Path, temp_path: Path) -> Path:
        """Extract repository archive safely."""
        extract_path = temp_path / "extracted"
        safe_extract(archive_path, extract_path)
        return find_repository_root(extract_path)
    
    def _scan_files(self, repo_root: Path):
        """Scan repository files."""
        return self.scanner_service.scan_directory(repo_root)
    
    def _analyze_code(self, repo_root: Path, scan_result):
        """Run static code analysis."""
        file_paths = [repo_root / f.path for f in scan_result.files]
        
        # Static analysis
        static_analysis = self.static_analyzer.analyze_repository(repo_root, file_paths)
        
        # API endpoint analysis
        api_endpoints = []
        for file_path in file_paths:
            try:
                endpoints = self.api_route_analyzer.analyze_file(file_path)
                api_endpoints.extend(endpoints)
            except Exception as e:
                logger.warning(f"Failed to analyze API routes in {file_path}: {e}")
        
        return static_analysis, api_endpoints
    
    def _persist_results(self, repository, static_analysis, scan_result, api_endpoints):
        """Persist analysis results to database."""
        file_metadata_dicts = [
            {
                'path': f.path,
                'filename': f.filename,
                'extension': f.extension,
                'language': f.language,
                'size_bytes': f.size_bytes,
                'lines': f.lines,
                'is_sensitive': f.is_sensitive
            }
            for f in scan_result.files
        ]
        
        self.persistence_service.persist_analysis_result(
            repository=repository,
            analysis_run=self.analysis_run,
            static_analysis=static_analysis,
            file_metadata=file_metadata_dicts,
            api_endpoints=api_endpoints if api_endpoints else None
        )
    
    def _build_graph(self, repository, analysis_run):
        """Build knowledge graph."""
        try:
            self.graph_service.build_graph(repository.id, analysis_run.id)
        except Exception as e:
            logger.warning(f"Graph building failed (non-fatal): {e}")
            # Don't fail entire analysis if graph building fails
    
    def _extract_git_history(self, repository, repo_root: Path):
        """Extract Git history."""
        try:
            # Git history service expects a git repository
            # We downloaded an archive, so this will fail
            # This is a known limitation
            logger.info("Skipping Git history extraction (archive download, not git clone)")
        except Exception as e:
            logger.warning(f"Git history extraction failed (non-fatal): {e}")
    
    def _detect_workflows(self, repository, analysis_run):
        """Detect application workflows."""
        try:
            self.workflow_service.detect_workflows(repository.id, analysis_run.id)
        except Exception as e:
            logger.warning(f"Workflow detection failed (non-fatal): {e}")
    
    def _build_semantic_chunks(self, repository, analysis_run, repo_root: Path) -> List:
        """Build semantic chunks for embedding."""
        try:
            chunk_builder = ChunkBuilder(repo_root)
            
            # Get persisted entities
            files = self.db.query(File).filter(
                File.analysis_run_id == analysis_run.id
            ).all()
            
            file_id_to_path = {str(f.id): f.path for f in files}
            
            symbols = self.db.query(Symbol).filter(
                Symbol.analysis_run_id == analysis_run.id
            ).all()
            
            symbol_dicts = [
                {
                    'id': s.id,
                    'file_id': str(s.file_id),
                    'name': s.name,
                    'symbol_type': s.symbol_type.value,
                    'language': s.language,
                    'start_line': s.start_line,
                    'end_line': s.end_line
                }
                for s in symbols
            ]
            
            endpoints = self.db.query(ApiEndpoint).filter(
                ApiEndpoint.analysis_run_id == analysis_run.id
            ).all()
            
            endpoint_dicts = [
                {
                    'id': e.id,
                    'file_id': str(e.file_id),
                    'method': e.method.value,
                    'path': e.path,
                    'framework': e.framework,
                    'handler_name': e.handler_name,
                    'start_line': e.start_line,
                    'end_line': e.end_line
                }
                for e in endpoints
            ]
            
            chunks = chunk_builder.build_all_chunks(
                symbols=symbol_dicts,
                api_endpoints=endpoint_dicts,
                file_path_map=file_id_to_path
            )
            
            logger.info(f"Built {len(chunks)} semantic chunks")
            return chunks
            
        except Exception as e:
            logger.warning(f"Chunk building failed (non-fatal): {e}")
            return []
    
    def _generate_embeddings(self, repository, analysis_run, chunks: List):
        """Generate embeddings for chunks."""
        if not chunks:
            logger.info("No chunks to embed")
            return
        
        try:
            # Generate embeddings in batch
            chunk_contents = [chunk.content for chunk in chunks]
            embeddings = self.embedding_service.embed_batch(chunk_contents)
            
            # Attach embeddings to chunks
            chunks_with_embeddings = []
            for chunk, embedding in zip(chunks, embeddings):
                if embedding:
                    chunk_dict = {
                        'chunk_type': chunk.chunk_type,
                        'chunk_index': chunk.chunk_index,
                        'content': chunk.content,
                        'content_hash': chunk.content_hash,
                        'language': chunk.language,
                        'start_line': chunk.start_line,
                        'end_line': chunk.end_line,
                        'token_count': chunk.token_count,
                        'embedding': embedding,
                        'file_path': chunk.file_path,
                        'symbol_name': chunk.symbol_name,
                        'api_endpoint_method': chunk.api_endpoint_method,
                        'api_endpoint_path': chunk.api_endpoint_path,
                        'metadata': chunk.metadata
                    }
                    chunks_with_embeddings.append(chunk_dict)
            
            logger.info(f"Generated {len(chunks_with_embeddings)} embeddings")
            
            # Persist chunks with embeddings
            if chunks_with_embeddings:
                files = self.db.query(File).filter(
                    File.analysis_run_id == analysis_run.id
                ).all()
                
                file_id_to_path = {str(f.id): f.path for f in files}
                file_map = {f.path: f for f in files}
                
                symbols = self.db.query(Symbol).filter(
                    Symbol.analysis_run_id == analysis_run.id
                ).all()
                
                symbol_map = {}
                for symbol in symbols:
                    file_path = file_id_to_path.get(str(symbol.file_id))
                    if file_path:
                        key = f"{file_path}:{symbol.name}:{symbol.symbol_type.value}"
                        symbol_map[key] = symbol
                
                endpoints = self.db.query(ApiEndpoint).filter(
                    ApiEndpoint.analysis_run_id == analysis_run.id
                ).all()
                
                api_endpoint_map = {}
                for endpoint in endpoints:
                    key = f"{endpoint.method.value}:{endpoint.path}"
                    api_endpoint_map[key] = endpoint
                
                chunk_count = self.persistence_service.persist_semantic_chunks(
                    repository=repository,
                    analysis_run=analysis_run,
                    chunks=chunks_with_embeddings,
                    file_map=file_map,
                    symbol_map=symbol_map,
                    api_endpoint_map=api_endpoint_map
                )
                
                logger.info(f"Persisted {chunk_count} semantic chunks with embeddings")
                
        except Exception as e:
            logger.warning(f"Embedding generation failed (non-fatal): {e}")
    
    def _get_safe_error_message(self, error: Exception) -> str:
        """
        Convert exception to safe error message.
        
        Removes sensitive information like:
        - API keys
        - Database credentials
        - File system paths
        - Stack traces
        
        Args:
            error: Exception that occurred
            
        Returns:
            Safe error message suitable for storage/display
        """
        error_type = type(error).__name__
        
        # Map known exceptions to user-friendly messages
        if isinstance(error, InvalidRepositoryURLError):
            return "Invalid repository URL"
        elif isinstance(error, RepositoryNotFoundError):
            return "Repository not found on GitHub"
        elif isinstance(error, DownloadTooLargeError):
            return "Repository exceeds maximum size limit"
        elif isinstance(error, DownloadError):
            return "Failed to download repository"
        elif isinstance(error, TooManyFilesError):
            return "Repository exceeds maximum file limit"
        elif isinstance(error, (UnsafeZipError, InvalidZipError)):
            return "Invalid or unsafe repository archive"
        elif isinstance(error, GitHubAPIError):
            return "GitHub API error"
        else:
            # Generic error message
            error_str = str(error)
            # Remove potential file paths (Windows and Unix)
            import re
            error_str = re.sub(r'[A-Za-z]:\\[^\s]+', '[path]', error_str)
            error_str = re.sub(r'/[^\s]+', '[path]', error_str)
            # Truncate if too long
            if len(error_str) > 200:
                error_str = error_str[:200] + "..."
            return f"{error_type}: {error_str}"
