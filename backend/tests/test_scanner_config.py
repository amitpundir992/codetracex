"""
Tests for scanner configuration utilities.
"""
import pytest
from app.utils.scanner_config import (
    is_binary_file,
    is_sensitive_file,
    get_file_extension,
    detect_language,
    IGNORED_DIRECTORIES
)


class TestFileExtension:
    """Tests for file extension extraction."""
    
    def test_get_extension_simple(self):
        assert get_file_extension("test.py") == ".py"
        assert get_file_extension("app.js") == ".js"
        assert get_file_extension("style.css") == ".css"
    
    def test_get_extension_multiple_dots(self):
        assert get_file_extension("file.test.js") == ".js"
        assert get_file_extension("app.config.ts") == ".ts"
    
    def test_get_extension_no_extension(self):
        assert get_file_extension("README") == ""
        assert get_file_extension("Makefile") == ""
    
    def test_get_extension_case_insensitive(self):
        assert get_file_extension("FILE.PY") == ".py"
        assert get_file_extension("App.JS") == ".js"


class TestBinaryFileDetection:
    """Tests for binary file detection."""
    
    def test_image_files_are_binary(self):
        assert is_binary_file("photo.png") is True
        assert is_binary_file("icon.jpg") is True
        assert is_binary_file("avatar.gif") is True
        assert is_binary_file("logo.svg") is True
    
    def test_archive_files_are_binary(self):
        assert is_binary_file("package.zip") is True
        assert is_binary_file("backup.tar") is True
        assert is_binary_file("data.gz") is True
    
    def test_executable_files_are_binary(self):
        assert is_binary_file("program.exe") is True
        assert is_binary_file("library.dll") is True
        assert is_binary_file("lib.so") is True
    
    def test_source_files_are_not_binary(self):
        assert is_binary_file("app.py") is False
        assert is_binary_file("script.js") is False
        assert is_binary_file("style.css") is False
        assert is_binary_file("README.md") is False


class TestSensitiveFileDetection:
    """Tests for sensitive file detection."""
    
    def test_env_files_are_sensitive(self):
        assert is_sensitive_file(".env") is True
        assert is_sensitive_file(".env.local") is True
        assert is_sensitive_file(".env.production") is True
    
    def test_credential_files_are_sensitive(self):
        assert is_sensitive_file("secrets.json") is True
        assert is_sensitive_file("credentials.json") is True
    
    def test_regular_files_are_not_sensitive(self):
        assert is_sensitive_file("app.py") is False
        assert is_sensitive_file("config.json") is False
        assert is_sensitive_file("README.md") is False


class TestLanguageDetection:
    """Tests for language detection."""
    
    def test_detect_javascript_typescript(self):
        assert detect_language("app.js") == "JavaScript"
        assert detect_language("component.jsx") == "JavaScript"
        assert detect_language("app.ts") == "TypeScript"
        assert detect_language("component.tsx") == "TypeScript"
    
    def test_detect_python(self):
        assert detect_language("script.py") == "Python"
        assert detect_language("types.pyi") == "Python"
    
    def test_detect_web_languages(self):
        assert detect_language("index.html") == "HTML"
        assert detect_language("style.css") == "CSS"
        assert detect_language("style.scss") == "SCSS"
    
    def test_detect_compiled_languages(self):
        assert detect_language("Main.java") == "Java"
        assert detect_language("app.rs") == "Rust"
        assert detect_language("main.go") == "Go"
        assert detect_language("program.c") == "C"
        assert detect_language("program.cpp") == "C++"
    
    def test_detect_data_formats(self):
        assert detect_language("package.json") == "JSON"
        assert detect_language("config.yaml") == "YAML"
        assert detect_language("config.yml") == "YAML"
        assert detect_language("Cargo.toml") == "TOML"
    
    def test_detect_markdown(self):
        assert detect_language("README.md") == "Markdown"
        assert detect_language("docs.markdown") == "Markdown"
    
    def test_unknown_extension_returns_none(self):
        assert detect_language("unknown.xyz") is None
        assert detect_language("file.unknown") is None


class TestIgnoredDirectories:
    """Tests for ignored directory configuration."""
    
    def test_version_control_ignored(self):
        assert ".git" in IGNORED_DIRECTORIES
        assert ".svn" in IGNORED_DIRECTORIES
    
    def test_dependencies_ignored(self):
        assert "node_modules" in IGNORED_DIRECTORIES
        assert "vendor" in IGNORED_DIRECTORIES
    
    def test_build_output_ignored(self):
        assert "dist" in IGNORED_DIRECTORIES
        assert "build" in IGNORED_DIRECTORIES
        assert "target" in IGNORED_DIRECTORIES
    
    def test_python_cache_ignored(self):
        assert "__pycache__" in IGNORED_DIRECTORIES
        assert ".pytest_cache" in IGNORED_DIRECTORIES
        assert "venv" in IGNORED_DIRECTORIES
