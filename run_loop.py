# run_loop.py

import os, time
from rich.console import Console
from audio_capture import record_segment
from transcribe_whisper import transcribe_segment
from poller import generate_poll_from_transcript, post_poll_to_zoom

console = Console()

def run_loop(zoom_token, meeting_id, duration, device):
    """
    Forever: record → transcribe → generate + post poll → delete files
    """
    cycle = 0
    while True:
        cycle += 1
        console.log(f"[blue]▶️  Cycle {cycle}[/]")
        try:
            # 1) Record
            record_segment(duration, output="segment.wav", device=device)

            # 2) Transcribe
            text = transcribe_segment("segment.wav")
            if not text.strip():
                console.log("[yellow]⚠️ Empty transcript—skipping poll[/]")
                continue

            # 3) Generate poll
            q, opts = generate_poll_from_transcript(text)

            # 4) Post poll
            post_poll_to_zoom(q, opts, meeting_id, zoom_token)

            # 5) Cleanup
            for f in ("segment.wav", "temp_stereo.wav"):
                if os.path.exists(f):
                    os.remove(f)
            console.log("[green]🗑️  Cleaned up audio files[/]")

        except Exception as e:
            console.log(f"[red]❌ Error in run_loop:[/] {e}")

        # small pause before next cycle
        time.sleep(1)
