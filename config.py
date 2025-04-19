# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # read .env

CLIENT_ID       = os.getenv("CLIENT_ID")
CLIENT_SECRET   = os.getenv("CLIENT_SECRET")
REDIRECT_URI    = os.getenv("REDIRECT_URI")

SECRET_TOKEN        = os.getenv("SECRET_TOKEN")
VERIFICATION_TOKEN  = os.getenv("VERIFICATION_TOKEN")

# Extract Ollama host from env, ensuring it's properly formatted
LLAMA_HOST_BASE = os.getenv("LLAMA_HOST", "http://localhost:11434")
# Ensure the URL doesn't have trailing slashes
LLAMA_HOST_BASE = LLAMA_HOST_BASE.rstrip('/')
# For OpenAI client compatibility
LLAMA_HOST = f"{LLAMA_HOST_BASE}/v1"
# For direct Ollama API calls
OLLAMA_API = LLAMA_HOST_BASE