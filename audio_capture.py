# audio_capture.py

import sounddevice as sd
import soundfile  as sf
import numpy     as np
import librosa
from rich.console import Console

console = Console()

def record_segment(duration: int,
                   samplerate: int = 44100,
                   channels:   int = 2,
                   output:     str = "segment.wav",
                   device:     str = None):
    """
    1) Record stereo @44.1 kHz from `device` (or default if device is None/empty)
    2) Mix to mono, resample to 16 kHz, normalize, save to `segment.wav`
    """
    # if user passed empty string, treat as None → default device
    dev = None if not device else device

    tmp = "temp_stereo.wav"
    console.log(f"🔴 Recording {duration}s @44.1kHz, stereo → {tmp} (device: {dev})")
    # record int16 PCM
    audio = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=channels,
        dtype="int16",
        device=dev
    )
    sd.wait()
    sf.write(tmp, audio, samplerate, subtype="PCM_16")
    console.log("✅ Stereo file saved")

    # load + mix + resample
    data, sr = sf.read(tmp, dtype="float32")
    mono     = data.mean(axis=1)
    mono16   = librosa.resample(mono, orig_sr=sr, target_sr=16000)
    # normalize RMS
    rms    = np.sqrt((mono16**2).mean())
    mono16 = mono16 * (0.1 / (rms + 1e-8))
    sf.write(output, mono16, 16000, subtype="PCM_16")
    console.log("✅ Final segment.wav @16kHz mono")
