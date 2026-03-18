from elevenlabs import ElevenLabs
from pydub import AudioSegment
import io
import os
import time
import config

client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

# Define voice IDs for Speaker A (Host) and Speaker B (Expert)
VOICE_IDS = {
    "A": "pNInz6obpgmqS7UaD16f",  # Host - Example: Adam
    "B": "MF3mGyEYCl7XYW7Lp9P9",  # Expert - Example: Bella
}

def generate_audio_chunk(text, voice_id, retries=3):
    for attempt in range(retries):
        try:
            audio_generator = client.generate(
                text=text,
                voice=voice_id,
                model="eleven_multilingual_v2"
            )

            # Collect the chunks from the generator into bytes
            audio_bytes = b"".join(audio_generator)
            return AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        except Exception as e:
            if "rate limit" in str(e).lower() and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise e

def concatenate_audio(script):
    full_audio = AudioSegment.silent(duration=0)

    for line in script:
        speaker = line.get("speaker")
        text = line.get("text")

        voice_id = VOICE_IDS.get(speaker, VOICE_IDS["A"])
        audio_chunk = generate_audio_chunk(text, voice_id)

        # Add 500ms silence between lines
        full_audio += audio_chunk + AudioSegment.silent(duration=500)

    return full_audio

def add_ambience(audio_segment, ambience_file_path=None):
    if not ambience_file_path or not os.path.exists(ambience_file_path):
        # Create a subtle studio-like hum if no file provided (using white noise at low volume)
        # For simplicity, we'll just return the original if no ambience path.
        # Ideally, we'd have a 'coffee_shop.mp3' or 'studio.mp3' available.
        return audio_segment

    ambience = AudioSegment.from_file(ambience_file_path)
    # Lower the ambience volume significantly
    ambience = ambience - 25
    # Loop ambience to match main audio duration
    ambience = ambience * (len(audio_segment) // len(ambience) + 1)
    ambience = ambience[:len(audio_segment)]

    return audio_segment.overlay(ambience)
