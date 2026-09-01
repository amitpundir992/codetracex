"""
Tree-sitter analyzer for JavaScript, TypeScript, and TSX files.

Tree-sitter provides a robust parser that generates concrete syntax trees
for source code. Unlike regex-based approaches, Tree-sitter understands:
- Nested structures
- Scopes
- Complex syntax patterns
- Multi-line constructs

This allows CodeTraceX to reliably extract symbols from JavaScript/TypeScript
codebases without executing the code.

Why Tree-sitter?
- Supports multiple languages with consistent API
- Produces concrete syntax trees (CST) with full syntactic information
- Incremental parsing support (useful for future IDE features)
- Battle-tested (used by GitHub, Atom, Neovim)
- Does not require language-specific compilers or runtimes
"""
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
import tree_sitter_javascript as ts_javascript
import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser


@dataclass
class JSSymbol:
    """Symbol extracted from JavaScript/TypeScript source code."""
    name: str
    type: str  # 'function', 'class', 'method', 'arrow_function'
    start_line: int
    end_line: int
    parent: Optional[str] = None  # Parent class for methods


@dataclass
class JSImport:
    """Import statement extracted from JavaScript/TypeScript source code."""
    source: str  # Module being imported from
    names: List[str]  # Names being imported (empty for default imports)
    line: int


@dataclass
class JSCall:
    """Function call extracted from JavaScript/TypeScript source code."""
    caller: str  # Function/method containing the call
    callee: str  # Function/method being called
    line: int


@dataclass
class JSAnalysisResult:
    """Result of analyzing a JavaScript/TypeScript file."""
    symbols: List[JSSymbol]
    imports: List[JSImport]
    calls: List[JSCall]
    success: bool
    error: Optional[str] = None


class TreeSitterAnalyzer:
    """
    Analyzer for JavaScript, TypeScript, and TSX files using Tree-sitter.
    
    Tree-sitter provides language grammars that parse source code into
    concrete syntax trees. This analyzer uses Tree-sitter to extract:
    - Functions (function declarations and arrow functions)
    - Classes
    - Methods
    - Import statements
    - Function calls
    
    Supported file types:
    - .js (JavaScript)
    - .jsx (React JSX)
    - .ts (TypeScript)
    - .tsx (React TypeScript)
    
    SECURITY: This analyzer only parses source code. It never executes it.
    """
    
    def __init__(self):
        """Initialize Tree-sitter parsers for JavaScript and TypeScript."""
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
    
    def analyze_file(self, file_path: Path) -> JSAnalysisResult:
        """
        Analyze a JavaScript/TypeScript file and extract symbols, imports, and calls.
        
        Args:
            file_path: Path to the JS/TS file
            
        Returns:
            JSAnalysisResult with extracted information or error
        """
        try:
            # Read source code
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()
            
            # DEBUG
            print(f"  Analyzing: {file_path.name} ({len(source_code)} bytes)")
            
            # Convert to bytes (Tree-sitter requires bytes)
            source_bytes = source_code.encode('utf-8')
            
            # Select appropriate parser based on file extension
            parser = self._get_parser_for_file(file_path)
            
            # Parse into syntax tree
            tree = parser.parse(source_bytes)
            root_node = tree.root_node
            
            # DEBUG
            print(f"    Parsed successfully. Root node type: {root_node.type}, has_error: {root_node.has_error}")
            
            # Extract information
            symbols = self._extract_symbols(root_node, source_bytes)
            imports = self._extract_imports(root_node, source_bytes)
            calls = self._extract_calls(root_node, source_bytes)
            
            # DEBUG
            print(f"    Extracted: {len(symbols)} symbols, {len(imports)} imports, {len(calls)} calls")
            if not symbols and not imports and not calls:
                print(f"    WARNING: No data extracted! Root node type: {root_node.type}, has_error: {root_node.has_error}")
                if root_node.has_error:
                    print(f"    Parse tree has errors - file may have syntax errors")
            
            return JSAnalysisResult(
                symbols=symbols,
                imports=imports,
                calls=calls,
                success=True
            )
            
        except Exception as e:
            print(f"    ERROR analyzing {file_path.name}: {str(e)}")
            return JSAnalysisResult(
                symbols=[],
                imports=[],
                calls=[],
                success=False,
                error=f"Failed to parse file: {str(e)}"
            )
    
    def _get_parser_for_file(self, file_path: Path) -> Parser:
        """
        Select the appropriate Tree-sitter parser based on file extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Configured parser
        """
        extension = file_path.suffix.lower()
        
        if extension == '.tsx':
            return self.tsx_parser
        elif extension == '.ts':
            return self.ts_parser
        else:  # .js, .jsx, or anything else defaults to JavaScript
            return self.js_parser
    
    def _extract_symbols(self, root_node, source_bytes: bytes) -> List[JSSymbol]:
        """
        Extract functions, classes, and methods from the syntax tree.
        
        Args:
            root_node: Root node of the syntax tree
            source_bytes: Source code as bytes
            
        Returns:
            List of extracted symbols
        """
        symbols = []
        
        # DEBUG: Count node types
        node_type_counts = {}
        for node in self._walk_tree(root_node):
            node_type_counts[node.type] = node_type_counts.get(node.type, 0) + 1
        print(f"    Node type distribution: {dict(sorted(node_type_counts.items())[:10])}")
        
        # Recursively walk the tree
        for node in self._walk_tree(root_node):
            # Extract function declarations
            # Example: function foo() {}
            if node.type == 'function_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = self._get_node_text(name_node, source_bytes)
                    symbols.append(JSSymbol(
                        name=name,
                        type='function',
                        start_line=node.start_point[0] + 1,  # Tree-sitter uses 0-based line numbers
                        end_line=node.end_point[0] + 1,
                        parent=None
                    ))
            
            # Extract arrow functions assigned to variables
            # Example: const foo = () => {}
            elif node.type == 'lexical_declaration' or node.type == 'variable_declaration':
                for declarator in node.children:
                    if declarator.type == 'variable_declarator':
                        name_node = declarator.child_by_field_name('name')
                        value_node = declarator.child_by_field_name('value')
                        
                        if name_node and value_node and value_node.type == 'arrow_function':
                            name = self._get_node_text(name_node, source_bytes)
                            symbols.append(JSSymbol(
                                name=name,
                                type='arrow_function',
                                start_line=value_node.start_point[0] + 1,
                                end_line=value_node.end_point[0] + 1,
                                parent=None
                            ))
            
            # Extract classes
            # Example: class UserService {}
            elif node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = self._get_node_text(name_node, source_bytes)
                    symbols.append(JSSymbol(
                        name=class_name,
                        type='class',
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=None
                    ))
                    
                    # Extract methods within the class
                    body = node.child_by_field_name('body')
                    if body:
                        for method_node in body.children:
                            if method_node.type == 'method_definition':
                                method_name_node = method_node.child_by_field_name('name')
                                if method_name_node:
                                    method_name = self._get_node_text(method_name_node, source_bytes)
                                    symbols.append(JSSymbol(
                                        name=method_name,
                                        type='method',
                                        start_line=method_node.start_point[0] + 1,
                                        end_line=method_node.end_point[0] + 1,
                                        parent=class_name
                                    ))
        
        return symbols
    
    def _extract_imports(self, root_node, source_bytes: bytes) -> List[JSImport]:
        """
        Extract import statements from the syntax tree.
        
        Handles:
        - import React from 'react'
        - import { useState } from 'react'
        - import * as module from 'module'
        - const express = require('express')
        
        Args:
            root_node: Root node of the syntax tree
            source_bytes: Source code as bytes
            
        Returns:
            List of extracted imports
        """
        imports = []
        
        for node in self._walk_tree(root_node):
            # Handle ES6 imports: import ... from '...'
            if node.type == 'import_statement':
                source_node = node.child_by_field_name('source')
                if source_node:
                    # Get the module path
                    source = self._get_node_text(source_node, source_bytes).strip('"\'')
                    
                    # Extract imported names
                    names = []
                    for child in node.children:
                        if child.type == 'import_clause':
                            # Handle named imports: { foo, bar }
                            for subchild in child.children:
                                if subchild.type == 'named_imports':
                                    for spec in subchild.children:
                                        if spec.type == 'import_specifier':
                                            name_node = spec.child_by_field_name('name')
                                            if name_node:
                                                names.append(self._get_node_text(name_node, source_bytes))
                                # Handle default import: import React
                                elif subchild.type == 'identifier':
                                    names.append(self._get_node_text(subchild, source_bytes))
                    
                    imports.append(JSImport(
                        source=source,
                        names=names if names else [],
                        line=node.start_point[0] + 1
                    ))
            
            # Handle CommonJS require: const x = require('module')
            elif node.type == 'variable_declaration' or node.type == 'lexical_declaration':
                for declarator in node.children:
                    if declarator.type == 'variable_declarator':
                        value_node = declarator.child_by_field_name('value')
                        if value_node and value_node.type == 'call_expression':
                            func_node = value_node.child_by_field_name('function')
                            if func_node and self._get_node_text(func_node, source_bytes) == 'require':
                                # Get the module path
                                args = value_node.child_by_field_name('arguments')
                                if args and len(args.children) > 0:
                                    for arg in args.children:
                                        if arg.type == 'string':
                                            source = self._get_node_text(arg, source_bytes).strip('"\'')
                                            name_node = declarator.child_by_field_name('name')
                                            names = [self._get_node_text(name_node, source_bytes)] if name_node else []
                                            imports.append(JSImport(
                                                source=source,
                                                names=names,
                                                line=node.start_point[0] + 1
                                            ))
        
        return imports
    
    def _extract_calls(self, root_node, source_bytes: bytes) -> List[JSCall]:
        """
        Extract function/method calls from the syntax tree.
        
        Note: This is conservative. We only extract syntactic call information.
        We do NOT attempt full call resolution.
        
        Args:
            root_node: Root node of the syntax tree
            source_bytes: Source code as bytes
            
        Returns:
            List of extracted calls
        """
        calls = []
        current_function: Optional[str] = None
        
        for node in self._walk_tree(root_node):
            # Track current function
            if node.type == 'function_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    current_function = self._get_node_text(name_node, source_bytes)
            
            # Extract calls
            if node.type == 'call_expression' and current_function:
                func_node = node.child_by_field_name('function')
                if func_node:
                    callee = self._get_call_name(func_node, source_bytes)
                    if callee:
                        calls.append(JSCall(
                            caller=current_function,
                            callee=callee,
                            line=node.start_point[0] + 1
                        ))
        
        return calls
    
    def _get_call_name(self, func_node, source_bytes: bytes) -> Optional[str]:
        """
        Extract function name from a call expression.
        
        Args:
            func_node: Function node from call expression
            source_bytes: Source code as bytes
            
        Returns:
            Function name if extractable
        """
        if func_node.type == 'identifier':
            return self._get_node_text(func_node, source_bytes)
        elif func_node.type == 'member_expression':
            property_node = func_node.child_by_field_name('property')
            if property_node:
                return self._get_node_text(property_node, source_bytes)
        return None
    
    def _walk_tree(self, node):
        """
        Recursively walk the syntax tree.
        
        Args:
            node: Starting node
            
        Yields:
            Each node in the tree
        """
        yield node
        for child in node.children:
            yield from self._walk_tree(child)
    
    def _get_node_text(self, node, source_bytes: bytes) -> str:
        """
        Extract text content from a node.
        
        Args:
            node: Tree-sitter node
            source_bytes: Source code as bytes
            
        Returns:
            Text content of the node
        """
        return source_bytes[node.start_byte:node.end_byte].decode('utf-8')
