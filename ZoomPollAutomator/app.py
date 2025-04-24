# app.py
from flask import Flask, redirect, url_for, session, request, render_template_string
import requests, base64, os, time
import logging
import config
import threading
import queue

logger = logging.getLogger(__name__)

# HTML Templates (keep these inline for simplicity in a single file)
ERROR_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Error - Zoom Poll Automator</title>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
    .error-container { background-color: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 20px 0; }
    h1 { color: #d32f2f; }
    .steps { background-color: #f5f5f5; padding: 15px; border-radius: 5px; }
    code { background-color: #eeeeee; padding: 2px 5px; border-radius: 3px; font-family: monospace; }
    .btn { display: inline-block; padding: 8px 16px; background-color: #2196f3; color: white; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 20px; }
    .btn:hover { background-color: #0b7dda; }
  </style>
</head>
<body>
  <h1>❌ Error</h1>

  <div class="error-container">
    <p><strong>{{ error }}</strong></p>
  </div>

  <div class="steps">
    <h2>Potential Issues & Steps to Fix:</h2>
    <p>Please check the application logs for more details. Ensure the following are correctly configured:</p>
    <ol>
      <li>
        <strong>Zoom App Credentials:</strong>
        <ul>
          <li>Verify your Client ID and Client Secret entered in the application's setup screen.</li>
        </ul>
      </li>
      <li>
        <strong>Zoom Marketplace App Configuration:</strong>
        <ul>
          <li>Go to <a href="https://marketplace.zoom.us/develop/create" target="_blank">Zoom Developer Portal</a> and manage your OAuth app.</li>
          <li>Ensure the Redirect URL is exactly: <code>http://localhost:8000/oauth/callback</code></li>
          <li>Ensure the required scopes are added: <code>meeting:read:list_meetings</code>, <code>meeting:read:poll</code>, <code>meeting:write:poll</code>, <code>meeting:read:meeting_transcript</code>, <code>user:read:zak</code></li>
        </ul>
      </li>
      <li>
        <strong>Local Server Access:</strong>
        <ul>
          <li>Your operating system's firewall or security software might be blocking the connection to <code>http://localhost:8000</code>. Temporarily disable it to test.</li>
          <li>Ensure the application's Flask server thread started successfully (check application logs).</li>
        </ul>
      </li>
       <li>
        <strong>Restart the application</strong> after making any changes.
      </li>
    </ol>
  </div>

</body>
</html>
"""

OAUTH_SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Zoom OAuth Successful</title>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px; text-align: center; }
    h1 { color: #28a745; }
    .success-message { background-color: #e9ffeb; border: 1px solid #c3e6cb; color: #155724; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
    .close-instruction { color: #555; font-size: 0.9em; }
  </style>
</head>
<body>
  <h1>✅ Success!</h1>
  <div class="success-message">
    <p>Zoom OAuth authentication was successful.</p>
    <p>You can now close this browser window and return to the Zoom Poll Automator application.</p>
  </div>
  <p class="close-instruction">You may close this browser window now.</p>
</body>
</html>
"""


app = Flask(__name__)
# Get SECRET_TOKEN from config module, which loads from .env
app.secret_key = config.get_config("SECRET_TOKEN") or os.urandom(24).hex()
app.config['SECRET_KEY'] = app.secret_key

gui_queue_for_flask = None

def set_gui_queue(q):
    """Sets the queue object used by Flask to communicate with the GUI."""
    global gui_queue_for_flask
    gui_queue_for_flask = q

# ─── 1) Home: Redirect to OAuth Start ─────────────────────────────────────────────
@app.route("/")
def index():
    """Redirects the user to the Zoom OAuth authorization flow start."""
    return redirect(url_for("authorize"))

# ─── 2) Start OAuth ─────────────────────────────────────────────────────────────
@app.route("/authorize")
def authorize():
    """Starts the Zoom OAuth authorization flow."""
    client_id = config.get_config("CLIENT_ID")
    client_secret = config.get_config("CLIENT_SECRET")
    redirect_uri = config.get_config("REDIRECT_URI")

    if not client_id or not client_secret or not redirect_uri:
        error = "Missing CLIENT_ID, CLIENT_SECRET, or REDIRECT_URI in configuration."
        logger.error(f"❌ {error}")
        if gui_queue_for_flask:
             gui_queue_for_flask.put(('STATUS', f"[red]❌ OAuth setup error: {error}[/]. Check logs."))
        return render_template_string(ERROR_HTML, error=error)

    # Correct and minimal required scopes
    # meeting:read:meeting_transcript is needed for accessing transcript data later if implemented
    scopes = "meeting:read:list_meetings meeting:read:poll meeting:write:poll meeting:read:meeting_transcript user:read:zak"

    params = {
        "response_type": "code",
        "client_id":     client_id,
        "redirect_uri":  redirect_uri,
        "scope":         scopes
    }
    url = "https://zoom.us/oauth/authorize"
    auth_url = f"{url}?{'&'.join(f'{k}={v}' for k,v in params.items())}"
    logger.info(f"Redirecting user to Zoom OAuth: {auth_url}")
    if gui_queue_for_flask:
        gui_queue_for_flask.put(('STATUS', f"Opening Zoom OAuth in browser. If it doesn't open, navigate to: {auth_url}"))
    return redirect(auth_url)

# ─── 3) OAuth callback ──────────────────────────────────────────────────────────
@app.route("/oauth/callback")
def oauth_callback():
    """Handles the callback from Zoom after user authorization."""
    code = request.args.get("code")
    error = request.args.get("error")
    error_description = request.args.get("error_description", "Unknown error")

    if error:
        logger.error(f"Zoom OAuth error received: {error} - {error_description}")
        error_message = f"Zoom OAuth failed: {error_description}. Check logs for details."
        if gui_queue_for_flask:
             gui_queue_for_flask.put(('STATUS', f"[red]❌ {error_message}[/]"))
        return render_template_string(ERROR_HTML, error=error_message)

    if not code:
        logger.error("No authorization code returned in OAuth callback.")
        error_message = "Zoom OAuth failed: No authorization code received. Check logs."
        if gui_queue_for_flask:
             gui_queue_for_flask.put(('STATUS', f"[red]❌ {error_message}[/]"))
        return render_template_string(ERROR_HTML, error=error_message)

    # Exchange the authorization code for an access token
    token_url = "https://zoom.us/oauth/token"
    client_id = config.get_config("CLIENT_ID")
    client_secret = config.get_config("CLIENT_SECRET")
    redirect_uri = config.get_config("REDIRECT_URI")

    if not client_id or not client_secret or not redirect_uri:
         error_msg = "Zoom API credentials not found in configuration for token exchange."
         logger.error(error_msg)
         if gui_queue_for_flask:
              gui_queue_for_flask.put(('STATUS', f"[red]❌ OAuth error: {error_msg}[/]"))
         return render_template_string(ERROR_HTML, error=error_msg)

    try:
        creds = f"{client_id}:{client_secret}".encode()
        auth_header = base64.b64encode(creds).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type":  "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": redirect_uri
        }

        r = requests.post(token_url, headers=headers, data=data, timeout=10)
        if r.ok:
            token_data_json = r.json()
            token = token_data_json.get("access_token")
            expires_in = token_data_json.get("expires_in", 3600) # Default to 1 hour

            if token:
                # Store the obtained token and its expiry time in the config module
                config.set_config("ZOOM_TOKEN", token)
                config.set_config("TOKEN_EXPIRY", time.time() + expires_in)
                logger.info("✅ Obtained Zoom access token successfully.")
                if gui_queue_for_flask:
                    # Signal OAuth success and pass the token back to the GUI
                    gui_queue_for_flask.put(('OAUTH_SUCCESS', token))
                    gui_queue_for_flask.put(('STATUS', "[green]✅ Zoom OAuth successful! Return to the application window.[/]"))

                return render_template_string(OAUTH_SUCCESS_HTML)
            else:
                error_msg = f"Token response from Zoom missing access_token: {r.text}"
                logger.error(f"❌ {error_msg}")
                if gui_queue_for_flask:
                     gui_queue_for_flask.put(('STATUS', f"[red]❌ OAuth error: {error_msg}[/]. Check logs."))
                return render_template_string(ERROR_HTML, error=error_msg)

        else:
            error_msg = f"Token exchange request failed: {r.status_code} - {r.text}"
            logger.error(f"❌ {error_msg}")
            if gui_queue_for_flask:
                 gui_queue_for_flask.put(('STATUS', f"[red]❌ OAuth error: {error_msg}[/]. Check logs."))
            return render_template_string(ERROR_HTML, error=error_msg)
    except requests.exceptions.RequestException as e:
        error_msg = f"Network or request error during token exchange: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        if gui_queue_for_flask:
             gui_queue_for_flask.put(('STATUS', f"[red]❌ OAuth error: {error_msg}[/]. Check logs."))
        return render_template_string(ERROR_HTML, error=error_msg)
    except Exception as e:
       error_msg = f"Unexpected error during token exchange: {str(e)}"
       logger.error(f"❌ {error_msg}", exc_info=True)
       if gui_queue_for_flask:
            gui_queue_for_flask.put(('STATUS', f"[red]❌ OAuth error: {error_msg}[/]. Check logs."))
       return render_template_string(ERROR_HTML, error=error_msg)

# Note: The Flask server thread will be started by main_gui.py using Waitress.
# The /setup and /stop routes in the previous PySimpleGUI version are no longer needed
# because the Customtkinter GUI handles configuration and stopping directly.