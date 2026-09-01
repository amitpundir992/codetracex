"""
Tests for Python AST analyzer (Phase 3).

These tests verify that the Python analyzer correctly extracts:
- Functions
- Classes
- Methods
- Import statements
- Function calls
"""
import pytest
from pathlib import Path
import tempfile

from app.services.parsers.python_analyzer import PythonASTAnalyzer


@pytest.fixture
def analyzer():
    """Create a Python AST analyzer instance."""
    return PythonASTAnalyzer()


@pytest.fixture
def temp_python_file(tmp_path):
    """Create a temporary Python file for testing."""
    def _create_file(content: str) -> Path:
        file_path = tmp_path / "test.py"
        file_path.write_text(content)
        return file_path
    return _create_file


class TestFunctionExtraction:
    """Tests for function extraction."""
    
    def test_simple_function(self, analyzer, temp_python_file):
        """Test extraction of a simple function."""
        code = """
def hello_world():
    print("Hello, World!")
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.symbols) == 1
        assert result.symbols[0].name == "hello_world"
        assert result.symbols[0].type == "function"
        assert result.symbols[0].parent is None
    
    def test_multiple_functions(self, analyzer, temp_python_file):
        """Test extraction of multiple functions."""
        code = """
def function_one():
    pass

def function_two():
    pass

def function_three():
    pass
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.symbols) == 3
        function_names = [s.name for s in result.symbols]
        assert "function_one" in function_names
        assert "function_two" in function_names
        assert "function_three" in function_names


class TestClassExtraction:
    """Tests for class extraction."""
    
    def test_simple_class(self, analyzer, temp_python_file):
        """Test extraction of a simple class."""
        code = """
class UserService:
    pass
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.symbols) == 1
        assert result.symbols[0].name == "UserService"
        assert result.symbols[0].type == "class"
    
    def test_class_with_methods(self, analyzer, temp_python_file):
        """Test extraction of class with methods."""
        code = """
class OrderService:
    def create_order(self):
        pass
    
    def delete_order(self):
        pass
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.symbols) == 3  # 1 class + 2 methods
        
        # Find class
        classes = [s for s in result.symbols if s.type == "class"]
        assert len(classes) == 1
        assert classes[0].name == "OrderService"
        
        # Find methods
        methods = [s for s in result.symbols if s.type == "method"]
        assert len(methods) == 2
        method_names = [m.name for m in methods]
        assert "create_order" in method_names
        assert "delete_order" in method_names
        
        # Verify parent relationship
        for method in methods:
            assert method.parent == "OrderService"


class TestImportExtraction:
    """Tests for import statement extraction."""
    
    def test_simple_import(self, analyzer, temp_python_file):
        """Test extraction of simple import."""
        code = """
import requests
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.imports) == 1
        assert result.imports[0].source == "requests"
        assert "requests" in result.imports[0].names
    
    def test_from_import(self, analyzer, temp_python_file):
        """Test extraction of from...import statement."""
        code = """
from app.services.order import OrderService
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.imports) == 1
        assert result.imports[0].source == "app.services.order"
        assert "OrderService" in result.imports[0].names
    
    def test_multiple_names_import(self, analyzer, temp_python_file):
        """Test extraction of import with multiple names."""
        code = """
from typing import List, Dict, Optional
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.imports) == 1
        assert "List" in result.imports[0].names
        assert "Dict" in result.imports[0].names
        assert "Optional" in result.imports[0].names


class TestCallExtraction:
    """Tests for function call extraction."""
    
    def test_simple_call(self, analyzer, temp_python_file):
        """Test extraction of simple function call."""
        code = """
def caller_function():
    callee_function()

def callee_function():
    pass
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.calls) >= 1
        
        # Find the call
        calls = [c for c in result.calls if c.caller == "caller_function"]
        assert len(calls) >= 1
        assert any(c.callee == "callee_function" for c in calls)


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_syntax_error(self, analyzer, temp_python_file):
        """Test handling of Python syntax error."""
        code = """
def broken_function(
    # Missing closing parenthesis
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is False
        assert result.error is not None
        assert "Syntax error" in result.error


class TestLineNumbers:
    """Tests for line number extraction."""
    
    def test_function_line_numbers(self, analyzer, temp_python_file):
        """Test that function line numbers are correct."""
        code = """
# Line 1

def my_function():  # Line 3
    pass            # Line 4
                    # Line 5
"""
        file_path = temp_python_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.symbols) == 1
        assert result.symbols[0].start_line == 3
