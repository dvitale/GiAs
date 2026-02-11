#!/usr/bin/env python3
"""
Whisper Python HTTP Server
Uses OpenAI's original whisper for best accuracy
"""
import os
import time
import whisper
from flask import Flask, request, jsonify

app = Flask(__name__)

MODEL_NAME = os.getenv("WHISPER_MODEL", "medium")

print(f"Loading Whisper model: {MODEL_NAME}...", flush=True)
start = time.time()
model = whisper.load_model(MODEL_NAME)
print(f"Model loaded in {time.time() - start:.2f}s", flush=True)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "model": MODEL_NAME})

@app.route('/inference', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    audio_file = request.files['file']
    temp_path = f"/tmp/whisper-python-{int(time.time()*1000)}.wav"

    try:
        audio_file.save(temp_path)

        file_size = os.path.getsize(temp_path)
        print(f"Received audio file: {file_size} bytes", flush=True)

        if file_size < 1000:
            print(f"WARNING: File too small ({file_size} bytes), likely corrupted", flush=True)
            return jsonify({"error": "Audio file too small or corrupted"}), 400

        start = time.time()
        result = model.transcribe(
            temp_path,
            language="it",
            fp16=False,
            verbose=True,
            temperature=0.0,
            beam_size=5,
            best_of=5,
            suppress_tokens="-1",
            without_timestamps=False
        )
        duration = time.time() - start

        text = result["text"].strip()
        print(f"Transcribed in {duration:.2f}s: {text[:60]}...", flush=True)
        print(f"Full transcription: {text}", flush=True)

        return jsonify({
            "text": text,
            "duration": duration,
            "language": result.get("language", "it")
        })

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    print(f"Starting Whisper server on :8090", flush=True)
    app.run(host='0.0.0.0', port=8090, threaded=True)
