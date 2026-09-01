"""
Tests for static analyzer orchestrator (Phase 3).

These tests verify that the static analyzer correctly:
- Routes files to appropriate parsers
- Aggregates results from multiple files
- Handles unsupported files
- Handles parsing errors gracefully
- Generates correct summary statistics
"""
import pytest
from pathlib import Path

from app.services.static_analyzer import StaticAnalyzer


@pytest.fixture
def analyzer():
    """Create a static analyzer instance."""
    return StaticAnalyzer()


@pytest.fixture
def test_repo(tmp_path):
    """
    Create a test repository with multiple language files.
    
    Structure:
        test_repo/
        ├── app.py
        ├── utils.js
        ├── component.tsx
        ├── README.md (unsupported)
        └── image.png (unsupported)
    """
    repo = tmp_path / "test_repo"
    repo.mkdir()
    
    # Python file
    (repo / "app.py").write_text("""
class Application:
    def run(self):
        print("Running")
""")
    
    # JavaScript file
    (repo / "utils.js").write_text("""
function helper() {
    return true;
}
""")
    
    # TypeScript file
    (repo / "component.tsx").write_text("""
const Component = () => {
    return <div>Hello</div>;
};
""")
    
    # Unsupported files
    (repo / "README.md").write_text("# Documentation")
    (repo / "image.png").write_bytes(b"\x89PNG")
    
    return repo


class TestFileRouting:
    """Tests for file routing to appropriate parsers."""
    
    def test_identifies_supported_files(self, analyzer):
        """Test that analyzer correctly identifies supported files."""
        assert analyzer.is_supported(Path("test.py")) is True
        assert analyzer.is_supported(Path("test.js")) is True
        assert analyzer.is_supported(Path("test.jsx")) is True
        assert analyzer.is_supported(Path("test.ts")) is True
        assert analyzer.is_supported(Path("test.tsx")) is True
        
        assert analyzer.is_supported(Path("test.md")) is False
        assert analyzer.is_supported(Path("test.txt")) is False
        assert analyzer.is_supported(Path("test.png")) is False
    
    def test_detects_correct_language(self, analyzer):
        """Test that analyzer detects the correct language."""
        assert analyzer.get_language(Path("test.py")) == "Python"
        assert analyzer.get_language(Path("test.js")) == "JavaScript"
        assert analyzer.get_language(Path("test.jsx")) == "JavaScript"
        assert analyzer.get_language(Path("test.ts")) == "TypeScript"
        assert analyzer.get_language(Path("test.tsx")) == "TypeScript"
        
        assert analyzer.get_language(Path("test.md")) is None


class TestMultiLanguageAnalysis:
    """Tests for analyzing repositories with multiple languages."""
    
    def test_analyzes_mixed_repository(self, analyzer, test_repo):
        """Test analysis of repository with multiple languages."""
        files = list(test_repo.glob("*"))
        
        result = analyzer.analyze_repository(test_repo, files)
        
        assert result is not None
        assert result.summary is not None
        
        # Should have analyzed 3 supported files (py, js, tsx)
        assert result.summary.analyzed_files >= 3
        
        # Should have skipped 2 unsupported files (md, png)
        assert result.summary.skipped_files >= 2
        
        # Should have extracted some symbols
        assert result.summary.total_symbols > 0
    
    def test_aggregates_symbols_from_multiple_files(self, analyzer, test_repo):
        """Test that symbols from all files are aggregated."""
        files = list(test_repo.glob("*"))
        
        result = analyzer.analyze_repository(test_repo, files)
        
        # Should have symbols from Python, JavaScript, and TypeScript
        symbol_names = [s.name for s in result.all_symbols]
        
        # From Python file
        assert "Application" in symbol_names or "run" in symbol_names
        
        # From JavaScript file
        assert "helper" in symbol_names
        
        # From TypeScript file
        assert "Component" in symbol_names


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_handles_broken_file_gracefully(self, analyzer, tmp_path):
        """Test that a broken file doesn't crash entire analysis."""
        repo = tmp_path / "repo"
        repo.mkdir()
        
        # Create a valid Python file
        (repo / "good.py").write_text("def good_function():\n    pass")
        
        # Create a broken Python file
        (repo / "broken.py").write_text("def broken( {\n")
        
        files = [repo / "good.py", repo / "broken.py"]
        
        result = analyzer.analyze_repository(repo, files)
        
        # Should have attempted to analyze 2 files
        assert result.summary.analyzed_files + result.summary.failed_files >= 1
        
        # Should have extracted symbol from the good file
        assert result.summary.total_symbols >= 1
        assert any(s.name == "good_function" for s in result.all_symbols)
    
    def test_records_failed_files(self, analyzer, tmp_path):
        """Test that failed files are recorded in results."""
        repo = tmp_path / "repo"
        repo.mkdir()
        
        # Create a broken Python file
        (repo / "broken.py").write_text("def broken( {\n")
        
        files = [repo / "broken.py"]
        
        result = analyzer.analyze_repository(repo, files)
        
        # Should have recorded the failure
        assert result.summary.failed_files >= 1


class TestSummaryGeneration:
    """Tests for summary statistics generation."""
    
    def test_generates_accurate_symbol_counts(self, analyzer, tmp_path):
        """Test that symbol counts are accurate."""
        repo = tmp_path / "repo"
        repo.mkdir()
        
        (repo / "test.py").write_text("""
class MyClass:
    def method_one(self):
        pass
    
    def method_two(self):
        pass

def standalone_function():
    pass
""")
        
        files = [repo / "test.py"]
        result = analyzer.analyze_repository(repo, files)
        
        assert result.summary.total_symbols == 4  # 1 class + 2 methods + 1 function
        assert result.summary.symbols_by_type.get("class", 0) == 1
        assert result.summary.symbols_by_type.get("method", 0) == 2
        assert result.summary.symbols_by_type.get("function", 0) == 1
