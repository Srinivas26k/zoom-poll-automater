# poller.py
import json, requests
from openai import OpenAI
from rich.console import Console
import config

console = Console()
llama = OpenAI(base_url=config.LLAMA_HOST, api_key="ollama")

def generate_poll_from_transcript(transcript: str):
    """Generate a poll question and options from transcript using LLaMA"""
    prompt = (
        "You are a meeting assistant.  "
        "Based on this transcript, generate one multiple‑choice question "
        "with exactly four answer options.  "
        "Reply _only_ in JSON like:\n"
        '{"question":"...","options":["A","B","C","D"]}\n\n'
        f"Transcript:\n{transcript}"
    )
    console.log("🤖 Asking LLaMA for poll…")
    try:
        resp = llama.chat.completions.create(
            model="llama3.2:latest",
            messages=[{"role":"user","content":prompt}]
        )
        raw = resp.choices[0].message.content.strip()
        console.log(f"📥 LLaMA raw: {raw}")
        
        # Try to parse JSON, handling possible formatting issues
        if raw.startswith("```json"):
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif raw.startswith("```"):
            raw = raw.split("```")[1].strip()
            
        data = json.loads(raw.replace("'", '"'))
        return data["question"], data["options"]
    except Exception as e:
        console.log(f"[yellow]⚠️ LLaMA/parsing error:[/] {e}")
        return (
            "What was discussed just now?",
            ["Option A","Option B","Option C","Option D"]
        )

def post_poll_to_zoom(question: str, options: list, meeting_id: str, token: str):
    """Post a poll to Zoom meeting using Zoom API"""
    url = f"https://api.zoom.us/v2/meetings/{meeting_id}/polls"
    headers = {"Authorization":f"Bearer {token}", "Content-Type":"application/json"}
    payload = {
        "title":"Automated Poll",
        "questions":[
            {"name":question, "type":"single", "answer_required":True, "answers":options}
        ]
    }
    console.log(f"📤 Posting poll to Zoom…")
    try:
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code == 201:
            console.log(f"[green]✅ Poll created[/]: {r.json()}")
            return True
        else:
            console.log(f"[red]❌ Zoom API error[/]: {r.status_code} {r.text}")
            return False
    except Exception as e:
        console.log(f"[red]❌ Poll posting error[/]: {e}")
        return False