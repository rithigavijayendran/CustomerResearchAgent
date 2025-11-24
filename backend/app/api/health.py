"""
Health check and LLM status endpoint
"""

from fastapi import APIRouter, Request
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "ok", "message": "Backend is running"}

@router.get("/llm-status")
async def llm_status():
    """Check Gemini LLM status (fast check without initialization)"""
    try:
        # Quick check based on environment variables (no actual initialization)
        gemini_key = os.getenv("GEMINI_API_KEY")
        
        if gemini_key:
            model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            return {
                "status": "ok",
                "provider": "gemini",
                "engine": "Gemini",
                "model": model,
                "message": "✅ Gemini is configured",
                "api_key_set": True
            }
        else:
            return {
                "status": "error",
                "message": "GEMINI_API_KEY not configured",
                "api_key_set": False,
                "hint": "Set GEMINI_API_KEY in backend/.env file. Get your API key at: https://makersuite.google.com/app/apikey"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error checking LLM status: {str(e)}",
            "error": str(e)
        }

