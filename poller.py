#poller.py
import json
import requests
from openai import OpenAI
from rich.console import Console
import config
from poll_prompt import POLL_PROMPT

console = Console()
llama = OpenAI(base_url=config.LLAMA_HOST, api_key="ollama")

def generate_poll_from_transcript(transcript: str) -> tuple[str, str, list[str]]:
    """
    Generate a poll from a transcript using LLaMA and the imported prompt.

    Args:
        transcript (str): The meeting transcript to analyze.

    Returns:
        tuple: (title, question, options) of the generated poll.
    """
    # Combine the prompt with the transcript
    full_prompt = POLL_PROMPT.replace("[Insert transcript here]", transcript)
    console.log("🤖 Generating poll from transcript…")

    try:
        # Request poll from LLaMA
        resp = llama.chat.completions.create(
            model="llama3.2:latest",
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.7,
            max_tokens=500
        )
        raw_response = resp.choices[0].message.content.strip()
        console.log(f"📥 LLaMA response: {raw_response}")

        # Parse the JSON response
        poll_data = json.loads(raw_response)
        title = poll_data.get("title", "Default Meeting Poll")
        question = poll_data.get("question", "What was discussed?")
        options = poll_data.get("options", [])

        # Validate and adjust options to ensure exactly 4
        if not isinstance(options, list):
            options = []
        if len(options) > 4:
            options = options[:4]
        while len(options) < 4:
            options.append(f"Option {len(options) + 1} (from transcript)")

        return title, question, options

    except json.JSONDecodeError as e:
        console.log(f"[yellow]⚠️ JSON parsing error:[/] {e}")
    except Exception as e:
        console.log(f"[yellow]⚠️ Poll generation error:[/] {e}")

    # Fallback in case of errors
    return (
        "Meeting Poll",
        "What was the main topic?",
        ["Option A", "Option B", "Option C", "Option D"]
    )

def post_poll_to_zoom(title: str, question: str, options: list[str], meeting_id: str, token: str) -> bool:
    """
    Post a poll to a Zoom meeting using the Zoom API.

    Args:
        title (str): Poll title.
        question (str): Poll question.
        options (list[str]): List of four poll options.
        meeting_id (str): Zoom meeting ID.
        token (str): Zoom API token.

    Returns:
        bool: True if successful, False otherwise.
    """
    url = f"https://api.zoom.us/v2/meetings/{meeting_id}/polls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "title": title,
        "questions": [{
            "name": question,
            "type": "single",
            "answer_required": True,
            "answers": options
        }]
    }

    console.log(f"📤 Posting poll to Zoom: {title} - {question}")
    console.log(f"Options: {options}")

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            console.log(f"[green]✅ Poll posted successfully[/]: {response.json()}")
            return True
        else:
            console.log(f"[red]❌ Zoom API error[/]: {response.status_code} {response.text}")
            return False
    except Exception as e:
        console.log(f"[red]❌ Poll posting error[/]: {e}")
        return False

if __name__ == "__main__":
    # Example usage
    sample_transcript = "Team discussed project timeline. Alice: 'We should extend it.' Bob: 'No, add resources instead.'"
    title, question, options = generate_poll_from_transcript(sample_transcript)
    console.log(f"Generated Poll: {title} - {question} - {options}")
    # Uncomment to test Zoom posting (requires config with meeting_id and token)
    # post_poll_to_zoom(title, question, options, config.MEETING_ID, config.ZOOM_TOKEN)