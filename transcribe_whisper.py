# transcribe_whisper.py
import whisper
from rich.console import Console

console = Console()
_model = whisper.load_model("tiny.en")

def transcribe_segment(audio_path: str = "segment.wav") -> str:
    console.log(f"🧠 Transcribing {audio_path} …")
    res  = _model.transcribe(audio_path)
    text = res.get("text", "").strip()
    console.log(f"📝 {text}")
    return text
