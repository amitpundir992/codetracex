"""
File hash utilities for content fingerprinting.

Phase 24: Repository Intelligence Quality & Analysis Reliability

This module provides utilities for computing file content hashes
to enable change detection and incremental analysis.
"""
import hashlib
from pathlib import Path
from typing import Optional


def compute_file_hash(file_path: Path, chunk_size: int = 8192) -> Optional[str]:
    """
    Compute SHA-256 hash of file content.
    
    Uses streaming to handle large files efficiently.
    
    Args:
        file_path: Path to file
        chunk_size: Size of chunks to read (default: 8KB)
        
    Returns:
        SHA-256 hex digest, or None if file cannot be read
    """
    try:
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
        
        return sha256.hexdigest()
        
    except Exception:
        # If file cannot be read (permissions, encoding, etc.), return None
        return None


def compute_content_hash(content: str) -> str:
    """
    Compute SHA-256 hash of string content.
    
    Args:
        content: String content to hash
        
    Returns:
        SHA-256 hex digest
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
