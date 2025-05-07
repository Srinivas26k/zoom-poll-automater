# app.py
from flask import Flask, redirect, url_for, session, request, render_template, flash
import requests, base64, threading, os, time
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.live import Live
from rich.panel import Panel
from run_loop import run_loop
import config
from audio_capture import list_audio_devices
from urllib.parse import urlencode

console = Console()

app = Flask(__name__)
app.secret_key = config.SECRET_TOKEN or os.urandom(24)  # Fallback for secret key

# Store the background thread
automation_thread = None
should_stop = threading.Event()  # Use an Event for thread communication

# ─── 1) Home: OAuth or Setup ────────────────────────────────────────────────────
@app.route("/")
def index():
    # Check if configuration is valid
    missing_config = []
    if not config.CLIENT_ID:
        missing_config.append("CLIENT_ID")
    if not config.CLIENT_SECRET:
        missing_config.append("CLIENT_SECRET")
    
    if missing_config:
        error_message = f"Missing required configuration: {', '.join(missing_config)}. Please update your .env file."
        console.log(f"[red]❌ {error_message}[/]")
        return render_template("error.html", error=error_message)
    
    if "zoom_token" in session:
        return redirect(url_for("setup"))
    return render_template("index.html")

# ─── 2) Start OAuth ─────────────────────────────────────────────────────────────
@app.route("/authorize")
def authorize():
    """Handle OAuth authorization initiation"""
    if not config.CLIENT_ID or not config.CLIENT_SECRET:
        error = "Missing CLIENT_ID or CLIENT_SECRET in .env file"
        console.log(f"[red]❌ {error}[/]")
        return render_template("error.html", error=error)

    # Use exact Zoom authorization URL format
    auth_url = (
        "https://zoom.us/oauth/authorize?"
        f"response_type=code&"
        f"client_id={config.CLIENT_ID}&"
        f"redirect_uri={config.REDIRECT_URI}"
    )
    
    console.log(f"[blue]Redirecting to:[/]\n{auth_url}")
    return redirect(auth_url)

# ─── 3) OAuth callback ──────────────────────────────────────────────────────────
@app.route("/oauth/callback")
def oauth_callback():
    """Handle OAuth callback from Zoom"""
    code = request.args.get('code')
    if not code:
        error = "No authorization code received from Zoom"
        console.log(f"[red]❌ {error}[/]")
        return render_template("error.html", error=error)

    # Exchange code for access token
    token_url = "https://zoom.us/oauth/token"
    auth = (config.CLIENT_ID, config.CLIENT_SECRET)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.REDIRECT_URI
    }

    try:
        response = requests.post(token_url, auth=auth, data=data)
        response.raise_for_status()
        tokens = response.json()
        
        # Store access token in session
        session['zoom_token'] = tokens['access_token']
        console.log("[green]✓[/] Successfully obtained Zoom access token")
        
        return render_template("setup.html")
        
    except Exception as e:
        error = f"Failed to obtain access token: {str(e)}"
        console.log(f"[red]❌ {error}[/]")
        return render_template("error.html", error=error)

# ─── 4) Setup page ──────────────────────────────────────────────────────────────
@app.route("/setup", methods=["GET","POST"])
def setup():
    global automation_thread
    
    if "zoom_token" not in session:
        return redirect(url_for("index"))
    
    # Check if token is still valid
    if "token_expiry" in session and time.time() > session["token_expiry"]:
        console.log("[yellow]⚠️ Zoom token expired, redirecting to login[/]")
        session.pop("zoom_token", None)
        session.pop("token_expiry", None)
        return redirect(url_for("index"))

    if request.method == "POST":
        # read user input
        meeting_id = request.form["meeting_id"]
        try:
            duration = int(request.form["duration"])
            if duration < 10 or duration > 300:
                flash("Duration must be between 10 and 300 seconds")
                return redirect(url_for("setup"))
        except ValueError:
            flash("Duration must be a valid number")
            return redirect(url_for("setup"))
            
        device = request.form["device"]
        zoom_token = session["zoom_token"]

        console.log(f"🚀 Starting automation: meeting={meeting_id}, dur={duration}s, dev={device}")
        
        # Stop existing thread if running
        if automation_thread and automation_thread.is_alive():
            console.log("[yellow]⚠️ Stopping existing automation thread[/]")
            should_stop.set()  # Signal the thread to stop
            # Give time for thread to clean up
            time.sleep(2)
            should_stop.clear()  # Reset the flag for next thread
        
        # Test Ollama connection before starting thread
        try:
            # Direct API test to Ollama
            ollama_url = f"{config.OLLAMA_API}/api/tags"
            console.log(f"Testing Ollama connection: {ollama_url}")
            r = requests.get(ollama_url, timeout=5)
            if not r.ok:
                error_msg = f"Failed to connect to Ollama API: {r.status_code} {r.text}"
                console.log(f"[red]❌ {error_msg}[/]")
                flash(error_msg)
                return redirect(url_for("setup"))
                
            # Verify llama3.2 model is available
            models = r.json().get("models", [])
            llama_available = any("llama3.2" in model.get("name", "") for model in models)
            if not llama_available:
                console.log("[yellow]⚠️ llama3.2 model not found, you may need to pull it[/]")
                flash("Warning: llama3.2 model not found in Ollama. Run 'ollama pull llama3.2' first.")
            else:
                console.log("[green]✅ Successfully connected to Ollama and found llama3.2 model[/]")
        except Exception as e:
            error_msg = f"Failed to connect to Ollama at {config.OLLAMA_API}: {str(e)}"
            console.log(f"[red]❌ {error_msg}[/]")
            flash(error_msg)
            return redirect(url_for("setup"))
        
        # launch background loop
        automation_thread = threading.Thread(
            target=run_loop,
            args=(zoom_token, meeting_id, duration, device, should_stop),
            daemon=True
        )
        automation_thread.start()
        return render_template("started.html")

    # List available audio devices for the UI
    try:
        devices = list_audio_devices()
    except Exception as e:
        console.log(f"[yellow]⚠️ Could not list audio devices: {e}[/]")
        devices = []
    
    # GET
    return render_template(
        "setup.html",
        token=session["zoom_token"],
        devices=devices
    )

@app.route("/stop")
def stop():
    global should_stop
    should_stop.set()  # Signal the thread to stop
    flash("Automation has been signaled to stop.")
    return redirect(url_for("setup"))

@app.route("/config", methods=["GET"])
def show_config():
    """Show the configuration form"""
    return render_template("config.html")

@app.route("/save_config", methods=["POST"])
def save_config():
    """Save Zoom credentials to .env file"""
    client_id = request.form.get("client_id")
    client_secret = request.form.get("client_secret")
    redirect_uri = request.form.get("redirect_uri")

    if not all([client_id, client_secret, redirect_uri]):
        return render_template("config.html", error="All fields are required")

    try:
        # Read existing .env content
        env_lines = []
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                env_lines = f.readlines()

        # Update or add new values
        updated = {"CLIENT_ID": False, "CLIENT_SECRET": False, "REDIRECT_URI": False}
        
        for i, line in enumerate(env_lines):
            if line.startswith("CLIENT_ID="):
                env_lines[i] = f"CLIENT_ID={client_id}\n"
                updated["CLIENT_ID"] = True
            elif line.startswith("CLIENT_SECRET="):
                env_lines[i] = f"CLIENT_SECRET={client_secret}\n"
                updated["CLIENT_SECRET"] = True
            elif line.startswith("REDIRECT_URI="):
                env_lines[i] = f"REDIRECT_URI={redirect_uri}\n"
                updated["REDIRECT_URI"] = True

        # Add any missing values
        if not updated["CLIENT_ID"]:
            env_lines.append(f"CLIENT_ID={client_id}\n")
        if not updated["CLIENT_SECRET"]:
            env_lines.append(f"CLIENT_SECRET={client_secret}\n")
        if not updated["REDIRECT_URI"]:
            env_lines.append(f"REDIRECT_URI={redirect_uri}\n")

        # Ensure we have a SECRET_TOKEN
        if not any(line.startswith("SECRET_TOKEN=") for line in env_lines):
            env_lines.append(f"SECRET_TOKEN={os.urandom(24).hex()}\n")

        # Ensure we have LLAMA_HOST
        if not any(line.startswith("LLAMA_HOST=") for line in env_lines):
            env_lines.append("LLAMA_HOST=http://localhost:11434\n")

        # Write back to .env
        with open(".env", "w") as f:
            f.writelines(env_lines)

        console.log("[green]✓[/] Configuration saved successfully")
        return render_template("config.html", success="Configuration saved successfully! You can now proceed to OAuth login.")

    except Exception as e:
        console.log(f"[red]❌ Error saving configuration:[/] {str(e)}")
        return render_template("config.html", error=f"Error saving configuration: {str(e)}")

def run_automation(duration, device):
    """Run the automation loop with progress indicators"""
    console = Console()
    
    # Verify zoom token exists
    if 'zoom_token' not in session:
        console.print("[red]❌ No Zoom token found. Please run setup first.[/]")
        return False
        
    # Progress spinner for initialization
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        # Initialize components
        init_task = progress.add_task("[cyan]Initializing automation...", total=None)
        time.sleep(1)  # Show initialization message
        
        try:
            # Start the automation loop in a background thread
            should_stop = threading.Event()
            automation_thread = threading.Thread(
                target=run_loop,
                args=(session['zoom_token'], config.MEETING_ID, duration, device, should_stop),
                daemon=True
            )
            automation_thread.start()
            progress.update(init_task, description="[green]Automation started successfully!")
            
            # Show live status
            with Live(console=console, refresh_per_second=4) as live:
                try:
                    while automation_thread.is_alive():
                        live.update(Panel(
                            "[green]🤖 Poll Automation Running[/green]\n\n"
                            "🎙️ Recording and analyzing meeting audio\n"
                            "Press Ctrl+C to stop",
                            title="Status"
                        ))
                        time.sleep(0.25)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Stopping automation...[/]")
                    should_stop.set()
                    automation_thread.join(timeout=5)
                    console.print("[green]✓ Automation stopped successfully[/]")
                    return True
                    
        except Exception as e:
            progress.update(init_task, description=f"[red]Error: {str(e)}")
            return False
            
    return True

if __name__ == "__main__":
    console.log("[green]Zoom Poll Automator starting...[/]")
    console.log(f"Access the web interface at: {config.REDIRECT_URI.split('/oauth')[0]}")
    app.run(host="0.0.0.0", port=8000)