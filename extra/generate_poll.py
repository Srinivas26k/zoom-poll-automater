# This file can be removed since functionality is now in poller.py
# Keeping it with a note to avoid confusion

# NOTE: This file is deprecated - use poller.py instead

import json
import os
from openai import OpenAI

# single client instance
_client = OpenAI(
    base_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
    api_key  = "ollama"
)

def generate_poll(transcript: str):
    """Ask LLaMA to make a poll question + 4 options from `transcript`."""
    prompt = (
        "Create a single‑choice poll question with exactly 4 answer options, "
        f"based on this meeting transcript:\n\n{transcript}\n\n"
        "Return JSON exactly as:\n"
        '{"question":"...", "options":["..","..","..",".."]}'
    )

    resp = _client.chat.completions.create(
        model="llama3.2:latest",
        messages=[
            {"role":"system","content":"You are a poll‑making assistant."},
            {"role":"user","content":prompt}
        ]
    )

    raw = resp.choices[0].message.content.strip()
    try:
        data = json.loads(raw)
        return data["question"], data["options"]
    except Exception:
        # fallback stub
        return (
            "What was discussed just now?",
            ["Option A","Option B","Option C","Option D"]
        )