"""
Tests for JavaScript/TypeScript Tree-sitter analyzer (Phase 3).

These tests verify that the JS/TS analyzer correctly extracts:
- Functions
- Arrow functions
- Classes
- Methods
- Import statements (ES6 and CommonJS)
- Function calls
"""
import pytest
from pathlib import Path

from app.services.parsers.javascript_analyzer import TreeSitterAnalyzer


@pytest.fixture
def analyzer():
    """Create a Tree-sitter analyzer instance."""
    return TreeSitterAnalyzer()


@pytest.fixture
def temp_js_file(tmp_path):
    """Create a temporary JavaScript file for testing."""
    def _create_file(content: str, extension: str = ".js") -> Path:
        file_path = tmp_path / f"test{extension}"
        file_path.write_text(content)
        return file_path
    return _create_file


class TestFunctionExtraction:
    """Tests for function extraction."""
    
    def test_function_declaration(self, analyzer, temp_js_file):
        """Test extraction of function declaration."""
        code = """
function createUser() {
    return { name: 'John' };
}
"""
        file_path = temp_js_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.symbols) >= 1
        functions = [s for s in result.symbols if s.name == "createUser"]
        assert len(functions) == 1
        assert functions[0].type == "function"
    
    def test_arrow_function(self, analyzer, temp_js_file):
        """Test extraction of arrow function."""
        code = """
const helper = () => {
    console.log('helping');
};
"""
        file_path = temp_js_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        assert len(result.symbols) >= 1
        arrows = [s for s in result.symbols if s.name == "helper"]
        assert len(arrows) == 1
        assert arrows[0].type == "arrow_function"


class TestClassExtraction:
    """Tests for class extraction."""
    
    def test_simple_class(self, analyzer, temp_js_file):
        """Test extraction of simple class."""
        code = """
class UserService {
}
"""
        file_path = temp_js_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        classes = [s for s in result.symbols if s.type == "class"]
        assert len(classes) >= 1
        assert any(c.name == "UserService" for c in classes)
    
    def test_class_with_methods(self, analyzer, temp_js_file):
        """Test extraction of class with methods."""
        code = """
class UserService {
    createUser() {
        return {};
    }
    
    deleteUser() {
        return true;
    }
}
"""
        file_path = temp_js_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        
        # Find class
        classes = [s for s in result.symbols if s.type == "class"]
        assert any(c.name == "UserService" for c in classes)
        
        # Find methods
        methods = [s for s in result.symbols if s.type == "method"]
        method_names = [m.name for m in methods]
        assert "createUser" in method_names
        assert "deleteUser" in method_names
        
        # Verify parent relationship
        for method in methods:
            if method.name in ["createUser", "deleteUser"]:
                assert method.parent == "UserService"


class TestImportExtraction:
    """Tests for import statement extraction."""
    
    def test_es6_default_import(self, analyzer, temp_js_file):
        """Test extraction of ES6 default import."""
        code = """
import React from 'react';
"""
        file_path = temp_js_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        imports = [i for i in result.imports if i.source == "react"]
        assert len(imports) >= 1
    
    def test_es6_named_import(self, analyzer, temp_js_file):
        """Test extraction of ES6 named imports."""
        code = """
import { useState, useEffect } from 'react';
"""
        file_path = temp_js_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        imports = [i for i in result.imports if i.source == "react"]
        assert len(imports) >= 1
        if imports:
            assert "useState" in imports[0].names or "useEffect" in imports[0].names
    
    def test_commonjs_require(self, analyzer, temp_js_file):
        """Test extraction of CommonJS require."""
        code = """
const express = require('express');
"""
        file_path = temp_js_file(code)
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        imports = [i for i in result.imports if i.source == "express"]
        assert len(imports) >= 1


class TestTypeScriptSupport:
    """Tests for TypeScript-specific features."""
    
    def test_typescript_function(self, analyzer, temp_js_file):
        """Test extraction of TypeScript function with types."""
        code = """
function createUser(name: string): User {
    return { name };
}
"""
        file_path = temp_js_file(code, ".ts")
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        functions = [s for s in result.symbols if s.name == "createUser"]
        assert len(functions) >= 1
    
    def test_tsx_component(self, analyzer, temp_js_file):
        """Test extraction of TSX React component."""
        code = """
const Button = () => {
    return <button>Click me</button>;
};
"""
        file_path = temp_js_file(code, ".tsx")
        result = analyzer.analyze_file(file_path)
        
        assert result.success is True
        # Should extract the arrow function
        arrows = [s for s in result.symbols if s.name == "Button"]
        assert len(arrows) >= 1


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_handles_parsing_errors_gracefully(self, analyzer, temp_js_file):
        """Test that parsing errors are handled gracefully."""
        code = """
function broken( {
    // Missing closing brace
"""
        file_path = temp_js_file(code)
        result = analyzer.analyze_file(file_path)
        
        # Tree-sitter is error-tolerant and may still extract some symbols
        # The key is that it doesn't crash
        assert result is not None
