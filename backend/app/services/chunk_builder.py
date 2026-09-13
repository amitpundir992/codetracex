"""
Chunk builder service for creating semantic chunks.

Phase 9: Embeddings + pgvector

This service builds deterministic semantic chunks from repository intelligence:
- Symbol chunks (functions, classes, methods)
- API endpoint chunks
- Documentation chunks (future)

Architecture:
    Repository source code (temporary)
        ↓
    ChunkBuilder
        ↓
    Semantic chunks with content
    
Content Extraction:
    During repository analysis (while source is available):
    1. Read source files
    2. Extract symbol content based on line ranges
    3. Build chunks with metadata
    4. Generate content hashes
    
Chunking Strategy:
    - One chunk per symbol (function/class/method)
    - Large symbols (>2000 chars): Split by newlines but preserve identity
    - API endpoints: Handler symbol content
    - Content hash for deduplication
    
Security:
    - Only reads files, never executes code
    - Safe file path handling
    - UTF-8 decoding with error handling
"""
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChunkData:
    """
    Data structure for a semantic chunk before persistence.
    
    This is the intermediate representation between source extraction
    and database persistence.
    """
    chunk_type: str  # "symbol", "api_endpoint", "documentation", "file"
    chunk_index: int
    content: str
    content_hash: str
    language: Optional[str]
    start_line: int
    end_line: int
    token_count: int
    
    # Linkage to source entities
    file_path: str  # Relative path from repository root
    symbol_name: Optional[str] = None
    api_endpoint_method: Optional[str] = None
    api_endpoint_path: Optional[str] = None
    
    # Optional metadata
    metadata: Optional[Dict[str, Any]] = None


class ChunkBuilder:
    """
    Service for building semantic chunks from repository intelligence.
    
    This service operates during repository analysis (Phase 2-3)
    while source files are temporarily available.
    
    Usage:
        builder = ChunkBuilder(repo_root)
        chunks = builder.build_symbol_chunks(symbols, file_metadata_map)
    """
    
    # Maximum chunk size before splitting
    MAX_CHUNK_SIZE = 2000
    
    def __init__(self, repo_root: Path):
        """
        Initialize chunk builder with repository root.
        
        Args:
            repo_root: Path to repository root directory
        """
        self.repo_root = Path(repo_root)
        self._file_cache: Dict[str, List[str]] = {}
        logger.info(f"ChunkBuilder initialized for: {repo_root}")
    
    def _read_file_lines(self, file_path: str) -> Optional[List[str]]:
        """
        Read file and cache lines for reuse.
        
        Args:
            file_path: Relative path from repository root
            
        Returns:
            List of file lines, or None if read fails
        """
        if file_path in self._file_cache:
            return self._file_cache[file_path]
        
        try:
            full_path = self.repo_root / file_path
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                self._file_cache[file_path] = lines
                return lines
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return None
    
    def _extract_content(self, file_path: str, start_line: int, end_line: int) -> Optional[str]:
        """
        Extract content from file between line ranges.
        
        Args:
            file_path: Relative path from repository root
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed, inclusive)
            
        Returns:
            Extracted content, or None if extraction fails
        """
        lines = self._read_file_lines(file_path)
        if not lines:
            return None
        
        try:
            # Convert to 0-indexed
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            
            content_lines = lines[start_idx:end_idx]
            content = ''.join(content_lines).strip()
            
            return content if content else None
        except Exception as e:
            logger.warning(f"Failed to extract content from {file_path}:{start_line}-{end_line}: {e}")
            return None
    
    def _compute_content_hash(self, content: str) -> str:
        """
        Compute SHA-256 hash of content for deduplication.
        
        Args:
            content: Text content
            
        Returns:
            Hex digest of SHA-256 hash
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _estimate_token_count(self, content: str) -> int:
        """
        Estimate token count for monitoring.
        
        Simple heuristic: ~4 characters per token.
        
        Args:
            content: Text content
            
        Returns:
            Estimated token count
        """
        return len(content) // 4
    
    def _split_large_content(self, content: str, max_size: int = MAX_CHUNK_SIZE) -> List[str]:
        """
        Split large content into smaller chunks.
        
        Splits by newlines to preserve code structure.
        
        Args:
            content: Text content
            max_size: Maximum chunk size in characters
            
        Returns:
            List of content chunks
        """
        if len(content) <= max_size:
            return [content]
        
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            if current_size + line_size > max_size and current_chunk:
                # Save current chunk
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add remaining chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def build_symbol_chunks(
        self,
        symbols: List[Dict[str, Any]],
        file_path_map: Dict[str, str]
    ) -> List[ChunkData]:
        """
        Build semantic chunks from symbols.
        
        Args:
            symbols: List of symbol dictionaries from static analysis
            file_path_map: Map of file_id to relative file path
            
        Returns:
            List of ChunkData objects
        """
        chunks = []
        
        for symbol in symbols:
            try:
                file_id = symbol.get('file_id')
                if not file_id or file_id not in file_path_map:
                    logger.debug(f"Skipping symbol without file: {symbol.get('name')}")
                    continue
                
                file_path = file_path_map[file_id]
                start_line = symbol.get('start_line')
                end_line = symbol.get('end_line')
                
                if start_line is None or end_line is None:
                    logger.debug(f"Skipping symbol without line info: {symbol.get('name')}")
                    continue
                
                # Extract content from source file
                content = self._extract_content(file_path, start_line, end_line)
                if not content:
                    logger.debug(f"Failed to extract content for symbol: {symbol.get('name')}")
                    continue
                
                # Split if too large
                content_chunks = self._split_large_content(content)
                
                for idx, chunk_content in enumerate(content_chunks):
                    chunk = ChunkData(
                        chunk_type="symbol",
                        chunk_index=idx,
                        content=chunk_content,
                        content_hash=self._compute_content_hash(chunk_content),
                        language=symbol.get('language'),
                        start_line=start_line,
                        end_line=end_line,
                        token_count=self._estimate_token_count(chunk_content),
                        file_path=file_path,
                        symbol_name=symbol.get('name'),
                        metadata={
                            'symbol_type': symbol.get('symbol_type'),
                            'symbol_id': str(symbol.get('id')) if symbol.get('id') else None,
                        }
                    )
                    chunks.append(chunk)
                
            except Exception as e:
                logger.warning(f"Failed to build chunk for symbol {symbol.get('name')}: {e}")
                continue
        
        logger.info(f"Built {len(chunks)} symbol chunks from {len(symbols)} symbols")
        return chunks
    
    def build_api_endpoint_chunks(
        self,
        api_endpoints: List[Dict[str, Any]],
        file_path_map: Dict[str, str]
    ) -> List[ChunkData]:
        """
        Build semantic chunks from API endpoints.
        
        Args:
            api_endpoints: List of API endpoint dictionaries
            file_path_map: Map of file_id to relative file path
            
        Returns:
            List of ChunkData objects
        """
        chunks = []
        
        for endpoint in api_endpoints:
            try:
                file_id = endpoint.get('file_id')
                if not file_id or file_id not in file_path_map:
                    logger.debug(f"Skipping endpoint without file: {endpoint.get('path')}")
                    continue
                
                file_path = file_path_map[file_id]
                start_line = endpoint.get('start_line')
                end_line = endpoint.get('end_line')
                
                if start_line is None or end_line is None:
                    logger.debug(f"Skipping endpoint without line info: {endpoint.get('path')}")
                    continue
                
                # Extract content from source file
                content = self._extract_content(file_path, start_line, end_line)
                if not content:
                    logger.debug(f"Failed to extract content for endpoint: {endpoint.get('path')}")
                    continue
                
                chunk = ChunkData(
                    chunk_type="api_endpoint",
                    chunk_index=0,
                    content=content,
                    content_hash=self._compute_content_hash(content),
                    language=None,  # Framework-specific, not a programming language
                    start_line=start_line,
                    end_line=end_line,
                    token_count=self._estimate_token_count(content),
                    file_path=file_path,
                    api_endpoint_method=endpoint.get('method'),
                    api_endpoint_path=endpoint.get('path'),
                    metadata={
                        'framework': endpoint.get('framework'),
                        'handler_name': endpoint.get('handler_name'),
                        'endpoint_id': str(endpoint.get('id')) if endpoint.get('id') else None,
                    }
                )
                chunks.append(chunk)
                
            except Exception as e:
                logger.warning(f"Failed to build chunk for endpoint {endpoint.get('path')}: {e}")
                continue
        
        logger.info(f"Built {len(chunks)} API endpoint chunks from {len(api_endpoints)} endpoints")
        return chunks
    
    def build_all_chunks(
        self,
        symbols: List[Dict[str, Any]],
        api_endpoints: List[Dict[str, Any]],
        file_path_map: Dict[str, str]
    ) -> List[ChunkData]:
        """
        Build all semantic chunks from repository intelligence.
        
        Args:
            symbols: List of symbol dictionaries
            api_endpoints: List of API endpoint dictionaries
            file_path_map: Map of file_id to relative file path
            
        Returns:
            Combined list of all chunks
        """
        all_chunks = []
        
        # Build symbol chunks
        symbol_chunks = self.build_symbol_chunks(symbols, file_path_map)
        all_chunks.extend(symbol_chunks)
        
        # Build API endpoint chunks
        if api_endpoints:
            endpoint_chunks = self.build_api_endpoint_chunks(api_endpoints, file_path_map)
            all_chunks.extend(endpoint_chunks)
        
        logger.info(f"Built {len(all_chunks)} total semantic chunks")
        return all_chunks
