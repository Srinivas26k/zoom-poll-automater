# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # read .env

CLIENT_ID       = os.getenv("CLIENT_ID")
CLIENT_SECRET   = os.getenv("CLIENT_SECRET")
REDIRECT_URI    = os.getenv("REDIRECT_URI")

SECRET_TOKEN        = os.getenv("SECRET_TOKEN")
VERIFICATION_TOKEN  = os.getenv("VERIFICATION_TOKEN")

LLAMA_HOST      = os.getenv("LLAMA_HOST", "http://localhost:11434")
