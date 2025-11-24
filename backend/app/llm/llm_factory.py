"""
LLM Factory - Creates Gemini LLM engine
Only Gemini is supported
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LLMFactory:
    """Factory for creating LLM engines - Gemini only"""
    
    @staticmethod
    def create_llm_engine(provider: Optional[str] = None):
        """
        Create Gemini LLM engine
        
        Args:
            provider: Optional provider override (ignored, always uses Gemini)
        
        Returns:
            GeminiEngine
            
        Raises:
            ValueError: If Gemini cannot be initialized
        """
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment variables. "
                "Please set GEMINI_API_KEY in backend/.env file. "
                "Get your API key at: https://makersuite.google.com/app/apikey"
            )
        
        try:
            from app.llm.gemini_engine import GeminiEngine
            logger.info("Initializing Gemini engine...")
            gemini_engine = GeminiEngine()
            logger.info("✅ Gemini engine initialized successfully")
            return gemini_engine
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to initialize Gemini engine: {error_msg}")
            raise ValueError(
                f"Failed to initialize Gemini engine: {error_msg}. "
                f"Please check your GEMINI_API_KEY in backend/.env file."
            )
    
    @staticmethod
    def get_llm_model_name(provider: Optional[str] = None) -> str:
        """Get Gemini model name"""
        return os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

