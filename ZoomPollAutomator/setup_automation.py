# setup_automation.py
import subprocess
import sys
import os
import time
import requests
import logging
import re
import json
import threading

# Local imports
import config
import audio_capture
from waitress import serve

logger = logging.getLogger(__name__)

OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/OllamaSetup.exe"

# Attempt to import the gui_queue from main_gui.py's scope
# This requires that main_gui.py has defined gui_queue in its global scope
try:
    from main_gui import gui_queue
except ImportError:
    logger.error("Could not import gui_queue in setup_automation. GUI updates will not work.")
    gui_queue = None # Set to None if import fails


def run_waitress_server(flask_app):
    """Runs the Flask server using Waitress."""
    try:
        logger.info("Starting Flask server with Waitress on http://0.0.0.0:8000")
        serve(flask_app, host='0.0.0.0', port=8000)
    except Exception as e:
        logger.error(f"Error running Waitress server: {e}", exc_info=True)
        if gui_queue:
            gui_queue.put(('STATUS', f"[red]❌ Error starting Flask server: {e}[/]. Check logs."))


def is_ollama_installed():
    """Checks if Ollama is running by querying its API."""
    ollama_api_url = config.get_config("OLLAMA_API") + "/api/tags"
    try:
        response = requests.get(ollama_api_url, timeout=3)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        logger.warning("Ollama connection failed during is_ollama_installed check.")
        return False
    except Exception as e:
        logger.error(f"Error checking Ollama status in is_ollama_installed: {e}", exc_info=True)
        return False

def get_ollama_models():
    """Gets the list of installed Ollama models."""
    ollama_api_url = config.get_config("OLLAMA_API") + "/api/tags"
    try:
        response = requests.get(ollama_api_url, timeout=5)
        if response.status_code == 200:
            models_data = response.json()
            return [model['name'] for model in models_data.get('models', [])]
        else:
            logger.warning(f"Failed to get Ollama models: {response.status_code} - {response.text}")
            return []
    except requests.exceptions.RequestException:
         logger.warning("Ollama connection failed during get_ollama_models check.")
         return []
    except Exception as e:
        logger.error(f"Error getting Ollama models: {e}", exc_info=True)
        return []


def install_ollama_windows(gui_queue):
    """Silently downloads and installs Ollama on Windows."""
    if gui_queue: gui_queue.put(('STATUS', 'Downloading Ollama Installer...'))
    logger.info("Downloading Ollama Installer...")
    ollama_installer_path = "OllamaSetup.exe" # Download to the current directory

    try:
        response = requests.get(OLLAMA_DOWNLOAD_URL, stream=True)
        response.raise_for_status()
        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 8192
        progress = 0
        with open(ollama_installer_path, 'wb') as file:
            for data in response.iter_content(block_size):
                progress += len(data)
                file.write(data)
                if total_size_in_bytes > 0 and gui_queue:
                     gui_queue.put(('PROGRESS', int((progress / total_size_in_bytes) * 50)))

        if gui_queue: gui_queue.put(('STATUS', 'Installing Ollama (this may take a few minutes)...'))
        logger.info("Installing Ollama...")
        if gui_queue: gui_queue.put(('PROGRESS', 50))

        # Run the installer silently using /S flag
        # Use shell=False for better security
        process = subprocess.Popen([ollama_installer_path, "/S"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate() # Wait for installation to finish

        if process.returncode == 0:
             if gui_queue: gui_queue.put(('PROGRESS', 100))
             logger.info("Ollama installation finished.")
             # Give Ollama a moment to start after installation
             time.sleep(5)
             return True
        else:
             logger.error(f"Ollama installation failed. Installer output:\n{stderr.decode()}")
             if gui_queue: gui_queue.put(('STATUS', f'[red]❌ Error installing Ollama. See logs.[/]'))
             if gui_queue: gui_queue.put(('PROGRESS', 0))
             return False

    except requests.exceptions.RequestException as e:
         logger.error(f"Error downloading Ollama installer: {e}", exc_info=True)
         if gui_queue: gui_queue.put(('STATUS', f'Error downloading Ollama: {e}[/]'))
         if gui_queue: gui_queue.put(('PROGRESS', 0))
         return False
    except FileNotFoundError:
         logger.error("OllamaSetup.exe not found after download attempt.", exc_info=True)
         if gui_queue: gui_queue.put(('STATUS', 'Installer file not found after download.'))
         if gui_queue: gui_queue.put(('PROGRESS', 0))
         return False
    except Exception as e:
        logger.error(f"Error during Ollama installation: {e}", exc_info=True)
        if gui_queue: gui_queue.put(('STATUS', f'Error installing Ollama: {e}[/]'))
        if gui_queue: gui_queue.put(('PROGRESS', 0))
        return False
    finally:
        # Clean up the installer file
        if os.path.exists(ollama_installer_path):
            try:
                os.remove(ollama_installer_path)
            except OSError as e:
                logger.warning(f"Failed to remove installer file: {e}")


def pull_ollama_model(model_name, gui_queue):
    """Pulls a specified Ollama model."""
    if gui_queue: gui_queue.put(('STATUS', f'Pulling Ollama model: {model_name}...'))
    logger.info(f'Pulling Ollama model: {model_name}')
    if gui_queue: gui_queue.put(('PROGRESS', 0))

    try:
        # Ensure Ollama command is accessible in the environment
        # If not in PATH after silent install, might need to find the install location
        # For simplicity, assume 'ollama' is in PATH
        process = subprocess.Popen(['ollama', 'pull', model_name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

        # Parse output to find progress updates
        progress_pattern = re.compile(r'pulling\s+(\d+)%|^success') # Added success pattern
        while True:
            output_line = process.stdout.readline()
            if output_line == '' and process.poll() is not None:
                break
            if output_line:
                logger.info(f"Ollama Pull: {output_line.strip()}")
                match = progress_pattern.search(output_line)
                if match:
                    if match.group(1): # Progress percentage found
                        try:
                            progress_percent = int(match.group(1))
                            if gui_queue: gui_queue.put(('PROGRESS', progress_percent))
                            if gui_queue: gui_queue.put(('STATUS', f'Pulling {model_name}: {progress_percent}%'))
                        except ValueError:
                            pass
                    elif 'success' in match.group(0): # Success message found
                         if gui_queue: gui_queue.put(('PROGRESS', 100))
                         if gui_queue: gui_queue.put(('STATUS', f'Successfully pulled {model_name}.'))


        rc = process.wait()

        if rc == 0:
            if gui_queue: gui_queue.put(('STATUS', f'Successfully pulled {model_name}.'))
            logger.info(f'Successfully pulled {model_name}.')
            # Ensure progress reaches 100% on success
            if gui_queue: gui_queue.put(('PROGRESS', 100))
            return True
        else:
            logger.error(f"Error pulling model {model_name}. Return code: {rc}")
            if gui_queue: gui_queue.put(('STATUS', f'[red]❌ Error pulling {model_name}. Check logs.[/]'))
            if gui_queue: gui_queue.put(('PROGRESS', 0))
            return False
    except FileNotFoundError:
        logger.error("Ollama command not found. Is Ollama installed and in PATH?", exc_info=True)
        if gui_queue: gui_queue.put(('STATUS', '[red]Error: Ollama command not found. Is Ollama installed?[/]'))
        if gui_queue: gui_queue.put(('PROGRESS', 0))
        return False
    except Exception as e:
        logger.error(f"Error pulling model {model_name}: {e}", exc_info=True)
        if gui_queue: gui_queue.put(('STATUS', f'Error pulling {model_name}: {e}[/]'))
        if gui_queue: gui_queue.put(('PROGRESS', 0))
        return False


def check_install_and_pull_ollama(model_name, gui_queue):
    """Orchestrates checking, installing, and pulling Ollama."""
    if gui_queue: gui_queue.put(('STATUS', 'Checking Ollama status...'))
    logger.info("Checking Ollama status...")
    if gui_queue: gui_queue.put(('PROGRESS', 0))

    # Check if model name is valid
    if not model_name or not isinstance(model_name, str):
        if gui_queue: gui_queue.put(('STATUS', "[red]❌ Invalid model name specified.[/]"))
        return False

    ollama_installed = is_ollama_installed()
    
    if not ollama_installed:
        logger.info("Ollama not found. Attempting installation.")
        install_success = install_ollama_windows(gui_queue)
        if not install_success:
            if gui_queue: gui_queue.put(('STATUS', "[red]❌ Ollama installation failed.[/]"))
            if gui_queue: gui_queue.put(('OLLAMA_SETUP_COMPLETE', False)) # Signal failure to GUI
            return False
        # Re-check if Ollama is running after installation attempt
        ollama_installed = is_ollama_installed()
        if not ollama_installed:
             if gui_queue: gui_queue.put(('STATUS', "[red]❌ Ollama installed but not running. Please start Ollama manually.[/]"))
             logger.error("Ollama installed but not running after waiting.")
             if gui_queue: gui_queue.put(('OLLAMA_SETUP_COMPLETE', False))
             return False
        logger.info("Ollama installed and appears to be running.")
    else:
        if gui_queue: gui_queue.put(('STATUS', "[green]✅ Ollama detected.[/]"))
        logger.info("Ollama detected.")
        if gui_queue: gui_queue.put(('PROGRESS', 10))


    # Check if the desired model is already installed
    if gui_queue: gui_queue.put(('STATUS', f'Checking for model: {model_name}...'))
    installed_models = get_ollama_models()
    if gui_queue: gui_queue.put(('OLLAMA_MODELS', installed_models))
    logger.info(f"Installed Ollama models: {installed_models}")

    # Enhanced model check
    if model_name not in installed_models:
        logger.info(f"Model '{model_name}' not found. Attempting to pull.")
        if gui_queue: gui_queue.put(('STATUS', f"[yellow]Model '{model_name}' not found. Downloading... This may take several minutes.[/]"))
        pull_success = pull_ollama_model(model_name, gui_queue)
        if not pull_success:
            if gui_queue: gui_queue.put(('STATUS', f"[red]❌ Failed to pull model '{model_name}'. Please check your internet connection and try again.[/]"))
            if gui_queue: gui_queue.put(('OLLAMA_SETUP_COMPLETE', False))
            return False
        logger.info(f"Model '{model_name}' pulled successfully.")
    else:
        if gui_queue: gui_queue.put(('STATUS', f"[green]✅ Model '{model_name}' already installed.[/]"))
        logger.info(f"Model '{model_name}' already installed.")
        if gui_queue: gui_queue.put(('PROGRESS', 100))

    # Signal to the GUI that Ollama setup is complete and successful
    if gui_queue: gui_queue.put(('OLLAMA_SETUP_COMPLETE', True))
    if gui_queue: gui_queue.put(('STATUS', "[green]✅ Ollama setup complete.[/]"))
    logger.info("Ollama setup complete process finished.")
    return True


def check_and_set_audio_devices(gui_queue):
    """Checks audio devices and sends list to GUI."""
    if gui_queue: gui_queue.put(('STATUS', 'Checking audio devices...'))
    logger.info('Checking audio devices...')
    try:
        devices = audio_capture.list_audio_devices()
        if gui_queue: gui_queue.put(('AUDIO_DEVICES', devices))
        logger.info(f"Audio device check complete. Found {len(devices)} devices.")
    except Exception as e:
        logger.error(f"Error listing audio devices: {e}", exc_info=True)
        if gui_queue: gui_queue.put(('STATUS', f'[red]❌ Error listing audio devices: {e}[/]. Check logs.'))
        if gui_queue: gui_queue.put(('AUDIO_DEVICES', [])) # Send empty list on error


# Note: The run_waitress_server function will be called from main_gui.py in a thread.