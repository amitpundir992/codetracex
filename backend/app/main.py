from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import repositories, analysis
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="CodeTraceX API",
    description="AI-powered repository intelligence platform",
    version="0.1.0"
)

# CORS middleware configured from environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(repositories.router)
app.include_router(analysis.router)


@app.get("/health")
async def health_check():
    """Health check endpoint to verify the service is running."""
    return {
        "status": "ok",
        "service": "codetracex-backend"
    }


@app.get("/")
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": "CodeTraceX API",
        "version": "0.1.0",
        "docs": "/docs"
    }
