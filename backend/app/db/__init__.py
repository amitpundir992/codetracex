"""
Database module for CodeTraceX.

Exports:
- Base: Declarative base for ORM models
- engine: SQLAlchemy engine
- SessionLocal: Session factory
- get_db: FastAPI dependency for database sessions
- models: All database models
"""
from app.db.session import Base, engine, SessionLocal, get_db
from app.db import models

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "models",
]
