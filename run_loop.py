# run_loop.py

import os, time
from rich.console import Console
from audio_capture import record_segment
from transcribe_whisper import transcribe_segment
from poller import generate_poll_from_transcript, post_poll_to_zoom

console = Console()

def run_loop(zoom_token, meeting_id, duration, device, should_stop=None):
    """
    Forever: record → transcribe → generate + post poll → delete files
    
    Args:
        zoom_token: Zoom OAuth token
        meeting_id: Zoom meeting ID
        duration: Recording duration in seconds
        device: Audio device name (or None for default)
        should_stop: Reference to a boolean flag to check for stop signal
    """
    cycle = 0
    while True:
        # Check if we should stop
        if should_stop and should_stop is True:
            console.log("[yellow]⚠️ Stopping automation due to stop signal[/]")
            break
            
        cycle += 1
        console.log(f"[blue]▶️  Cycle {cycle}[/]")
        try:
            # 1) Record
            record_segment(duration=duration, output="segment.wav", device=device)

            # 2) Transcribe
            text = transcribe_segment("segment.wav")
            if not text.strip():
                console.log("[yellow]⚠️ Empty transcript—skipping poll[/]")
                time.sleep(5)  # Wait a bit before next cycle
                continue

            # 3) Generate poll
            title, q, opts = generate_poll_from_transcript(text)

            # 4) Post poll
            post_poll_to_zoom(title, q, opts, meeting_id, zoom_token)

            # 5) Cleanup
            for f in ("segment.wav", "temp_stereo.wav"):
                if os.path.exists(f):
                    os.remove(f)
            console.log("[green]🗑️  Cleaned up audio files[/]")

        except Exception as e:
            console.log(f"[red]❌ Error in run_loop:[/] {e}")
            time.sleep(5)  # Pause on error to avoid rapid error loops

        # small pause before next cycle
        time.sleep(1)