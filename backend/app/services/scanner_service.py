"""
Repository file scanner service.

This service recursively scans repository directories, identifies relevant
source files, collects metadata, and respects ignore rules and file limits.
"""
import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from app.utils.scanner_config import (
    IGNORED_DIRECTORIES,
    is_binary_file,
    is_sensitive_file,
    get_file_extension,
    detect_language
)


class TooManyFilesError(Exception):
    """Exception raised when a repository exceeds the maximum file limit."""
    pass


@dataclass
class FileMetadata:
    """Metadata about a single file in the repository."""
    path: str  # Relative path from repository root
    filename: str
    extension: str
    size_bytes: int
    language: Optional[str]
    lines: Optional[int]
    is_sensitive: bool


@dataclass
class ScanResult:
    """Result of scanning a repository."""
    total_files: int
    total_size_bytes: int
    files: List[FileMetadata]
    languages: Dict[str, int]  # Language name -> file count


class FileScannerService:
    """Service for scanning repository files and collecting metadata."""
    
    def __init__(self, max_files: int):
        """
        Initialize the file scanner service.
        
        Args:
            max_files: Maximum number of files to scan before aborting
        """
        self.max_files = max_files
    
    def should_ignore_directory(self, dir_name: str) -> bool:
        """
        Check if a directory should be ignored during scanning.
        
        Args:
            dir_name: Name of the directory
            
        Returns:
            True if the directory should be ignored, False otherwise
        """
        return dir_name in IGNORED_DIRECTORIES
    
    def should_scan_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be scanned.
        
        Files are excluded if they are:
        - Binary files (images, executables, etc.)
        - In ignored directories
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file should be scanned, False otherwise
        """
        # Check if it's a binary file
        if is_binary_file(file_path.name):
            return False
        
        return True
    
    def count_lines(self, file_path: Path) -> Optional[int]:
        """
        Count the number of lines in a text file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Number of lines, or None if the file cannot be read
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except Exception:
            # If we can't read the file (encoding issues, permissions, etc.),
            # return None rather than failing the entire scan
            return None
    
    def collect_file_metadata(self, file_path: Path, repo_root: Path) -> FileMetadata:
        """
        Collect metadata about a single file.
        
        Args:
            file_path: Absolute path to the file
            repo_root: Absolute path to the repository root
            
        Returns:
            FileMetadata object containing file information
        """
        # Calculate relative path from repository root
        relative_path = file_path.relative_to(repo_root)
        
        # Get file stats
        stat = file_path.stat()
        size_bytes = stat.st_size
        
        # Extract file information
        filename = file_path.name
        extension = get_file_extension(filename)
        language = detect_language(filename)
        
        # Check if file might contain sensitive data
        sensitive = is_sensitive_file(filename)
        
        # Count lines for text files
        lines = self.count_lines(file_path)
        
        return FileMetadata(
            path=str(relative_path).replace('\\', '/'),  # Normalize path separators
            filename=filename,
            extension=extension,
            size_bytes=size_bytes,
            language=language,
            lines=lines,
            is_sensitive=sensitive
        )
    
    def scan_directory(self, repo_root: Path) -> ScanResult:
        """
        Recursively scan a repository directory and collect file metadata.
        
        This method:
        1. Walks through the directory tree
        2. Skips ignored directories (node_modules, .git, etc.)
        3. Identifies source files vs binary files
        4. Collects metadata for each relevant file
        5. Tracks language statistics
        6. Enforces file count limits
        
        Args:
            repo_root: Path to the repository root directory
            
        Returns:
            ScanResult containing metadata about all scanned files
            
        Raises:
            TooManyFilesError: If the repository contains more than max_files
        """
        files: List[FileMetadata] = []
        total_size_bytes = 0
        language_counts: Dict[str, int] = {}
        
        # Walk through the repository directory
        for root, dirs, filenames in os.walk(repo_root):
            # Remove ignored directories from the walk
            # Modifying dirs in-place affects which directories os.walk visits
            dirs[:] = [d for d in dirs if not self.should_ignore_directory(d)]
            
            # Process each file in the current directory
            for filename in filenames:
                file_path = Path(root) / filename
                
                # Check file count limit
                if len(files) >= self.max_files:
                    raise TooManyFilesError(
                        f"Repository contains more than {self.max_files} files. "
                        "Scanning aborted to prevent resource exhaustion."
                    )
                
                # Check if we should scan this file
                if not self.should_scan_file(file_path):
                    continue
                
                # Collect file metadata
                try:
                    metadata = self.collect_file_metadata(file_path, repo_root)
                    files.append(metadata)
                    
                    # Update statistics
                    total_size_bytes += metadata.size_bytes
                    
                    if metadata.language:
                        language_counts[metadata.language] = \
                            language_counts.get(metadata.language, 0) + 1
                    
                except Exception:
                    # If we fail to process a single file, continue with the rest
                    # This prevents one problematic file from failing the entire scan
                    continue
        
        return ScanResult(
            total_files=len(files),
            total_size_bytes=total_size_bytes,
            files=files,
            languages=language_counts
        )
    
    def get_top_files(self, scan_result: ScanResult, limit: int = 100) -> List[FileMetadata]:
        """
        Get a limited number of files from the scan result.
        
        This is useful for API responses where returning thousands of files
        would be impractical.
        
        Args:
            scan_result: The complete scan result
            limit: Maximum number of files to return
            
        Returns:
            List of up to 'limit' files, prioritizing source code files
        """
        # Prioritize files with known languages
        files_with_language = [f for f in scan_result.files if f.language]
        files_without_language = [f for f in scan_result.files if not f.language]
        
        # Return language files first, up to the limit
        result = files_with_language[:limit]
        
        # Fill remaining space with other files if needed
        if len(result) < limit:
            remaining = limit - len(result)
            result.extend(files_without_language[:remaining])
        
        return result
