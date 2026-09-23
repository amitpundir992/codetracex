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
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import enum

from app.db.session import Base


class AnalysisStatus(str, enum.Enum):
    """
    Status of an analysis run.
    
    Inheriting from str ensures SQLAlchemy serializes the value not the name.
    
    Phase 14: Enhanced for background job processing
    
    queued - Analysis job queued in Redis, waiting for worker
    pending - Analysis queued but not started (legacy, maps to queued)
    running - Analysis currently in progress
    completed - Analysis finished successfully
    failed - Analysis failed with error
    cancelled - Analysis was cancelled by user
    """
    QUEUED = "queued"
    PENDING = "pending"  # Legacy, maps to queued
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SymbolType(str, enum.Enum):
    """
    Type of code symbol.
    
    Inheriting from str ensures SQLAlchemy serializes the value not the name.
    
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


class RelationshipType(str, enum.Enum):
    """
    Type of relationship between entities.
    
    Inheriting from str ensures SQLAlchemy serializes the value not the name.
    
    CONTAINS - Class contains method, file contains symbol
    IMPORTS - File imports module
    CALLS - Function calls another function
    """
    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"


class ChangeType(str, enum.Enum):
    """
    Type of Git file change.
    
    Inheriting from str ensures SQLAlchemy serializes the value not the name.
    
    ADDED - File was added
    MODIFIED - File was modified
    DELETED - File was deleted
    RENAMED - File was renamed
    """
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class HttpMethod(str, enum.Enum):
    """
    HTTP methods for API endpoints.
    
    Inheriting from str ensures SQLAlchemy serializes the value not the name.
    """
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


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
    
    Lifecycle (Phase 14 - Background Jobs):
    1. Create AnalysisRun (status=queued)
    2. Enqueue job in Redis queue
    3. Worker picks up job (status=running)
    4. Worker executes pipeline stages with progress updates
    5. Mark completed or failed
    
    Fields:
        id: Internal UUID primary key
        repository_id: Foreign key to repositories
        status: Current status (queued/pending/running/completed/failed/cancelled)
        job_id: RQ job identifier (Phase 14)
        progress: Progress percentage 0-100 (Phase 14)
        current_stage: Current pipeline stage description (Phase 14)
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
    status = Column(Enum(AnalysisStatus, values_callable=lambda x: [e.value for e in x]), default=AnalysisStatus.QUEUED, nullable=False)
    
    # Phase 14: Background job tracking
    job_id = Column(String(255))  # RQ job identifier
    progress = Column(Integer, default=0)  # Progress percentage 0-100
    current_stage = Column(String(255))  # Current pipeline stage
    
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
        Index("idx_analysis_runs_job_id", "job_id"),  # Phase 14
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
    symbol_type = Column(Enum(SymbolType, values_callable=lambda x: [e.value for e in x]), nullable=False)
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
    relationship_type = Column(Enum(RelationshipType, values_callable=lambda x: [e.value for e in x]), nullable=False)
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


class Commit(Base):
    """
    Represents a Git commit in repository history.
    
    Phase 6: Git History Intelligence
    
    Git commits are fundamental to understanding repository evolution:
    - Who made changes?
    - When were changes made?
    - What was the intent (commit message)?
    - What files were changed?
    
    Architecture:
        Commits belong to repositories, not analysis runs.
        Git history is a permanent property of the repository.
        
        Repository → Commits (one-to-many)
        Commit → CommitFileChanges (one-to-many)
    
    Duplicate Handling:
        Commits are unique by (repository_id, commit_hash).
        Re-analyzing a repository does not duplicate commits.
    
    Parent Commits:
        Stored as comma-separated SHA list for simplicity.
        Most commits have 1 parent, merge commits have 2+.
    
    Fields:
        id: Internal UUID primary key
        repository_id: Repository this commit belongs to
        commit_hash: Full Git SHA-1 hash (40 characters)
        author_name: Commit author name
        author_email: Commit author email
        commit_message: Full commit message
        committed_at: Timestamp when commit was made
        parent_hashes: Comma-separated parent commit SHAs
        created_at: When this record was created
    
    Relationships:
        repository: Parent repository
        file_changes: Files changed in this commit
    """
    __tablename__ = "commits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    commit_hash = Column(String(40), nullable=False)
    author_name = Column(String(255), nullable=False)
    author_email = Column(String(255), nullable=False)
    commit_message = Column(Text, nullable=False)
    committed_at = Column(DateTime, nullable=False)
    parent_hashes = Column(Text)  # Comma-separated parent SHAs
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    repository = relationship("Repository", backref="commits")
    file_changes = relationship("CommitFileChange", back_populates="commit", cascade="all, delete-orphan")
    
    # Indexes and Constraints
    __table_args__ = (
        Index("idx_commits_repository_id", "repository_id"),
        Index("idx_commits_commit_hash", "commit_hash"),
        Index("idx_commits_committed_at", "committed_at"),
        Index("idx_commits_author_email", "author_email"),
        # Commit hash must be unique within a repository
        UniqueConstraint("repository_id", "commit_hash", name="uq_commits_repository_hash"),
    )
    
    def __repr__(self):
        return f"<Commit {self.commit_hash[:8]} by {self.author_name}>"


class CommitFileChange(Base):
    """
    Represents a file change in a Git commit.
    
    Phase 6: Git History Intelligence
    
    Each commit can change multiple files. This table tracks:
    - Which files were changed
    - How they were changed (added/modified/deleted/renamed)
    - How much they changed (additions/deletions)
    
    Architecture:
        CommitFileChange links commits to files where possible.
        
        Commit → CommitFileChange → File (nullable)
        
        file_id is NULLABLE because:
        - Historical files may not exist in current analysis
        - Files may have been deleted
        - Files may have been renamed (old path no longer exists)
    
    Change Types:
        ADDED - File was newly created
        MODIFIED - File content was changed
        DELETED - File was removed
        RENAMED - File was moved/renamed
    
    Rename Handling:
        For renames, both old_path and new_path are populated.
        file_id links to the current File if it exists.
        Historical path information is preserved.
    
    Fields:
        id: Internal UUID primary key
        commit_id: Commit that made this change
        file_id: Current File record (nullable)
        path: File path (current path or new_path for renames)
        change_type: Type of change (added/modified/deleted/renamed)
        additions: Number of lines added
        deletions: Number of lines deleted
        old_path: Original path (for renames)
        new_path: New path (for renames)
        created_at: When this record was created
    
    Relationships:
        commit: Parent commit
        file: Current file (if exists)
    """
    __tablename__ = "commit_file_changes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commit_id = Column(UUID(as_uuid=True), ForeignKey("commits.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"))
    path = Column(String(1024), nullable=False)
    change_type = Column(Enum(ChangeType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    old_path = Column(String(1024))
    new_path = Column(String(1024))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    commit = relationship("Commit", back_populates="file_changes")
    file = relationship("File", backref="historical_changes")
    
    # Indexes
    __table_args__ = (
        Index("idx_commit_file_changes_commit_id", "commit_id"),
        Index("idx_commit_file_changes_file_id", "file_id"),
        Index("idx_commit_file_changes_path", "path"),
    )
    
    def __repr__(self):
        return f"<CommitFileChange {self.change_type.value} {self.path}>"


class ApiEndpoint(Base):
    """
    Represents an API endpoint in the repository.
    
    Phase 7: API & Application Structure Intelligence
    
    API endpoints are discovered through static analysis of web framework code:
    - FastAPI: @app.get, @app.post, etc.
    - Flask: @app.route, @blueprint.route
    - Express: router.get, router.post, app.get, app.post
    - Next.js: App Router route handlers (export GET, POST, etc.)
    
    Architecture:
        Endpoints belong to repositories and analysis runs.
        Endpoints reference files and optionally resolve to handler symbols.
        
        Repository → AnalysisRun → ApiEndpoint → File
                                              ↓
                                            Symbol (nullable)
    
    Handler Resolution:
        When possible, endpoints link to existing Symbol records.
        If handler cannot be resolved confidently, symbol_id remains NULL.
        This maintains conservative factual reporting.
    
    Path Representation:
        Paths are stored as declared in the framework:
        - FastAPI: /users/{id}
        - Flask: /users/<id>
        - Express: /users/:id
        
        Original framework syntax is preserved for accuracy.
    
    Fields:
        id: Internal UUID primary key
        repository_id: Repository containing this endpoint
        analysis_run_id: Analysis run that discovered this endpoint
        file_id: File containing the endpoint definition
        symbol_id: Handler symbol (NULL if not resolved)
        method: HTTP method (GET, POST, PUT, PATCH, DELETE, etc.)
        path: Endpoint path as declared in code
        framework: Web framework (fastapi, flask, express, nextjs)
        handler_name: Name of handler function (for reference)
        start_line: Starting line of endpoint definition
        end_line: Ending line of endpoint definition
        created_at: When this record was created
    
    Relationships:
        repository: Parent repository
        analysis_run: Analysis run that discovered this endpoint
        file: File containing endpoint definition
        symbol: Handler symbol (if resolved)
    """
    __tablename__ = "api_endpoints"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    analysis_run_id = Column(UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    symbol_id = Column(UUID(as_uuid=True), ForeignKey("symbols.id", ondelete="SET NULL"))
    method = Column(Enum(HttpMethod, values_callable=lambda x: [e.value for e in x]), nullable=False)
    path = Column(String(1024), nullable=False)
    framework = Column(String(50), nullable=False)
    handler_name = Column(String(255))
    start_line = Column(Integer)
    end_line = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    repository = relationship("Repository", backref="api_endpoints")
    analysis_run = relationship("AnalysisRun", backref="api_endpoints")
    file = relationship("File", backref="api_endpoints")
    symbol = relationship("Symbol", backref="api_endpoints")
    
    # Indexes and Constraints
    __table_args__ = (
        Index("idx_api_endpoints_repository_id", "repository_id"),
        Index("idx_api_endpoints_analysis_run_id", "analysis_run_id"),
        Index("idx_api_endpoints_file_id", "file_id"),
        Index("idx_api_endpoints_symbol_id", "symbol_id"),
        Index("idx_api_endpoints_method", "method"),
        Index("idx_api_endpoints_framework", "framework"),
        Index("idx_api_endpoints_path", "path"),
        # Endpoint should be unique within an analysis run
        UniqueConstraint("analysis_run_id", "method", "path", name="uq_api_endpoints_analysis_run_method_path"),
    )
    
    def __repr__(self):
        return f"<ApiEndpoint {self.method.value} {self.path}>"


class ChunkType(str, enum.Enum):
    """
    Type of semantic chunk for embeddings.
    
    Phase 9: Embeddings + pgvector
    
    Inheriting from str ensures SQLAlchemy serializes the value not the name.
    
    SYMBOL - Code symbol (function, class, method)
    API_ENDPOINT - API endpoint with handler
    DOCUMENTATION - Documentation section (README, markdown)
    FILE - Entire file (fallback for small files)
    """
    SYMBOL = "symbol"
    API_ENDPOINT = "api_endpoint"
    DOCUMENTATION = "documentation"
    FILE = "file"


class SemanticChunk(Base):
    """
    Represents a semantic chunk with embedding for similarity search.
    
    Phase 9: Embeddings + pgvector
    
    Semantic chunks are deterministic units of repository intelligence:
    - Functions, classes, methods (from symbols)
    - API endpoints with handlers
    - Documentation sections
    
    Why chunks?
    
    Repository code cannot be embedded as one giant block.
    Chunking enables:
    - Focused retrieval of relevant code sections
    - Efficient similarity search
    - Source traceability to exact lines
    - Later: RAG with precise context
    
    Architecture:
        Repository → AnalysisRun → SemanticChunk → Symbol/File/ApiEndpoint
    
    Content Hashing:
        Each chunk has deterministic identity via content_hash.
        Same content = same hash = avoid duplicate embeddings.
        Changed content = different hash = regenerate embedding.
    
    Vector Dimension:
        The embedding dimension must match the embedding model.
        Default: 384 (sentence-transformers/all-MiniLM-L6-v2)
        Configurable via environment variable.
    
    Source Traceability:
        Every chunk links back to:
        - Repository
        - Analysis run
        - File
        - Symbol (if chunk represents a symbol)
        - API endpoint (if chunk represents an endpoint)
        - Source line ranges
        
        This enables precise source citations for later RAG.
    
    Chunking Strategy:
        - Symbols: One chunk per symbol (function/class/method)
        - Large symbols (>2000 chars): Split deterministically but preserve identity
        - API endpoints: One chunk per endpoint+handler
        - Documentation: Split by headers/sections
        - Small files: Entire file as one chunk (fallback)
    
    Update Semantics:
        Chunks are tied to analysis_run_id.
        New analysis = new chunks.
        Stale chunks from old analyses remain for historical queries.
        Query should filter by latest analysis_run_id unless time travel is desired.
    
    Fields:
        id: Internal UUID primary key
        repository_id: Repository this chunk belongs to
        analysis_run_id: Analysis run that generated this chunk
        file_id: File this chunk originates from
        symbol_id: Symbol this chunk represents (nullable)
        api_endpoint_id: API endpoint this chunk represents (nullable)
        chunk_type: Type of chunk (symbol/api_endpoint/documentation/file)
        chunk_index: Index for multi-chunk splits (0 for single chunks)
        content: Text content of the chunk
        content_hash: SHA-256 hash of content (for deduplication)
        language: Programming language (nullable for documentation)
        start_line: Starting line in source file
        end_line: Ending line in source file
        token_count: Approximate token count (for monitoring)
        embedding: Vector embedding (pgvector)
        metadata_json: Optional JSON metadata (for extensibility)
        created_at: When this chunk was created
    
    Relationships:
        repository: Parent repository
        analysis_run: Analysis run that generated this chunk
        file: Source file
        symbol: Source symbol (if applicable)
        api_endpoint: Source API endpoint (if applicable)
    """
    __tablename__ = "semantic_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    analysis_run_id = Column(UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    symbol_id = Column(UUID(as_uuid=True), ForeignKey("symbols.id", ondelete="CASCADE"))
    api_endpoint_id = Column(UUID(as_uuid=True), ForeignKey("api_endpoints.id", ondelete="CASCADE"))
    chunk_type = Column(Enum(ChunkType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    chunk_index = Column(Integer, default=0, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    content_tsv = Column(TSVECTOR)  # Phase 10: Full-text search vector (auto-populated by trigger)
    language = Column(String(100))
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    token_count = Column(Integer)
    embedding = Column(Vector(384))  # pgvector column - dimension 384 for all-MiniLM-L6-v2
    metadata_json = Column(Text)  # JSON string for extensibility
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    repository = relationship("Repository", backref="semantic_chunks")
    analysis_run = relationship("AnalysisRun", backref="semantic_chunks")
    file = relationship("File", backref="semantic_chunks")
    symbol = relationship("Symbol", backref="semantic_chunks")
    api_endpoint = relationship("ApiEndpoint", backref="semantic_chunks")
    
    # Indexes and Constraints
    __table_args__ = (
        Index("idx_semantic_chunks_repository_id", "repository_id"),
        Index("idx_semantic_chunks_analysis_run_id", "analysis_run_id"),
        Index("idx_semantic_chunks_file_id", "file_id"),
        Index("idx_semantic_chunks_symbol_id", "symbol_id"),
        Index("idx_semantic_chunks_api_endpoint_id", "api_endpoint_id"),
        Index("idx_semantic_chunks_chunk_type", "chunk_type"),
        Index("idx_semantic_chunks_content_hash", "content_hash"),
        # Unique constraint for deduplication within an analysis run
        UniqueConstraint("analysis_run_id", "content_hash", "chunk_index", name="uq_semantic_chunks_analysis_run_hash_index"),
    )
    
    def __repr__(self):
        return f"<SemanticChunk {self.chunk_type.value} {self.id}>"
