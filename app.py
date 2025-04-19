# app.py
from flask import Flask, redirect, url_for, session, request, render_template
import requests, base64, threading
from rich.console import Console
from run_loop import run_loop
import config

console = Console()

app = Flask(__name__)
app.secret_key = config.SECRET_TOKEN  # secure your sessions

# ─── 1) Home: OAuth or Setup ────────────────────────────────────────────────────
@app.route("/")
def index():
    if "zoom_token" in session:
        return redirect(url_for("setup"))
    return render_template("index.html")

# ─── 2) Start OAuth ─────────────────────────────────────────────────────────────
@app.route("/authorize")
def authorize():
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
    return redirect(f"{url}?{'&'.join(f'{k}={v}' for k,v in params.items())}")

# ─── 3) OAuth callback ──────────────────────────────────────────────────────────
@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return "❌ No code returned", 400

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
    r = requests.post(token_url, headers=headers, data=data)
    if not r.ok:
        console.log(f"[red]OAuth token error[/]: {r.status_code} {r.text}")
        return f"❌ Token error: {r.text}", 500

    token = r.json()["access_token"]
    session["zoom_token"] = token
    console.log("[green]✅ Obtained Zoom access token[/]")
    return redirect(url_for("setup"))

# ─── 4) Setup page ──────────────────────────────────────────────────────────────
@app.route("/setup", methods=["GET","POST"])
def setup():
    if "zoom_token" not in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        # read user input
        meeting_id   = request.form["meeting_id"]
        duration     = int(request.form["duration"])
        device       = request.form["device"]
        zoom_token   = session["zoom_token"]

        console.log(f"🚀 Starting automation: meeting={meeting_id}, dur={duration}s, dev={device}")
        # launch background loop
        threading.Thread(
            target=run_loop,
            args=(zoom_token, meeting_id, duration, device),
            daemon=True
        ).start()
        return render_template("started.html")

    # GET
    return render_template(
        "setup.html",
        token=session["zoom_token"]
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
