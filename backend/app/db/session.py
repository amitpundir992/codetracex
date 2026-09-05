"""
Database connection and session management for CodeTraceX.

This module provides the core database infrastructure:
- SQLAlchemy engine configuration
- Session factory
- Dependency injection for FastAPI
- Connection pooling

Architecture:
    
    FastAPI Endpoint
         ↓
    get_db() dependency
         ↓
    SQLAlchemy Session
         ↓
    PostgreSQL

Why Database Sessions?
    
    A database session represents a "workspace" for database operations.
    
    - Sessions track changes (inserts, updates, deletes)
    - Sessions manage transactions
    - Sessions handle commit/rollback
    - Sessions ensure data consistency
    
    Without sessions, every database operation would be independent,
    making it impossible to group related changes into atomic transactions.
    
Example:
    
    with Session() as session:
        # Create repository
        repo = Repository(name="react")
        session.add(repo)
        
        # Create analysis run
        analysis = AnalysisRun(repository_id=repo.id)
        session.add(analysis)
        
        # Commit both together (atomic)
        session.commit()
        
    If commit() fails, both changes are rolled back automatically.

Connection Pooling:
    
    SQLAlchemy maintains a pool of database connections to:
    - Avoid connection overhead for each request
    - Limit maximum concurrent connections
    - Reuse connections efficiently
    
    Pool size configured via DB_POOL_SIZE environment variable.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

from app.core.config import get_settings

# Get application settings
settings = get_settings()

# Create SQLAlchemy engine
# 
# The engine is the central source of database connections.
# It manages connection pooling and database dialect.
#
# Pool configuration:
# - pool_size: Number of connections to keep open (default 5)
# - max_overflow: Additional connections when pool is full (default 10)
# - pool_pre_ping: Test connections before use (prevents stale connections)
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections are alive
    echo=settings.APP_ENV == "development",  # Log SQL in development
)

# Session factory
#
# SessionLocal is a factory that creates new database sessions.
# Each session is independent and should be used for a single
# "unit of work" (typically one API request).
#
# autocommit=False: We control when to commit (explicit transactions)
# autoflush=False: We control when to flush changes to database
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Declarative base for ORM models
#
# All database models inherit from this base class.
# It provides SQLAlchemy with metadata about tables and relationships.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency for database sessions.
    
    This function provides a database session to API endpoints.
    The session is automatically closed after the request completes,
    even if an exception occurs.
    
    Usage in FastAPI:
        
        @app.get("/repositories")
        def get_repositories(db: Session = Depends(get_db)):
            return db.query(Repository).all()
    
    How it works:
        
        1. Creates a new session
        2. Yields session to endpoint
        3. Endpoint uses session
        4. Session automatically closed (finally block)
    
    Why use a dependency?
        
        - Ensures session is always closed
        - Prevents connection leaks
        - Works with FastAPI dependency injection
        - Easy to mock in tests
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
