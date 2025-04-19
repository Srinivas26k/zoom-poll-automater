# poller.py
import json, requests
from openai import OpenAI
from rich.console import Console
import config

console = Console()
llama = OpenAI(base_url=config.LLAMA_HOST, api_key="ollama")

def generate_poll_from_transcript(transcript: str):
    prompt = (
        "You are a meeting assistant.  "
        "Based on this transcript, generate one multiple‑choice question "
        "with exactly four answer options.  "
        "Reply _only_ in JSON like:\n"
        '{"question":"...","options":["A","B","C","D"]}\n\n'
        f"Transcript:\n{transcript}"
    )
    console.log("🤖 Asking LLaMA for poll…")
    resp = llama.chat.completions.create(
        model="llama3.2:latest",
        messages=[{"role":"user","content":prompt}]
    )
    raw = resp.choices[0].message.content.strip()
    console.log(f"📥 LLaMA raw: {raw}")
    try:
        data = json.loads(raw.replace("'", '"'))
        return data["question"], data["options"]
    except Exception as e:
        console.log(f"[yellow]⚠️ Parsing fail:[/] {e}")
        return (
            "What was discussed just now?",
            ["Option A","Option B","Option C","Option D"]
        )

def post_poll_to_zoom(question: str, options: list, meeting_id: str, token: str):
    url = f"https://api.zoom.us/v2/meetings/{meeting_id}/polls"
    headers = {"Authorization":f"Bearer {token}", "Content-Type":"application/json"}
    payload = {
        "title":"Automated Poll",
        "questions":[
            {"name":question, "type":"single", "answer_required":True, "answers":options}
        ]
    }
    console.log(f"📤 Posting poll to Zoom…")
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code == 201:
        console.log(f"[green]✅ Poll created[/]: {r.json()}")
    else:
        console.log(f"[red]❌ Zoom API error[/]: {r.status_code} {r.text}")
