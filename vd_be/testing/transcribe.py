import whisper
import os

model = whisper.load_model("base")  # You can use "small" or "medium" too

def transcribe_audio(file_path):
    try:
        result = model.transcribe(file_path)
        return result['text']
    except Exception as e:
        print("Transcription failed:", e)
        return None
