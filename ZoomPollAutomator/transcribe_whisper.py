# transcribe_whisper.py
import whisper
import time
import os
import logging
import soundfile as sf
import threading
import numpy as np # Import numpy for array checks

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()

def get_model():
    """Loads and returns the Whisper tiny.en model (thread-safe lazy loading)."""
    global _model
    with _model_lock:
        if _model is None:
            logger.info("📥 Loading Whisper tiny.en model...")
            try:
                _model = whisper.load_model("tiny.en")
                logger.info("✅ Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"❌ Error loading Whisper model: {e}", exc_info=True)
                raise
    return _model


def transcribe_segment(audio_path: str = "segment.wav") -> str:
    """Enhanced transcription with better error handling."""
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return ""

    try:
        # Validate audio file
        with sf.SoundFile(audio_path) as audio_file:
            if audio_file.frames == 0:
                logger.error("Empty audio file")
                return ""
            if audio_file.samplerate < 8000:
                logger.error("Sample rate too low for reliable transcription")
                return ""

        # Get model with timeout
        try:
            model = get_model()
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return ""

        # Transcribe with improved parameters
        result = model.transcribe(
            audio_path,
            fp16=False,
            temperature=0.0,
            language='en',
            task='transcribe'
        )

        text = result.get("text", "").strip()
        if not text:
            logger.warning("Transcription returned empty text")
        return text

    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        return ""

# ... (if __name__ == "__main__" block for testing)