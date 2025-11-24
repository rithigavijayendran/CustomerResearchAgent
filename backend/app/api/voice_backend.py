"""
Backend voice STT endpoint using Whisper (optional)
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import Optional
import logging
import os

from app.auth.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Check if Whisper is available
try:
    import whisper
    WHISPER_AVAILABLE = True
    model = whisper.load_model("base") if WHISPER_AVAILABLE else None
except ImportError:
    WHISPER_AVAILABLE = False
    model = None
    logger.warning("Whisper not available. Install with: pip install openai-whisper")

@router.post("/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Transcribe audio file using Whisper"""
    if not WHISPER_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Whisper transcription not available. Please install: pip install openai-whisper"
        )
    
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{audio_file.filename}"
        with open(temp_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        # Transcribe using Whisper
        result = model.transcribe(temp_path)
        transcript = result["text"]
        
        # Clean up
        os.remove(temp_path)
        
        return {
            "text": transcript,
            "language": result.get("language", "en")
        }
    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@router.post("/tts")
async def text_to_speech(
    text: str,
    current_user: dict = Depends(get_current_user)
):
    """Text-to-speech endpoint (optional - can use browser SpeechSynthesis instead)"""
    # For production, you might want to use a TTS service like:
    # - Google Cloud Text-to-Speech
    # - Amazon Polly
    # - Azure Cognitive Services
    
    # This is a placeholder - implement based on your TTS service
    raise HTTPException(
        status_code=501,
        detail="Server-side TTS not implemented. Use browser SpeechSynthesis API instead."
    )

