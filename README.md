# CodeTraceX

**AI-powered repository intelligence platform for developers**

CodeTraceX is designed to help developers understand unfamiliar repositories by analyzing source code, documentation, API endpoints, dependencies, and git history to build a comprehensive knowledge graph combined with RAG and LLM capabilities.

## 🎯 Project Status

**Current Phase:** Phase 3 — Static Code Analysis ✅

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

### Planned 🚧
- Database persistence (PostgreSQL)
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
- **Tree-sitter** - Multi-language code parser
- **Python AST** - Python code analysis
- PostgreSQL (planned) - Primary database
- pgvector (planned) - Vector similarity search
- Redis (planned) - Caching and job queue

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS framework

### Future Additions
- Background workers - Async job processing
- LLM integration - Natural language understanding
- Docker - Containerization

## 📁 Repository Structure

```
CodeTraceX/
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── main.py       # FastAPI application entry point
│   │   ├── api/          # API route handlers
│   │   ├── core/         # Configuration and settings
│   │   ├── models/       # Database models (future)
│   │   ├── schemas/      # Pydantic schemas for validation
│   │   ├── services/     # Business logic layer
│   │   └── utils/        # Helper functions
│   ├── tests/            # Backend tests
│   ├── requirements.txt  # Python dependencies
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
├── docs/                 # Documentation (future)
├── docker/               # Docker configuration (future)
├── docker-compose.yml    # Multi-container orchestration
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or higher
- Node.js 18 or higher
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create and activate a virtual environment:

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

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create environment file:
```bash
copy .env.example .env  # Windows
cp .env.example .env    # macOS/Linux
```

5. Start the FastAPI development server:
```bash
uvicorn app.main:app --reload
```

The backend will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create environment file:
```bash
copy .env.example .env.local  # Windows
cp .env.example .env.local    # macOS/Linux
```

4. Start the Next.js development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

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

**GET** `/docs`
- Interactive API documentation (Swagger UI)
- Automatically generated by FastAPI

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

## 🐳 Docker (Optional)

Note: Docker configuration will be completed in a future phase.

```bash
docker-compose up
```

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
