#!/usr/bin/env python3
import click
import os
import sys
import time
import threading
import requests
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from dotenv import load_dotenv

from audio_capture import list_audio_devices, record_segment
from run_loop import run_loop

console = Console()

def check_dependencies():
    """Check if required dependencies are installed and configured"""
    
    # Check if Whisper is available
    try:
        import whisper
        console.log("[green]✓[/] Whisper is installed")
        
        # Check if tiny.en model exists
        home = os.path.expanduser("~")
        model_path = os.path.join(home, ".cache", "whisper", "tiny.en.pt")
        if not os.path.exists(model_path):
            console.log("[yellow]![/] Whisper tiny.en model not found")
            if click.confirm("Would you like to download the tiny.en model now?", default=True):
                console.log("Downloading Whisper tiny.en model...")
                model = whisper.load_model("tiny.en")
                console.log("[green]✓[/] Downloaded Whisper tiny.en model")
    except ImportError:
        console.log("[red]✗[/] Whisper is not installed")
        sys.exit(1)

    # Check if Ollama is running and has the required model
    try:
        r = requests.get("http://localhost:11434/api/tags")
        if not r.ok:
            console.log("[red]✗[/] Ollama is not running. Please start Ollama first")
            sys.exit(1)
        
        models = r.json().get("models", [])
        llama_available = any("llama3.2" in model.get("name", "") for model in models)
        if not llama_available:
            console.log("[yellow]![/] llama3.2 model not found in Ollama")
            if click.confirm("Would you like to pull the llama3.2 model now?", default=True):
                os.system("ollama pull llama3.2")
    except Exception as e:
        console.log(f"[red]✗[/] Failed to connect to Ollama: {e}")
        console.log("Please make sure Ollama is installed and running")
        sys.exit(1)

def save_credentials(client_id, client_secret):
    """Save Zoom credentials to .env file"""
    with open(".env", "w") as f:
        f.write(f"CLIENT_ID={client_id}\n")
        f.write(f"CLIENT_SECRET={client_secret}\n")
        f.write("REDIRECT_URI=http://localhost:8000/oauth/callback\n")
        f.write(f"SECRET_TOKEN={os.urandom(24).hex()}\n")
        f.write("LLAMA_HOST=http://localhost:11434\n")

@click.group()
def cli():
    """Zoom Poll Automator CLI"""
    pass

@cli.command()
def setup():
    """Configure Zoom credentials and check dependencies"""
    console.print(Panel("Welcome to Zoom Poll Automator Setup!", title="🔧 Setup"))
    
    # Check dependencies first
    check_dependencies()
    
    # Get Zoom credentials
    console.print("\n[bold]Please enter your Zoom OAuth credentials[/]")
    console.print("You can get these by creating an app at https://marketplace.zoom.us/develop/create")
    client_id = click.prompt("Client ID", type=str)
    client_secret = click.prompt("Client Secret", type=str)
    
    # Save credentials
    save_credentials(client_id, client_secret)
    console.print("[green]✓[/] Credentials saved to .env file")
    
    # List available audio devices
    console.print("\n[bold]Available Audio Devices:[/]")
    devices = list_audio_devices()
    
    click.echo("\nSetup complete! You can now run 'python cli.py start' to begin automation")

@cli.command()
@click.option("--meeting-id", prompt="Enter your Zoom meeting ID", help="Zoom meeting ID")
@click.option("--duration", default=60, prompt="Recording duration (seconds)", 
              help="Duration to record before generating each poll (10-300 seconds)")
@click.option("--device", prompt="Audio device name (leave empty for default)", 
              default="", help="Name of the audio input device to use")
def start(meeting_id, duration, device):
    """Start the Zoom poll automation"""
    
    # Load environment variables
    load_dotenv()
    
    # Verify credentials exist
    if not os.getenv("CLIENT_ID") or not os.getenv("CLIENT_SECRET"):
        console.print("[red]Error:[/] Missing Zoom credentials. Please run 'python cli.py setup' first")
        sys.exit(1)
    
    # Validate duration
    if duration < 10 or duration > 300:
        console.print("[red]Error:[/] Duration must be between 10 and 300 seconds")
        sys.exit(1)
    
    # Start web server for OAuth
    from app import app
    import threading
    server_thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8000), daemon=True)
    server_thread.start()
    
    console.print(Panel(
        "[green]Zoom Poll Automator is starting![/]\n\n"
        "1. A browser window will open for Zoom OAuth login\n"
        "2. After authorizing, the automation will begin\n"
        "3. Press Ctrl+C to stop the automation",
        title="🚀 Starting"
    ))
    
    # Open browser for OAuth
    import webbrowser
    webbrowser.open("http://localhost:8000")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping automation...[/]")
        sys.exit(0)

if __name__ == "__main__":
    cli()