#!/usr/bin/env python3
"""
Faster-Whisper HTTP Server
Uses CTranslate2 for optimized inference
"""
import os
import time
from flask import Flask, request, jsonify
from faster_whisper import WhisperModel

app = Flask(__name__)

MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

print(f"Loading Faster-Whisper model: {MODEL_SIZE} on {DEVICE} with {COMPUTE_TYPE}")
start = time.time()
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print(f"Model loaded in {time.time() - start:.2f}s")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/inference', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    audio_file = request.files['file']

    temp_path = f"/tmp/faster-whisper-{int(time.time()*1000)}.wav"
    audio_file.save(temp_path)

    try:
        import subprocess
        audio_info = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                                     'format=duration,size', '-of', 'default=noprint_wrappers=1',
                                     temp_path], capture_output=True, text=True)
        print(f"Audio info: {audio_info.stdout}")

        start = time.time()
        segments, info = model.transcribe(
            temp_path,
            language="it",
            beam_size=5,
            best_of=5,
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            initial_prompt="Chi dovrei controllare oggi? Quale stabilimento controllare? Piano di controllo. Attività di verifica. Ispezioni veterinarie. Controlli sanitari.",
            condition_on_previous_text=True,
            word_timestamps=True,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6
        )

        segments_list = list(segments)
        for i, seg in enumerate(segments_list):
            print(f"Segment {i}: [{seg.start:.2f}s - {seg.end:.2f}s] '{seg.text}' (prob: {seg.avg_logprob:.2f})")

        text = " ".join([segment.text for segment in segments_list])
        duration = time.time() - start

        print(f"Transcribed in {duration:.2f}s: '{text}'")

        return jsonify({
            "text": text.strip(),
            "duration": duration,
            "language": info.language
        })

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8090, threaded=True)
