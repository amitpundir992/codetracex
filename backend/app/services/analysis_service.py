"""
Repository analysis service.

This service orchestrates the complete repository analysis workflow:
1. Validate repository URL
2. Get repository metadata
3. Download repository archive
4. Extract archive safely
5. Scan files and collect metadata
6. Run static code analysis (Phase 3)
7. Persist results to PostgreSQL (Phase 4)
8. Clean up temporary files

Phase 4 Enhancement:
    After static analysis completes, results are persisted to PostgreSQL:
    - Repository metadata saved
    - Analysis run created
    - Files, symbols, imports, calls persisted
    - Relationships created
    
    The analysis workflow now follows:
    
    GitHub → Download → Scan → Analyze → PostgreSQL → Cleanup

This is the main entry point for Phase 2, Phase 3, and Phase 4 functionality.
"""
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.repository_service import RepositoryService
from app.services.download_service import RepositoryDownloadService
from app.services.scanner_service import FileScannerService
from app.services.static_analyzer import StaticAnalyzer
from app.services.persistence_service import PersistenceService
from app.services.api_route_analyzer import ApiRouteAnalyzer
from app.utils.zip_utils import safe_extract, find_repository_root

logger = logging.getLogger(__name__)


class RepositoryAnalysisService:
    """Service for analyzing GitHub repositories."""
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the analysis service with required dependencies.
        
        Args:
            db: Optional database session for persistence (Phase 4)
        """
        settings = get_settings()
        
        self.repository_service = RepositoryService()
        self.download_service = RepositoryDownloadService(
            max_size_bytes=settings.max_repository_size_bytes
        )
        self.scanner_service = FileScannerService(
            max_files=settings.MAX_REPOSITORY_FILES
        )
        self.static_analyzer = StaticAnalyzer()
        self.api_route_analyzer = ApiRouteAnalyzer()  # Phase 7
        
        # Phase 4: Database persistence
        self.db = db
        self.persistence_service = PersistenceService(db) if db else None
    
    async def analyze_repository(
        self,
        url: str,
        persist: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze a GitHub repository from start to finish.
        
        This method orchestrates the complete workflow:
        1. Parse and validate the GitHub URL
        2. Retrieve repository metadata from GitHub API
        3. Create a temporary workspace
        4. Download the repository archive
        5. Extract the archive safely
        6. Find the repository root
        7. Scan all files and collect metadata (Phase 2)
        8. Run static code analysis on source files (Phase 3)
        9. Persist results to PostgreSQL (Phase 4, if enabled)
        10. Clean up temporary files (even if errors occur)
        11. Return structured analysis results
        
        The temporary workspace is automatically cleaned up using a context manager,
        ensuring cleanup happens even if an exception occurs during processing.
        
        Phase 4 Persistence:
            If persist=True and database session is available:
            - Repository is created or retrieved
            - AnalysisRun is created with status=running
            - Results are persisted in a transaction
            - Status is updated to completed or failed
        
        Args:
            url: GitHub repository URL
            persist: Whether to persist results to database (default: True)
            
        Returns:
            Dictionary containing:
                - repository: Repository identifier (owner/name)
                - metadata: Repository metadata from GitHub
                - scan_result: File scanning results with metadata
                - static_analysis: Static code analysis results (Phase 3)
                - analysis_run_id: UUID of persisted analysis run (if persisted)
                - repository_id: UUID of repository record (if persisted)
                
        Raises:
            InvalidRepositoryURLError: If URL is invalid
            RepositoryNotFoundError: If repository doesn't exist
            DownloadTooLargeError: If repository exceeds size limit
            DownloadError: If download fails
            UnsafeZipError: If archive contains unsafe paths
            InvalidZipError: If archive is corrupted
            TooManyFilesError: If repository exceeds file limit
        """
        # Step 1 & 2: Validate URL and get repository metadata
        metadata = await self.repository_service.get_repository_metadata(url)
        
        owner = metadata["owner"]
        repository_name = metadata["name"]
        default_branch = metadata["default_branch"]
        repository_id = f"{owner}/{repository_name}"
        
        # Phase 4: Create repository and analysis run if persistence enabled
        db_repository = None
        db_analysis_run = None
        
        if persist and self.persistence_service:
            try:
                db_repository = self.persistence_service.create_or_get_repository(
                    owner=owner,
                    name=repository_name,
                    github_url=metadata["url"],
                    default_branch=default_branch,
                    description=metadata.get("description"),
                    language=metadata.get("language"),
                    stars=metadata.get("stars")
                )
                
                db_analysis_run = self.persistence_service.create_analysis_run(db_repository)
                
                logger.info(f"Created analysis run: {db_analysis_run.id} for repository: {repository_id}")
                
            except Exception as e:
                logger.error(f"Failed to create analysis run: {str(e)}")
                # Continue with analysis even if persistence setup fails
                persist = False
        
        # Step 3-9: Use temporary directory for download and extraction
        # The 'with' statement ensures cleanup happens automatically
        try:
            with tempfile.TemporaryDirectory(prefix="codetracex_") as temp_dir:
                temp_path = Path(temp_dir)
                
                # Step 4: Download repository archive
                archive_path = await self.download_service.download_repository(
                    owner=owner,
                    repository=repository_name,
                    branch=default_branch,
                    destination=temp_path
                )
                
                # Step 5: Extract archive safely
                extract_path = temp_path / "extracted"
                safe_extract(archive_path, extract_path)
                
                # Step 6: Find repository root
                repo_root = find_repository_root(extract_path)
                
                # Step 7: Scan files
                scan_result = self.scanner_service.scan_directory(repo_root)
                
                # Step 8: Run static code analysis on scanned files
                # Convert FileMetadata objects to Path objects for analysis
                file_paths = [
                    repo_root / file_meta.path 
                    for file_meta in scan_result.files
                ]
                
                static_analysis_result = self.static_analyzer.analyze_repository(
                    repo_root=repo_root,
                    files=file_paths
                )
                
                # Update summary with import and call counts
                static_analysis_result.summary.total_imports = len(static_analysis_result.all_imports)
                static_analysis_result.summary.total_calls = len(static_analysis_result.all_calls)
                
                # Phase 7: Extract API endpoints
                api_endpoints = []
                for file_path in file_paths:
                    try:
                        endpoints = self.api_route_analyzer.analyze_file(file_path)
                        api_endpoints.extend(endpoints)
                    except Exception as e:
                        logger.warning(f"Failed to analyze API routes in {file_path}: {e}")
                
                logger.info(f"Detected {len(api_endpoints)} API endpoints")
                
                # Step 9: Persist results to PostgreSQL (Phase 4)
                if persist and self.persistence_service and db_repository and db_analysis_run:
                    try:
                        # Convert FileMetadata objects to dictionaries for persistence
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
                            repository=db_repository,
                            analysis_run=db_analysis_run,
                            static_analysis=static_analysis_result,
                            file_metadata=file_metadata_dicts,
                            api_endpoints=api_endpoints if api_endpoints else None  # Phase 7
                        )
                        
                        logger.info(f"Successfully persisted analysis run: {db_analysis_run.id}")
                        
                        # Phase 9: Generate embeddings and persist semantic chunks
                        try:
                            await self._generate_and_persist_embeddings(
                                repository=db_repository,
                                analysis_run=db_analysis_run,
                                repo_root=repo_root,
                                static_analysis=static_analysis_result,
                                api_endpoints=api_endpoints
                            )
                        except Exception as embed_error:
                            logger.error(f"Failed to generate embeddings: {str(embed_error)}")
                            # Don't fail entire analysis if embeddings fail
                            # This is a best-effort enhancement
                        
                    except Exception as e:
                        logger.error(f"Failed to persist analysis results: {str(e)}")
                        
                        # Mark analysis as failed
                        if db_analysis_run:
                            self.persistence_service.mark_analysis_failed(
                                db_analysis_run,
                                f"Persistence failed: {str(e)}"
                            )
                        
                        # Re-raise the exception
                        raise
            
            # Temporary directory is automatically deleted here
            
            # Step 11: Return structured results
            result = {
                "repository": repository_id,
                "metadata": metadata,
                "scan_result": scan_result,
                "static_analysis": static_analysis_result
            }
            
            # Add persistence information if available
            if db_repository:
                result["repository_id"] = str(db_repository.id)
            if db_analysis_run:
                result["analysis_run_id"] = str(db_analysis_run.id)
            
            return result
            
        except Exception as e:
            # Mark analysis as failed if persistence was enabled
            if persist and self.persistence_service and db_analysis_run:
                try:
                    self.persistence_service.mark_analysis_failed(
                        db_analysis_run,
                        str(e)
                    )
                except Exception as persist_error:
                    logger.error(f"Failed to mark analysis as failed: {str(persist_error)}")
            
            # Re-raise the original exception
            raise


    
    async def _generate_and_persist_embeddings(
        self,
        repository: 'Repository',
        analysis_run: 'AnalysisRun',
        repo_root: Path,
        static_analysis: 'StaticAnalysisResult',
        api_endpoints: Optional[List] = None
    ) -> None:
        """
        Generate embeddings and persist semantic chunks.
        
        Phase 9: Embeddings + pgvector
        
        This method:
        1. Builds semantic chunks from symbols and API endpoints
        2. Generates embeddings for chunk content
        3. Persists chunks with embeddings to database
        
        Args:
            repository: Repository model instance
            analysis_run: AnalysisRun model instance
            repo_root: Path to repository root (source files available)
            static_analysis: Static analysis result
            api_endpoints: Optional list of API endpoints
        """
        from app.services.chunk_builder import ChunkBuilder
        from app.services.embedding_service import EmbeddingService
        
        logger.info("Starting embedding generation...")
        
        try:
            # Initialize services
            chunk_builder = ChunkBuilder(repo_root)
            embedding_service = EmbeddingService()
            
            # Build file_path_map and extract persisted entities
            # We need to query the database for the persisted entities
            from app.db.models import File, Symbol, ApiEndpoint
            
            # Get persisted files for this analysis run
            files = self.db.query(File).filter(
                File.analysis_run_id == analysis_run.id
            ).all()
            
            file_id_to_path = {str(f.id): f.path for f in files}
            file_path_to_id = {f.path: str(f.id) for f in files}
            
            # Get persisted symbols
            symbols = self.db.query(Symbol).filter(
                Symbol.analysis_run_id == analysis_run.id
            ).all()
            
            # Convert symbols to dict format for chunk builder
            symbol_dicts = [
                {
                    'id': symbol.id,
                    'file_id': str(symbol.file_id),
                    'name': symbol.name,
                    'symbol_type': symbol.symbol_type.value,
                    'language': symbol.language,
                    'start_line': symbol.start_line,
                    'end_line': symbol.end_line
                }
                for symbol in symbols
            ]
            
            # Get persisted API endpoints
            endpoints = self.db.query(ApiEndpoint).filter(
                ApiEndpoint.analysis_run_id == analysis_run.id
            ).all()
            
            endpoint_dicts = [
                {
                    'id': endpoint.id,
                    'file_id': str(endpoint.file_id),
                    'method': endpoint.method.value,
                    'path': endpoint.path,
                    'framework': endpoint.framework,
                    'handler_name': endpoint.handler_name,
                    'start_line': endpoint.start_line,
                    'end_line': endpoint.end_line
                }
                for endpoint in endpoints
            ]
            
            # Build semantic chunks
            chunks = chunk_builder.build_all_chunks(
                symbols=symbol_dicts,
                api_endpoints=endpoint_dicts,
                file_path_map=file_id_to_path
            )
            
            if not chunks:
                logger.warning("No chunks generated for embedding")
                return
            
            logger.info(f"Built {len(chunks)} semantic chunks")
            
            # Generate embeddings in batch
            chunk_contents = [chunk.content for chunk in chunks]
            embeddings = embedding_service.embed_batch(chunk_contents)
            
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
                # Build file_map for persistence
                file_map = {f.path: f for f in files}
                
                # Build symbol_map (key: file_path:symbol_name:symbol_type)
                symbol_map = {}
                for symbol in symbols:
                    file_path = file_id_to_path.get(str(symbol.file_id))
                    if file_path:
                        key = f"{file_path}:{symbol.name}:{symbol.symbol_type.value}"
                        symbol_map[key] = symbol
                
                # Build api_endpoint_map (key: method:path)
                api_endpoint_map = {}
                for endpoint in endpoints:
                    key = f"{endpoint.method.value}:{endpoint.path}"
                    api_endpoint_map[key] = endpoint
                
                # Persist chunks
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
            logger.error(f"Embedding generation failed: {str(e)}", exc_info=True)
            # Don't raise - this is a best-effort enhancement
            # We don't want to fail the entire analysis if embeddings fail
