# =========================================
# 🔫 GUNSHOT PREDICTOR (FINAL)
# =========================================

import numpy as np
import librosa
import tensorflow as tf
import subprocess
import os
import uuid
import shutil

# CONFIG
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "final_gunshot_model.h5")
SAMPLE_RATE = 44100
DURATION = 3
SAMPLES_PER_TRACK = SAMPLE_RATE * DURATION
THRESHOLD = 0.28


def _resolve_ffmpeg_path():
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    path_cmd = shutil.which("ffmpeg")
    if path_cmd:
        return path_cmd

    # Common Windows winget location fallback.
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    winget_candidate = os.path.join(
        local_app_data,
        "Microsoft",
        "WinGet",
        "Packages",
    )
    if os.path.isdir(winget_candidate):
        for root, _, files in os.walk(winget_candidate):
            if "ffmpeg.exe" in files:
                return os.path.join(root, "ffmpeg.exe")

    return None

# LOAD MODEL
model = tf.keras.models.load_model(MODEL_PATH)
print("✅ Model Loaded")

# CONVERT AUDIO → WAV (COLAB MATCH)
def convert_to_wav(input_file):
    if not os.path.exists(input_file):
        raise RuntimeError(f"Input audio file not found: {input_file}")

    ffmpeg_path = _resolve_ffmpeg_path()
    if not ffmpeg_path:
        raise RuntimeError(
            "ffmpeg executable not found. Install ffmpeg and add it to PATH, "
            "or set FFMPEG_PATH to ffmpeg.exe."
        )

    output_file = f"temp_{uuid.uuid4()}.wav"

    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_file,
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "-y",
        output_file
    ]

    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"ffmpeg launch failed (WinError 2). Resolved path: {ffmpeg_path}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr_text = exc.stderr.decode(errors="ignore").strip()
        stderr_lines = [line.strip() for line in stderr_text.splitlines() if line.strip()]
        short_error = stderr_lines[-1] if stderr_lines else "unsupported or invalid audio format"
        raise RuntimeError(f"ffmpeg conversion failed: {short_error}") from exc

    return output_file

# SPLIT AUDIO
def split_audio(audio):
    chunks = []

    for i in range(0, len(audio), SAMPLES_PER_TRACK):
        chunk = audio[i:i + SAMPLES_PER_TRACK]

        if len(chunk) < SAMPLES_PER_TRACK:
            chunk = np.pad(chunk, (0, SAMPLES_PER_TRACK - len(chunk)))

        chunks.append(chunk)

    return chunks

# PREPROCESS (EXACT TRAINING MATCH)
def preprocess_chunk(audio_chunk):
    mel = librosa.feature.melspectrogram(y=audio_chunk, sr=SAMPLE_RATE)
    mel_db = librosa.power_to_db(mel, ref=np.max)

    mel_db = librosa.util.fix_length(mel_db, size=128, axis=1)
    mel_db = mel_db[:128, :]

    mel_min = mel_db.min()
    mel_max = mel_db.max()

    if mel_max - mel_min == 0:
        mel_db = np.zeros((128, 128))
    else:
        mel_db = (mel_db - mel_min) / (mel_max - mel_min)

    return mel_db.reshape(1, 128, 128, 1)

# MAIN FUNCTION
def detect_gunshot(file_path):
    wav_file = convert_to_wav(file_path)
    try:
        audio, _ = librosa.load(wav_file, sr=SAMPLE_RATE)
        chunks = split_audio(audio)

        results = []
        gunshot_detected = False
        max_score = 0.0

        for i, chunk in enumerate(chunks):
            processed = preprocess_chunk(chunk)
            prediction = model.predict(processed, verbose=0)[0][0]
            score = float(prediction)

            is_gunshot = bool(score > THRESHOLD)

            results.append({
                "chunk": int(i + 1),
                "score": score,
                "gunshot": is_gunshot
            })

            if score > max_score:
                max_score = score

            if is_gunshot:
                gunshot_detected = True

        return {
            "gunshot_detected": bool(gunshot_detected),
            "threshold": float(THRESHOLD),
            "max_score": float(max_score),
            "chunks": results
        }
    finally:
        if os.path.exists(wav_file):
            os.remove(wav_file)