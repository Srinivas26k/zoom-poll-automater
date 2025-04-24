# run_loop.py
import os, time
import logging
import threading # Import threading Event

# Local imports
from audio_capture import record_segment
from transcribe_whisper import transcribe_segment
from poller import generate_poll_from_transcript, post_poll_to_zoom
import config # Import config to get token and meeting ID

logger = logging.getLogger(__name__)

# Callback function to send updates to the GUI (set by main_gui.py)
_gui_update_callback = None

def set_gui_update_callback(callback):
    """Sets the callback function to send messages to the GUI."""
    global _gui_update_callback
    _gui_update_callback = callback

def update_gui_status(message):
    """Sends a status message to the GUI if the callback is set."""
    if _gui_update_callback:
        _gui_update_callback(message)
    else:
        logger.info(f"STATUS: {message}") # Log if no GUI callback set


def run_loop(meeting_id, duration, device, should_stop: threading.Event):
    """Optimized run loop with better error handling and recovery."""
    cycle = 0
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3
    
    logger.info(f"Starting automation loop for meeting {meeting_id}")
    update_gui_status("[green]Automation started[/]")

    while not should_stop.is_set():
        cycle += 1
        try:
            # Record audio
            if not record_segment(duration, device=device):
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error("Too many consecutive recording failures")
                    update_gui_status("[red]Recording issues detected. Please check audio setup.[/]")
                    time.sleep(5)
                    consecutive_failures = 0
                continue

            # Reset failure counter on successful recording
            consecutive_failures = 0

            # Process recording
            text = transcribe_segment()
            if not text:
                logger.warning("Empty transcription - skipping poll")
                continue

            # Generate and post poll
            try:
                poll_data = generate_poll_from_transcript(text)
                if poll_data:
                    post_poll_to_zoom(meeting_id, poll_data)
            except Exception as e:
                logger.error(f"Poll generation/posting error: {e}")
                continue

        except Exception as e:
            logger.error(f"Cycle {cycle} error: {e}", exc_info=True)
            time.sleep(5)  # Brief pause before next cycle
            
        finally:
            # Clean up any temporary files
            if os.path.exists("segment.wav"):
                try:
                    os.remove("segment.wav")
                except OSError:
                    pass

# Note: This run_loop function is designed to be called in a separate thread by main_gui.py