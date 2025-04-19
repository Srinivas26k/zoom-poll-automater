import os, time, shutil
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from audio_capture    import record_segment
from transcribe_whisper import transcribe_segment
from generate_poll    import generate_poll
from post_poll        import post_poll

console = Console()
load_dotenv()  # reads .env

MEETING_ID       = os.getenv("MEETING_ID")
ZOOM_TOKEN       = os.getenv("ZOOM_TOKEN")
SEGMENT_DURATION = int(os.getenv("SEGMENT_DURATION", "30"))

def main():
    if not (MEETING_ID and ZOOM_TOKEN):
        console.print("[red]Please set MEETING_ID and ZOOM_TOKEN in .env[/red]")
        return

    cycle = 1
    console.print(Panel("[bold green]Zoom Poll Automator Started[/bold green]\nPress Ctrl+C to stop", title="▶️ Live"))

    try:
        while True:
            console.rule(f"Cycle {cycle}", style="cyan")

            # 1) Record
            console.print(f"🎙️ Recording [bold]{SEGMENT_DURATION}s[/bold]…")
            record_segment(SEGMENT_DURATION, out="segment.wav")
            console.print(":white_check_mark: [green]Audio captured → segment.wav[/green]")

            # 2) Transcribe
            console.print("🧠 Transcribing with Whisper…")
            transcript = transcribe_segment("segment.wav")
            console.print(Panel(transcript or "(no speech detected)", title="📝 Transcript", width=80))

            # 3) Generate poll
            console.print("🤖 Generating poll via LLaMA 3.2…")
            question, options = generate_poll(transcript)
            console.print(Panel(f"[bold]{question}[/bold]\n\n" + "\n".join(f"- {o}" for o in options),
                                title="❓ Poll Preview", width=80))

            # 4) Post poll
            console.print("📤 Posting poll to Zoom…")
            success, resp = post_poll(MEETING_ID, ZOOM_TOKEN, question, options)
            if success:
                console.print(Panel(str(resp), title="[green]✅ Poll Posted[/green]", width=80))
            else:
                console.print(Panel(str(resp), title="[red]❌ Poll Failed[/red]", width=80))

            # Cleanup
            for f in ("segment.wav",):
                if os.path.exists(f):
                    os.remove(f)

            cycle += 1
            console.print("\n[dim]Waiting 5s before next cycle…[/dim]")
            time.sleep(5)

    except KeyboardInterrupt:
        console.print("\n[bold red]Stopped by user. Goodbye![/bold red]")

if __name__ == "__main__":
    main()
