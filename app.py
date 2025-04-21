# app.py
from flask import Flask, redirect, url_for, session, request, render_template, flash
import requests, base64, threading, os, time
from rich.console import Console
from run_loop import run_loop
import config
from audio_capture import list_audio_devices

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
    # Verify configuration
    if not config.CLIENT_ID or not config.CLIENT_SECRET:
        error = "Missing CLIENT_ID or CLIENT_SECRET in .env file"
        console.log(f"[red]❌ {error}[/]")
        return render_template("error.html", error=error)
        
    scopes = "meeting:read:meeting_transcript meeting:read:list_meetings " \
             "meeting:read:poll meeting:read:token meeting:write:poll " \
             "meeting:update:poll user:read:zak zoomapp:inmeeting"
    params = {
        "response_type": "code",
        "client_id":     config.CLIENT_ID,
        "redirect_uri":  config.REDIRECT_URI,
        "scope":         scopes
    }
    url = "https://zoom.us/oauth/authorize"
    auth_url = f"{url}?{'&'.join(f'{k}={v}' for k,v in params.items())}"
    console.log(f"Redirecting to: {auth_url}")
    return redirect(auth_url)

# ─── 3) OAuth callback ──────────────────────────────────────────────────────────
@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    error = request.args.get("error")
    
    if error:
        error_description = request.args.get("error_description", "Unknown error")
        console.log(f"[red]OAuth error: {error} - {error_description}[/]")
        return render_template("error.html", error=f"OAuth error: {error_description}")
        
    if not code:
        return render_template("error.html", error="No authorization code returned")

    # swap code for token
    token_url = "https://zoom.us/oauth/token"
    creds = f"{config.CLIENT_ID}:{config.CLIENT_SECRET}".encode()
    auth_header = base64.b64encode(creds).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type":  "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type":   "authorization_code",
        "code":         code,
        "redirect_uri": config.REDIRECT_URI
    }
    
    try:
        r = requests.post(token_url, headers=headers, data=data)
        if r.ok:
            token_data = r.json()
            token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour
            session["zoom_token"] = token
            session["token_expiry"] = time.time() + expires_in
            console.log("[green]✅ Obtained Zoom access token[/]")
            return redirect(url_for("setup"))
        else:
            error_msg = f"Token error: {r.status_code} - {r.text}"
            console.log(f"[red]{error_msg}[/]")
            return render_template("error.html", error=error_msg)
    except Exception as e:
        error_msg = f"Error during token exchange: {str(e)}"
        console.log(f"[red]{error_msg}[/]")
        return render_template("error.html", error=error_msg)

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

if __name__ == "__main__":
    console.log("[green]Zoom Poll Automator starting...[/]")
    console.log(f"Access the web interface at: {config.REDIRECT_URI.split('/oauth')[0]}")
    app.run(host="0.0.0.0", port=8000)