import os
import time
import requests
import json
import base64
import hmac
import hashlib
import datetime
import pyaudio
import wave
import threading
import whisper
from llama_cpp import Llama

# Configuration
ZOOM_API_KEY = "your_zoom_api_key"
ZOOM_API_SECRET = "your_zoom_api_secret"
ZOOM_ACCOUNT_ID = "your_zoom_account_id"
MEETING_ID = "your_meeting_id"
RECORDING_SECONDS = 30  # How long to record audio
LLAMA_MODEL_PATH = "/path/to/llama-3.2-model.gguf"  # Path to Llama 3.2 model

class AudioRecorder:
    def _init_(self, output_filename="recording.wav", 
                 format=pyaudio.paInt16, channels=1, 
                 rate=16000, chunk=1024, record_seconds=RECORDING_SECONDS):
        self.output_filename = output_filename
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.record_seconds = record_seconds
        self.audio = pyaudio.PyAudio()
        self.frames = []
        self.is_recording = False
        
    def start_recording(self):
        """Start recording audio in a separate thread"""
        self.is_recording = True
        self.frames = []
        threading.Thread(target=self._record).start()
        print("Recording started...")
        
    def stop_recording(self):
        """Stop the recording"""
        self.is_recording = False
        print("Recording stopped.")
        
    def _record(self):
        """Record audio from microphone"""
        stream = self.audio.open(format=self.format, channels=self.channels,
                                rate=self.rate, input=True,
                                frames_per_buffer=self.chunk)
        
        start_time = time.time()
        while self.is_recording and (time.time() - start_time) < self.record_seconds:
            data = stream.read(self.chunk)
            self.frames.append(data)
            
        stream.stop_stream()
        stream.close()
        
        # Save the recorded data as a WAV file
        self._save_recording()
        
    def _save_recording(self):
        """Save recording to WAV file"""
        wf = wave.open(self.output_filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.audio.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        print(f"Recording saved to {self.output_filename}")
        
    def close(self):
        """Clean up resources"""
        self.audio.terminate()


class Transcriber:
    def _init_(self, model_size="base"):
        """Initialize the transcriber with the specified model size
        model_size can be: "tiny", "base", "small", "medium", "large"
        """
        print(f"Loading Whisper {model_size} model...")
        self.model = whisper.load_model(model_size)
        print("Model loaded successfully")
        
    def transcribe(self, audio_file):
        """Transcribe the given audio file"""
        print(f"Transcribing {audio_file}...")
        result = self.model.transcribe(audio_file)
        print("Transcription complete")
        return result["text"]


class LlamaProcessor:
    def _init_(self, model_path=LLAMA_MODEL_PATH):
        """Initialize Llama model"""
        print("Loading Llama 3.2 model...")
        self.llm = Llama(model_path=model_path, n_ctx=4096)
        print("Llama model loaded successfully")
        
    def generate_poll_from_transcript(self, transcript):
        """Generate poll question and options from transcript using Llama"""
        prompt = f"""
Based on the following transcript, generate a poll question and four options that would be engaging for the audience.
Format your response as a JSON object with 'question' and 'options' fields.

Transcript: {transcript}

JSON response:
"""
        
        print("Generating poll with Llama 3.2...")
        response = self.llm(prompt, max_tokens=1024, temperature=0.7, stop=["```"])
        
        # Extract JSON from the response
        try:
            # Find JSON in the response
            response_text = response['choices'][0]['text']
            # Extract JSON part between first { and last }
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                poll_data = json.loads(json_str)
                return poll_data
            else:
                # Fallback if JSON formatting failed
                return {
                    "question": "What was the most interesting part of the discussion?",
                    "options": [
                        "Option 1", "Option 2", "Option 3", "Option 4"
                    ]
                }
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            # Return a default poll if parsing fails
            return {
                "question": "What was the most interesting part of the discussion?",
                "options": [
                    "Option 1", "Option 2", "Option 3", "Option 4"
                ]
            }


class ZoomAPI:
    def _init_(self, api_key=ZOOM_API_KEY, api_secret=ZOOM_API_SECRET, account_id=ZOOM_ACCOUNT_ID):
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self.base_url = "https://api.zoom.us/v2"
        
    def _generate_jwt_token(self):
        """Generate a JWT token for Zoom API authentication"""
        expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        expiration_seconds = int(expiration.timestamp())
        
        header = {
            "alg": "HS256",
            "typ": "JWT"
        }
        
        payload = {
            "iss": self.api_key,
            "exp": expiration_seconds
        }
        
        header_str = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
        payload_str = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        
        signature_data = f"{header_str}.{payload_str}".encode()
        signature = hmac.new(self.api_secret.encode(), signature_data, hashlib.sha256).digest()
        signature_str = base64.urlsafe_b64encode(signature).decode().rstrip('=')
        
        jwt_token = f"{header_str}.{payload_str}.{signature_str}"
        return jwt_token
    
    def create_poll(self, meeting_id, poll_title, question, options):
        """Create a poll in a Zoom meeting"""
        url = f"{self.base_url}/meetings/{meeting_id}/polls"
        
        # Format the questions as required by Zoom API
        questions = [{
            "name": question,
            "type": "single",
            "answers": options
        }]
        
        data = {
            "title": poll_title,
            "questions": questions
        }
        
        headers = {
            "Authorization": f"Bearer {self._generate_jwt_token()}",
            "Content-Type": "application/json"
        }
        
        print(f"Creating Zoom poll: {poll_title}")
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in [200, 201, 204]:
            print("Poll created successfully!")
            return response.json()
        else:
            print(f"Error creating poll: {response.status_code} - {response.text}")
            return None
            
    def launch_poll(self, meeting_id, poll_id):
        """Launch an already created poll in an active meeting"""
        url = f"{self.base_url}/meetings/{meeting_id}/polls/{poll_id}/launch"
        
        headers = {
            "Authorization": f"Bearer {self._generate_jwt_token()}",
            "Content-Type": "application/json"
        }
        
        print(f"Launching poll {poll_id}...")
        response = requests.put(url, headers=headers)
        
        if response.status_code in [200, 201, 204]:
            print("Poll launched successfully!")
            return True
        else:
            print(f"Error launching poll: {response.status_code} - {response.text}")
            return False


def run_automation():
    """Run the complete automation pipeline"""
    # Step 1: Record audio
    recorder = AudioRecorder(record_seconds=RECORDING_SECONDS)
    recorder.start_recording()
    
    # Wait for recording to complete (can be replaced with a stop button in a UI)
    time.sleep(RECORDING_SECONDS + 1)
    
    # Step 2: Transcribe the audio
    transcriber = Transcriber(model_size="base")
    transcript = transcriber.transcribe("recording.wav")
    print(f"Transcript: {transcript}")
    
    # Step 3: Process with Llama to generate poll
    llm_processor = LlamaProcessor()
    poll_data = llm_processor.generate_poll_from_transcript(transcript)
    print(f"Generated poll: {poll_data}")
    
    # Step 4: Create and launch the poll in Zoom
    zoom_api = ZoomAPI()
    poll_title = "Generated Poll from Discussion"
    poll_response = zoom_api.create_poll(
        MEETING_ID, 
        poll_title, 
        poll_data["question"], 
        poll_data["options"]
    )
    
    if poll_response and "id" in poll_response:
        # Launch the poll if created successfully
        zoom_api.launch_poll(MEETING_ID, poll_response["id"])
    
    # Clean up
    recorder.close()
    print("Automation completed!")


if _name_ == "_main_":
    run_automation()