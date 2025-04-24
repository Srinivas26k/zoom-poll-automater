# main_gui.py (Refined Customtkinter Outline)
import customtkinter as ctk
import tkinter as tk
import threading
import webbrowser
import time
import logging
import os
import sys
import subprocess
import json
import queue
import signal

# Create a queue for GUI updates
gui_queue = queue.Queue()

# Local imports
import config
# Import the app and a function to set the queue it should use
from app import app, set_gui_queue as set_flask_gui_queue
from run_loop import run_loop, set_gui_update_callback
import setup_automation
# from audio_capture import list_audio_devices # Use function via setup_automation

# --- Logging Setup ---
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
logging.basicConfig(filename=os.path.join(log_dir, 'app.log'), level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Customtkinter Setup ---
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Add custom colors and styles
COLORS = {
    "primary": "#2b6cb0",
    "secondary": "#4299e1",
    "success": "#48bb78",
    "warning": "#ed8936",
    "error": "#f56565",
    "background": "#f7fafc",
    "text": "#2d3748"
}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Zoom Poll Automator")
        self.geometry("800x700")  # Slightly larger window
        try:
            self.iconbitmap("assets/icon.ico")
        except:
            logger.warning("Could not load assets/icon.ico")
        
        # Configure window appearance
        self.configure(fg_color=COLORS["background"])
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Setup Frame ---
        self.setup_frame = ctk.CTkFrame(self, fg_color="white", corner_radius=15)
        self.setup_frame.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")
        self.setup_frame.grid_columnconfigure(1, weight=1)

        # Stylish header
        header_frame = ctk.CTkFrame(self.setup_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, pady=(20, 30))
        
        ctk.CTkLabel(
            header_frame,
            text="Zoom Poll Automator",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=COLORS["primary"]
        ).pack()

        # Progress section with improved visuals
        progress_frame = ctk.CTkFrame(self.setup_frame, fg_color="transparent")
        progress_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20)
        
        ctk.CTkLabel(
            progress_frame,
            text="Setup Progress",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w")

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Initializing...",
            font=ctk.CTkFont(size=13),
            wraplength=700,
            justify="left"
        )
        self.status_label.pack(fill="x", pady=(5, 10))

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", pady=(0, 20))
        self.progress_bar.set(0)

        # Zoom API Credentials
        ctk.CTkLabel(self.setup_frame, text="Zoom API Credentials:", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

        ctk.CTkLabel(self.setup_frame, text="Client ID:", width=120, anchor="w").grid(row=5, column=0, sticky="w")
        self.client_id_entry = ctk.CTkEntry(self.setup_frame)
        self.client_id_entry.grid(row=5, column=1, sticky="ew")
        self.client_id_entry.bind("<KeyRelease>", self.check_oauth_button)

        ctk.CTkLabel(self.setup_frame, text="Client Secret:", width=120, anchor="w").grid(row=6, column=0, sticky="w")
        self.client_secret_entry = ctk.CTkEntry(self.setup_frame, show="*")
        self.client_secret_entry.grid(row=6, column=1, sticky="ew")
        self.client_secret_entry.bind("<KeyRelease>", self.check_oauth_button)

        ctk.CTkLabel(self.setup_frame, text="Redirect URI:", width=120, anchor="w").grid(row=7, column=0, sticky="w")
        self.redirect_uri_entry = ctk.CTkEntry(self.setup_frame)
        self.redirect_uri_entry.grid(row=7, column=1, sticky="ew")
        self.redirect_uri_entry.insert(0, config.get_config("REDIRECT_URI")) # Corrected line

        ctk.CTkLabel(self.setup_frame, text="Secret Token:", width=120, anchor="w").grid(row=8, column=0, sticky="w")
        self.secret_token_entry = ctk.CTkEntry(self.setup_frame, show="*")
        self.secret_token_entry.grid(row=8, column=1, sticky="ew")
        self.secret_token_entry.insert(0, config.get_config("SECRET_TOKEN"))

        self.oauth_button = ctk.CTkButton(self.setup_frame, text="Proceed to Zoom OAuth", command=self.start_oauth, state="disabled")
        self.oauth_button.grid(row=9, column=0, columnspan=2, pady=(10, 0))

        # Ollama Configuration
        ctk.CTkLabel(self.setup_frame, text="Ollama Configuration:", font=ctk.CTkFont(weight="bold")).grid(row=10, column=0, columnspan=2, sticky="w", pady=(10, 0))

        ctk.CTkLabel(self.setup_frame, text="Ollama Host:", width=120, anchor="w").grid(row=11, column=0, sticky="w")
        self.ollama_host_entry = ctk.CTkEntry(self.setup_frame)
        self.ollama_host_entry.grid(row=11, column=1, sticky="ew")
        self.ollama_host_entry.insert(0, config.get_config("OLLAMA_API"))

        ctk.CTkLabel(self.setup_frame, text="Ollama Model:", width=120, anchor="w").grid(row=12, column=0, sticky="w")
        self.ollama_model_combo = ctk.CTkComboBox(self.setup_frame, values=['deepseek-r1:1.5b', 'llama3.2:latest', 'Other'])
        self.ollama_model_combo.grid(row=12, column=1, sticky="ew")
        self.ollama_model_combo.set('deepseek-r1:1.5b')

        self.check_ollama_button = ctk.CTkButton(self.setup_frame, text="Check & Configure Ollama", command=self.check_and_configure_ollama)
        self.check_ollama_button.grid(row=13, column=0, columnspan=2, pady=(10, 0))

        self.exit_setup_button = ctk.CTkButton(self.setup_frame, text="Exit Setup", command=self.quit)
        self.exit_setup_button.grid(row=14, column=0, columnspan=2, pady=(20, 0))

        # --- Main App Frame (Initially hidden) ---
        self.main_app_frame = ctk.CTkFrame(self)
        self.main_app_frame.grid_columnconfigure(1, weight=1)
        self.main_app_frame.grid_columnconfigure(2, weight=0) # Column for refresh button
        self.main_app_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.main_app_frame, text="Zoom Poll Automator", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=3, pady=(0, 10))

        # Status Output
        ctk.CTkLabel(self.main_app_frame, text="Application Status:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        # Use CTkTextbox for multi-line output
        self.output_box = ctk.CTkTextbox(self.main_app_frame, wrap="word", state="disabled")
        self.output_box.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(0, 10))

        # Automation Controls
        ctk.CTkLabel(self.main_app_frame, text="Automation Controls:", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ctk.CTkLabel(self.main_app_frame, text="Zoom Meeting ID:", width=150, anchor="w").grid(row=4, column=0, sticky="w")
        self.meeting_id_entry = ctk.CTkEntry(self.main_app_frame)
        self.meeting_id_entry.grid(row=4, column=1, columnspan=2, sticky="ew")

        ctk.CTkLabel(self.main_app_frame, text="Segment Duration (sec):", width=150, anchor="w").grid(row=5, column=0, sticky="w")
        self.duration_entry = ctk.CTkEntry(self.main_app_frame)
        self.duration_entry.grid(row=5, column=1, columnspan=2, sticky="ew")
        self.duration_entry.insert(0, "60")

        ctk.CTkLabel(self.main_app_frame, text="Audio Input Device:", width=150, anchor="w").grid(row=6, column=0, sticky="w")
        self.audio_device_combo = ctk.CTkComboBox(self.main_app_frame, values=[])
        self.audio_device_combo.grid(row=6, column=1, sticky="ew", padx=(0, 10))

        self.refresh_audio_button = ctk.CTkButton(self.main_app_frame, text="Refresh", command=self.refresh_audio_devices, width=100) # Compact button
        self.refresh_audio_button.grid(row=6, column=2)


        self.start_button = ctk.CTkButton(self.main_app_frame, text="Start Automation", command=self.start_automation, state="disabled") # Disabled initially
        self.start_button.grid(row=7, column=0, pady=(10, 0))

        self.stop_button = ctk.CTkButton(self.main_app_frame, text="Stop Automation", command=self.stop_automation, state="disabled", fg_color="red", hover_color="darkred")
        self.stop_button.grid(row=7, column=1, pady=(10, 0))

        self.exit_main_button = ctk.CTkButton(self.main_app_frame, text="Exit Application", command=self.quit)
        self.exit_main_button.grid(row=7, column=2, pady=(10, 0))


        # --- Initial Setup Checks ---
        self.after(100, self.initial_setup_checks) # Start checks after GUI is visible

        # --- Poll the queue for updates ---
        self.after(100, self.poll_queue)

    def poll_queue(self):
        """Checks the queue for messages and updates the GUI."""
        try:
            while True:
                message_type, message_value = gui_queue.get_nowait()
                if message_type == 'STATUS':
                    self.update_status(message_value)
                elif message_type == 'PROGRESS':
                    self.progress_bar.set(message_value / 100.0)
                elif message_type == 'OLLAMA_MODELS':
                    logger.info(f"Detected Ollama models: {message_value}")
                    # Decide if you want to update the model combo box values here
                    # self.ollama_model_combo.configure(values=message_value + ['Other'])
                elif message_type == 'AUDIO_DEVICES':
                    global audio_devices, audio_devices_found
                    audio_devices = message_value
                    audio_devices_found = len([dev for dev in audio_devices if dev['max_input_channels'] > 0]) > 0
                    self.update_audio_device_dropdown()
                    self.update_status(f"Found {len(audio_devices)} audio input devices.")
                    self.check_enable_start_button() # Check if start button can be enabled
                elif message_type == 'OAUTH_SUCCESS':
                    global zoom_token, oauth_complete
                    zoom_token = message_value
                    oauth_complete = True
                    self.update_status("[green]✅ Zoom OAuth successful! Proceeding to main app.[/]")
                    self.check_enable_start_button() # Check if start button can be enabled
                    # Optional: Automatically transition to main app after a short delay
                    # self.after(2000, self.transition_to_main_app)


                self.update()

        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Error processing GUI queue message: {e}", exc_info=True)
            self.update_status(f"[red]❌ Error processing GUI update: {e}[/]")

        self.after(100, self.poll_queue)

    def update_status(self, message):
        """Updates status labels and output box."""
        if self.setup_frame.winfo_ismapped():
             self.status_label.configure(text=message)

        if self.main_app_frame.winfo_ismapped():
             self.output_box.configure(state="normal")
             self.output_box.insert("end", message + "\n")
             self.output_box.configure(state="disabled")
             self.output_box.see("end")


    def update_audio_device_dropdown(self):
        """Populates the audio device dropdown."""
        device_names = [dev['name'] for dev in audio_devices if dev['max_input_channels'] > 0]
        if device_names:
             self.audio_device_combo.configure(values=device_names)
             self.audio_device_combo.set(device_names[0])
        else:
             self.audio_device_combo.configure(values=['No devices found'])
             self.audio_device_combo.set('No devices found')


    def initial_setup_checks(self):
        """Starts background checks."""
        self.update_status("Checking system prerequisites...")
        # Check Ollama status and audio devices in parallel threads
        threading.Thread(target=lambda: setup_automation.check_and_set_ollama_status(gui_queue), daemon=True).start()
        threading.Thread(target=lambda: setup_automation.check_and_set_audio_devices(gui_queue), daemon=True).start()


    def check_oauth_button(self, event=None):
        """Enables OAuth button if required fields are filled."""
        if self.client_id_entry.get().strip() and self.client_secret_entry.get().strip():
             self.oauth_button.configure(state="normal")
        else:
             self.oauth_button.configure(state="disabled")

    def start_oauth(self):
        """Collects credentials, saves to config, opens browser."""
        client_id = self.client_id_entry.get().strip()
        client_secret = self.client_secret_entry.get().strip()
        redirect_uri = self.redirect_uri_entry.get().strip()
        secret_token = self.secret_token_entry.get().strip()

        if not client_id or not client_secret or not redirect_uri:
            self.update_status("[red]❌ Client ID, Client Secret, and Redirect URI are required.[/]")
            ctk.CTkMessageBox("Error", "Client ID, Client Secret, and Redirect URI are required.").wait_window()
            return

        config.set_config("CLIENT_ID", client_id)
        config.set_config("CLIENT_SECRET", client_secret)
        config.set_config("REDIRECT_URI", redirect_uri)
        config.set_config("SECRET_TOKEN", secret_token)
        config.set_ollama_host(self.ollama_host_entry.get().strip())

        self.update_status("Initiating Zoom OAuth... Please check your browser.")
        logger.info("Opening browser for Zoom OAuth.")
        try:
            webbrowser.open(config.get_config("REDIRECT_URI").split('/oauth')[0] + "/authorize")
        except Exception as e:
            self.update_status(f"[red]❌ Failed to open browser: {e}. Copy the URL manually.[/]")
            logger.error(f"Failed to open browser: {e}", exc_info=True)
            # Optionally display the URL in the status message for manual copy


        # Flask thread will handle the callback and signal OAUTH_SUCCESS via queue

    def check_and_configure_ollama(self):
        """Starts background Ollama setup."""
        selected_model = self.ollama_model_combo.get()
        if selected_model == 'Other':
             dialog = ctk.CTkInputDialog(text="Enter the Ollama model name to use:", title="Custom Ollama Model")
             custom_model = dialog.get_input()
             if custom_model:
                  selected_model = custom_model
             else:
                  self.update_status("[yellow]Ollama model selection cancelled.[/]")
                  return

        # Run the Ollama setup process in a separate thread
        threading.Thread(target=lambda: setup_automation.check_install_and_pull_ollama(selected_model, gui_queue), daemon=True).start()

    def check_enable_start_button(self):
        """Checks if all prerequisites are met to enable the Start button."""
        global ollama_setup_complete, audio_devices_found, oauth_complete

        # A more robust check would be needed to confirm Ollama model is actually pulled
        # For simplicity here, we'll rely on a flag set by the ollama setup thread
        ollama_setup_complete = setup_automation.is_ollama_installed() and (self.ollama_model_combo.get() in setup_automation.get_ollama_models() or sg.popup_yes_no("Configured Ollama model not found. Proceed anyway?") == 'Yes') # Basic model check

        # Enable start button only if critical steps are done
        if ollama_setup_complete and audio_devices_found and oauth_complete:
             self.start_button.configure(state="normal", text="Start Automation", tooltip="")
             self.update_status("[green]Setup complete. Ready to start automation.[/]")
             # Transition to main app after a short delay if needed
             # self.after(1000, self.transition_to_main_app)
        else:
             self.start_button.configure(state="disabled", text="Setup Incomplete", tooltip="Complete Ollama, Audio, and Zoom OAuth setup")
             # Update status based on what's missing
             status_messages = []
             if not ollama_setup_complete: status_messages.append("Ollama not configured/model not found.")
             if not audio_devices_found: status_messages.append("No audio devices found.")
             if not oauth_complete: status_messages.append("Zoom OAuth not complete.")
             if status_messages:
                  self.update_status("[yellow]Setup incomplete:[/]\n" + "\n".join(status_messages))


    def transition_to_main_app(self):
        """Hides setup frame and shows main app frame."""
        if self.setup_frame.winfo_ismapped(): # Only transition if currently in setup frame
            self.setup_frame.grid_forget()
            self.main_app_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
            self.update_audio_device_dropdown() # Populate audio devices
            # Redirect stdout/stderr to the output box after transitioning
            sys.stdout = self.output_box
            sys.stderr = self.output_box
            logger.info("Transitioned to main application interface.")


    def refresh_audio_devices(self):
        """Refreshes the list of audio devices."""
        self.update_status("Refreshing audio devices...")
        threading.Thread(target=lambda: setup_automation.check_and_set_audio_devices(gui_queue), daemon=True).start()


    def start_automation(self):
        """Starts the main automation loop."""
        global automation_thread, should_stop_automation

        meeting_id = self.meeting_id_entry.get().strip()
        duration_str = self.duration_entry.get().strip()
        selected_device_name = self.audio_device_combo.get()

        # Basic validation
        if not meeting_id or not duration_str or selected_device_name == 'No devices found':
            self.update_status("[red]❌ Missing required automation parameters.[/]")
            ctk.CTkMessageBox("Warning", "Please provide Meeting ID, Duration, and select an Audio Device.").wait_window()
            return

        try:
            duration = int(duration_str)
            if duration < 10 or duration > 300:
                 self.update_status("[red]❌ Segment duration must be between 10 and 300 seconds.[/]")
                 ctk.CTkMessageBox("Warning", "Segment duration must be between 10 and 300 seconds.").wait_window()
                 return
        except ValueError:
            self.update_status("[red]❌ Invalid duration. Please enter a number.[/]")
            ctk.CTkMessageBox("Warning", "Invalid duration. Please enter a number.").wait_window()
            return

        # Disable controls while running
        self.meeting_id_entry.configure(state="disabled")
        self.duration_entry.configure(state="disabled")
        self.audio_device_combo.configure(state="disabled")
        self.refresh_audio_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        should_stop_automation.clear()
        automation_thread = threading.Thread(
            target=run_loop,
            args=(meeting_id, duration, selected_device_name, should_stop_automation),
            daemon=True
        )
        automation_thread.start()
        self.update_status("[green]🚀 Automation started.[/]")
        logger.info(f"Automation started for meeting {meeting_id} with {duration}s segments on device '{selected_device_name}'")


    def stop_automation(self):
        """Signals the automation loop to stop."""
        self.update_status("[yellow]Signaling automation to stop...[/]")
        should_stop_automation.set()

        # Re-enable controls
        self.meeting_id_entry.configure(state="normal")
        self.duration_entry.configure(state="normal")
        self.audio_device_combo.configure(state="normal")
        self.refresh_audio_button.configure(state="normal")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        logger.info("Stop signal sent to automation thread.")


    def quit(self):
        """Handles application exit."""
        logger.info("Application requested to exit.")
        # Signal automation thread to stop before exiting if it's running
        if automation_thread and automation_thread.is_alive():
            should_stop_automation.set()
            logger.info("Signaling automation thread to stop before exit.")
            # Give it a moment to stop, but don't block indefinitely
            # automation_thread.join(2)

        # Restore stdout/stderr before closing the window
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        super().quit() # Call CTk top-level quit


# --- Entry point ---
if __name__ == "__main__":
    # --- Start Flask Server Thread ---
    # Pass the queue to the Flask app before starting its thread
    set_flask_gui_queue(gui_queue)
    # Use waitress to run Flask in a robust way
    flask_thread = threading.Thread(target=setup_automation.run_waitress_server, args=(app,), daemon=True)
    flask_thread.start()
    logger.info("Flask server thread started.")

    # --- Run the Customtkinter GUI App ---
    app_gui = App()
    app_gui.mainloop()

    logger.info("GUI application main loop finished. Application exit.")