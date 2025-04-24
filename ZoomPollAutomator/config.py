# config.py
import os
from pathlib import Path
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# --- Configuration Storage (In-Memory) ---
_config = {
    "CLIENT_ID": None,
    "CLIENT_SECRET": None,
    "REDIRECT_URI": "http://localhost:8000/oauth/callback", # Default redirect URI
    "SECRET_TOKEN": None,
    "VERIFICATION_TOKEN": None, # Not strictly needed for OAuth, but good to keep
    "OLLAMA_HOST_BASE": "http://localhost:11434", # Default Ollama host
    "OLLAMA_HOST": None, # Will be set based on OLLAMA_HOST_BASE
    "OLLAMA_API": None, # Will be set based on OLLAMA_HOST_BASE
    "ZOOM_TOKEN": None, # Store Zoom access token
    "TOKEN_EXPIRY": 0 # Store token expiry time
}

# --- Load .env file ---
def sanitize_path(path):
    """Sanitize file paths to prevent path traversal"""
    return str(Path(path).resolve())

# Load environment variables
load_dotenv()

# Secure configuration loading
class Config:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ZOOM_CLIENT_ID = os.getenv('ZOOM_CLIENT_ID')
    ZOOM_CLIENT_SECRET = os.getenv('ZOOM_CLIENT_SECRET')
    
    # Validate required environment variables
    @classmethod
    def validate_config(cls):
        required_vars = ['OPENAI_API_KEY', 'ZOOM_CLIENT_ID', 'ZOOM_CLIENT_SECRET']
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    # Whisper model configuration
    WHISPER_MODEL = "tiny"  # Using tiny model for better performance
    
    # Security configurations
    MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25MB max audio file size
    ALLOWED_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a'}
    
    @classmethod
    def is_valid_audio_file(cls, filename):
        return Path(filename).suffix.lower() in cls.ALLOWED_AUDIO_EXTENSIONS

logger.info(".env file loaded.")

# Load initial values from environment variables (overwrites defaults if present)
_config["CLIENT_ID"] = os.getenv("CLIENT_ID")
_config["CLIENT_SECRET"] = os.getenv("CLIENT_SECRET")
_config["REDIRECT_URI"] = os.getenv("REDIRECT_URI") or _config["REDIRECT_URI"]
_config["SECRET_TOKEN"] = os.getenv("SECRET_TOKEN")
_config["VERIFICATION_TOKEN"] = os.getenv("VERIFICATION_TOKEN")
_config["OLLAMA_HOST_BASE"] = os.getenv("OLLAMA_HOST", _config["OLLAMA_HOST_BASE"])

# Set derived Ollama API URLs
_config["OLLAMA_HOST_BASE"] = _config["OLLAMA_HOST_BASE"].rstrip('/')
_config["OLLAMA_HOST"] = f"{_config['OLLAMA_HOST_BASE']}/v1" # For OpenAI client compatibility
_config["OLLAMA_API"] = _config["OLLAMA_HOST_BASE"] # For direct Ollama API calls

logger.info(f"Configuration loaded. Ollama Host: {_config['OLLAMA_API']}, Redirect URI: {_config['REDIRECT_URI']}")


# --- Functions to Access/Set Config ---
def get_config(key):
    """Gets a configuration value by key."""
    return _config.get(key)

# Add these new methods for better config management
def validate_config_value(key, value):
    """Validates configuration values before setting."""
    if key in ["CLIENT_ID", "CLIENT_SECRET", "SECRET_TOKEN"]:
        return bool(value and isinstance(value, str))
    elif key == "TOKEN_EXPIRY":
        return isinstance(value, (int, float)) and value >= 0
    elif key.startswith("OLLAMA_"):
        return bool(value and isinstance(value, str))
    return True

def set_config(key, value):
    """Sets a configuration value with validation."""
    if not validate_config_value(key, value):
        logger.error(f"Invalid configuration value for {key}")
        return False
    _config[key] = value
    logger.debug(f"Config key '{key}' set to valid value")
    return True

def get_config_with_default(key, default=None):
    """Gets a configuration value with a default fallback."""
    return _config.get(key, default)

def set_ollama_host(host_url):
    """Sets the Ollama host and updates derived URLs."""
    if not host_url:
        logger.error("Invalid Ollama host URL provided")
        return False
        
    try:
        # Validate the URL format
        if not host_url.startswith(('http://', 'https://')):
            host_url = f"http://{host_url}"
            
        _config["OLLAMA_HOST_BASE"] = host_url.rstrip('/')
        _config["OLLAMA_HOST"] = f"{_config['OLLAMA_HOST_BASE']}/v1"
        _config["OLLAMA_API"] = _config["OLLAMA_HOST_BASE"]
        logger.info(f"Ollama host set to: {_config['OLLAMA_API']}")
        return True
    except Exception as e:
        logger.error(f"Error setting Ollama host: {e}")