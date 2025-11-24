# 🚀 Company Research Assistant & Account Plan Generator

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![Node](https://img.shields.io/badge/node-18+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

**An Enterprise-Grade Agentic AI System for Autonomous Company Research & Account Planning**

[Features](#-features) • [Architecture](#-system-architecture) • [Algorithms](#-core-algorithms) • [Quick Start](#-quick-start) • [API Docs](#-api-documentation)

</div>

---

## 🎯 Use Case

**Company Research Assistant (Account Plan Generator)** - An intelligent, interactive AI agent that revolutionizes how businesses research companies and generate comprehensive account plans through natural conversation.

### What It Does

The system autonomously:
- 🔍 **Researches companies** through natural language (chat or voice)
- 📚 **Gathers information** from multiple sources (web, PDFs, documents)
- ⚠️ **Detects conflicts** and asks clarifying questions ("I'm finding conflicting information about X, should I dig deeper?")
- 📝 **Synthesizes findings** into structured, professional account plans
- ✏️ **Allows real-time editing** of any section with full version control

### Key Differentiators

✨ **True Agentic Behavior** - Not just a chatbot, but an autonomous agent that plans, executes, and adapts  
🧠 **Multi-Step Reasoning** - Plans workflow before execution, thinks before acting  
🔗 **RAG-Powered** - All knowledge retrieval uses Retrieval-Augmented Generation for accuracy  
⚡ **Real-Time Updates** - WebSocket streaming keeps users informed during long operations  
🎯 **Conflict Detection** - Identifies contradictions and asks for clarification  

---

## 🎯 Features

### Core Capabilities

| Feature | Description | Technology |
|---------|-------------|------------|
| **🤖 Conversational Agent** | Natural language interaction with real-time progress updates | FastAPI WebSocket + React |
| **🔍 Multi-Step Research** | Agent plans workflow, gathers data, detects conflicts | Agent Controller + LLM Planning |
| **📚 RAG Pipeline** | Full pipeline from document ingestion to vector search | ChromaDB + Sentence Transformers |
| **🌐 Multi-Source Research** | PDFs, PPTX, DOCX, TXT, web search, company websites | Serper API + Firecrawl |
| **⚠️ Conflict Detection** | Identifies contradictions with user-friendly prompts | LLM-based Comparison Engine |
| **📝 Account Plan Generation** | Structured, editable JSON with section-level updates | Gemini Pro + Structured Output |
| **🎤 Voice + Chat** | Browser-based STT/TTS with chat UI | Web Speech API |
| **💾 Session Memory** | Maintains context across interactions | MongoDB + In-Memory Cache |

### Production-Ready Features

- ✅ **Production-Grade Error Handling** - Comprehensive error handling with user-friendly messages
- ✅ **Structured Logging** - Rotating log files with different log levels (app.log, errors.log)
- ✅ **Performance Optimized** - Async processing, connection pooling, efficient vector search
- ✅ **Security** - JWT authentication, input validation, CORS configuration, API key management
- ✅ **Monitoring Ready** - Health checks, structured logging, Prometheus metrics
- ✅ **Scalable Architecture** - Stateless API, horizontal scaling, background workers

---

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  React UI    │  │  WebSocket   │  │  Voice Hook  │              │
│  │  Components  │  │  Client      │  │  (STT/TTS)   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                       │
└─────────┼─────────────────┼──────────────────┼───────────────────────┘
          │ HTTP/REST       │ WebSocket        │ Voice API
          │                 │                  │
┌─────────┼─────────────────┼──────────────────┼───────────────────────┐
│         │                 │                  │   API GATEWAY LAYER   │
│  ┌──────▼──────────┐  ┌───▼──────────┐  ┌───▼──────────┐           │
│  │  FastAPI       │  │  WebSocket   │  │  Auth        │           │
│  │  REST API      │  │  Server      │  │  Middleware  │           │
│  └──────┬─────────┘  └───┬───────────┘  └───┬──────────┘           │
│         │                 │                  │                       │
│  ┌──────▼─────────────────▼──────────────────▼──────────┐          │
│  │           ORCHESTRATOR LAYER                          │          │
│  │  ┌──────────────┐  ┌──────────────┐                  │          │
│  │  │ Query Router │  │ Cache Mgr    │                  │          │
│  │  │ Validation   │  │ (SERP 1-6h)  │                  │          │
│  │  └──────────────┘  └──────────────┘                  │          │
│  └───────────────────────────────────────────────────────┘          │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │              AGENT CONTROLLER (THE BRAIN)                 │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │     │
│  │  │ Multi-Step   │  │ Conflict     │  │ Memory       │  │     │
│  │  │ Planner      │  │ Detector     │  │ Management   │  │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │     │
│  └───────────────────────────────────────────────────────────┘     │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │              RAG PIPELINE                                  │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │     │
│  │  │ Document     │  │ Vector Store │  │ Retrieval    │  │     │
│  │  │ Processor    │  │ (ChromaDB)   │  │ API          │  │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │     │
│  └───────────────────────────────────────────────────────────┘     │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │              TOOLS LAYER                                  │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │     │
│  │  │ Web Search   │  │ Entity       │  │ Conflict     │  │     │
│  │  │ (Serper API) │  │ Extractor    │  │ Detector     │  │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │     │
│  └───────────────────────────────────────────────────────────┘     │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │              LLM LAYER                                    │     │
│  │  ┌──────────────┐  ┌──────────────┐                      │     │
│  │  │ Gemini Pro   │  │ Account Plan │                      │     │
│  │  │ Engine       │  │ Generator    │                      │     │
│  │  └──────────────┘  └──────────────┘                      │     │
│  └───────────────────────────────────────────────────────────┘     │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │              DATA LAYER                                    │     │
│  │  ┌──────────────┐  ┌──────────────┐                      │     │
│  │  │ MongoDB      │  │ ChromaDB    │                      │     │
│  │  │ (Documents)  │  │ (Vectors)   │                      │     │
│  │  └──────────────┘  └──────────────┘                      │     │
│  └───────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. **Orchestrator Layer**
- **Query Router**: Validates requests, routes to appropriate handlers
- **Cache Manager**: Caches SERP results (1-6 hour TTL), reduces API calls
- **Request Validation**: Input sanitization, rate limiting

#### 2. **Agent Controller (The Brain)**
- **Multi-Step Planner**: Plans workflow before execution
- **Conflict Detector**: Identifies contradictory information
- **Memory Management**: Maintains conversation context

#### 3. **RAG Pipeline**
- **Document Processor**: Extracts text from PDFs, DOCX, PPTX, TXT
- **Vector Store**: ChromaDB for semantic search
- **Retrieval API**: Top-K retrieval with relevance scoring

#### 4. **Tools Layer**
- **Web Search**: Serper API (top 10 results) + Firecrawl (top 5 deep scrape)
- **Entity Extractor**: Extracts revenue, profit, employees, products, competitors
- **Conflict Detector**: Compares information from multiple sources

#### 5. **LLM Layer**
- **Gemini Engine**: Primary LLM for reasoning and generation
- **Account Plan Generator**: Generates structured JSON account plans

#### 6. **Data Layer**
- **MongoDB**: Stores users, chats, messages, account plans with version history
- **ChromaDB**: Vector embeddings for semantic search

---

## 🧠 Core Algorithms

### 1. Multi-Step Agent Planning Algorithm

```python
Algorithm: Agent Research Workflow
Input: user_message, session_id
Output: account_plan_json

1. INTENT_DETECTION
   - Analyze message with conversation context
   - Classify: research_company | update_section | clarify | general

2. IF intent == research_company:
   
   2.1 COMPANY_IDENTITY_DISCOVERY
       - Extract company name from message
       - Validate company exists
       - Store in session memory
   
   2.2 DATA_GATHERING (Parallel)
       - RAG_RETRIEVAL: Query vector store for company documents
       - WEB_SEARCH: Search web for company information
       - ENTITY_EXTRACTION: Extract structured data (revenue, products, etc.)
   
   2.3 CONFLICT_DETECTION
       - Compare values from different sources
       - Calculate confidence scores
       - IF conflicts found:
         - Generate user-friendly conflict message
         - ASK_USER_CLARIFICATION
         - Wait for user response
         - Update data based on user input
   
   2.4 SYNTHESIS
       - Combine all gathered data
       - Generate account plan sections:
         * Company Overview
         * Financial Summary
         * Products & Services
         * Key People
         * SWOT Analysis
         * Competitors
         * Strategic Recommendations
       - Add source attribution
       - Calculate confidence scores
   
   2.5 ACCOUNT_PLAN_GENERATION
       - Structure as JSON
       - Save to MongoDB
       - Return to user

3. ELSE IF intent == update_section:
   - Identify section to update
   - Regenerate section with new context
   - Update version history
   - Return updated section

4. ELSE:
   - General conversation handling
   - Context-aware responses
```

### 2. RAG (Retrieval-Augmented Generation) Pipeline

```python
Algorithm: RAG Knowledge Retrieval
Input: query, company_name, user_id
Output: relevant_chunks_with_scores

1. QUERY_EMBEDDING
   - Encode query using Sentence Transformers
   - Model: all-MiniLM-L6-v2 (384 dimensions)

2. VECTOR_SEARCH
   - Search ChromaDB with metadata filters:
     * user_id == current_user
     * company_name == target_company
   - Top-K retrieval (K=5-10)
   - Cosine similarity scoring

3. RELEVANCE_FILTERING
   - Filter chunks with score < 0.7
   - Sort by relevance score (descending)

4. CONTEXT_AUGMENTATION
   - Combine top-K chunks
   - Add metadata (source, timestamp, confidence)
   - Format for LLM context

5. GENERATION
   - Send query + context to Gemini
   - Generate answer grounded in retrieved context
   - Return answer + sources
```

### 3. Conflict Detection Algorithm

```python
Algorithm: Conflict Detection
Input: data_from_multiple_sources
Output: conflicts_list, user_prompts

1. ENTITY_EXTRACTION
   - Extract entities from each source:
     * Revenue
     * Profit
     * Employee count
     * Products
     * Key people
     * Competitors

2. VALUE_COMPARISON
   FOR each entity_type:
     - Collect all values from different sources
     - Normalize values (units, formats)
     - Calculate statistical variance
   
3. CONFLICT_IDENTIFICATION
   FOR each entity:
     IF variance > threshold:
       - Mark as conflict
       - Store conflicting values
       - Store source URLs
   
4. CONFLICT_SCORING
   - Calculate confidence for each value
   - Weight by source credibility
   - Generate conflict score
   
5. USER_PROMPT_GENERATION
   IF conflicts found:
     - Generate natural language prompt:
       "I'm finding conflicting information about {entity}.
        Source A says {value_A}, Source B says {value_B}.
        Should I dig deeper?"
     - Return to user
     - Wait for user response
   
6. RESOLUTION
   - Based on user input:
     * "Yes, dig deeper" → Additional research
     * "Use Source A" → Update with Source A value
     * "Use latest" → Use most recent value
```

### 4. Account Plan Generation Algorithm

```python
Algorithm: Account Plan Generation
Input: synthesized_data, company_name
Output: structured_account_plan_json

1. SECTION_GENERATION (Parallel where possible)
   FOR each section in [overview, financial, products, swot, competitors, strategy]:
     - Generate section content using Gemini
     - Add source attribution
     - Calculate confidence score
     - Validate JSON structure

2. STRUCTURED_OUTPUT
   - Format as JSON matching exact schema:
     {
       "company_name": str,
       "company_overview": str,
       "financial_summary": {
         "revenue": {"value": str, "source": [str], "confidence": float},
         "profit": {"value": str, "source": [str], "confidence": float}
       },
       "products_services": str,
       "key_people": [{"name": str, "title": str, "source": str}],
       "swot": {
         "strengths": str,
         "weaknesses": str,
         "opportunities": str,
         "threats": str
       },
       "competitors": [{"name": str, "reason": str, "source": str}],
       "recommended_strategy": str,
       "sources": [{"url": str, "type": str, "extracted_at": str}],
       "last_updated": str
     }

3. VALIDATION
   - Validate all required fields present
   - Validate JSON structure
   - Validate data types

4. PERSISTENCE
   - Save to MongoDB
   - Create version history entry
   - Return plan_id
```

### 5. WebSocket Streaming Algorithm

```python
Algorithm: Real-Time Streaming
Input: user_message, chat_id
Output: streamed_response

1. CONNECTION_ESTABLISHMENT
   - Accept WebSocket connection
   - Authenticate user (JWT token)
   - Verify chat ownership

2. MESSAGE_PROCESSING
   - Send message to Agent Controller
   - Agent processes in background

3. PROGRESS_STREAMING
   WHILE agent is processing:
     - Send progress updates:
       * "🔍 Discovering company identity..."
       * "📚 Searching web sources..."
       * "⚠️ Found conflicting information..."
     - Stream via WebSocket

4. TOKEN_STREAMING
   WHEN LLM generates response:
     - Stream tokens one-by-one
     - Update frontend in real-time
     - Maintain connection alive

5. COMPLETION
   - Send completion signal
   - Send final response
   - Close stream (keep connection for next message)
```

---

## 📊 Data Flow

### Research Workflow Data Flow

```
User Input: "Research Microsoft"
    │
    ├─► Intent Detection
    │   └─► Classify: research_company
    │
    ├─► Company Identity Discovery
    │   └─► Extract: "Microsoft"
    │
    ├─► Data Gathering (Parallel)
    │   ├─► RAG Retrieval
    │   │   ├─► Query Vector Store
    │   │   ├─► Semantic Search
    │   │   └─► Return: 5-10 relevant chunks
    │   │
    │   ├─► Web Search
    │   │   ├─► Serper API (top 10 results)
    │   │   ├─► Firecrawl (top 5 deep scrape)
    │   │   └─► Return: structured data
    │   │
    │   └─► Entity Extraction
    │       ├─► Extract: revenue, profit, products, etc.
    │       └─► Return: structured entities
    │
    ├─► Conflict Detection
    │   ├─► Compare values from sources
    │   ├─► IF conflicts:
    │   │   └─► Ask user: "I'm finding conflicting information..."
    │   └─► Wait for user response
    │
    ├─► Synthesis
    │   ├─► Combine all data
    │   ├─► Generate account plan sections
    │   └─► Add source attribution
    │
    └─► Account Plan Generation
        ├─► Structure as JSON
        ├─► Save to MongoDB
        └─► Return to user
```

### RAG Pipeline Data Flow

```
Document Upload
    │
    ├─► Document Processing
    │   ├─► Extract text (PDF/DOCX/PPTX/TXT)
    │   ├─► Clean HTML/boilerplate
    │   └─► Chunk text (500-800 chars, 100-char overlap)
    │
    ├─► Embedding Generation
    │   ├─► Encode chunks with Sentence Transformers
    │   └─► Generate 384-dim vectors
    │
    ├─► Vector Storage
    │   ├─► Store in ChromaDB
    │   ├─► Add metadata:
    │   │   * user_id
    │   │   * company_name
    │   │   * source_url
    │   │   * timestamp
    │   └─► Index for fast retrieval
    │
    └─► Ready for Retrieval

Query: "What is Microsoft's revenue?"
    │
    ├─► Query Embedding
    │   └─► Encode query to vector
    │
    ├─► Vector Search
    │   ├─► Search ChromaDB with metadata filters
    │   ├─► Cosine similarity scoring
    │   └─► Return top-K chunks
    │
    ├─► Context Augmentation
    │   └─► Combine chunks + metadata
    │
    └─► LLM Generation
        ├─► Send query + context to Gemini
        └─► Generate answer: "Microsoft's revenue is $211B (2023)"
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **MongoDB 7.0+** (or use Docker Compose)
- **Redis** (optional, for rate limiting)
- **API Keys:**
  - **Gemini API key** (required) - [Get one here](https://makersuite.google.com/app/apikey)
  - **Serper API key** (recommended) - [Get one here](https://serper.dev)
  - **Firecrawl API key** (optional) - [Get one here](https://firecrawl.dev)

### Installation

#### Option 1: Docker Compose (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd Company_Research_Assistant

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

cp frontend/.env.example frontend/.env.local
# Edit frontend/.env.local if needed

# Start all services
docker-compose up -d

# Access application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

#### Option 2: Manual Setup

**Backend:**

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run backend
uvicorn main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local if needed

# Run frontend
npm run dev
```

Visit `http://localhost:3000` to use the application.

---

## 📖 Usage Guide

### Basic Workflow

1. **Register/Login** - Create an account or login
2. **Upload Documents** (Optional) - Upload PDFs, DOCX, PPTX, or TXT files about the company
3. **Start Research** - Type or speak: "Research Microsoft" or "Analyze Apple Inc."
4. **Agent Works** - Watch the agent:
   - 🔍 Discover company identity
   - 📚 Collect data from multiple sources
   - 🔎 Detect conflicts
   - ❓ Ask for clarification if needed
   - 📝 Generate account plan
5. **Review Plan** - View the generated account plan
6. **Edit Sections** - Click edit icon to modify any section
7. **Download** - Export as PDF or JSON

### Example Interactions

**User:** "Research Microsoft Corporation"

**Agent:** 
```
🔍 Discovering company identity...
📚 Searching web sources... Found 15 sources
📄 Processing uploaded documents... Found 3 PDFs
⚠️ I'm finding conflicting information about Microsoft's revenue.
   Source A says $200B, Source B says $180B. Should I dig deeper?
```

**User:** "Yes, check the latest annual report"

**Agent:**
```
📊 Checking annual report... Found official figure: $211B
✅ Synthesizing findings into account plan...
📝 Account plan generated! View it here...
```

---

## 🔧 Configuration

### Backend Environment Variables

Create `backend/.env`:

```bash
# Required
GEMINI_API_KEY=your-gemini-api-key
JWT_SECRET=your-secret-key  # Generate with: python GENERATE_JWT_SECRET.py

# Recommended
SERPER_API_KEY=your-serper-api-key
FIRECRAWL_API_KEY=your-firecrawl-api-key
MONGODB_URL=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379

# Optional
ENVIRONMENT=production
DEBUG=false
VECTOR_DB_PATH=./vector_db
MAX_CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### Frontend Environment Variables

Create `frontend/.env.local`:

```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

---

## 📚 API Documentation

Once the backend is running:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | User registration |
| `/api/auth/login` | POST | User login |
| `/api/chats` | GET | List user chats |
| `/api/chats/{id}/messages` | POST | Send message |
| `/ws/chats/{id}/stream` | WebSocket | Real-time streaming |
| `/api/plans` | GET | List account plans |
| `/api/plans/{id}` | GET | Get account plan |
| `/api/uploads/init` | POST | Initialize file upload |

---

## 🏗️ Project Structure

```
Company_Research_Assistant/
├── backend/
│   ├── app/
│   │   ├── agent/              # Agent controller & multi-step planning
│   │   ├── api/                # FastAPI endpoints
│   │   ├── auth/               # Authentication & authorization
│   │   ├── llm/                # LLM engine & account plan generator
│   │   ├── models/             # Pydantic schemas & MongoDB models
│   │   ├── orchestrator/       # Query router, caching, validation
│   │   ├── processing/         # Document preprocessing, chunking, scoring
│   │   ├── rag/                # RAG pipeline, vector store, retrieval
│   │   ├── services/            # Business logic services
│   │   ├── tools/              # Web search, entity extraction, conflict detection
│   │   ├── workers/            # Background tasks (Celery)
│   │   ├── middleware/         # Rate limiting, auth middleware
│   │   └── observability/      # Logging, metrics, tracing
│   ├── main.py                 # FastAPI application entry point
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Docker configuration
│
├── frontend/
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   ├── hooks/              # Custom React hooks
│   │   ├── lib/                # API client & utilities
│   │   ├── contexts/           # React contexts (Auth, etc.)
│   │   └── types/              # TypeScript type definitions
│   ├── package.json            # Node.js dependencies
│   └── Dockerfile              # Docker configuration
│
├── docker-compose.yml          # Docker Compose configuration
├── README.md                   # This file
└── .gitignore                  # Git ignore rules
```

---

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest tests/
```

### Frontend Tests

```bash
cd frontend
npm test
```

---

## 🐛 Troubleshooting

### Common Issues

**Backend Issues:**
- **MongoDB connection failed**: Ensure MongoDB is running and `MONGODB_URL` is correct
- **Vector store initialization error**: Delete `vector_db/` folder and restart
- **API key errors**: Verify `GEMINI_API_KEY` is set correctly in `.env`

**Frontend Issues:**
- **CORS errors**: Check backend CORS settings in `main.py`
- **WebSocket connection failed**: Verify `VITE_WS_URL` matches backend URL
- **Build errors**: Clear cache: `rm -rf node_modules/.vite`

---

## 🤝 Contributing

This is an enterprise-grade system. When contributing:

1. Follow the existing code structure
2. Maintain agentic behavior patterns
3. Ensure RAG is used for all generation tasks
4. Test conflict detection thoroughly
5. Update documentation

---

## 📝 License

MIT License - see LICENSE file for details

---

## 🙏 Acknowledgments

Built with cutting-edge technologies:

- **FastAPI** - High-performance async web framework
- **React + TypeScript + Vite** - Modern frontend stack
- **Google Gemini** - Advanced LLM for reasoning and generation
- **ChromaDB** - Vector database for semantic search
- **MongoDB** - Document database for persistence
- **Sentence Transformers** - State-of-the-art embeddings
- **Serper API** - Web search integration
- **Firecrawl** - Deep web scraping

---

<div align="center">

**⭐ Star this repo if you find it useful! ⭐**

Made with ❤️ for intelligent company research

</div>
