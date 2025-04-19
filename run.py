# run.py
import time
from config import get_config
from audio_capture import record_segment
from transcribe_whisper import transcribe_segment
from poller import generate_and_post_poll

def main():
    cfg = get_config()
    token     = cfg["zoom_token"]
    meeting   = cfg["meeting_id"]
    duration  = cfg["segment_duration"]
    device    = cfg["audio_device"]

    print("\n🚀 Starting automated poll loop. Press Ctrl+C to stop.\n")
    try:
        while True:
            # 1) capture
            record_segment(duration, device)
            # 2) transcribe
            with open("transcript.txt", "a", encoding="utf-8") as _:
                pass  # ensure file exists
            text = transcribe_segment("segment.wav", "transcript.txt")
            # 3) poll
            generate_and_post_poll(text, token, meeting)
            # 4) wait until next cycle
            time.sleep(1)  # small pause or remove if instantaneous
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user. Goodbye!")

if __name__ == "__main__":
    main()
