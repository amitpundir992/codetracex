"""
Python AST analyzer for Phase 3.

This module uses Python's built-in ast module to parse Python source files
and extract structured information:
- Functions
- Classes
- Methods
- Imports
- Function calls

The ast module provides deterministic parsing without requiring external dependencies.
"""
import ast
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PythonSymbol:
    """Symbol extracted from Python source code."""
    name: str
    type: str  # 'function', 'class', 'method'
    start_line: int
    end_line: int
    parent: Optional[str] = None  # Parent class for methods


@dataclass
class PythonImport:
    """Import statement extracted from Python source code."""
    source: str  # Module being imported from
    names: List[str]  # Names being imported
    line: int


@dataclass
class PythonCall:
    """Function call extracted from Python source code."""
    caller: str  # Function/method containing the call
    callee: str  # Function/method being called
    line: int


@dataclass
class PythonAnalysisResult:
    """Result of analyzing a Python file."""
    symbols: List[PythonSymbol]
    imports: List[PythonImport]
    calls: List[PythonCall]
    success: bool
    error: Optional[str] = None


class PythonASTAnalyzer:
    """
    Analyzer for Python source files using the ast module.
    
    This analyzer extracts symbols, imports, and calls from Python files
    using Abstract Syntax Tree parsing. The ast module provides a safe,
    deterministic way to understand Python code structure without executing it.
    
    SECURITY: This analyzer only parses source code. It never executes it.
    """
    
    def __init__(self):
        """Initialize the Python AST analyzer."""
        pass
    
    def analyze_file(self, file_path: Path) -> PythonAnalysisResult:
        """
        Analyze a Python file and extract symbols, imports, and calls.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            PythonAnalysisResult with extracted information or error
        """
        try:
            # Read source code
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()
            
            # DEBUG
            print(f"  Analyzing: {file_path.name} ({len(source_code)} bytes)")
            
            # Parse into AST
            tree = ast.parse(source_code, filename=str(file_path))
            
            # Extract information
            symbols = self._extract_symbols(tree)
            imports = self._extract_imports(tree)
            calls = self._extract_calls(tree)
            
            # DEBUG
            print(f"    Extracted: {len(symbols)} symbols, {len(imports)} imports, {len(calls)} calls")
            if not symbols and not imports and not calls:
                print(f"    WARNING: No data extracted from file!")
            
            return PythonAnalysisResult(
                symbols=symbols,
                imports=imports,
                calls=calls,
                success=True
            )
            
        except SyntaxError as e:
            print(f"    ERROR analyzing {file_path.name}: Syntax error - {str(e)}")
            return PythonAnalysisResult(
                symbols=[],
                imports=[],
                calls=[],
                success=False,
                error=f"Syntax error: {str(e)}"
            )
        except Exception as e:
            print(f"    ERROR analyzing {file_path.name}: {str(e)}")
            return PythonAnalysisResult(
                symbols=[],
                imports=[],
                calls=[],
                success=False,
                error=f"Failed to parse file: {str(e)}"
            )
    
    def _extract_symbols(self, tree: ast.AST) -> List[PythonSymbol]:
        """
        Extract functions, classes, and methods from AST.
        
        Args:
            tree: Parsed AST
            
        Returns:
            List of extracted symbols
        """
        symbols = []
        
        for node in ast.walk(tree):
            # Extract functions (top-level functions)
            if isinstance(node, ast.FunctionDef):
                # Check if this is a method (inside a class) or standalone function
                parent_class = self._find_parent_class(tree, node)
                
                if parent_class:
                    # It's a method
                    symbols.append(PythonSymbol(
                        name=node.name,
                        type='method',
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        parent=parent_class
                    ))
                else:
                    # It's a standalone function
                    symbols.append(PythonSymbol(
                        name=node.name,
                        type='function',
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        parent=None
                    ))
            
            # Extract classes
            elif isinstance(node, ast.ClassDef):
                symbols.append(PythonSymbol(
                    name=node.name,
                    type='class',
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    parent=None
                ))
        
        return symbols
    
    def _find_parent_class(self, tree: ast.AST, func_node: ast.FunctionDef) -> Optional[str]:
        """
        Find the parent class of a function node.
        
        Args:
            tree: Full AST
            func_node: Function node to check
            
        Returns:
            Parent class name if function is a method, None otherwise
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if the function is in this class's body
                for item in node.body:
                    if item is func_node:
                        return node.name
        return None
    
    def _extract_imports(self, tree: ast.AST) -> List[PythonImport]:
        """
        Extract import statements from AST.
        
        Handles:
        - import module
        - from module import name
        - from module import name1, name2
        
        Args:
            tree: Parsed AST
            
        Returns:
            List of extracted imports
        """
        imports = []
        
        for node in ast.walk(tree):
            # Handle: import module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(PythonImport(
                        source=alias.name,
                        names=[alias.asname or alias.name],
                        line=node.lineno
                    ))
            
            # Handle: from module import name
            elif isinstance(node, ast.ImportFrom):
                if node.module:  # Can be None for relative imports like "from . import x"
                    names = [alias.name for alias in node.names]
                    imports.append(PythonImport(
                        source=node.module,
                        names=names,
                        line=node.lineno
                    ))
        
        return imports
    
    def _extract_calls(self, tree: ast.AST) -> List[PythonCall]:
        """
        Extract function/method calls from AST.
        
        Note: This is conservative. We only extract the syntactic call information.
        We do NOT attempt to resolve which specific definition the call refers to,
        as that would require full program analysis including:
        - Module resolution
        - Import tracking
        - Scope analysis
        - Dynamic dispatch
        
        Args:
            tree: Parsed AST
            
        Returns:
            List of extracted calls
        """
        calls = []
        
        # We need to track which function we're currently in
        # to record the "caller"
        current_function: Optional[str] = None
        
        for node in ast.walk(tree):
            # Track when we enter a function
            if isinstance(node, ast.FunctionDef):
                current_function = node.name
            
            # Extract calls
            if isinstance(node, ast.Call) and current_function:
                callee_name = self._get_call_name(node)
                if callee_name:
                    calls.append(PythonCall(
                        caller=current_function,
                        callee=callee_name,
                        line=node.lineno
                    ))
        
        return calls
    
    def _get_call_name(self, call_node: ast.Call) -> Optional[str]:
        """
        Extract the name from a Call node.
        
        Handles:
        - foo()
        - obj.method()
        - module.function()
        
        Args:
            call_node: Call AST node
            
        Returns:
            Call name if extractable, None otherwise
        """
        func = call_node.func
        
        # Simple name: foo()
        if isinstance(func, ast.Name):
            return func.id
        
        # Attribute: obj.method() or module.function()
        elif isinstance(func, ast.Attribute):
            return func.attr
        
        # More complex expressions - skip for now
        return None
