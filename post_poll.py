import requests, os

POLL_TITLE = os.getenv("POLL_TITLE", "Automated Poll")

def post_poll(meeting_id, token, question, options):
    """
    Posts a single‑question poll to a Zoom meeting.
    Returns (success:bool, response_json_or_text).
    """
    url = f"https://api.zoom.us/v2/meetings/{meeting_id}/polls"
    payload = {
        "title": POLL_TITLE,
        "questions": [{
            "name": question,
            "type": "single",
            "answer_required": True,
            "answers": options
        }]
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, json=payload, headers=headers)
    if r.status_code == 201:
        return True, r.json()
    else:
        return False, r.text
