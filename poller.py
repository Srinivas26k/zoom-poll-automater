# poller.py
import json, requests
from rich.console import Console
import config

console = Console()

def generate_poll_from_transcript(transcript: str):
    """Generate a poll title, question and options from transcript using Ollama/LLaMA directly"""
    prompt = (
        "You are a meeting assistant. "
        "Based on this transcript, generate one multiple-choice poll with a title, "
        "one question, and exactly four answer options. "
        "The poll should help check if attendees were paying attention to key discussion points. "
        "Make the title concise but descriptive of the topic. "
        "Reply _only_ in JSON like:\n"
        '{"title":"...","question":"...","options":["A","B","C","D"]}\n\n'
        f"Transcript:\n{transcript}"
    )
    console.log("🤖 Asking LLaMA for poll…")
    try:
        # Use direct Ollama API for more reliable results
        url = f"{config.OLLAMA_API}/api/generate"
        payload = {
            "model": "llama3.2:latest",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 256
            }
        }
        
        r = requests.post(url, json=payload)
        if not r.ok:
            raise Exception(f"Ollama API error: {r.status_code} {r.text}")
            
        raw = r.json().get("response", "").strip()
        console.log(f"📥 LLaMA raw: {raw}")
        
        # Try to parse JSON, handling possible formatting issues
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_text = raw[json_start:json_end].strip()
            # Replace single quotes with double quotes if needed
            json_text = json_text.replace("'", '"')
            data = json.loads(json_text)
            
            # Ensure we have all required fields
            if "title" in data and "question" in data and "options" in data:
                if len(data["options"]) == 4:
                    return data["title"], data["question"], data["options"]
                else:
                    # Fix options if not exactly 4
                    options = data["options"][:4]  # Trim if more than 4
                    while len(options) < 4:  # Add generic ones if less than 4
                        options.append(f"Option {len(options)+1}")
                    return data["title"], data["question"], data["options"]
            
        # If we couldn't parse or missing fields, return default
        raise Exception("Could not parse valid JSON from LLaMA response")
            
    except Exception as e:
        console.log(f"[yellow]⚠️ LLaMA/parsing error:[/] {e}")
        # Extract potential topics from transcript
        words = transcript.split()
        topic = "Meeting"
        if len(words) > 5:
            topic = " ".join(words[:2]) + "..."
            
        return (
            f"Quick Poll: {topic}",
            "What was discussed just now?",
            ["Option A", "Option B", "Option C", "Option D"]
        )

def post_poll_to_zoom(title: str, question: str, options: list, meeting_id: str, token: str):
    """Post a poll to Zoom meeting using Zoom API"""
    url = f"https://api.zoom.us/v2/meetings/{meeting_id}/polls"
    headers = {"Authorization":f"Bearer {token}", "Content-Type":"application/json"}
    payload = {
        "title": title,
        "questions":[
            {"name":question, "type":"single", "answer_required":True, "answers":options}
        ]
    }
    console.log(f"📤 Posting poll to Zoom…")
    console.log(f"Poll: {title} - {question}")
    console.log(f"Options: {options}")
    
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