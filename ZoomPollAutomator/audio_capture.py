# audio_capture.py
import sounddevice as sd
import soundfile  as sf
import numpy     as np
import librosa
import logging
import os
import tempfile
import time # Import time for sleep if needed

logger = logging.getLogger(__name__)

def list_audio_devices():
    """List all available audio input devices."""
    logger.info("Listing available audio devices...")
    try:
        devices = sd.query_devices()
        input_devices = [
            {"name": dev['name'], "index": i, "max_input_channels": dev['max_input_channels']}
            for i, dev in enumerate(devices) if dev['max_input_channels'] > 0
        ]
        if not input_devices:
            logger.warning("No audio input devices found. Please check your microphone connections.")
            return []
            
        logger.info(f"Found {len(input_devices)} audio input devices.")
        for dev in input_devices:
             logger.info(f"  Index {dev['index']}: {dev['name']}")
        return input_devices
    except Exception as e:
        logger.error(f"Error listing audio devices: {e}", exc_info=True)
        if "PortAudio" in str(e):
             logger.error("PortAudio binding error. Please ensure your audio drivers are properly installed.")
        return []


def record_segment(duration: int,
                   samplerate: int = 44100,
                   channels:   int = 2,
                   device:     str = None):
    """
    1) Record audio @44.1 kHz, stereo from `device` name (or default).
    2) Mix to mono, resample to 16 kHz, normalize, save to "segment.wav".
    Returns True on success (audio captured), False on failure or silence.
    """
    tmp_path = None
    output_path = "segment.wav"
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        # Find device index with improved error handling
        device_index = None
        if device and device.lower() != 'default':
            try:
                devices = sd.query_devices()
                device_index = next(
                    (i for i, d in enumerate(devices) 
                     if d['name'].lower() == device.lower() and d['max_input_channels'] > 0),
                    None
                )
                
                if device_index is None:
                    # Try partial match
                    device_index = next(
                        (i for i, d in enumerate(devices)
                         if device.lower() in d['name'].lower() and d['max_input_channels'] > 0),
                        None
                    )
                
                if device_index is not None:
                    logger.info(f"Using audio device '{devices[device_index]['name']}' (Index {device_index})")
                else:
                    logger.warning(f"Device '{device}' not found. Using default.")
            except Exception as e:
                logger.error(f"Error finding device: {e}", exc_info=True)

        # Record audio with improved error handling
        try:
            audio_data = sd.rec(
                int(duration * samplerate),
                samplerate=samplerate,
                channels=channels,
                dtype="float32",  # Changed to float32 for better processing
                device=device_index,
                blocking=True
            )
        except sd.PortAudioError as e:
            logger.error(f"PortAudio recording error: {e}", exc_info=True)
            return False

        # Early silence check
        if audio_data is None or np.all(np.abs(audio_data) < 1e-4):
            logger.warning("Detected silence or no input")
            return False

        # Process audio
        if audio_data.ndim > 1:
            mono = audio_data.mean(axis=1)
        else:
            mono = audio_data

        # Normalize with improved method
        abs_max = np.abs(mono).max()
        if abs_max > 1e-6:  # Avoid division by very small numbers
            mono = mono / abs_max * 0.9  # Leave headroom
        
        # Resample
        target_sr = 16000
        mono16 = librosa.resample(mono, orig_sr=samplerate, target_sr=target_sr)

        # Save final output
        sf.write(output_path, mono16, target_sr, subtype='PCM_16')
        logger.info(f"Successfully saved audio to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Recording error: {e}", exc_info=True)
        return False
        
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as e:
                logger.warning(f"Failed to remove temp file: {e}")


if __name__ == "__main__":
    # For testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Testing audio_capture.py")
    devices = list_audio_devices()
    if devices:
        logger.info("Recording a 5-second segment using the default device...")
        success = record_segment(5)
        logger.info(f"Recording test finished. Success: {success}")
    else:
        logger.warning("No audio devices found. Skipping recording test.")