# transcribe_whisper.py
import whisper
from rich.console import Console

console = Console()
_model = None  # Lazy loading to avoid slow startup

def get_model():
    global _model
    if _model is None:
        console.log("📥 Loading Whisper tiny.en model...")
        _model = whisper.load_model("tiny.en")
    return _model

def transcribe_segment(audio_path: str = "segment.wav") -> str:
    """Transcribe audio file using Whisper tiny.en model"""
    console.log(f"🧠 Transcribing {audio_path}...")
    model = get_model()
    res = model.transcribe(audio_path)
    text = res.get("text", "").strip()
    console.log(f"📝 {text}")
    return text