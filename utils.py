import numpy as np
import librosa

SAMPLE_RATE = 22050
DURATION = 3
SAMPLES_PER_TRACK = SAMPLE_RATE * DURATION

def preprocess_chunk(audio_chunk):

    audio_chunk = audio_chunk - np.mean(audio_chunk)

    max_val = np.max(np.abs(audio_chunk))
    if max_val > 0:
        audio_chunk = audio_chunk / max_val

    audio_chunk = audio_chunk * 3.0
    audio_chunk = np.clip(audio_chunk, -1, 1)

    mel = librosa.feature.melspectrogram(
        y=audio_chunk,
        sr=SAMPLE_RATE,
        n_mels=128
    )

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


def split_audio(audio):
    chunks = []
    step = SAMPLES_PER_TRACK // 2

    for i in range(0, len(audio), step):
        chunk = audio[i:i + SAMPLES_PER_TRACK]

        if len(chunk) < SAMPLES_PER_TRACK:
            chunk = np.pad(chunk, (0, SAMPLES_PER_TRACK - len(chunk)))

        chunks.append(chunk)

    return chunks