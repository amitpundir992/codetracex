"""
API Route Analyzer for Phase 7.

This service detects API endpoints from web framework code using static analysis.
It uses the same parsing infrastructure as Phase 3 (Python AST and Tree-sitter)
to extract API route definitions deterministically.

Supported Frameworks:
    
    Python:
    - FastAPI: @app.get, @app.post, @router.get, etc.
    - Flask: @app.route, @blueprint.route
    
    JavaScript/TypeScript:
    - Express: router.get, router.post, app.get, app.post
    
Detection Strategy:
    
    1. Parse file using appropriate parser (AST for Python, Tree-sitter for JS/TS)
    2. Look for framework-specific patterns (decorators, method calls)
    3. Extract: HTTP method, path, handler function name
    4. Return normalized endpoint representation
    
Conservative Approach:
    
    - Only detect patterns we can reliably identify
    - Skip dynamic/runtime route registration
    - Skip routes from decorators we can't confidently parse
    - Never fabricate endpoints
    
Handler Resolution:
    
    Handler names are extracted but NOT resolved to Symbol records here.
    Symbol resolution happens separately in the persistence layer where
    we can query the database for matching symbols.
"""
import ast
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging

from tree_sitter import Parser, Language, Node
import tree_sitter_javascript as ts_javascript
import tree_sitter_typescript as ts_typescript

logger = logging.getLogger(__name__)


@dataclass
class DetectedEndpoint:
    """Represents a detected API endpoint."""
    method: str  # GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD
    path: str  # Route path as declared in code
    handler_name: Optional[str]  # Handler function name
    framework: str  # fastapi, flask, express, nextjs
    start_line: int
    end_line: int
    file_path: Optional[str] = None  # Source file path (set by analyzer)


class ApiRouteAnalyzer:
    """
    Analyzer for detecting API endpoints in web framework code.
    
    This analyzer uses static code analysis to detect API route definitions
    without executing code. It integrates with the existing Python AST and
    Tree-sitter infrastructure from Phase 3.
    """
    
    def __init__(self):
        """Initialize API route analyzer with parsers."""
        # JavaScript and JSX use the same grammar
        self.js_language = Language(ts_javascript.language(), "javascript")
        self.js_parser = Parser()
        self.js_parser.set_language(self.js_language)
        
        # TypeScript requires the TypeScript grammar
        self.ts_language = Language(ts_typescript.language_typescript(), "typescript")
        self.ts_parser = Parser()
        self.ts_parser.set_language(self.ts_language)
        
        # TSX requires the TSX grammar
        self.tsx_language = Language(ts_typescript.language_tsx(), "tsx")
        self.tsx_parser = Parser()
        self.tsx_parser.set_language(self.tsx_language)
    
    def analyze_python_file(self, file_path: Path) -> List[DetectedEndpoint]:
        """
        Analyze a Python file for FastAPI and Flask route definitions.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            List of detected endpoints
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()
            
            tree = ast.parse(source_code, filename=str(file_path))
            
            endpoints = []
            endpoints.extend(self._extract_fastapi_routes(tree))
            endpoints.extend(self._extract_flask_routes(tree))
            
            # Set file_path on all endpoints
            file_path_str = str(file_path)
            for endpoint in endpoints:
                endpoint.file_path = file_path_str
            
            return endpoints
            
        except SyntaxError as e:
            logger.warning(f"Syntax error parsing {file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return []
    
    def _extract_fastapi_routes(self, tree: ast.AST) -> List[DetectedEndpoint]:
        """
        Extract FastAPI route definitions.
        
        Detects patterns like:
        - @app.get("/users")
        - @app.post("/orders")
        - @router.get("/items/{id}")
        
        Args:
            tree: Python AST
            
        Returns:
            List of detected FastAPI endpoints
        """
        endpoints = []
        
        for node in ast.walk(tree):
            # Handle both regular and async functions
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            
            for decorator in node.decorator_list:
                endpoint = self._parse_fastapi_decorator(decorator, node)
                if endpoint:
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _parse_fastapi_decorator(
        self,
        decorator: ast.expr,
        func: ast.FunctionDef
    ) -> Optional[DetectedEndpoint]:
        """
        Parse a FastAPI decorator to extract endpoint information.
        
        Args:
            decorator: Decorator AST node
            func: Function being decorated
            
        Returns:
            DetectedEndpoint if this is a FastAPI route, None otherwise
        """
        # Check if decorator is a method call like app.get("/path")
        if not isinstance(decorator, ast.Call):
            return None
        
        if not isinstance(decorator.func, ast.Attribute):
            return None
        
        # Extract HTTP method from decorator attribute
        method_name = decorator.func.attr.upper()
        
        # Check if it's a valid HTTP method
        valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']
        if method_name not in valid_methods:
            return None
        
        # Extract path from first argument
        if not decorator.args:
            return None
        
        path_arg = decorator.args[0]
        if not isinstance(path_arg, ast.Constant):
            # Skip dynamic paths
            return None
        
        path = path_arg.value
        if not isinstance(path, str):
            return None
        
        # Check if the decorator object looks like FastAPI (app or router)
        # This is a heuristic but helps filter false positives
        if isinstance(decorator.func.value, ast.Name):
            obj_name = decorator.func.value.id
            # Common FastAPI naming patterns
            if obj_name not in ['app', 'router', 'api']:
                return None
        
        return DetectedEndpoint(
            method=method_name,
            path=path,
            handler_name=func.name,
            framework='fastapi',
            start_line=func.lineno,
            end_line=func.end_lineno or func.lineno
        )
    
    def _extract_flask_routes(self, tree: ast.AST) -> List[DetectedEndpoint]:
        """
        Extract Flask route definitions.
        
        Detects patterns like:
        - @app.route("/users", methods=["GET"])
        - @app.route("/orders", methods=["POST"])
        - @blueprint.route("/items/<id>", methods=["GET", "PUT"])
        
        Args:
            tree: Python AST
            
        Returns:
            List of detected Flask endpoints
        """
        endpoints = []
        
        for node in ast.walk(tree):
            # Handle both regular and async functions
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            
            for decorator in node.decorator_list:
                flask_endpoints = self._parse_flask_decorator(decorator, node)
                endpoints.extend(flask_endpoints)
        
        return endpoints
    
    def _parse_flask_decorator(
        self,
        decorator: ast.expr,
        func: ast.FunctionDef
    ) -> List[DetectedEndpoint]:
        """
        Parse a Flask decorator to extract endpoint information.
        
        Flask @route decorator can specify multiple methods, so this
        may return multiple endpoints for a single decorator.
        
        Args:
            decorator: Decorator AST node
            func: Function being decorated
            
        Returns:
            List of DetectedEndpoints (may be empty or contain multiple)
        """
        # Check if decorator is a method call like app.route("/path")
        if not isinstance(decorator, ast.Call):
            return []
        
        if not isinstance(decorator.func, ast.Attribute):
            return []
        
        # Check if it's a route decorator
        if decorator.func.attr != 'route':
            return []
        
        # Extract path from first argument
        if not decorator.args:
            return []
        
        path_arg = decorator.args[0]
        if not isinstance(path_arg, ast.Constant):
            # Skip dynamic paths
            return []
        
        path = path_arg.value
        if not isinstance(path, str):
            return []
        
        # Check if the decorator object looks like Flask (app or blueprint)
        if isinstance(decorator.func.value, ast.Name):
            obj_name = decorator.func.value.id
            # Common Flask naming patterns
            if obj_name not in ['app', 'blueprint', 'bp', 'api']:
                return []
        
        # Extract methods from keyword arguments
        methods = ['GET']  # Flask defaults to GET
        
        for keyword in decorator.keywords:
            if keyword.arg == 'methods':
                if isinstance(keyword.value, ast.List):
                    methods = []
                    for elt in keyword.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            methods.append(elt.value.upper())
        
        # Create an endpoint for each method
        endpoints = []
        for method in methods:
            # Validate method
            valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']
            if method in valid_methods:
                endpoints.append(DetectedEndpoint(
                    method=method,
                    path=path,
                    handler_name=func.name,
                    framework='flask',
                    start_line=func.lineno,
                    end_line=func.end_lineno or func.lineno
                ))
        
        return endpoints
    
    def analyze_javascript_file(self, file_path: Path) -> List[DetectedEndpoint]:
        """
        Analyze a JavaScript/TypeScript file for Express route definitions.
        
        Args:
            file_path: Path to JS/TS file
            
        Returns:
            List of detected endpoints
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()
            
            # Choose appropriate parser based on file extension
            ext = file_path.suffix.lower()
            if ext in ['.ts', '.mts', '.cts']:
                parser = self.ts_parser
            elif ext in ['.tsx']:
                parser = self.tsx_parser
            else:
                parser = self.js_parser
            
            tree = parser.parse(bytes(source_code, 'utf8'))
            
            endpoints = self._extract_express_routes(tree.root_node, source_code)
            
            # Set file_path on all endpoints
            file_path_str = str(file_path)
            for endpoint in endpoints:
                endpoint.file_path = file_path_str
            
            return endpoints
            
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return []
    
    def _extract_express_routes(self, node: Node, source_code: str) -> List[DetectedEndpoint]:
        """
        Extract Express route definitions from Tree-sitter parse tree.
        
        Detects patterns like:
        - router.get("/users", handler)
        - router.post("/orders", handler)
        - app.get("/health", handler)
        
        Args:
            node: Tree-sitter root node
            source_code: Original source code (for text extraction)
            
        Returns:
            List of detected Express endpoints
        """
        endpoints = []
        
        def visit_node(n: Node):
            # Look for call expressions like router.get(...) or app.post(...)
            if n.type == 'call_expression':
                endpoint = self._parse_express_call(n, source_code)
                if endpoint:
                    endpoints.append(endpoint)
            
            # Recursively visit children
            for child in n.children:
                visit_node(child)
        
        visit_node(node)
        return endpoints
    
    def _parse_express_call(
        self,
        node: Node,
        source_code: str
    ) -> Optional[DetectedEndpoint]:
        """
        Parse an Express route call expression.
        
        Args:
            node: Call expression node
            source_code: Original source code
            
        Returns:
            DetectedEndpoint if this is an Express route, None otherwise
        """
        # Get the function being called
        function_node = node.child_by_field_name('function')
        if not function_node or function_node.type != 'member_expression':
            return None
        
        # Extract object and method
        object_node = function_node.child_by_field_name('object')
        property_node = function_node.child_by_field_name('property')
        
        if not object_node or not property_node:
            return None
        
        # Get object and method names
        obj_text = source_code[object_node.start_byte:object_node.end_byte]
        method_text = source_code[property_node.start_byte:property_node.end_byte]
        
        # Check if object looks like Express (app, router, api)
        if obj_text not in ['app', 'router', 'api']:
            return None
        
        # Check if method is an HTTP verb
        method = method_text.upper()
        valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD']
        if method not in valid_methods:
            return None
        
        # Extract path from first argument
        arguments_node = node.child_by_field_name('arguments')
        if not arguments_node or not arguments_node.named_child_count:
            return None
        
        path_node = arguments_node.named_child(0)
        
        # Only handle string literals for now (skip template literals, variables)
        if path_node.type not in ['string', 'template_string']:
            return None
        
        path_text = source_code[path_node.start_byte:path_node.end_byte]
        
        # Remove quotes/backticks
        if path_text.startswith('"') or path_text.startswith("'"):
            path = path_text[1:-1]
        elif path_text.startswith('`'):
            # Template string - only accept if no interpolation
            if '${' in path_text:
                return None
            path = path_text[1:-1]
        else:
            return None
        
        # Try to extract handler name from second argument
        handler_name = None
        if arguments_node.named_child_count > 1:
            handler_node = arguments_node.named_child(1)
            
            # Skip if there's middleware (more than 2 arguments)
            # We want the actual route handler which is typically last
            if arguments_node.named_child_count > 2:
                handler_node = arguments_node.named_child(arguments_node.named_child_count - 1)
            
            if handler_node.type == 'identifier':
                handler_name = source_code[handler_node.start_byte:handler_node.end_byte]
            elif handler_node.type == 'arrow_function' or handler_node.type == 'function':
                handler_name = None  # Anonymous function
        
        return DetectedEndpoint(
            method=method,
            path=path,
            handler_name=handler_name,
            framework='express',
            start_line=node.start_point[0] + 1,  # Tree-sitter lines are 0-indexed
            end_line=node.end_point[0] + 1
        )
    
    def analyze_file(self, file_path: Path) -> List[DetectedEndpoint]:
        """
        Analyze a file for API endpoints based on its extension.
        
        Args:
            file_path: Path to file
            
        Returns:
            List of detected endpoints
        """
        ext = file_path.suffix.lower()
        
        if ext == '.py':
            return self.analyze_python_file(file_path)
        elif ext in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.mts', '.cts']:
            return self.analyze_javascript_file(file_path)
        else:
            return []
