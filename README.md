# CodeTraceX

**AI-powered repository intelligence platform for developers**

CodeTraceX is designed to help developers understand unfamiliar repositories by analyzing source code, documentation, API endpoints, dependencies, and git history to build a comprehensive knowledge graph combined with RAG and LLM capabilities.

## 🎯 Project Status

**Current Phase:** Phase 4 — PostgreSQL Database Persistence ✅

CodeTraceX is being built incrementally with a focus on deterministic analysis before LLM integration.

### Completed ✅

**Phase 0: Project Scaffolding**
- Backend FastAPI application with health check endpoint
- Frontend Next.js application with landing page
- Basic project structure
- Development environment setup

**Phase 1: GitHub Repository Ingestion**
- GitHub API integration
- Repository URL validation and parsing
- Repository metadata retrieval
- Error handling and API client

**Phase 2: Repository Download & File Scanner**
- Repository archive download with streaming
- Safe ZIP extraction with path traversal protection
- Recursive file scanning with ignore rules
- Language detection and file metadata collection
- Binary file detection
- Repository size and file count limits
- Temporary workspace with automatic cleanup
- Comprehensive test coverage (83 tests passing)

**Phase 3: Static Code Analysis**
- Python AST analyzer for .py files
- Tree-sitter analyzer for .js, .jsx, .ts, .tsx files
- Symbol extraction (functions, classes, methods)
- Import statement detection
- Function call mapping
- Multi-language support (Python, JavaScript, TypeScript)
- Common symbol representation across languages
- Deterministic parsing without code execution
- Comprehensive test coverage

**Phase 4: Database & Persistence**
- PostgreSQL integration with Neon serverless database
- SQLAlchemy ORM with 7 database models
- Alembic migrations for schema management
- Persistence service for storing analysis results
- Retrieval API endpoints for querying data
- Database connection pooling
- Automatic schema creation and updates
- Comprehensive database tests

### Planned 🚧
- Knowledge graph construction
- Vector embeddings with pgvector
- RAG-based question answering
- Impact analysis
- Automatic documentation generation
- Background job processing
- Git history analysis

## 🏗️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **Python 3.11+** - Programming language
- **PostgreSQL** - Primary database (Neon serverless)
- **SQLAlchemy** - ORM for database operations
- **Alembic** - Database migration tool
- **Tree-sitter** - Multi-language code parser
- **Python AST** - Python code analysis
- **python-dotenv** - Environment variable management
- pgvector (planned) - Vector similarity search
- Redis (planned) - Caching and job queue

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS framework
- **shadcn/ui** - UI component library

### Database Schema
- **7 Tables**: repositories, analysis_runs, files, symbols, imports, calls, relationships
- **UUID Primary Keys** - For all tables
- **Cascade Deletes** - Maintain referential integrity
- **Enum Types** - Type-safe status fields

## 📁 Repository Structure

```
CodeTraceX/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── main.py       # FastAPI application entry point
│   │   ├── api/          # API route handlers
│   │   ├── core/         # Configuration and settings
│   │   ├── db/           # Database models and session
│   │   ├── schemas/      # Pydantic schemas for validation
│   │   ├── services/     # Business logic layer
│   │   └── utils/        # Helper functions
│   ├── alembic/          # Database migrations
│   ├── scripts/          # Utility scripts
│   ├── tests/            # Backend tests
│   ├── requirements.txt  # Python dependencies
│   ├── alembic.ini       # Alembic configuration
│   ├── pytest.ini        # Pytest configuration
│   └── .env.example      # Environment variable template
│
├── frontend/             # Next.js frontend
│   ├── app/              # Next.js App Router pages
│   ├── components/       # Reusable UI components
│   ├── lib/              # Utility functions and API client
│   ├── types/            # TypeScript type definitions
│   ├── public/           # Static assets
│   ├── package.json      # Node dependencies
│   └── .env.example      # Environment variable template
│
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or higher
- Node.js 18 or higher
- npm or yarn
- PostgreSQL database (we use Neon serverless, but any PostgreSQL 14+ works)

### Backend Setup

1. **Navigate to the backend directory:**
```bash
cd backend
```

2. **Create and activate a virtual environment:**

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables:**
```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

5. **Configure your database:**

Edit `backend/.env` and update the `DATABASE_URL`:

```env
# For Neon (recommended for development):
DATABASE_URL=postgresql+psycopg://user:password@host/database?sslmode=require

# For local PostgreSQL:
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/codetracex
```

**Option A: Using Neon (Serverless PostgreSQL)**
- Sign up at [neon.tech](https://neon.tech) (free tier available)
- Create a new project
- Copy the connection string to your `.env` file

**Option B: Using Local PostgreSQL**
- Install PostgreSQL 14+
- Create a database: `CREATE DATABASE codetracex;`
- Update `DATABASE_URL` in `.env`

6. **Run database migrations:**
```bash
alembic upgrade head
```

This will create all necessary tables (repositories, analysis_runs, files, symbols, imports, calls, relationships).

7. **Start the FastAPI development server:**
```bash
uvicorn app.main:app --reload
```

The backend will be available at `http://localhost:8000`

**Verify installation:**
- Visit `http://localhost:8000/health` - Should return `{"status":"ok"}`
- Visit `http://localhost:8000/docs` - Interactive API documentation

### Frontend Setup

1. **Navigate to the frontend directory:**
```bash
cd frontend
```

2. **Install dependencies:**
```bash
npm install
```

3. **Create environment file:**
```bash
# Windows
copy .env.example .env.local

# macOS/Linux
cp .env.example .env.local
```

4. **Configure API endpoint (optional):**

Edit `frontend/.env.local` if your backend runs on a different port:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

5. **Start the Next.js development server:**
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Running Tests

**Backend tests:**
```bash
cd backend
pytest                    # Run all tests
pytest tests/test_database_models.py -v  # Run specific test file
```

**Frontend tests:**
```bash
cd frontend
npm test
```

### Common Issues & Troubleshooting

**Database connection errors:**
- Verify your `DATABASE_URL` is correct in `.env`
- Ensure PostgreSQL is running (if using local DB)
- Check firewall settings for Neon cloud connections

**Migration errors:**
- Reset database: `python scripts/reset_database.py` (dev only)
- Re-run migrations: `alembic upgrade head`

**Module import errors:**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

**Port already in use:**
- Backend: Change `APP_PORT` in `.env` or use `uvicorn app.main:app --port 8001`
- Frontend: Use `npm run dev -- -p 3001`

## 📡 API Endpoints

### Current Endpoints

**GET** `/health`
- Health check endpoint
- Returns service status

**Response:**
```json
{
  "status": "ok",
  "service": "codetracex-backend"
}
```

**POST** `/api/repositories`
- Retrieve GitHub repository metadata
- Validates URL and fetches repository information from GitHub API

**Request:**
```json
{
  "url": "https://github.com/facebook/react"
}
```

**Response:**
```json
{
  "name": "react",
  "full_name": "facebook/react",
  "owner": "facebook",
  "description": "The library for web and native user interfaces.",
  "url": "https://github.com/facebook/react",
  "default_branch": "main",
  "visibility": "public",
  "stars": 100000,
  "forks": 20000,
  "language": "JavaScript"
}
```

**POST** `/api/repositories/analyze`
- Download and analyze a GitHub repository
- Scans files, detects languages, collects metadata
- Persists analysis results to database
- Returns file statistics and language distribution

**Request:**
```json
{
  "url": "https://github.com/facebook/react"
}
```

**Response:**
```json
{
  "repository": "facebook/react",
  "status": "completed",
  "repository_id": "uuid-here",
  "analysis_run_id": "uuid-here",
  "total_files": 1200,
  "total_size_bytes": 12845678,
  "languages": {
    "JavaScript": 450,
    "TypeScript": 300
  },
  "files": [...],
  "files_returned": 100
}
```

**GET** `/api/retrieval/repositories`
- List all analyzed repositories with their latest analysis
- Supports pagination

**Query Parameters:**
- `limit` (optional): Number of results per page (default: 50)
- `offset` (optional): Number of results to skip (default: 0)

**GET** `/api/retrieval/repositories/{repository_id}`
- Get detailed information about a specific repository

**GET** `/api/retrieval/repositories/{repository_id}/latest-analysis`
- Get the most recent analysis run for a repository

**GET** `/api/retrieval/repositories/{repository_id}/analyses`
- Get all analysis runs for a repository (paginated)

**GET** `/api/retrieval/symbols/search`
- Search for code symbols across all analyzed repositories

**Query Parameters:**
- `name` (optional): Symbol name pattern
- `symbol_type` (optional): Filter by type (function, class, method, etc.)
- `language` (optional): Filter by programming language
- `limit` (optional): Results per page
- `offset` (optional): Results to skip

**GET** `/docs`
- Interactive API documentation (Swagger UI)
- Automatically generated by FastAPI

## 🛣️ Development Roadmap

1. **Phase 0: Project Scaffolding** ✅
   - Project structure
   - Basic FastAPI backend
   - Basic Next.js frontend

2. **Phase 1: GitHub Repository Ingestion** ✅
   - GitHub API integration
   - URL validation and parsing
   - Repository metadata retrieval

3. **Phase 2: Repository Download & File Scanner** ✅
   - Repository archive download
   - Safe ZIP extraction
   - File scanning and metadata collection

4. **Phase 3: Static Code Analysis** ✅
   - Tree-sitter integration
   - Python AST parsing
   - Symbol extraction
   - Dependency mapping

5. **Phase 4: Database & Storage** (Next)
   - PostgreSQL setup
   - Database models
   - Knowledge graph schema

6. **Phase 5: Vector Search**
   - pgvector integration
   - Embedding generation
   - Similarity search

7. **Phase 6: RAG & LLM**
   - LLM integration
   - RAG pipeline
   - Question answering

8. **Phase 7: Advanced Features**
   - Impact analysis
   - Workflow detection
   - Auto-documentation

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

This project is in early development. Contribution guidelines will be added later.

---

**Note:** This is an early-stage project. Features are being built incrementally with a focus on deterministic analysis before LLM integration.
