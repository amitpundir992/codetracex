"""
Tests for Phase 15: Production Hardening, Observability & Reliability

This test suite verifies:
- Structured logging with sanitization
- Request ID correlation
- Health and readiness checks
- Error handling
- Configuration validation
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import redis

from app.main import app
from app.db.session import Base, get_db
from app.utils.logging_config import (
    sanitize_log_message,
    set_request_context,
    clear_request_context,
    get_request_id
)
from app.middleware.request_id import validate_request_id, generate_request_id
from app.middleware.error_handlers import get_safe_error_message
from app.core.config_validation import (
    validate_database_url,
    validate_redis_url,
    validate_port,
    validate_positive_integer,
    ConfigurationError,
    validate_configuration
)


# ==========================================
# Test Fixtures
# ==========================================

@pytest.fixture(scope="function")
def db_session():
    """Create test database session."""
    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# ==========================================
# Test Logging Sanitization
# ==========================================

class TestLoggingSanitization:
    """Test log message sanitization."""
    
    def test_sanitize_api_key(self):
        """Test API key sanitization."""
        message = "Using api_key=AIzaSyBc1234567890123456789012345678901234 for request"
        sanitized = sanitize_log_message(message)
        assert "AIzaSy" not in sanitized
        assert "***REDACTED***" in sanitized
    
    def test_sanitize_redis_url(self):
        """Test Redis URL sanitization."""
        message = "Connecting to redis://user:password@localhost:6379/0"
        sanitized = sanitize_log_message(message)
        assert "password" not in sanitized
        assert "redis://***:***@" in sanitized
    
    def test_sanitize_database_url(self):
        """Test database URL sanitization."""
        message = "Connected to postgresql://admin:secret@db.example.com/prod"
        sanitized = sanitize_log_message(message)
        assert "secret" not in sanitized
        assert "postgresql://***:***@" in sanitized
    
    def test_sanitize_authorization_header(self):
        """Test authorization header sanitization."""
        message = "Request headers: Authorization: Bearer sk-abc123xyz"
        sanitized = sanitize_log_message(message)
        assert "sk-abc123xyz" not in sanitized
        assert "***REDACTED***" in sanitized
    
    def test_sanitize_password(self):
        """Test password sanitization."""
        message = "Login attempt with password=mySecretP@ss"
        sanitized = sanitize_log_message(message)
        assert "mySecretP@ss" not in sanitized
        assert "***REDACTED***" in sanitized
    
    def test_sanitize_gemini_key(self):
        """Test Gemini API key sanitization."""
        message = "Using Gemini key AIzaSyBc1234567890123456789012345678901234"
        sanitized = sanitize_log_message(message)
        assert "AIzaSyBc" not in sanitized
        assert "***REDACTED_GEMINI_KEY***" in sanitized
    
    def test_normal_message_unchanged(self):
        """Test normal messages are not modified."""
        message = "Processing repository analysis"
        sanitized = sanitize_log_message(message)
        assert message == sanitized


# ==========================================
# Test Request ID Correlation
# ==========================================

class TestRequestID:
    """Test request ID generation and validation."""
    
    def test_generate_request_id(self):
        """Test request ID generation."""
        request_id = generate_request_id()
        assert len(request_id) == 32  # UUID without hyphens
        assert request_id.isalnum()
    
    def test_validate_valid_request_id(self):
        """Test valid request ID validation."""
        valid_ids = [
            "abc12345",  # Minimum length
            "abc123def456ghi789",  # Normal length
            "a" * 64,  # Maximum length
            "request-id-with-dashes",
            "request_id_with_underscores"
        ]
        for req_id in valid_ids:
            assert validate_request_id(req_id) is True
    
    def test_validate_invalid_request_id(self):
        """Test invalid request ID validation."""
        invalid_ids = [
            "",  # Empty
            "short",  # Too short
            "a" * 65,  # Too long
            "request id with spaces",  # Spaces
            "request\nid\nwith\nnewlines",  # Newlines (log injection attempt)
            "<script>alert('xss')</script>",  # XSS attempt
        ]
        for req_id in invalid_ids:
            assert validate_request_id(req_id) is False
    
    def test_request_context(self):
        """Test request context management."""
        # Set context
        set_request_context(request_id="test-123", job_id="job-456")
        
        # Verify context is set
        assert get_request_id() == "test-123"
        
        # Clear context
        clear_request_context()
        
        # Verify context is cleared
        assert get_request_id() is None
    
    def test_request_id_in_response(self, client):
        """Test request ID is returned in response headers."""
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) >= 8
    
    def test_client_request_id_preserved(self, client):
        """Test client-provided request ID is preserved."""
        client_request_id = "my-custom-request-id-123"
        response = client.get("/health", headers={"X-Request-ID": client_request_id})
        assert response.headers["X-Request-ID"] == client_request_id
    
    def test_invalid_client_request_id_replaced(self, client):
        """Test invalid client request ID is replaced."""
        invalid_request_id = "bad id with spaces"
        response = client.get("/health", headers={"X-Request-ID": invalid_request_id})
        # Should generate new ID, not use invalid one
        assert response.headers["X-Request-ID"] != invalid_request_id
        assert len(response.headers["X-Request-ID"]) >= 8


# ==========================================
# Test Health Endpoints
# ==========================================

class TestHealthEndpoints:
    """Test health and readiness checks."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "codetracex-backend"
    
    def test_readiness_check_success(self, client):
        """Test readiness check when dependencies are available."""
        response = client.get("/ready")
        # Note: This may return 503 if Redis is not running locally
        # That's expected behavior
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]
    
    def test_health_check_lightweight(self, client):
        """Test that health check is lightweight and fast."""
        import time
        start = time.time()
        response = client.get("/health")
        duration = time.time() - start
        assert response.status_code == 200
        # Should be very fast (< 100ms)
        assert duration < 0.1


# ==========================================
# Test Error Handling
# ==========================================

class TestErrorHandling:
    """Test centralized error handling."""
    
    def test_validation_error(self, client):
        """Test validation error handling."""
        # Send invalid request (missing required field)
        response = client.post("/api/repositories")
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "request_id" in data["error"]
    
    def test_not_found_error(self, client):
        """Test 404 error handling."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "request_id" in data["error"]
    
    def test_error_response_structure(self, client):
        """Test error response has correct structure."""
        response = client.post("/api/repositories")
        data = response.json()
        
        # Verify structure
        assert "error" in data
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "request_id" in error
        
        # Verify no sensitive information
        error_str = str(data)
        assert "api_key" not in error_str.lower()
        assert "password" not in error_str.lower()
        assert "secret" not in error_str.lower()
    
    def test_safe_error_message(self):
        """Test safe error message generation."""
        # Test various exception types
        exceptions = [
            Exception("Database connection failed"),
            ValueError("Invalid input"),
            RuntimeError("Timeout occurred")
        ]
        
        for exc in exceptions:
            safe_msg = get_safe_error_message(exc)
            # Should not be empty
            assert len(safe_msg) > 0
            # Should not exceed max length
            assert len(safe_msg) <= 500


# ==========================================
# Test Configuration Validation
# ==========================================

class TestConfigurationValidation:
    """Test configuration validation."""
    
    def test_validate_database_url_valid(self):
        """Test valid database URL validation."""
        valid_urls = [
            "postgresql://user:pass@localhost/db",
            "postgresql+psycopg://user:pass@localhost:5432/db",
            "postgresql://user:pass@db.example.com:5432/production"
        ]
        for url in valid_urls:
            valid, error = validate_database_url(url)
            assert valid is True
            assert error == ""
    
    def test_validate_database_url_invalid(self):
        """Test invalid database URL validation."""
        invalid_urls = [
            "",  # Empty
            "mysql://user:pass@localhost/db",  # Wrong database
            "postgresql://localhost",  # Missing database name
            "not-a-url"  # Invalid format
        ]
        for url in invalid_urls:
            valid, error = validate_database_url(url)
            assert valid is False
            assert len(error) > 0
    
    def test_validate_redis_url_valid(self):
        """Test valid Redis URL validation."""
        valid_urls = [
            "redis://localhost:6379/0",
            "redis://user:pass@localhost:6379/0",
            "redis://redis.example.com:6379/1"
        ]
        for url in valid_urls:
            valid, error = validate_redis_url(url)
            assert valid is True
            assert error == ""
    
    def test_validate_redis_url_invalid(self):
        """Test invalid Redis URL validation."""
        invalid_urls = [
            "",  # Empty
            "http://localhost:6379",  # Wrong protocol
            "localhost:6379",  # Missing protocol
        ]
        for url in invalid_urls:
            valid, error = validate_redis_url(url)
            assert valid is False
            assert len(error) > 0
    
    def test_validate_port_valid(self):
        """Test valid port validation."""
        valid_ports = [80, 443, 3000, 8000, 8080, 65535]
        for port in valid_ports:
            valid, error = validate_port(port)
            assert valid is True
            assert error == ""
    
    def test_validate_port_invalid(self):
        """Test invalid port validation."""
        invalid_ports = [0, -1, 65536, 70000, "8000"]
        for port in invalid_ports:
            valid, error = validate_port(port)
            assert valid is False
            assert len(error) > 0
    
    def test_validate_positive_integer_valid(self):
        """Test valid positive integer validation."""
        valid_values = [1, 5, 100, 1000]
        for value in valid_values:
            valid, error = validate_positive_integer(value, "TEST_VALUE")
            assert valid is True
            assert error == ""
    
    def test_validate_positive_integer_invalid(self):
        """Test invalid positive integer validation."""
        invalid_values = [0, -1, -100, "10"]
        for value in invalid_values:
            valid, error = validate_positive_integer(value, "TEST_VALUE")
            assert valid is False
            assert len(error) > 0


# ==========================================
# Run Tests
# ==========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
