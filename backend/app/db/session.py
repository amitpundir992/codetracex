"""
Database connection and session management for CodeTraceX.

Phase 15: Production Hardening
- Connection recycling to prevent stale connections
- Pool pre-ping for connection health checks
- Proper error handling and rollback

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
    
Connection Recycling (Phase 15):
    
    Connections are recycled after 1 hour (3600s) to prevent:
    - Stale connections from firewall timeouts
    - Database server connection limits
    - Connection state issues
"""
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

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
# - pool_recycle: Recycle connections after 1 hour (3600s)
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections are alive before use
    pool_recycle=3600,   # Recycle connections after 1 hour
    echo=settings.APP_ENV == "development",  # Log SQL in development
)


# Event listener for connection checkout (optional diagnostics)
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log database connections in development."""
    if settings.APP_ENV == "development":
        logger.debug("Database connection established")


# Session factory
#
# SessionLocal is a factory that creates new database sessions.
# Each session is independent and should be used for a single
# "unit of work" (typically one API request).
#
# autocommit=False: We control when to commit (explicit transactions)
# autoflush=False: We control when to flush changes to database
# expire_on_commit=False: Don't expire objects after commit (reduces queries)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Phase 15: Reduce unnecessary queries
)

# Declarative base for ORM models
#
# All database models inherit from this base class.
# It provides SQLAlchemy with metadata about tables and relationships.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency for database sessions.
    
    Phase 15: Improved error handling with automatic rollback
    
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
        4. On exception: rollback transaction
        5. Session automatically closed (finally block)
    
    Why use a dependency?
        
        - Ensures session is always closed
        - Automatic rollback on errors
        - Prevents connection leaks
        - Works with FastAPI dependency injection
        - Easy to mock in tests
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    except DBAPIError as e:
        # Database-level errors (connection issues, constraint violations, etc.)
        logger.error(f"Database error: {e}", exc_info=True)
        db.rollback()
        raise
    except Exception as e:
        # Any other exception during request handling
        logger.error(f"Error during database operation: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def close_db_connections():
    """
    Close all database connections.
    
    Call this during application shutdown to cleanly close
    all connections in the pool.
    """
    try:
        engine.dispose()
        logger.info("Database connection pool disposed")
    except Exception as e:
        logger.error(f"Error disposing database pool: {e}")
