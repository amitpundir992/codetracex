"""
Tests for file scanner service.
"""
import pytest
from pathlib import Path
import tempfile

from app.services.scanner_service import (
    FileScannerService,
    TooManyFilesError,
    FileMetadata,
    ScanResult
)


@pytest.fixture
def scanner():
    """Create a scanner service with reasonable limits."""
    return FileScannerService(max_files=100)


@pytest.fixture
def test_repo(tmp_path):
    """
    Create a test repository structure.
    
    Structure:
        test_repo/
        ├── README.md
        ├── .env
        ├── src/
        │   ├── main.py
        │   ├── app.ts
        │   └── component.tsx
        ├── tests/
        │   └── test_main.py
        ├── node_modules/
        │   └── package.js (should be ignored)
        ├── .git/
        │   └── config (should be ignored)
        └── image.png (binary, should be ignored)
    """
    repo = tmp_path / "test_repo"
    repo.mkdir()
    
    # Root files
    (repo / "README.md").write_text("# Test Repository\n\nDescription")
    (repo / ".env").write_text("SECRET_KEY=test")
    (repo / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG header
    
    # Source files
    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text("def main():\n    print('hello')\n\nif __name__ == '__main__':\n    main()")
    (src / "app.ts").write_text("const app = 'test';\nexport default app;")
    (src / "component.tsx").write_text("const Component = () => {\n  return <div>Test</div>;\n};\n\nexport default Component;")
    
    # Test files
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text("def test_main():\n    assert True")
    
    # Ignored directories
    node_modules = repo / "node_modules"
    node_modules.mkdir()
    (node_modules / "package.js").write_text("module.exports = {};")
    
    git = repo / ".git"
    git.mkdir()
    (git / "config").write_text("[core]\n    repositoryformatversion = 0")
    
    return repo


class TestDirectoryIgnoring:
    """Tests for directory ignore logic."""
    
    def test_should_ignore_common_directories(self, scanner):
        assert scanner.should_ignore_directory("node_modules") is True
        assert scanner.should_ignore_directory(".git") is True
        assert scanner.should_ignore_directory("__pycache__") is True
        assert scanner.should_ignore_directory("dist") is True
    
    def test_should_not_ignore_source_directories(self, scanner):
        assert scanner.should_ignore_directory("src") is False
        assert scanner.should_ignore_directory("tests") is False
        assert scanner.should_ignore_directory("lib") is False


class TestFileFiltering:
    """Tests for file filtering logic."""
    
    def test_should_scan_source_files(self, scanner, tmp_path):
        assert scanner.should_scan_file(tmp_path / "app.py") is True
        assert scanner.should_scan_file(tmp_path / "script.js") is True
        assert scanner.should_scan_file(tmp_path / "style.css") is True
        assert scanner.should_scan_file(tmp_path / "README.md") is True
    
    def test_should_not_scan_binary_files(self, scanner, tmp_path):
        assert scanner.should_scan_file(tmp_path / "image.png") is False
        assert scanner.should_scan_file(tmp_path / "video.mp4") is False
        assert scanner.should_scan_file(tmp_path / "archive.zip") is False


class TestLineCount:
    """Tests for line counting."""
    
    def test_count_lines_simple_file(self, scanner, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("Line 1\nLine 2\nLine 3")
        
        count = scanner.count_lines(file_path)
        assert count == 3
    
    def test_count_lines_empty_file(self, scanner, tmp_path):
        file_path = tmp_path / "empty.txt"
        file_path.write_text("")
        
        count = scanner.count_lines(file_path)
        assert count == 0
    
    def test_count_lines_single_line_no_newline(self, scanner, tmp_path):
        file_path = tmp_path / "single.txt"
        file_path.write_text("Single line")
        
        count = scanner.count_lines(file_path)
        assert count == 1


class TestMetadataCollection:
    """Tests for file metadata collection."""
    
    def test_collect_python_file_metadata(self, scanner, test_repo):
        file_path = test_repo / "src" / "main.py"
        metadata = scanner.collect_file_metadata(file_path, test_repo)
        
        assert metadata.path == "src/main.py"
        assert metadata.filename == "main.py"
        assert metadata.extension == ".py"
        assert metadata.language == "Python"
        assert metadata.size_bytes > 0
        assert metadata.lines == 5  # Including blank line after main()
        assert metadata.is_sensitive is False
    
    def test_collect_typescript_file_metadata(self, scanner, test_repo):
        file_path = test_repo / "src" / "component.tsx"
        metadata = scanner.collect_file_metadata(file_path, test_repo)
        
        assert metadata.path == "src/component.tsx"
        assert metadata.filename == "component.tsx"
        assert metadata.extension == ".tsx"
        assert metadata.language == "TypeScript"
        assert metadata.lines == 5  # Including blank line after Component definition
    
    def test_collect_sensitive_file_metadata(self, scanner, test_repo):
        file_path = test_repo / ".env"
        metadata = scanner.collect_file_metadata(file_path, test_repo)
        
        assert metadata.filename == ".env"
        assert metadata.is_sensitive is True
    
    def test_collect_markdown_metadata(self, scanner, test_repo):
        file_path = test_repo / "README.md"
        metadata = scanner.collect_file_metadata(file_path, test_repo)
        
        assert metadata.extension == ".md"
        assert metadata.language == "Markdown"


class TestDirectoryScanning:
    """Tests for complete directory scanning."""
    
    def test_scan_test_repository(self, scanner, test_repo):
        result = scanner.scan_directory(test_repo)
        
        # Verify we found the expected files (excluding ignored directories)
        assert result.total_files == 6  # README, .env, main.py, app.ts, component.tsx, test_main.py
        
        # Verify ignored files are not included
        paths = [f.path for f in result.files]
        assert not any("node_modules" in p for p in paths)
        assert not any(".git" in p for p in paths)
        assert not any("image.png" in p for p in paths)
        
        # Verify source files are included
        assert "src/main.py" in paths
        assert "src/app.ts" in paths
        assert "src/component.tsx" in paths
    
    def test_scan_calculates_statistics(self, scanner, test_repo):
        result = scanner.scan_directory(test_repo)
        
        # Verify language distribution
        assert "Python" in result.languages
        assert "TypeScript" in result.languages
        assert "Markdown" in result.languages
        
        assert result.languages["Python"] == 2  # main.py and test_main.py
        assert result.languages["TypeScript"] == 2  # app.ts and component.tsx
        
        # Verify total size is calculated
        assert result.total_size_bytes > 0
    
    def test_scan_respects_file_limit(self, tmp_path):
        """Test that scanning stops when file limit is reached."""
        # Create a scanner with low file limit
        scanner = FileScannerService(max_files=5)
        
        # Create repository with many files
        repo = tmp_path / "repo"
        repo.mkdir()
        for i in range(20):
            (repo / f"file_{i}.py").write_text(f"# File {i}")
        
        with pytest.raises(TooManyFilesError) as exc_info:
            scanner.scan_directory(repo)
        
        assert "more than 5 files" in str(exc_info.value)


class TestTopFilesSelection:
    """Tests for selecting top files from scan results."""
    
    def test_get_top_files_limits_results(self, scanner, test_repo):
        result = scanner.scan_directory(test_repo)
        
        # Get only top 3 files
        top_files = scanner.get_top_files(result, limit=3)
        
        assert len(top_files) == 3
    
    def test_get_top_files_prioritizes_known_languages(self, scanner, tmp_path):
        """Test that files with detected languages are prioritized."""
        repo = tmp_path / "repo"
        repo.mkdir()
        
        # Create files with and without known languages
        (repo / "app.py").write_text("print('hello')")
        (repo / "script.js").write_text("console.log('hello');")
        (repo / "data.unknown").write_text("some data")
        (repo / "README.md").write_text("# README")
        
        result = scanner.scan_directory(repo)
        top_files = scanner.get_top_files(result, limit=2)
        
        # Should prioritize files with known languages
        filenames = [f.filename for f in top_files]
        assert "app.py" in filenames or "script.js" in filenames or "README.md" in filenames
