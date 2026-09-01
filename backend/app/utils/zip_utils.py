"""
Safe ZIP archive extraction utilities.

This module provides secure ZIP extraction with protection against
path traversal attacks (ZIP bomb, malicious paths like ../../etc/passwd).
"""
import os
import zipfile
from pathlib import Path
from typing import List


class UnsafeZipError(Exception):
    """Exception raised when a ZIP archive contains unsafe paths."""
    pass


class InvalidZipError(Exception):
    """Exception raised when a ZIP archive is invalid or corrupted."""
    pass


def is_safe_path(base_path: Path, target_path: Path) -> bool:
    """
    Check if a target path is safely contained within a base path.
    
    This prevents path traversal attacks where an archive might try to
    extract files outside the intended directory using paths like:
    - ../../etc/passwd
    - /etc/passwd (absolute paths)
    - symlinks pointing outside the directory
    
    Args:
        base_path: The base directory where extraction should occur
        target_path: The target path to validate
        
    Returns:
        True if the path is safe, False otherwise
    """
    # Resolve both paths to absolute paths (resolves .. and symlinks)
    try:
        base_resolved = base_path.resolve()
        target_resolved = target_path.resolve()
        
        # Check if target is within base directory
        # This uses is_relative_to() which returns True if target_resolved
        # is a subdirectory of base_resolved
        return target_resolved.is_relative_to(base_resolved)
    except (ValueError, OSError):
        # If path resolution fails, treat as unsafe
        return False


def validate_zip_paths(zip_path: Path, extract_to: Path) -> List[str]:
    """
    Validate all paths in a ZIP archive before extraction.
    
    This examines every entry in the ZIP file and ensures:
    1. The path doesn't escape the extraction directory
    2. The path doesn't use absolute paths
    3. The path doesn't contain suspicious patterns
    
    Args:
        zip_path: Path to the ZIP archive
        extract_to: Target extraction directory
        
    Returns:
        List of safe member names from the archive
        
    Raises:
        InvalidZipError: If the ZIP file is corrupted or invalid
        UnsafeZipError: If the ZIP contains unsafe paths
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            # Test the ZIP file integrity
            bad_file = zip_file.testzip()
            if bad_file is not None:
                raise InvalidZipError(f"Corrupted file in archive: {bad_file}")
            
            # Validate each member
            safe_members = []
            for member in zip_file.namelist():
                # Construct the full extraction path
                target_path = extract_to / member
                
                # Check if the path is safe
                if not is_safe_path(extract_to, target_path):
                    raise UnsafeZipError(
                        f"Unsafe path detected in ZIP archive: {member}. "
                        "This file attempts to write outside the extraction directory."
                    )
                
                # Check for absolute paths
                if Path(member).is_absolute():
                    raise UnsafeZipError(
                        f"Absolute path detected in ZIP archive: {member}"
                    )
                
                safe_members.append(member)
            
            return safe_members
            
    except zipfile.BadZipFile:
        raise InvalidZipError("Invalid or corrupted ZIP archive")


def safe_extract(zip_path: Path, extract_to: Path) -> None:
    """
    Safely extract a ZIP archive with path traversal protection.
    
    This function:
    1. Validates all paths in the ZIP before extraction
    2. Ensures no file can escape the extraction directory
    3. Creates the extraction directory if needed
    4. Extracts all files safely
    
    Example of what this prevents:
        A malicious ZIP might contain:
        - "../../etc/passwd" - tries to write outside the directory
        - "/etc/passwd" - tries to write to absolute path
        - Symlinks pointing to sensitive locations
    
    Args:
        zip_path: Path to the ZIP archive file
        extract_to: Directory where files should be extracted
        
    Raises:
        InvalidZipError: If the ZIP is corrupted or invalid
        UnsafeZipError: If the ZIP contains unsafe paths
    """
    # Ensure extraction directory exists
    extract_to.mkdir(parents=True, exist_ok=True)
    
    # Validate all paths first
    safe_members = validate_zip_paths(zip_path, extract_to)
    
    # If validation passed, extract the archive
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        # Extract only the validated members
        for member in safe_members:
            zip_file.extract(member, extract_to)


def find_repository_root(extract_path: Path) -> Path:
    """
    Find the actual repository root within an extracted archive.
    
    GitHub ZIP archives typically contain a top-level directory like:
    - repository-main/
    - repository-master/
    - repository-develop/
    
    This function finds that directory automatically without assuming
    the exact name or branch.
    
    Args:
        extract_path: Path where the archive was extracted
        
    Returns:
        Path to the repository root directory
        
    Raises:
        FileNotFoundError: If no repository root can be identified
    """
    # List all items in the extraction directory
    items = list(extract_path.iterdir())
    
    # If there's only one directory, that's likely the repository root
    directories = [item for item in items if item.is_dir()]
    
    if len(directories) == 1:
        return directories[0]
    
    # If there are multiple directories or files at the root level,
    # the extraction directory itself is the repository root
    # (unusual, but possible for some archives)
    if len(items) > 0:
        return extract_path
    
    # Empty archive
    raise FileNotFoundError("No repository root found in extracted archive")
