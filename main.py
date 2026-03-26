import numpy as np
import librosa
import tensorflow as tf
import subprocess
import os
import uuid
import shutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from utils import split_audio, preprocess_chunk as shared_preprocess_chunk

app = FastAPI()
templates = Jinja2Templates(directory="templates")

MODEL_PATH = "model/final_audio_model_v4.h5"
model = tf.keras.models.load_model(MODEL_PATH)

SAMPLE_RATE = 22050
CHUNK_SECONDS = 3
SAMPLES_PER_TRACK = SAMPLE_RATE * CHUNK_SECONDS
LIVE_MIN_SECONDS = 0.5
UPLOAD_GUNSHOT_THRESHOLD = 0.5
UPLOAD_SCREAM_THRESHOLD = 0.2
LIVE_GUNSHOT_CONFIRM_THRESHOLD = 0.22
LIVE_GUNSHOT_PROBABLE_THRESHOLD = 0.12
LIVE_SCREAM_THRESHOLD = 0.18
UPLOAD_GAIN_DB = 6
LIVE_GAIN_DB = 4
LIVE_SHAPING_FILTER = "highpass=f=120,lowpass=f=7000,acompressor=threshold=-22dB:ratio=3:attack=5:release=80,loudnorm"
UPLOAD_RMS_MIN = 0.003
LIVE_RMS_MIN = 0.01
UPLOAD_DIR = "uploaded_audio"
SAVE_LIVE_CHUNKS_FOR_TESTING = True
TEST_CHUNKS_DIR = os.path.join("testing_chunks", "live_chunks")
TEST_RAW_DIR = os.path.join(TEST_CHUNKS_DIR, "raw")
TEST_WAV_DIR = os.path.join(TEST_CHUNKS_DIR, "wav")

# Email Configuration
EMAIL_ENABLED = True  # Set to False to disable email notifications
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "sahilbhandare80@gmail.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "hxzbgdbbfopqhrme")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "sahilbhandare79@gmail.com")

# If a legacy file named uploaded_audio exists, switch to a safe folder name.
if os.path.exists(UPLOAD_DIR) and not os.path.isdir(UPLOAD_DIR):
    UPLOAD_DIR = "uploaded_audio_dir"

os.makedirs(UPLOAD_DIR, exist_ok=True)
if SAVE_LIVE_CHUNKS_FOR_TESTING:
    os.makedirs(TEST_RAW_DIR, exist_ok=True)
    os.makedirs(TEST_WAV_DIR, exist_ok=True)


def _resolve_ffmpeg_path():
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    path_cmd = shutil.which("ffmpeg")
    if path_cmd:
        return path_cmd

    return None


def send_alert_email(label, detection_type="upload", score=None, probabilities=None):
    """
    Send an email alert when gunshot or scream is detected.
    
    Args:
        label: Detection label (e.g., "Gunshot 🔫", "Scream 😱")
        detection_type: Either "upload" or "live"
        score: Confidence score
        probabilities: Dict with gunshot, scream, background probabilities
    """
    if not EMAIL_ENABLED:
        return
    
    try:
        subject = f"🚨 ALERT: {label} Detected ({detection_type.upper()})"
        
        body = f"""
Gunshot/Scream Detection Alert
==============================

Detection Type: {detection_type.upper()}
Label: {label}
Timestamp: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""
        
        if probabilities:
            body += f"""
Probabilities:
- Gunshot: {probabilities.get('gunshot', 0.0):.4f}
- Scream: {probabilities.get('scream', 0.0):.4f}
- Background: {probabilities.get('background', 0.0):.4f}
"""
        
        if score is not None:
            body += f"\nConfidence Score: {score:.4f}"
        
        body += "\n\nPlease check and take appropriate action if necessary."
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        print(f"[EMAIL] Alert sent: {label}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send alert email: {str(e)}")



def _prediction_from_probs(gun, scream, bg, mode="upload"):
    gun = float(gun)
    scream = float(scream)
    bg = float(bg)

    if mode == "live":
        if gun >= LIVE_GUNSHOT_CONFIRM_THRESHOLD:
            return "Gunshot 🔫", True
        if gun >= LIVE_GUNSHOT_PROBABLE_THRESHOLD:
            return "Possible Gunshot ⚠️", False
        if scream >= LIVE_SCREAM_THRESHOLD:
            return "Scream 😱", False
        return "Background", False

    if gun > UPLOAD_GUNSHOT_THRESHOLD:
        return "Gunshot 🔫", True
    if scream > UPLOAD_SCREAM_THRESHOLD:
        return "Scream 😱", False
    return "Background", False


def _load_audio_for_prediction(
    path,
    min_seconds=0.0,
    debug_wav_path=None,
    gain_db=UPLOAD_GAIN_DB,
    use_live_shaping=False
):
    wav = os.path.splitext(path)[0] + "_converted.wav"
    try:
        filter_chain = LIVE_SHAPING_FILTER if use_live_shaping else None
        convert_to_wav(path, wav, gain_db=gain_db, filter_chain=filter_chain)

        if debug_wav_path:
            os.makedirs(os.path.dirname(debug_wav_path), exist_ok=True)
            try:
                shutil.copy2(wav, debug_wav_path)
            except OSError:
                pass

        audio, _ = librosa.load(wav, sr=SAMPLE_RATE, mono=True)
        audio = np.asarray(audio, dtype=np.float32)
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

        if audio.size == 0:
            raise RuntimeError("empty_audio_after_decode")

        if min_seconds > 0 and audio.size < int(SAMPLE_RATE * min_seconds):
            raise RuntimeError("audio_too_short")

        return audio
    finally:
        if os.path.exists(wav):
            os.remove(wav)

# ==============================
# CONVERT
# ==============================
def convert_to_wav(input_path, output_path, gain_db=UPLOAD_GAIN_DB, filter_chain=None):

    ffmpeg_path = _resolve_ffmpeg_path()
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg_not_found")

    if filter_chain:
        audio_filter = f"{filter_chain},volume={gain_db}dB"
    else:
        audio_filter = f"loudnorm,volume={gain_db}dB"

    result = subprocess.run([
        ffmpeg_path,
        "-hide_banner",
        "-loglevel", "error",
        "-nostdin",
        "-fflags", "+genpts",
        "-err_detect", "ignore_err",
        "-i", input_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "-af", audio_filter,
        "-f", "wav",
        "-y", output_path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        stderr_lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
        short_error = stderr_lines[-1] if stderr_lines else "invalid_audio_input"
        raise RuntimeError(f"ffmpeg_conversion_failed:{short_error}")

    return output_path


# ==============================
# PREDICT
# ==============================
def predict_audio(path):

    audio = _load_audio_for_prediction(path, gain_db=UPLOAD_GAIN_DB)
    chunks = split_audio(audio)

    results = []
    best_score = 0.0
    best_label = "Background"

    for i, chunk in enumerate(chunks):
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        if rms < UPLOAD_RMS_MIN:
            continue

        processed = shared_preprocess_chunk(chunk)
        pred = model.predict(processed, verbose=0)[0]
        gun, scream, bg = pred

        label, _ = _prediction_from_probs(gun, scream, bg, mode="upload")
        score = float(max(gun, scream))

        results.append({
            "chunk": i + 1,
            "gunshot": round(float(gun), 3),
            "scream": round(float(scream), 3),
            "background": round(float(bg), 3),
            "label": label
        })

        if score > best_score:
            best_score = score
            best_label = label

    # Send email alert if gunshot or scream detected
    if best_label in ["Gunshot 🔫", "Scream 😱"] and results:
        best_chunk = max(results, key=lambda x: max(x['gunshot'], x['scream']))
        send_alert_email(
            best_label,
            detection_type="upload",
            score=best_score,
            probabilities={
                'gunshot': best_chunk['gunshot'],
                'scream': best_chunk['scream'],
                'background': best_chunk['background']
            }
        )

    return best_label, results


def predict_single_live_chunk(path, debug_wav_path=None):

    audio = _load_audio_for_prediction(
        path,
        min_seconds=LIVE_MIN_SECONDS,
        debug_wav_path=debug_wav_path,
        gain_db=LIVE_GAIN_DB,
        use_live_shaping=True
    )
    chunks = split_audio(audio)

    best = {
        "gunshot": 0.0,
        "scream": 0.0,
        "background": 1.0,
        "label": "Background",
        "alert": False,
        "score": -1.0
    }

    for chunk in chunks:
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        if rms < LIVE_RMS_MIN:
            continue

        processed = shared_preprocess_chunk(chunk)
        pred = model.predict(processed, verbose=0)[0]
        gun, scream, bg = pred
        label, alert = _prediction_from_probs(gun, scream, bg, mode="live")
        score = float(max(gun, scream))

        if score > best["score"]:
            best = {
                "gunshot": round(float(gun), 3),
                "scream": round(float(scream), 3),
                "background": round(float(bg), 3),
                "label": label,
                "alert": alert,
                "score": score
            }

    if best["score"] < 0:
        return {
            "gunshot": 0.0,
            "scream": 0.0,
            "background": 1.0,
            "label": "Background",
            "alert": False,
            "gunshot_alert": False,
            "scream_alert": False,
            "reason": "low_energy"
        }

    # Send email alert if gunshot or scream with high confidence detected
    if best["alert"] or best["label"] in ["Gunshot 🔫", "Scream 😱"]:
        send_alert_email(
            best["label"],
            detection_type="live",
            score=best["score"],
            probabilities={
                'gunshot': best["gunshot"],
                'scream': best["scream"],
                'background': best["background"]
            }
        )

    return {
        "gunshot": best["gunshot"],
        "scream": best["scream"],
        "background": best["background"],
        "label": best["label"],
        "alert": best["alert"],
        "gunshot_alert": best["label"] == "Gunshot 🔫",
        "scream_alert": best["label"] == "Scream 😱",
        "live_thresholds": {
            "gunshot_confirm": LIVE_GUNSHOT_CONFIRM_THRESHOLD,
            "gunshot_probable": LIVE_GUNSHOT_PROBABLE_THRESHOLD,
            "scream": LIVE_SCREAM_THRESHOLD
        }
    }


def save_upload_file(file: UploadFile):
    ext = os.path.splitext(file.filename or "")[1] or ".bin"
    file_name = f"{uuid.uuid4().hex}{ext}"
    return os.path.join(UPLOAD_DIR, file_name)

# ==============================
# ROUTES
# ==============================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/predict", response_class=HTMLResponse)
async def predict(request: Request, file: UploadFile = File(...)):

    path = save_upload_file(file)
    with open(path, "wb") as f:
        f.write(await file.read())

    try:
        try:
            final, chunks = predict_audio(path)
        except RuntimeError:
            final, chunks = "Invalid audio input", []
    finally:
        if os.path.exists(path):
            os.remove(path)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "result": final,
        "chunks": chunks
    })


@app.post("/predict-live", response_class=HTMLResponse)
async def predict_live(request: Request, file: UploadFile = File(...)):

    path = save_upload_file(file)
    with open(path, "wb") as f:
        f.write(await file.read())

    try:
        try:
            final, chunks = predict_audio(path)
        except RuntimeError:
            final, chunks = "Invalid audio input", []
    finally:
        if os.path.exists(path):
            os.remove(path)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "result": final,
        "chunks": chunks
    })


@app.post("/predict-live-chunk")
async def predict_live_chunk(file: UploadFile = File(...)):

    path = save_upload_file(file)
    original_ext = os.path.splitext(file.filename or "")[1] or ".bin"
    debug_id = uuid.uuid4().hex
    debug_raw_path = os.path.join(TEST_RAW_DIR, f"{debug_id}{original_ext}")
    debug_wav_path = os.path.join(TEST_WAV_DIR, f"{debug_id}.wav")

    with open(path, "wb") as f:
        f.write(await file.read())

    if SAVE_LIVE_CHUNKS_FOR_TESTING:
        try:
            os.makedirs(TEST_RAW_DIR, exist_ok=True)
            os.makedirs(TEST_WAV_DIR, exist_ok=True)
            shutil.copy2(path, debug_raw_path)
        except OSError:
            pass

    try:
        try:
            result = predict_single_live_chunk(
                path,
                debug_wav_path=debug_wav_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None
            )
        except RuntimeError as exc:
            result = {
                "gunshot": 0.0,
                "scream": 0.0,
                "background": 1.0,
                "label": "Background",
                "alert": False,
                "gunshot_alert": False,
                "scream_alert": False,
                "error": str(exc),
                "debug_chunk": debug_id if SAVE_LIVE_CHUNKS_FOR_TESTING else None
            }
    finally:
        if os.path.exists(path):
            os.remove(path)

    if SAVE_LIVE_CHUNKS_FOR_TESTING:
        result["debug_chunk"] = debug_id

    return JSONResponse(result)