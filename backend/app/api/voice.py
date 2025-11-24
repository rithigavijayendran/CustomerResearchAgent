"""
Voice API endpoints with STT/TTS support
Supports both OpenAI Whisper (STT) and browser-based speech recognition
"""

from fastapi import APIRouter, Request, HTTPException
from app.models.schemas import VoiceInput, VoiceResponse
import base64
import io
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()

def _transcribe_with_openai(audio_data: bytes) -> Optional[str]:
    """Transcribe audio using OpenAI Whisper API"""
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set - Whisper transcription unavailable")
            return None
        
        client = OpenAI(api_key=api_key)
        
        # Create a file-like object from audio bytes
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.webm"  # or .wav, .mp3, etc.
        
        # Call Whisper API
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        return transcript.text.strip()
    
    except ImportError:
        logger.warning("OpenAI library not installed - install with: pip install openai")
        return None
    except Exception as e:
        logger.error(f"OpenAI Whisper transcription error: {e}")
        return None

@router.post("/transcribe", response_model=VoiceResponse)
async def transcribe_voice(voice_input: VoiceInput, request: Request):
    """Transcribe voice input to text using OpenAI Whisper or browser SpeechRecognition"""
    try:
        # Decode base64 audio
        # Handle data URL format: "data:audio/webm;base64,..."
        audio_data_str = voice_input.audio_data
        if "," in audio_data_str:
            audio_data_str = audio_data_str.split(",", 1)[1]
        
        audio_data = base64.b64decode(audio_data_str)
        
        # Get session
        session_memory = request.state.session_memory
        session_id = voice_input.session_id
        if not session_id:
            session_id = session_memory.create_session()
        
        # Try OpenAI Whisper first (if API key is available)
        transcribed_text = _transcribe_with_openai(audio_data)
        
        if transcribed_text:
            logger.info(f"Successfully transcribed audio using Whisper: {len(transcribed_text)} characters")
            return VoiceResponse(
                text=transcribed_text,
                session_id=session_id
            )
        
        # Fallback: Return message indicating voice was received but transcription needs setup
        logger.info("Voice input received but transcription not configured - returning placeholder")
        return VoiceResponse(
            text="Voice input received! For full transcription, please configure OPENAI_API_KEY in backend/.env and install openai: pip install openai. For now, you can use the browser's built-in speech recognition.",
            session_id=session_id
        )
    
    except Exception as e:
        logger.error(f"Voice transcription error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Voice transcription failed: {str(e)}. Please check backend logs."
        )

@router.post("/synthesize")
async def synthesize_voice(text: str, request: Request):
    """Synthesize text to speech using OpenAI TTS or browser SpeechSynthesis"""
    try:
        # Try OpenAI TTS first (if API key is available)
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                
                # Generate speech using OpenAI TTS
                response = client.audio.speech.create(
                    model="tts-1",  # or "tts-1-hd" for higher quality
                    voice="alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
                    input=text[:4096]  # Limit to 4096 characters
                )
                
                # Convert to base64 for frontend
                audio_bytes = response.content
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                return {
                    "audio_url": f"data:audio/mp3;base64,{audio_base64}",
                    "message": "Speech synthesized successfully",
                    "format": "mp3"
                }
            except ImportError:
                logger.warning("OpenAI library not installed - install with: pip install openai")
            except Exception as e:
                logger.warning(f"OpenAI TTS error: {e} - falling back to browser TTS")
        
        # Fallback: Return message indicating browser TTS should be used
        return {
            "audio_url": None,
            "message": "TTS synthesis available via browser SpeechSynthesis API. For server-side TTS, configure OPENAI_API_KEY and install openai: pip install openai",
            "format": "browser"
        }
    
    except Exception as e:
        logger.error(f"Voice synthesis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Voice synthesis failed: {str(e)}. Please check backend logs."
        )

