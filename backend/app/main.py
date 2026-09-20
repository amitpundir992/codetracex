from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import repositories, analysis, retrieval, git_history, api_endpoints, workflow, semantic_search, hybrid_search, rag_context, ask
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
app.include_router(retrieval.router)  # Phase 4: Retrieval endpoints
app.include_router(git_history.router, prefix="/api")  # Phase 6: Git history endpoints
app.include_router(api_endpoints.router, prefix="/api")  # Phase 7: API endpoints
app.include_router(workflow.router, prefix="/api")  # Phase 8: Workflow endpoints
app.include_router(semantic_search.router)  # Phase 9: Semantic search endpoints
app.include_router(hybrid_search.router)  # Phase 10: Hybrid search endpoints
app.include_router(rag_context.router)  # Phase 11: RAG context endpoints
app.include_router(ask.router)  # Phase 12: LLM Ask endpoints


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
