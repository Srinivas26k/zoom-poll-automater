# transcribe_whisper.py
import whisper
import time
import os
from rich.console import Console
import torch

console = Console()
_model = None  # Lazy loading to avoid slow startup

def get_model():
    global _model
    if _model is None:
        console.log("📥 Loading Whisper tiny.en model...")
        try:
            # Check CUDA availability
            if torch.cuda.is_available():
                console.log("[green]✓[/] CUDA detected - using GPU acceleration")
            else:
                console.log("[yellow]![/] No GPU detected - using CPU (this will be slower)")

            # Check if model exists in cache
            home = os.path.expanduser("~")
            model_path = os.path.join(home, ".cache", "whisper", "tiny.en.pt")
            if not os.path.exists(model_path):
                console.log("[yellow]![/] Whisper model not found - downloading...")
            
            # Load model
            _model = whisper.load_model("tiny.en")
            console.log("[green]✓[/] Whisper model loaded successfully")
        except Exception as e:
            console.log(f"[red]❌ Error loading Whisper model:[/] {e}")
            console.log("Please ensure you have:")
            console.log("1. A stable internet connection")
            console.log("2. Sufficient disk space")
            console.log("3. Installed all requirements (pip install -r requirements.txt)")
            raise
    return _model

def transcribe_segment(audio_path: str = "segment.wav") -> str:
    """
    Transcribe audio file using Whisper tiny.en model
    
    Args:
        audio_path (str): Path to the audio file to transcribe
        
    Returns:
        str: Transcribed text or empty string if transcription fails
    """
    if not os.path.exists(audio_path):
        console.log(f"[red]❌ Audio file not found:[/] {audio_path}")
        return ""
    
    # Check file size and validity
    try:
        file_size = os.path.getsize(audio_path) / (1024 * 1024)  # Size in MB
        console.log(f"📊 Audio file size: {file_size:.2f} MB")
        
        if file_size < 0.001:
            console.log(f"[yellow]⚠️ Audio file is very small ({file_size:.2f} MB), may contain no audio[/]")
            return ""
        
        if file_size > 100:  # 100MB limit
            console.log(f"[red]❌ Audio file too large ({file_size:.2f} MB)[/]")
            return ""
    except Exception as e:
        console.log(f"[yellow]⚠️ Could not check file size:[/] {e}")
    
    try:
        # Get the model (loads if not already loaded)
        model = get_model()
        
        # Measure transcription time
        start_time = time.time()
        
        # Perform transcription with error handling
        try:
            res = model.transcribe(audio_path)
            text = res.get("text", "").strip()
        except RuntimeError as e:
            if "out of memory" in str(e):
                console.log("[red]❌ GPU out of memory - falling back to CPU[/]")
                torch.cuda.empty_cache()
                res = model.transcribe(audio_path, device="cpu")
                text = res.get("text", "").strip()
            else:
                raise
        
        # Calculate and log processing time
        process_time = time.time() - start_time
        console.log(f"⏱️ Transcription took {process_time:.2f} seconds")
        
        # Log results
        if text:
            console.log(f"📝 Transcribed ({len(text)} chars): {text}")
        else:
            console.log("[yellow]⚠️ Transcription returned empty text[/]")
        
        return text
        
    except Exception as e:
        console.log(f"[red]❌ Transcription error:[/] {e}")
        return ""

# For testing
if __name__ == "__main__":
    result = transcribe_segment("segment.wav")
    print(f"Transcription result: {result}")