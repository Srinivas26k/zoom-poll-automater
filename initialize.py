import os
import sys
import requests
from rich.console import Console
import torch
import whisper

console = Console()

def check_ollama():
    """Check if Ollama is running and has required model"""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if not r.ok:
            return False, "Cannot connect to Ollama server"
        
        models = r.json().get("models", [])
        if not any("llama3.2" in model.get("name", "") for model in models):
            return False, "llama3.2 model not found"
        
        return True, "Ollama is running with llama3.2 model"
    except Exception as e:
        return False, f"Error connecting to Ollama: {str(e)}"

def check_whisper():
    """Check and download Whisper model if needed"""
    try:
        console.print("Checking Whisper model...")
        model = whisper.load_model("tiny.en")
        return True, "Whisper model is ready"
    except Exception as e:
        return False, f"Error loading Whisper model: {str(e)}"

def check_gpu():
    """Check if GPU is available for acceleration"""
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        return True, f"GPU acceleration available: {device_name}"
    return False, "No GPU found, will use CPU"

def initialize():
    """Run all initialization checks"""
    # Check Python version
    python_version = sys.version.split()[0]
    if tuple(map(int, python_version.split('.'))) < (3, 8):
        console.print("[red]Error: Python 3.8 or higher is required[/]")
        return False

    # Check Ollama
    ollama_ok, ollama_msg = check_ollama()
    if not ollama_ok:
        console.print(f"[red]Ollama check failed: {ollama_msg}[/]")
        return False
    console.print(f"[green]✓[/] {ollama_msg}")

    # Check Whisper
    whisper_ok, whisper_msg = check_whisper()
    if not whisper_ok:
        console.print(f"[red]Whisper check failed: {whisper_msg}[/]")
        return False
    console.print(f"[green]✓[/] {whisper_msg}")

    # Check GPU
    gpu_ok, gpu_msg = check_gpu()
    console.print(f"[cyan]ℹ[/] {gpu_msg}")

    # Check environment file
    if not os.path.exists(".env"):
        console.print("[red]Error: .env file not found[/]")
        return False

    console.print("[green]✓[/] All initialization checks passed!")
    return True

if __name__ == "__main__":
    if not initialize():
        sys.exit(1)