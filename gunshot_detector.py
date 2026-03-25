# =========================================
# 🔫 GUNSHOT PREDICTOR (FINAL)
# =========================================

import numpy as np
import librosa
import tensorflow as tf
import subprocess
import os
import uuid

# CONFIG
MODEL_PATH = "model/final_gunshot_model.h5"
SAMPLE_RATE = 22050
DURATION = 3
SAMPLES_PER_TRACK = SAMPLE_RATE * DURATION
THRESHOLD = 0.4

# LOAD MODEL
model = tf.keras.models.load_model(MODEL_PATH)
print("✅ Model Loaded")

# CONVERT AUDIO → WAV (COLAB MATCH)
def convert_to_wav(input_file):
    output_file = f"temp_{uuid.uuid4()}.wav"

    command = [
        "ffmpeg",
        "-i", input_file,
        "-ac", "1",
        "-ar", "22050",
        "-y",
        output_file
    ]

    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    audio, _ = librosa.load(wav_file, sr=SAMPLE_RATE)
    chunks = split_audio(audio)

    results = []
    gunshot_detected = False

    for i, chunk in enumerate(chunks):
        processed = preprocess_chunk(chunk)
        prediction = model.predict(processed, verbose=0)[0][0]

        is_gunshot = bool(prediction > THRESHOLD)

        results.append({
            "chunk": int(i + 1),
            "score": float(prediction),
            "gunshot": is_gunshot
        })

        if is_gunshot:
            gunshot_detected = True

    if os.path.exists(wav_file):
        os.remove(wav_file)

    return {
        "gunshot_detected": bool(gunshot_detected),
        "chunks": results
    }