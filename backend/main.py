"""
Company Research Assistant - FastAPI Backend
Main entry point for the backend server
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Will be logged after logging setup
    pass

# Disable ChromaDB telemetry to prevent PostHog errors
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# Setup production-grade logging BEFORE other imports
from app.logging_config import setup_logging
setup_logging()

import logging
logger = logging.getLogger(__name__)

# Log .env loading status
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    logger.info(f"Loaded .env file from {env_path}")
else:
    logger.warning(f".env file not found at {env_path}")

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from app.api import chat, voice, files, account_plan, health, pdf_export, auth, chats, websocket, uploads, plans
from app.api import voice_backend
from app.rag.vector_store import VectorStore
from app.agent.memory import SessionMemory
from app.config import VECTOR_DB_PATH
from app.database import connect_to_mongo, close_mongo_connection
from app.middleware.rate_limit import rate_limit_middleware

# Global state
vector_store = None
session_memory = SessionMemory()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    global vector_store
    
    # Connect to MongoDB
    mongo_connected = await connect_to_mongo()
    if not mongo_connected:
        logger.warning("MongoDB connection failed - some features may be limited")
    
    # Initialize vector store (non-blocking - don't wait for model download)
    try:
        os.makedirs(VECTOR_DB_PATH, exist_ok=True)
        logger.info(f"Initializing vector store at {VECTOR_DB_PATH}...")
        logger.info("Note: Embedding model download may take time on first run. Server will start anyway.")
        
        # Initialize in background to avoid blocking server startup
        vector_store = VectorStore(VECTOR_DB_PATH)
        # Log the actual path being used (may differ if auto-reset created new path)
        actual_path = vector_store.db_path if vector_store else VECTOR_DB_PATH
        logger.info(f"✅ Vector store initialized at {actual_path}")
    except ValueError as e:
        # Schema error - provide helpful instructions
        error_msg = str(e)
        if "schema" in error_msg.lower() or "no such column" in error_msg.lower():
            logger.error(f"Vector store initialization error: {e}")
            logger.error("ChromaDB schema incompatibility detected!")
            logger.error("To fix this, run: python reset_vector_db.py")
            logger.error("Or manually delete the vector_db folder and restart.")
        else:
            logger.error(f"Vector store initialization error: {e}")
        logger.warning("Server will continue but RAG features may be limited")
        vector_store = None
    except Exception as e:
        logger.error(f"Vector store initialization error: {e}")
        logger.warning("Server will continue but RAG features may be limited")
        vector_store = None
    
    # Check LLM availability (quick check - just verify API keys, don't initialize)
    try:
        gemini_key = os.getenv("GEMINI_API_KEY")
        
        if gemini_key:
            logger.info("✅ GEMINI_API_KEY found - Gemini will be used")
        else:
            logger.warning("⚠️ GEMINI_API_KEY not found in .env file")
            logger.warning("⚠️ Please set GEMINI_API_KEY in backend/.env file")
            logger.warning("⚠️ Get your API key at: https://makersuite.google.com/app/apikey")
    except Exception as e:
        logger.warning(f"⚠️ LLM configuration check failed: {e}")
    
    yield
    
    # Cleanup
    if vector_store:
        try:
            vector_store.close()
            logger.info("Vector store closed")
        except:
            pass
    
    # Close MongoDB connection
    await close_mongo_connection()

app = FastAPI(
    title="Company Research Assistant API",
    description="Enterprise-grade Agentic AI system for company research and account planning",
    version="1.0.0",
    lifespan=lifespan
)

# Global exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with proper logging"""
    # Handle client disconnection gracefully
    from anyio import EndOfStream
    from starlette.responses import Response
    if isinstance(exc, EndOfStream):
        # Client disconnected, don't try to send response
        logger.debug("Client disconnected (EndOfStream)")
        # Return an empty response that won't try to send data
        # This prevents trying to send to a disconnected client
        return Response(status_code=204)  # No Content - won't send body
    
    # Don't log client disconnection errors as errors
    if "client disconnected" in str(exc).lower() or "connection closed" in str(exc).lower() or "endofstream" in str(exc).lower():
        logger.debug(f"Client disconnected: {exc}")
        try:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"detail": "Client disconnected"}
            )
        except Exception:
            return None
    
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else "unknown"
        }
    )
    
    try:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred. Please try again or contact support.",
                "detail": str(exc) if os.getenv("DEBUG", "false").lower() == "true" else None
            }
        )
    except Exception:
        # If we can't send response, return None
        return None

# Request validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "message": "Invalid request data. Please check your input.",
            "details": exc.errors()
        }
    )

# CORS middleware - allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    try:
        return await rate_limit_middleware(request, call_next)
    except Exception as e:
        # Handle client disconnection in middleware
        from anyio import EndOfStream
        from starlette.responses import Response
        if isinstance(e, EndOfStream):
            logger.debug("Client disconnected during rate limit check")
            # Return empty response - won't try to send to disconnected client
            return Response(status_code=204)  # No Content
        raise

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])  # Legacy chat endpoint
app.include_router(chats.router, prefix="/api/chats", tags=["chats"])  # New production chat endpoints
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
app.include_router(voice_backend.router, prefix="/api/voice", tags=["voice"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(account_plan.router, prefix="/api/account-plan", tags=["account-plan"])
app.include_router(pdf_export.router, prefix="/api/account-plan", tags=["account-plan"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(plans.router, prefix="/api/plans", tags=["plans"])

# Metrics endpoint
try:
    from app.api import metrics
    app.include_router(metrics.router, prefix="/api", tags=["metrics"])
except ImportError:
    logger.warning("Prometheus client not available. Metrics endpoint disabled.")

# Static file serving for avatars
import os
from pathlib import Path
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
avatars_dir = uploads_dir / "avatars"
avatars_dir.mkdir(exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# WebSocket routes (no prefix, handled differently)
from fastapi import WebSocket
app.websocket("/ws/chats/{chat_id}/stream")(websocket.chat_stream)

@app.get("/")
async def root():
    return {
        "message": "Company Research Assistant API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Make vector_store available to routes
@app.middleware("http")
async def add_vector_store(request, call_next):
    try:
        request.state.vector_store = vector_store
        request.state.session_memory = session_memory
        response = await call_next(request)
        return response
    except Exception as e:
        # Handle client disconnection gracefully
        from anyio import EndOfStream
        from starlette.responses import Response
        if isinstance(e, EndOfStream):
            logger.debug("Client disconnected during request processing")
            # Return empty response - won't try to send to disconnected client
            return Response(status_code=204)  # No Content
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

