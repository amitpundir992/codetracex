"""
CodeTraceX FastAPI application.

Phase 15: Production Hardening
- Structured logging with request correlation
- Centralized error handling
- Health and readiness checks
- Configuration validation
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    repositories, analysis, retrieval, git_history, api_endpoints,
    workflow, semantic_search, hybrid_search, rag_context, ask,
    impact_analysis, jobs, health, investigation
)
from app.core.config import get_settings
from app.core.config_validation import validate_configuration, ConfigurationError
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.error_handlers import (
    validation_exception_handler,
    http_exception_handler,
    safe_api_error_handler,
    generic_exception_handler,
    SafeAPIError
)
from app.utils.logging_config import configure_logging

# Get settings
settings = get_settings()

# Configure logging
log_level = "DEBUG" if settings.APP_ENV == "development" else "INFO"
use_json = settings.APP_ENV == "production"
configure_logging(level=log_level, use_json=use_json)

logger = logging.getLogger(__name__)

# Validate configuration at startup (skip in test mode)
if settings.APP_ENV != "test":
    try:
        validate_configuration()
    except ConfigurationError as e:
        logger.critical(f"Configuration validation failed: {e}")
        raise

logger.info("=" * 60)
logger.info("Starting CodeTraceX API")
logger.info("=" * 60)

# Create FastAPI application
app = FastAPI(
    title="CodeTraceX API",
    description="AI-powered repository intelligence platform",
    version="0.1.0"
)

# Add middleware
# Order matters: request ID must be first to set context for logging
app.add_middleware(RequestIDMiddleware)

# CORS middleware configured from environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(SafeAPIError, safe_api_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include routers
app.include_router(health.router)  # Phase 15: Health checks
app.include_router(repositories.router)
app.include_router(analysis.router)
app.include_router(retrieval.router)  # Phase 4: Retrieval endpoints
app.include_router(git_history.router, prefix="/api")  # Phase 6: Git history endpoints
app.include_router(api_endpoints.router, prefix="/api")  # Phase 7: API endpoints
app.include_router(workflow.router, prefix="/api")  # Phase 8: Workflow endpoints
app.include_router(semantic_search.router)  # Phase 9: Semantic search endpoints
app.include_router(hybrid_search.router)  # Phase 10: Hybrid search endpoints
app.include_router(rag_context.router)  # Phase 11: RAG context endpoints
app.include_router(ask.router)  # Phase 12: LLM Ask endpoints
app.include_router(impact_analysis.router)  # Phase 13: Impact Analysis endpoints
app.include_router(jobs.router)  # Phase 14: Background Jobs endpoints
app.include_router(investigation.router, prefix="/api")  # Phase 16: Investigation endpoints


@app.get("/")
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": "CodeTraceX API",
        "version": "0.1.0",
        "docs": "/docs"
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup tasks."""
    logger.info("CodeTraceX API started successfully")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Docs available at: /docs")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks."""
    logger.info("Shutting down CodeTraceX API")
    
    # Close database connections
    from app.db.session import close_db_connections
    try:
        close_db_connections()
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
    logger.info("CodeTraceX API shutdown complete")
