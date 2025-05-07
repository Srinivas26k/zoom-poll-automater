#!/usr/bin/env python3
import click
import os
import sys
import time
import threading
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from rich.prompt import Prompt, Confirm
from dotenv import load_dotenv
import config

console = Console()

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code = None
    
    def do_GET(self):
        """Handle the OAuth callback"""
        try:
            if '/oauth/callback' in self.path:
                query = urlparse(self.path).query
                params = parse_qs(query)
                OAuthCallbackHandler.auth_code = params.get('code', [None])[0]
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                html_content="""
                    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; text-align: center;">
                        <h1 style="color: #2D8CFF;">✅ Authorization Successful!</h1>
                        <p>You can close this window and return to the terminal.</p>
                    </body></html>
                """
                self.wfile.write(html_content.encode('utf-8'))
        except Exception as e:
            console.print(f"[red]Error in callback handler: {e}[/]")

def save_credentials(client_id, client_secret):
    """Save credentials to .env file"""
    try:
        env_content = {
            "CLIENT_ID": client_id,
            "CLIENT_SECRET": client_secret,
            "REDIRECT_URI": "http://localhost:8000/oauth/callback",
            "SECRET_TOKEN": os.urandom(24).hex(),
            "LLAMA_HOST": "http://localhost:11434"
        }
        
        with open(".env", "w") as f:
            for key, value in env_content.items():
                f.write(f"{key}={value}\n")
        
        return True
    except Exception as e:
        console.print(f"[red]Error saving credentials: {e}[/]")
        return False

def get_access_token(auth_code, client_id, client_secret):
    """Exchange authorization code for access token"""
    token_url = "https://zoom.us/oauth/token"
    auth_data = {
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": "http://localhost:8000/oauth/callback"
    }
    
    try:
        response = requests.post(
            token_url,
            auth=(client_id, client_secret),
            data=auth_data
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        console.print(f"[red]Error getting access token: {e}[/]")
        return None

@click.group()
def cli():
    """Zoom Poll Automator - Generate polls from meeting discussions"""
    pass

@cli.command()
def check():
    """Check for required models and dependencies"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        # Overall progress
        overall = progress.add_task("[cyan]Checking components...", total=3)
        
        # 1. Check Whisper
        whisper_task = progress.add_task("[yellow]Checking Whisper model...", total=100)
        try:
            import whisper
            progress.update(whisper_task, advance=50)
            model = whisper.load_model("tiny.en")
            progress.update(whisper_task, completed=100)
            progress.update(overall, advance=1)
        except Exception as e:
            progress.update(whisper_task, description=f"[red]Failed to load Whisper: {e}")
            return False
            
        # 2. Check Ollama
        ollama_task = progress.add_task("[yellow]Checking Ollama connection...", total=100)
        try:
            r = requests.get("http://localhost:11434/api/tags")
            progress.update(ollama_task, advance=50)
            
            if not r.ok:
                progress.update(ollama_task, description="[red]❌ Ollama is not running")
                return False
                
            models = r.json().get("models", [])
            if any("llama3.2" in model.get("name", "") for model in models):
                progress.update(ollama_task, completed=100)
            else:
                progress.update(ollama_task, description="[yellow]llama3.2 model not found")
                return False
            progress.update(overall, advance=1)
        except Exception as e:
            progress.update(ollama_task, description=f"[red]Failed to connect to Ollama: {e}")
            return False
            
        # 3. Check audio devices
        audio_task = progress.add_task("[yellow]Checking audio devices...", total=100)
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            if any(d['max_input_channels'] > 0 for d in devices):
                progress.update(audio_task, completed=100)
                progress.update(overall, advance=1)
            else:
                progress.update(audio_task, description="[red]No audio input devices found")
                return False
        except Exception as e:
            progress.update(audio_task, description=f"[red]Failed to check audio: {e}")
            return False
            
        return True

@cli.command()
def setup():
    """Configure Zoom credentials and perform OAuth flow"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Starting setup...", total=None)
        
        # Clear screen and show welcome
        os.system('cls' if os.name == 'nt' else 'clear')
        console.print(Panel(
            "[bold cyan]Welcome to Zoom Poll Automator Setup![/]\n\n"
            "This wizard will help you configure your Zoom credentials.\n"
            "You'll need to create a Zoom App first at [link]https://marketplace.zoom.us/develop/create[/link]",
            title="🔧 Setup"
        ))
        
        # Get Zoom credentials
        console.print("\n[bold]Please enter your Zoom OAuth credentials:[/]")
        console.print("[dim]You can find these in your Zoom App settings[/]")
        client_id = Prompt.ask("\n[cyan]Client ID")
        client_secret = Prompt.ask("[cyan]Client Secret", password=True)
        
        # Save credentials
        progress.update(task, description="[cyan]Saving credentials...")
        if not save_credentials(client_id, client_secret):
            return
        
        progress.update(task, description="[green]✓ Credentials saved")
        
        # Start OAuth flow
        if Confirm.ask("\nWould you like to authorize with Zoom now?", default=True):
            progress.update(task, description="[cyan]Starting OAuth server...")
            server = HTTPServer(('localhost', 8000), OAuthCallbackHandler)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            
            # Generate and open authorization URL
            auth_url = (
                "https://zoom.us/oauth/authorize?"
                f"response_type=code&"
                f"client_id={client_id}&"
                f"redirect_uri=http://localhost:8000/oauth/callback"
            )
            
            progress.update(task, description="[cyan]Opening browser for authorization...")
            webbrowser.open(auth_url)
            
            console.print("\n[yellow]Browser window opened for Zoom authorization.")
            console.print("Please complete the authorization in your browser.[/]")
            
            # Wait for OAuth callback with spinner
            progress.update(task, description="[cyan]⏳ Waiting for authorization...")
            start_time = time.time()
            while not OAuthCallbackHandler.auth_code:
                time.sleep(0.1)
                if time.time() - start_time > 300:  # 5 minute timeout
                    progress.update(task, description="[red]Authorization timeout")
                    server.shutdown()
                    return
            
            # Exchange code for token
            progress.update(task, description="[cyan]Getting access token...")
            auth_code = OAuthCallbackHandler.auth_code
            access_token = get_access_token(auth_code, client_id, client_secret)
            
            if access_token:
                # Save token to env
                with open(".env", "a") as f:
                    f.write(f"\nZOOM_TOKEN={access_token}\n")
                progress.update(task, description="[green]✓ Setup completed successfully!")
                console.print("\n[green]✓ Setup complete! You can now run the automation.[/]")
            else:
                progress.update(task, description="[red]Failed to get access token")
                console.print("\n[red]Failed to get access token. Please try setup again.[/]")
            
            # Cleanup
            server.shutdown()
            server.server_close()

@cli.command()
@click.option("--duration", default=60, help="Recording duration in seconds (10-300)")
@click.option("--device", default="", help="Audio input device name (optional)")
def run(duration, device):
    """Start the Zoom poll automation"""
    # First check components
    if not check():
        console.print("[red]Component check failed. Please fix the issues above.[/]")
        return
        
    # Load environment variables
    load_dotenv()
    
    if not os.path.exists(".env"):
        console.print("[red]No configuration found. Running setup...[/]")
        setup()
        return
        
    if not all([os.getenv("CLIENT_ID"), os.getenv("CLIENT_SECRET")]):
        console.print("[red]Missing Zoom credentials. Running setup...[/]")
        setup()
        return
    
    if not os.getenv("ZOOM_TOKEN"):
        console.print("[red]Not authorized with Zoom. Running setup...[/]")
        setup()
        return
    
    # Start the automation
    from run_loop import run_loop
    console.print("[green]Starting automation...[/]")
    
    should_stop = threading.Event()
    try:
        run_loop(os.getenv("ZOOM_TOKEN"), "", duration, device, should_stop)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping automation...[/]")
        should_stop.set()
    except Exception as e:
        console.print(f"[red]Error in automation: {e}[/]")

if __name__ == "__main__":
    cli()