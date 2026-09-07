"""
Shared test fixtures for CodeTraceX tests.

This module provides common fixtures used across multiple test files.
"""
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables before any other imports
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal, engine, Base


@pytest.fixture(scope="function")
def db():
    """
    Create a fresh database session for each test.
    
    This fixture:
    1. Creates all tables
    2. Provides a database session
    3. Cleans up tables after test
    """
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """
    Create a FastAPI test client.
    
    This fixture provides a test client for making HTTP requests
    to the FastAPI application.
    """
    return TestClient(app)
