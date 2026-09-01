"""
Tests for safe ZIP extraction utilities.
"""
import pytest
import zipfile
from pathlib import Path
import tempfile
import shutil

from app.utils.zip_utils import (
    is_safe_path,
    validate_zip_paths,
    safe_extract,
    find_repository_root,
    UnsafeZipError,
    InvalidZipError
)


class TestSafePathValidation:
    """Tests for path safety validation."""
    
    def test_safe_relative_path(self, tmp_path):
        """Test that normal relative paths are considered safe."""
        base = tmp_path / "workspace"
        base.mkdir()
        
        target = base / "src" / "app.py"
        assert is_safe_path(base, target) is True
    
    def test_unsafe_parent_traversal(self, tmp_path):
        """Test that paths using .. to escape are blocked."""
        base = tmp_path / "workspace"
        base.mkdir()
        
        # Try to escape using ../..
        target = base / ".." / ".." / "etc" / "passwd"
        assert is_safe_path(base, target) is False
    
    def test_unsafe_absolute_path(self, tmp_path):
        """Test that absolute paths outside base are blocked."""
        base = tmp_path / "workspace"
        base.mkdir()
        
        target = Path("/etc/passwd")
        assert is_safe_path(base, target) is False


class TestZipPathValidation:
    """Tests for ZIP archive path validation."""
    
    def test_valid_zip_passes_validation(self, tmp_path):
        """Test that a normal ZIP archive passes validation."""
        # Create a test ZIP with normal paths
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("repo-main/README.md", "# Test")
            zf.writestr("repo-main/src/app.py", "print('hello')")
        
        extract_to = tmp_path / "extract"
        extract_to.mkdir()
        
        members = validate_zip_paths(zip_path, extract_to)
        assert len(members) == 2
        assert "repo-main/README.md" in members
        assert "repo-main/src/app.py" in members
    
    def test_malicious_parent_traversal_blocked(self, tmp_path):
        """Test that ZIP with ../ paths is rejected."""
        # Create a malicious ZIP trying to escape
        zip_path = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("../../etc/passwd", "malicious")
        
        extract_to = tmp_path / "extract"
        extract_to.mkdir()
        
        with pytest.raises(UnsafeZipError) as exc_info:
            validate_zip_paths(zip_path, extract_to)
        
        assert "Unsafe path detected" in str(exc_info.value)
    
    def test_absolute_path_in_zip_blocked(self, tmp_path):
        """Test that ZIP with absolute paths is rejected."""
        zip_path = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("/etc/passwd", "malicious")
        
        extract_to = tmp_path / "extract"
        extract_to.mkdir()
        
        with pytest.raises(UnsafeZipError) as exc_info:
            validate_zip_paths(zip_path, extract_to)
        
        # Absolute paths are caught by the safe path check
        assert "Unsafe path detected" in str(exc_info.value)
    
    def test_corrupted_zip_raises_error(self, tmp_path):
        """Test that a corrupted ZIP file is detected."""
        # Create an invalid ZIP file
        zip_path = tmp_path / "corrupted.zip"
        zip_path.write_text("This is not a valid ZIP file")
        
        extract_to = tmp_path / "extract"
        extract_to.mkdir()
        
        with pytest.raises(InvalidZipError) as exc_info:
            validate_zip_paths(zip_path, extract_to)
        
        assert "Invalid or corrupted" in str(exc_info.value)


class TestSafeExtraction:
    """Tests for safe ZIP extraction."""
    
    def test_safe_extraction_succeeds(self, tmp_path):
        """Test that a normal ZIP extracts successfully."""
        # Create a test ZIP
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("repo-main/README.md", "# Test Repository")
            zf.writestr("repo-main/src/app.py", "print('hello')")
            zf.writestr("repo-main/src/utils.py", "def helper(): pass")
        
        extract_to = tmp_path / "extract"
        
        # Extract safely
        safe_extract(zip_path, extract_to)
        
        # Verify files were extracted
        assert (extract_to / "repo-main" / "README.md").exists()
        assert (extract_to / "repo-main" / "src" / "app.py").exists()
        assert (extract_to / "repo-main" / "src" / "utils.py").exists()
        
        # Verify content
        readme_content = (extract_to / "repo-main" / "README.md").read_text()
        assert readme_content == "# Test Repository"
    
    def test_malicious_zip_extraction_blocked(self, tmp_path):
        """Test that malicious ZIP is not extracted."""
        # Create a malicious ZIP
        zip_path = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("../../malicious.txt", "bad content")
        
        extract_to = tmp_path / "extract"
        
        with pytest.raises(UnsafeZipError):
            safe_extract(zip_path, extract_to)
        
        # Verify malicious file was NOT created outside extract directory
        malicious_path = tmp_path / "malicious.txt"
        assert not malicious_path.exists()


class TestRepositoryRootDetection:
    """Tests for finding repository root in extracted archives."""
    
    def test_find_single_directory_root(self, tmp_path):
        """Test finding root when archive has single top-level directory."""
        # Create structure: extract/repo-main/...
        extract_path = tmp_path / "extract"
        repo_dir = extract_path / "repository-main"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Test")
        (repo_dir / "src").mkdir()
        
        root = find_repository_root(extract_path)
        assert root == repo_dir
    
    def test_find_root_with_multiple_directories(self, tmp_path):
        """Test when extraction directory itself is the root."""
        extract_path = tmp_path / "extract"
        extract_path.mkdir()
        (extract_path / "README.md").write_text("# Test")
        (extract_path / "src").mkdir()
        (extract_path / "tests").mkdir()
        
        root = find_repository_root(extract_path)
        assert root == extract_path
    
    def test_empty_archive_raises_error(self, tmp_path):
        """Test that empty archive raises appropriate error."""
        extract_path = tmp_path / "extract"
        extract_path.mkdir()
        
        with pytest.raises(FileNotFoundError) as exc_info:
            find_repository_root(extract_path)
        
        assert "No repository root found" in str(exc_info.value)
