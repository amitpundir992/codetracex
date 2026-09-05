"""
Database models for CodeTraceX Phase 4.

This module defines the PostgreSQL schema for storing repository intelligence.

Model Hierarchy:
    
    Repository (GitHub repository)
        ↓
    AnalysisRun (one analysis snapshot)
        ↓
    Files, Symbols, Imports, Calls
    
Architecture Philosophy:
    
    We store STRUCTURED INTELLIGENCE, not source code.
    
    Flow:
    1. Download repository (temporary)
    2. Analyze structure
    3. Extract symbols, imports, calls
    4. Store metadata in PostgreSQL
    5. Delete temporary repository
    
    Why?
    - Source code changes frequently
    - We need structured relationships
    - Queries should be fast
    - Storage should be efficient
    
Tables:
    
    1. Repository - GitHub repository metadata
    2. AnalysisRun - One analysis execution
    3. File - File metadata from scan
    4. Symbol - Functions, classes, methods
    5. Import - Import statements
    6. Call - Function calls
    7. Relationship - Generic relationships (contains, imports, calls)
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, DateTime, Text,
    ForeignKey, Enum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.db.session import Base


class AnalysisStatus(enum.Enum):
    """
    Status of an analysis run.
    
    pending - Analysis queued but not started
    running - Analysis currently in progress
    completed - Analysis finished successfully
    failed - Analysis failed with error
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SymbolType(enum.Enum):
    """
    Type of code symbol.
    
    Supports multiple languages with common abstractions:
    - function: Standalone function
    - class: Class definition
    - method: Function inside a class
    - arrow_function: JavaScript/TypeScript arrow function
    """
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    ARROW_FUNCTION = "arrow_function"
    INTERFACE = "interface"


class RelationshipType(enum.Enum):
    """
    Type of relationship between entities.
    
    CONTAINS - Class contains method, file contains symbol
    IMPORTS - File imports module
    CALLS - Function calls another function
    """
    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"


class Repository(Base):
    """
    Represents a GitHub repository.
    
    This table stores permanent repository metadata.
    One repository can have multiple analysis runs over time.
    
    Why separate from AnalysisRun?
    - Repository metadata is relatively static
    - Multiple analyses can be performed on same repository
    - Enables tracking repository evolution over time
    
    Fields:
        id: Internal UUID primary key
        owner: GitHub username or organization
        name: Repository name
        full_name: owner/name (e.g., "facebook/react")
        github_url: Full GitHub URL
        default_branch: Default branch name (usually "main" or "master")
        description: Repository description
        language: Primary language reported by GitHub
        stars: Star count (snapshot at creation)
        created_at: When this record was created
        updated_at: When this record was last updated
    
    Relationships:
        analysis_runs: All analysis runs for this repository
    """
    __tablename__ = "repositories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    full_name = Column(String(511), nullable=False, unique=True)
    github_url = Column(String(1024), nullable=False)
    default_branch = Column(String(255))
    description = Column(Text)
    language = Column(String(100))
    stars = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    analysis_runs = relationship("AnalysisRun", back_populates="repository", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_repositories_full_name", "full_name"),
        Index("idx_repositories_owner", "owner"),
    )
    
    def __repr__(self):
        return f"<Repository {self.full_name}>"


class AnalysisRun(Base):
    """
    Represents one analysis execution of a repository.
    
    Why this table exists:
    
    A repository can be analyzed multiple times:
    - Initial analysis
    - Re-analysis after changes
    - Historical snapshots
    
    Each analysis is independent, allowing:
    - Change detection over time
    - Rollback to previous state
    - Historical queries
    
    Lifecycle:
    1. Create AnalysisRun (status=pending)
    2. Start analysis (status=running)
    3. Extract symbols, imports, calls
    4. Persist to database
    5. Mark completed or failed
    
    Fields:
        id: Internal UUID primary key
        repository_id: Foreign key to repositories
        status: Current status (pending/running/completed/failed)
        total_files: Total files scanned
        analyzed_files: Files successfully analyzed
        total_symbols: Total symbols extracted
        total_imports: Total imports extracted
        total_calls: Total function calls extracted
        started_at: When analysis started
        completed_at: When analysis finished (null if running)
        error_message: Error details if failed
    
    Relationships:
        repository: Parent repository
        files: Files analyzed in this run
        symbols: Symbols extracted in this run
        imports: Imports extracted in this run
        calls: Calls extracted in this run
        relationships: Relationships discovered in this run
    """
    __tablename__ = "analysis_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False)
    total_files = Column(Integer, default=0)
    analyzed_files = Column(Integer, default=0)
    total_symbols = Column(Integer, default=0)
    total_imports = Column(Integer, default=0)
    total_calls = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Relationships
    repository = relationship("Repository", back_populates="analysis_runs")
    files = relationship("File", back_populates="analysis_run", cascade="all, delete-orphan")
    symbols = relationship("Symbol", back_populates="analysis_run", cascade="all, delete-orphan")
    imports = relationship("Import", back_populates="analysis_run", cascade="all, delete-orphan")
    calls = relationship("Call", back_populates="analysis_run", cascade="all, delete-orphan")
    relationships = relationship("Relationship", back_populates="analysis_run", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_analysis_runs_repository_id", "repository_id"),
        Index("idx_analysis_runs_status", "status"),
        Index("idx_analysis_runs_started_at", "started_at"),
    )
    
    def __repr__(self):
        return f"<AnalysisRun {self.id} status={self.status.value}>"


class File(Base):
    """
    Represents a file in a repository.
    
    Stores metadata about files discovered during scanning.
    Linked to a specific analysis run to support historical tracking.
    
    Why store file metadata?
    - Understand repository structure
    - Track file-level dependencies
    - Associate symbols with files
    - Future: detect changed files between analyses
    
    Fields:
        id: Internal UUID primary key
        repository_id: Repository this file belongs to
        analysis_run_id: Analysis run that discovered this file
        path: Relative path from repository root
        filename: Just the filename
        extension: File extension (e.g., ".py")
        language: Detected programming language
        size_bytes: File size in bytes
        line_count: Number of lines
        is_sensitive: Whether file might contain secrets
    
    Relationships:
        repository: Parent repository
        analysis_run: Analysis run that scanned this file
        symbols: Symbols defined in this file
        imports: Imports in this file
        calls: Calls in this file
    """
    __tablename__ = "files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    analysis_run_id = Column(UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    path = Column(String(1024), nullable=False)
    filename = Column(String(255), nullable=False)
    extension = Column(String(50))
    language = Column(String(100))
    size_bytes = Column(BigInteger)
    line_count = Column(Integer)
    is_sensitive = Column(Boolean, default=False)
    
    # Relationships
    analysis_run = relationship("AnalysisRun", back_populates="files")
    symbols = relationship("Symbol", back_populates="file", cascade="all, delete-orphan")
    imports = relationship("Import", back_populates="file", cascade="all, delete-orphan")
    calls = relationship("Call", back_populates="file", cascade="all, delete-orphan")
    
    # Indexes and Constraints
    __table_args__ = (
        Index("idx_files_repository_id", "repository_id"),
        Index("idx_files_analysis_run_id", "analysis_run_id"),
        Index("idx_files_path", "path"),
        Index("idx_files_language", "language"),
        # Path should be unique within an analysis run
        UniqueConstraint("analysis_run_id", "path", name="uq_files_analysis_run_path"),
    )
    
    def __repr__(self):
        return f"<File {self.path}>"


class Symbol(Base):
    """
    Represents a code symbol (function, class, method).
    
    Symbols are the building blocks of code understanding:
    - Functions: Standalone functions
    - Classes: Class definitions
    - Methods: Functions inside classes
    
    Why track symbols?
    - Build symbol index for search
    - Understand code structure
    - Detect dependencies
    - Enable "find usages"
    - Future: semantic code search
    
    Self-referencing relationship:
    - Methods have parent_symbol_id pointing to their class
    - Enables hierarchical queries
    
    Fields:
        id: Internal UUID primary key
        file_id: File containing this symbol
        analysis_run_id: Analysis run that discovered this symbol
        name: Symbol name (e.g., "OrderService")
        symbol_type: Type (function/class/method)
        language: Programming language
        start_line: Starting line number
        end_line: Ending line number
        parent_symbol_id: Parent symbol (e.g., class for a method)
    
    Relationships:
        file: File containing this symbol
        analysis_run: Analysis run that discovered this symbol
        parent: Parent symbol (for methods)
        children: Child symbols (methods of a class)
    """
    __tablename__ = "symbols"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_run_id = Column(UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    symbol_type = Column(Enum(SymbolType), nullable=False)
    language = Column(String(100), nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    parent_symbol_id = Column(UUID(as_uuid=True), ForeignKey("symbols.id", ondelete="SET NULL"))
    
    # Relationships
    file = relationship("File", back_populates="symbols")
    analysis_run = relationship("AnalysisRun", back_populates="symbols")
    parent = relationship("Symbol", remote_side=[id], backref="children")
    
    # Indexes
    __table_args__ = (
        Index("idx_symbols_file_id", "file_id"),
        Index("idx_symbols_analysis_run_id", "analysis_run_id"),
        Index("idx_symbols_name", "name"),
        Index("idx_symbols_type", "symbol_type"),
        Index("idx_symbols_parent_symbol_id", "parent_symbol_id"),
    )
    
    def __repr__(self):
        return f"<Symbol {self.name} ({self.symbol_type.value})>"


class Import(Base):
    """
    Represents an import/require statement.
    
    Imports are critical for understanding dependencies:
    - Which modules does a file depend on?
    - Which symbols are imported?
    - What's the dependency graph?
    
    Examples:
    - Python: from app.services import OrderService
    - JavaScript: import UserService from './services/UserService'
    - TypeScript: import { useState } from 'react'
    
    Why track imports?
    - Build dependency graph
    - Detect circular dependencies
    - Understand module boundaries
    - Enable impact analysis
    
    Fields:
        id: Internal UUID primary key
        file_id: File containing the import
        analysis_run_id: Analysis run that discovered this import
        source: Module being imported from
        imported_names: Comma-separated list of imported names
        line_number: Line number of import statement
    
    Relationships:
        file: File containing this import
        analysis_run: Analysis run that discovered this import
    """
    __tablename__ = "imports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_run_id = Column(UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(1024), nullable=False)
    imported_names = Column(Text)  # Comma-separated list of imported names
    line_number = Column(Integer, nullable=False)
    
    # Relationships
    file = relationship("File", back_populates="imports")
    analysis_run = relationship("AnalysisRun", back_populates="imports")
    
    # Indexes
    __table_args__ = (
        Index("idx_imports_file_id", "file_id"),
        Index("idx_imports_analysis_run_id", "analysis_run_id"),
        Index("idx_imports_source", "source"),
    )
    
    def __repr__(self):
        return f"<Import from {self.source}>"


class Call(Base):
    """
    Represents a function/method call.
    
    Calls represent execution flow:
    - Which functions call which other functions?
    - What's the call graph?
    - Where is a function used?
    
    Important: These are SYNTACTIC calls, not semantic.
    Static analysis cannot always resolve the exact target function,
    especially with:
    - Dynamic dispatch
    - Reflection
    - Runtime code generation
    
    We store the syntactic information observed in the code.
    
    Fields:
        id: Internal UUID primary key
        file_id: File containing the call
        analysis_run_id: Analysis run that discovered this call
        caller_name: Name of function making the call
        callee_name: Name of function being called
        line_number: Line number of the call
    
    Relationships:
        file: File containing this call
        analysis_run: Analysis run that discovered this call
    """
    __tablename__ = "calls"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_run_id = Column(UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    caller_name = Column(String(255), nullable=False)
    callee_name = Column(String(255), nullable=False)
    line_number = Column(Integer, nullable=False)
    
    # Relationships
    file = relationship("File", back_populates="calls")
    analysis_run = relationship("AnalysisRun", back_populates="calls")
    
    # Indexes
    __table_args__ = (
        Index("idx_calls_file_id", "file_id"),
        Index("idx_calls_analysis_run_id", "analysis_run_id"),
        Index("idx_calls_caller_name", "caller_name"),
        Index("idx_calls_callee_name", "callee_name"),
    )
    
    def __repr__(self):
        return f"<Call {self.caller_name} -> {self.callee_name}>"


class Relationship(Base):
    """
    Generic relationship table for code relationships.
    
    This table stores structured relationships discovered by static analysis:
    - CONTAINS: Class contains method, file contains symbol
    - IMPORTS: File imports module
    - CALLS: Function calls function
    
    Design Note:
    
    This is a simplified generic relationship table. In a more complex
    system, you might have separate tables for each relationship type
    to maintain stricter foreign key constraints.
    
    However, for CodeTraceX Phase 4, this design is sufficient and
    provides flexibility for future relationship types without schema changes.
    
    Fields:
        id: Internal UUID primary key
        analysis_run_id: Analysis run that discovered this relationship
        relationship_type: Type of relationship (contains/imports/calls)
        source_type: Type of source entity (symbol/file)
        source_id: UUID of source entity
        target_type: Type of target entity (symbol/file/module)
        target_id: UUID of target entity (nullable for external references)
        target_name: Name of target (for external references like module names)
    
    Example:
        Class "OrderService" CONTAINS method "create_order"
        source_type="symbol", source_id=<OrderService UUID>
        relationship_type="contains"
        target_type="symbol", target_id=<create_order UUID>
    
    Relationships:
        analysis_run: Analysis run that discovered this relationship
    """
    __tablename__ = "relationships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_run_id = Column(UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(Enum(RelationshipType), nullable=False)
    source_type = Column(String(50), nullable=False)  # "symbol", "file"
    source_id = Column(UUID(as_uuid=True), nullable=False)  # UUID of source entity
    target_type = Column(String(50), nullable=False)  # "symbol", "file", "module"
    target_id = Column(UUID(as_uuid=True))  # UUID of target entity (nullable for external refs)
    target_name = Column(String(1024))  # Name for external references
    
    # Relationships
    analysis_run = relationship("AnalysisRun", back_populates="relationships")
    
    # Indexes
    __table_args__ = (
        Index("idx_relationships_analysis_run_id", "analysis_run_id"),
        Index("idx_relationships_type", "relationship_type"),
        Index("idx_relationships_source", "source_type", "source_id"),
        Index("idx_relationships_target", "target_type", "target_id"),
    )
    
    def __repr__(self):
        return f"<Relationship {self.source_type}:{self.source_id} {self.relationship_type.value} {self.target_type}:{self.target_id or self.target_name}>"
