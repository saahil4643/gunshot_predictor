# import numpy as np
# import librosa
# import tensorflow as tf
# import subprocess
# import os
# import uuid
# import shutil
# import tempfile
# from datetime import datetime
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from fastapi import FastAPI, Request, UploadFile, File
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.templating import Jinja2Templates
# from fastapi.staticfiles import StaticFiles

# from utils import split_audio, preprocess_chunk as shared_preprocess_chunk

# app = FastAPI()
# templates = Jinja2Templates(directory="templates")
# app.mount("/static", StaticFiles(directory="static"), name="static")

# MODEL_PATH = "model/final_audio_model_v4.h5"


# class CompatibleInputLayer(tf.keras.layers.InputLayer):
#     @classmethod
#     def from_config(cls, config):
#         config = dict(config)
#         if "batch_shape" in config and "batch_input_shape" not in config:
#             config["batch_input_shape"] = tuple(config.pop("batch_shape"))
#         config.pop("optional", None)
#         return super().from_config(config)


# class CompatibleDTypePolicy(tf.keras.mixed_precision.Policy):
#     @classmethod
#     def from_config(cls, config):
#         policy_name = config.get("name", "float32") if isinstance(config, dict) else "float32"
#         return tf.keras.mixed_precision.Policy(policy_name)


# def _sanitize_layer_config(config):
#     config = dict(config)
#     config.pop("quantization_config", None)
#     return config


# class CompatibleDense(tf.keras.layers.Dense):
#     @classmethod
#     def from_config(cls, config):
#         return super().from_config(_sanitize_layer_config(config))


# class CompatibleConv2D(tf.keras.layers.Conv2D):
#     @classmethod
#     def from_config(cls, config):
#         return super().from_config(_sanitize_layer_config(config))


# class CompatibleConv1D(tf.keras.layers.Conv1D):
#     @classmethod
#     def from_config(cls, config):
#         return super().from_config(_sanitize_layer_config(config))


# def load_model_with_compat(model_path):
#     try:
#         return tf.keras.models.load_model(model_path, compile=False)
#     except Exception:
#         return tf.keras.models.load_model(
#             model_path,
#             custom_objects={
#                 "InputLayer": CompatibleInputLayer,
#                 "DTypePolicy": CompatibleDTypePolicy,
#                 "Dense": CompatibleDense,
#                 "Conv2D": CompatibleConv2D,
#                 "Conv1D": CompatibleConv1D,
#             },
#             compile=False,
#         )


# model = load_model_with_compat(MODEL_PATH)

# SAMPLE_RATE = 22050
# CHUNK_SECONDS = 3
# SAMPLES_PER_TRACK = SAMPLE_RATE * CHUNK_SECONDS
# LIVE_MIN_SECONDS = 0.5
# UPLOAD_GUNSHOT_THRESHOLD = 0.5
# UPLOAD_SCREAM_THRESHOLD = 0.2
# LIVE_GUNSHOT_CONFIRM_THRESHOLD = 0.22
# LIVE_GUNSHOT_PROBABLE_THRESHOLD = 0.12
# LIVE_SCREAM_THRESHOLD = 0.18
# UPLOAD_GAIN_DB = 6
# LIVE_GAIN_DB = 4
# LIVE_SHAPING_FILTER = "highpass=f=120,lowpass=f=7000,acompressor=threshold=-22dB:ratio=3:attack=5:release=80,loudnorm"
# UPLOAD_RMS_MIN = 0.003
# LIVE_RMS_MIN = 0.01
# LIVE_SPIKE_BOOST = 1.08
# UPLOAD_DIR = "uploaded_audio"
# SAVE_LIVE_CHUNKS_FOR_TESTING = True
# TEST_CHUNKS_DIR = os.path.join("testing_chunks", "live_chunks")
# TEST_RAW_DIR = os.path.join(TEST_CHUNKS_DIR, "raw")
# TEST_WAV_DIR = os.path.join(TEST_CHUNKS_DIR, "wav")
# TEST_AUDIO_RECEIVED_DIR = os.path.join(TEST_CHUNKS_DIR, "audio_received")
# TEST_AUDIO_TO_MODEL_DIR = os.path.join(TEST_CHUNKS_DIR, "audio_to_model")
# DETECTION_LOG_FILE = os.path.join(tempfile.gettempdir(), "gunshot_predictor_detection_events.tmp.txt")
# MAX_DETECTION_LOG_LINES = 200

# # Email Configuration
# EMAIL_ENABLED = True  # Set to False to disable email notifications
# SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
# SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
# SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "sahilbhandare80@gmail.com")
# SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "hxzbgdbbfopqhrme")
# RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "sahilbhandare79@gmail.com")

# # Email config file for dynamic receiver email
# EMAIL_CONFIG_DIR = "config"
# EMAIL_CONFIG_FILE = os.path.join(EMAIL_CONFIG_DIR, "receiver_email.txt")

# # If a legacy file named uploaded_audio exists, switch to a safe folder name.
# if os.path.exists(UPLOAD_DIR) and not os.path.isdir(UPLOAD_DIR):
#     UPLOAD_DIR = "uploaded_audio_dir"

# os.makedirs(UPLOAD_DIR, exist_ok=True)
# os.makedirs(EMAIL_CONFIG_DIR, exist_ok=True)
# if SAVE_LIVE_CHUNKS_FOR_TESTING:
#     os.makedirs(TEST_RAW_DIR, exist_ok=True)
#     os.makedirs(TEST_WAV_DIR, exist_ok=True)
#     os.makedirs(TEST_AUDIO_RECEIVED_DIR, exist_ok=True)
#     os.makedirs(TEST_AUDIO_TO_MODEL_DIR, exist_ok=True)


# def _resolve_ffmpeg_path():
#     env_path = os.environ.get("FFMPEG_PATH")
#     if env_path and os.path.isfile(env_path):
#         return env_path

#     path_cmd = shutil.which("ffmpeg")
#     if path_cmd:
#         return path_cmd

#     return None


# def get_receiver_email():
#     """
#     Get the receiver email from config file or use default.
#     Returns the saved email address or the default RECIPIENT_EMAIL.
#     """
#     if os.path.exists(EMAIL_CONFIG_FILE):
#         try:
#             with open(EMAIL_CONFIG_FILE, 'r') as f:
#                 email = f.read().strip()
#                 if email and '@' in email:
#                     return email
#         except Exception as e:
#             print(f"[CONFIG] Error reading email config: {str(e)}")
    
#     return RECIPIENT_EMAIL


# def set_receiver_email(email):
#     """
#     Save the receiver email to config file.
#     """
#     try:
#         os.makedirs(EMAIL_CONFIG_DIR, exist_ok=True)
#         with open(EMAIL_CONFIG_FILE, 'w') as f:
#             f.write(email.strip())
#         return True
#     except Exception as e:
#         print(f"[CONFIG] Error writing email config: {str(e)}")
#         return False


# def get_email_html_template(label, detection_type, timestamp, probabilities, score):
#     """
#     Generate a professional HTML email template for detection alerts.
#     """
#     gunshot_prob = probabilities.get('gunshot', 0.0) * 100 if probabilities else 0
#     scream_prob = probabilities.get('scream', 0.0) * 100 if probabilities else 0
#     background_prob = probabilities.get('background', 0.0) * 100 if probabilities else 0
#     score_percent = score * 100 if score is not None else 0
    
#     # Determine colors based on label
#     alert_color = "#DC2626" if "Gunshot" in label else "#FF6B35"
#     icon = "🔫" if "Gunshot" in label else "📢"
    
#     html_template = f"""
#     <!DOCTYPE html>
#     <html lang="en">
#     <head>
#         <meta charset="UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <style>
#             body {{
#                 font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
#                 margin: 0;
#                 padding: 20px;
#                 background-color: #f5f5f5;
#             }}
#             .container {{
#                 max-width: 600px;
#                 margin: 0 auto;
#                 background-color: #ffffff;
#                 border-radius: 8px;
#                 box-shadow: 0 2px 10px rgba(0,0,0,0.1);
#                 overflow: hidden;
#             }}
#             .header {{
#                 background: linear-gradient(135deg, {alert_color} 0%, #8b1a1a 100%);
#                 color: white;
#                 padding: 30px;
#                 text-align: center;
#             }}
#             .header h1 {{
#                 margin: 0;
#                 font-size: 28px;
#                 font-weight: bold;
#             }}
#             .header p {{
#                 margin: 10px 0 0 0;
#                 font-size: 14px;
#                 opacity: 0.9;
#             }}
#             .content {{
#                 padding: 30px;
#             }}
#             .alert-section {{
#                 background-color: #fef2f2;
#                 border-left: 4px solid {alert_color};
#                 padding: 16px;
#                 margin-bottom: 20px;
#                 border-radius: 4px;
#             }}
#             .info-grid {{
#                 display: grid;
#                 grid-template-columns: 1fr 1fr;
#                 gap: 20px;
#                 margin-bottom: 20px;
#             }}
#             .info-item {{
#                 background-color: #f9fafb;
#                 padding: 15px;
#                 border-radius: 6px;
#                 border: 1px solid #e5e7eb;
#             }}
#             .info-label {{
#                 font-size: 12px;
#                 font-weight: 600;
#                 color: #6b7280;
#                 text-transform: uppercase;
#                 margin-bottom: 5px;
#             }}
#             .info-value {{
#                 font-size: 16px;
#                 font-weight: 600;
#                 color: #111827;
#             }}
#             .probabilities {{
#                 background-color: #f9fafb;
#                 padding: 20px;
#                 border-radius: 6px;
#                 margin-bottom: 20px;
#                 border: 1px solid #e5e7eb;
#             }}
#             .prob-title {{
#                 font-size: 12px;
#                 font-weight: 600;
#                 color: #6b7280;
#                 text-transform: uppercase;
#                 margin-bottom: 12px;
#             }}
#             .prob-item {{
#                 display: flex;
#                 justify-content: space-between;
#                 align-items: center;
#                 margin-bottom: 10px;
#             }}
#             .prob-item:last-child {{
#                 margin-bottom: 0;
#             }}
#             .prob-label {{
#                 color: #374151;
#                 font-weight: 500;
#             }}
#             .prob-bar {{
#                 flex: 1;
#                 margin: 0 15px;
#                 height: 8px;
#                 background-color: #e5e7eb;
#                 border-radius: 4px;
#                 overflow: hidden;
#             }}
#             .prob-fill {{
#                 height: 100%;
#                 background: linear-gradient(90deg, #3b82f6, #60a5fa);
#                 border-radius: 4px;
#             }}
#             .prob-value {{
#                 color: #111827;
#                 font-weight: 600;
#                 font-size: 14px;
#                 min-width: 45px;
#                 text-align: right;
#             }}
#             .gunshot-fill {{
#                 background: linear-gradient(90deg, #dc2626, #ef4444) !important;
#             }}
#             .scream-fill {{
#                 background: linear-gradient(90deg, #f97316, #fb923c) !important;
#             }}
#             .background-fill {{
#                 background: linear-gradient(90deg, #10b981, #34d399) !important;
#             }}
#             .action-section {{
#                 background-color: #eff6ff;
#                 border-left: 4px solid #3b82f6;
#                 padding: 16px;
#                 margin-bottom: 20px;
#                 border-radius: 4px;
#             }}
#             .action-section p {{
#                 margin: 0;
#                 color: #1e40af;
#                 font-size: 14px;
#             }}
#             .footer {{
#                 background-color: #f9fafb;
#                 border-top: 1px solid #e5e7eb;
#                 padding: 20px;
#                 text-align: center;
#                 font-size: 12px;
#                 color: #6b7280;
#             }}
#             .timestamp {{
#                 color: #9ca3af;
#                 font-size: 12px;
#                 margin-top: 5px;
#             }}
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <div class="header">
#                 <h1>{icon} DETECTION ALERT</h1>
#                 <p>{label.strip()} detected</p>
#             </div>
            
#             <div class="content">
#                 <div class="alert-section">
#                     <strong>⚠️ {label.upper()} Detection Confirmed</strong>
#                     <p style="margin: 8px 0 0 0; font-size: 14px;">A {label.lower().strip()} event has been detected in your audio stream.</p>
#                 </div>
                
#                 <div class="info-grid">
#                     <div class="info-item">
#                         <div class="info-label">Detection Type</div>
#                         <div class="info-value">{detection_type.upper()}</div>
#                     </div>
#                     <div class="info-item">
#                         <div class="info-label">Status</div>
#                         <div class="info-value" style="color: {alert_color};">ACTIVE</div>
#                     </div>
#                 </div>
                
#                 <div class="info-grid">
#                     <div class="info-item">
#                         <div class="info-label">Detection Label</div>
#                         <div class="info-value">{label.strip()}</div>
#                     </div>
#                     <div class="info-item">
#                         <div class="info-label">Confidence Score</div>
#                         <div class="info-value">{score_percent:.2f}%</div>
#                     </div>
#                 </div>
                
#                 <div class="probabilities">
#                     <div class="prob-title">📊 Detection Probabilities</div>
                    
#                     <div class="prob-item">
#                         <span class="prob-label">🔫 Gunshot</span>
#                         <div class="prob-bar">
#                             <div class="prob-fill gunshot-fill" style="width: {min(gunshot_prob, 100)}%"></div>
#                         </div>
#                         <span class="prob-value">{gunshot_prob:.2f}%</span>
#                     </div>
                    
#                     <div class="prob-item">
#                         <span class="prob-label">📢 Scream</span>
#                         <div class="prob-bar">
#                             <div class="prob-fill scream-fill" style="width: {min(scream_prob, 100)}%"></div>
#                         </div>
#                         <span class="prob-value">{scream_prob:.2f}%</span>
#                     </div>
                    
#                     <div class="prob-item">
#                         <span class="prob-label">🔊 Background</span>
#                         <div class="prob-bar">
#                             <div class="prob-fill background-fill" style="width: {min(background_prob, 100)}%"></div>
#                         </div>
#                         <span class="prob-value">{background_prob:.2f}%</span>
#                     </div>
#                 </div>
                
#                 <div class="action-section">
#                     <p><strong>ℹ️ Action Required</strong></p>
#                     <p>Please check the audio stream and take appropriate action if necessary. Review the detection details above for more information.</p>
#                 </div>
                
#                 <div class="timestamp">
#                     <strong>Timestamp:</strong> {timestamp}
#                 </div>
#             </div>
            
#             <div class="footer">
#                 <p>🎙️ Gunshot & Scream Detection System</p>
#                 <p style="margin: 5px 0 0 0;">This is an automated alert. Do not reply to this email.</p>
#             </div>
#         </div>
#     </body>
#     </html>
#     """
#     return html_template


# def send_alert_email(label, detection_type="upload", score=None, probabilities=None):
#     """
#     Send an email alert when gunshot or scream is detected with professional HTML template.
    
#     Args:
#         label: Detection label (e.g., "Gunshot ", "Scream ")
#         detection_type: Either "upload" or "live"
#         score: Confidence score
#         probabilities: Dict with gunshot, scream, background probabilities
#     """
#     if not EMAIL_ENABLED:
#         return
    
#     # Get the current receiver email
#     recipient = get_receiver_email()
    
#     try:
#         subject = f"🚨 ALERT: {label} Detected ({detection_type.upper()})"
#         timestamp = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
#         # Generate HTML email body
#         html_body = get_email_html_template(label, detection_type, timestamp, probabilities or {}, score)
        
#         # Create email message
#         msg = MIMEMultipart('alternative')
#         msg['From'] = SENDER_EMAIL
#         msg['To'] = recipient
#         msg['Subject'] = subject
        
#         # Attach HTML version
#         msg.attach(MIMEText(html_body, 'html'))
        
#         # Send email
#         with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
#             server.starttls()
#             server.login(SENDER_EMAIL, SENDER_PASSWORD)
#             server.send_message(msg)
        
#         print(f"[EMAIL] Alert sent to {recipient}: {label}")
#     except Exception as e:
#         print(f"[EMAIL ERROR] Failed to send alert email: {str(e)}")



# def _prediction_from_probs(gun, scream, bg, mode="upload"):
#     gun = float(gun)
#     scream = float(scream)
#     bg = float(bg)

#     if mode == "live":
#         if gun >= LIVE_GUNSHOT_CONFIRM_THRESHOLD:
#             return "Gunshot ", True
#         if gun >= LIVE_GUNSHOT_PROBABLE_THRESHOLD:
#             return "Possible Gunshot ", False
#         if scream >= LIVE_SCREAM_THRESHOLD:
#             return "Scream ", False
#         return "Background", False

#     if gun > UPLOAD_GUNSHOT_THRESHOLD:
#         return "Gunshot ", True
#     if scream > UPLOAD_SCREAM_THRESHOLD:
#         return "Scream ", False
#     return "Background", False


# def _load_audio_for_prediction(
#     path,
#     min_seconds=0.0,
#     debug_wav_path=None,
#     gain_db=0,
#     use_live_shaping=False,
#     spike_boost=1.0
# ):
#     wav = os.path.splitext(path)[0] + "_converted.wav"
#     try:
#         filter_chain = LIVE_SHAPING_FILTER if use_live_shaping else None
#         convert_to_wav(path, wav, gain_db=gain_db, filter_chain=filter_chain)

#         if debug_wav_path:
#             os.makedirs(os.path.dirname(debug_wav_path), exist_ok=True)
#             try:
#                 shutil.copy2(wav, debug_wav_path)
#             except OSError:
#                 pass

#         audio, _ = librosa.load(wav, sr=SAMPLE_RATE, mono=True)
#         audio = np.asarray(audio, dtype=np.float32)
#         audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

#         # Slightly boost transients before feature extraction for quicker event pickup.
#         if spike_boost > 1.0:
#             audio = np.clip(audio * float(spike_boost), -1.0, 1.0)

#         if audio.size == 0:
#             raise RuntimeError("empty_audio_after_decode")

#         if min_seconds > 0 and audio.size < int(SAMPLE_RATE * min_seconds):
#             raise RuntimeError("audio_too_short")

#         return audio
#     finally:
#         if os.path.exists(wav):
#             os.remove(wav)

# # ==============================
# # CONVERT
# # ==============================
# def convert_to_wav(input_path, output_path, gain_db=0, filter_chain=None):

#     ffmpeg_path = _resolve_ffmpeg_path()
#     if not ffmpeg_path:
#         raise RuntimeError("ffmpeg_not_found")

#     af_filters = []
#     if gain_db:
#         af_filters.append(f"volume={float(gain_db)}dB")
#     if filter_chain:
#         af_filters.append(filter_chain)

#     cmd = [
#         ffmpeg_path,
#         "-hide_banner",
#         "-loglevel", "error",
#         "-nostdin",
#         "-fflags", "+genpts",
#         "-err_detect", "ignore_err",
#         "-i", input_path,
#         "-vn",
#     ]

#     if af_filters:
#         cmd.extend(["-af", ",".join(af_filters)])

#     cmd.extend([
#         "-acodec", "pcm_s16le",
#         "-ac", "1",
#         "-ar", str(SAMPLE_RATE),
#         "-f", "wav",
#         "-y", output_path
#     ])

#     result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

#     if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
#         stderr_lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
#         short_error = stderr_lines[-1] if stderr_lines else "invalid_audio_input"
#         raise RuntimeError(f"ffmpeg_conversion_failed:{short_error}")

#     return output_path


# # ==============================
# # PREDICT
# # ==============================
# def predict_audio(path):

#     audio = _load_audio_for_prediction(
#         path,
#         gain_db=UPLOAD_GAIN_DB,
#         spike_boost=1.0
#     )
#     chunks = split_audio(audio)

#     results = []
#     best_score = -1.0
#     best_label = "Background"
#     best_for_email = None

#     for i, chunk in enumerate(chunks):
#         rms = float(np.sqrt(np.mean(np.square(chunk))))
#         if rms < UPLOAD_RMS_MIN:
#             continue

#         processed = shared_preprocess_chunk(chunk)
#         pred = model.predict(processed, verbose=0)[0]
#         gun, scream, bg = pred

#         label, _ = _prediction_from_probs(gun, scream, bg, mode="upload")
#         score = float(max(gun, scream))

#         results.append({
#             "chunk": i + 1,
#             "gunshot": round(float(gun), 3),
#             "scream": round(float(scream), 3),
#             "background": round(float(bg), 3),
#             "label": label
#         })

#         # Prefer explicit event detections over high-confidence background chunks.
#         if label == "Gunshot ":
#             candidate_score = float(gun)
#         elif label == "Scream ":
#             candidate_score = float(scream)
#         else:
#             candidate_score = -1.0

#         if candidate_score > best_score:
#             best_score = candidate_score
#             best_label = label
#             best_for_email = {
#                 "gunshot": round(float(gun), 3),
#                 "scream": round(float(scream), 3),
#                 "background": round(float(bg), 3)
#             }

#         if best_label == "Background" and score > best_score:
#             best_score = score
#             best_label = label

#     # Send email alert if gunshot or scream detected
#     if best_label in ["Gunshot ", "Scream "] and results:
#         send_alert_email(
#             best_label,
#             detection_type="upload",
#             score=best_score,
#             probabilities={
#                 'gunshot': (best_for_email or {}).get('gunshot', 0.0),
#                 'scream': (best_for_email or {}).get('scream', 0.0),
#                 'background': (best_for_email or {}).get('background', 0.0)
#             }
#         )

#     return best_label, results


# def predict_single_live_chunk(path, debug_wav_path=None, debug_audio_received_path=None, debug_audio_to_model_path=None):

#     audio = _load_audio_for_prediction(
#         path,
#         min_seconds=LIVE_MIN_SECONDS,
#         debug_wav_path=debug_wav_path,
#         gain_db=LIVE_GAIN_DB,
#         use_live_shaping=True,
#         spike_boost=LIVE_SPIKE_BOOST
#     )
    
#     # Save audio received (after WAV conversion, before preprocessing)
#     if debug_audio_received_path:
#         try:
#             os.makedirs(os.path.dirname(debug_audio_received_path), exist_ok=True)
#             import soundfile as sf
#             sf.write(debug_audio_received_path, audio, SAMPLE_RATE)
#         except Exception as e:
#             print(f"[DEBUG] Failed to save audio_received: {str(e)}")
    
#     chunks = split_audio(audio)
#     preprocessed_chunks = []

#     best = {
#         "gunshot": 0.0,
#         "scream": 0.0,
#         "background": 1.0,
#         "label": "Background",
#         "alert": False,
#         "score": -1.0
#     }

#     for chunk in chunks:
#         rms = float(np.sqrt(np.mean(np.square(chunk))))
#         if rms < LIVE_RMS_MIN:
#             continue

#         processed = shared_preprocess_chunk(chunk)
#         preprocessed_chunks.append(processed)
#         pred = model.predict(processed, verbose=0)[0]
#         gun, scream, bg = pred
#         label, alert = _prediction_from_probs(gun, scream, bg, mode="live")
#         score = float(max(gun, scream))

#         if score > best["score"]:
#             best = {
#                 "gunshot": round(float(gun), 3),
#                 "scream": round(float(scream), 3),
#                 "background": round(float(bg), 3),
#                 "label": label,
#                 "alert": alert,
#                 "score": score
#             }
    
#     # Save audio given to model (preprocessed chunks)
#     if debug_audio_to_model_path and preprocessed_chunks:
#         try:
#             os.makedirs(os.path.dirname(debug_audio_to_model_path), exist_ok=True)
#             np.save(debug_audio_to_model_path, np.array(preprocessed_chunks))
#         except Exception as e:
#             print(f"[DEBUG] Failed to save audio_to_model: {str(e)}")

#     if best["score"] < 0:
#         return {
#             "gunshot": 0.0,
#             "scream": 0.0,
#             "background": 1.0,
#             "label": "Background",
#             "alert": False,
#             "gunshot_alert": False,
#             "scream_alert": False,
#             "reason": "low_energy"
#         }

#     # Send email alert if gunshot or scream with high confidence detected
#     if best["alert"] or best["label"] in ["Gunshot ", "Scream "]:
#         send_alert_email(
#             best["label"],
#             detection_type="live",
#             score=best["score"],
#             probabilities={
#                 'gunshot': best["gunshot"],
#                 'scream': best["scream"],
#                 'background': best["background"]
#             }
#         )

#     return {
#         "gunshot": best["gunshot"],
#         "scream": best["scream"],
#         "background": best["background"],
#         "label": best["label"],
#         "alert": best["alert"],
#         "gunshot_alert": best["label"] == "Gunshot ",
#         "scream_alert": best["label"] == "Scream ",
#         "live_thresholds": {
#             "gunshot_confirm": LIVE_GUNSHOT_CONFIRM_THRESHOLD,
#             "gunshot_probable": LIVE_GUNSHOT_PROBABLE_THRESHOLD,
#             "scream": LIVE_SCREAM_THRESHOLD
#         }
#     }


# def save_upload_file(file: UploadFile):
#     ext = os.path.splitext(file.filename or "")[1] or ".bin"
#     file_name = f"{uuid.uuid4().hex}{ext}"
#     return os.path.join(UPLOAD_DIR, file_name)


# def append_detection_log(event_type: str, source: str) -> None:
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     line = f"{timestamp}\t{event_type}\t{source}\n"

#     with open(DETECTION_LOG_FILE, "a", encoding="utf-8") as f:
#         f.write(line)

#     try:
#         with open(DETECTION_LOG_FILE, "r", encoding="utf-8") as f:
#             lines = f.readlines()
#         if len(lines) > MAX_DETECTION_LOG_LINES:
#             with open(DETECTION_LOG_FILE, "w", encoding="utf-8") as f:
#                 f.writelines(lines[-MAX_DETECTION_LOG_LINES:])
#     except OSError:
#         pass


# def read_detection_logs(limit: int = 50):
#     if not os.path.exists(DETECTION_LOG_FILE):
#         return []

#     logs = []
#     try:
#         with open(DETECTION_LOG_FILE, "r", encoding="utf-8") as f:
#             for raw in f:
#                 parts = raw.rstrip("\n").split("\t")
#                 if len(parts) != 3:
#                     continue
#                 logs.append({
#                     "timestamp": parts[0],
#                     "event": parts[1],
#                     "source": parts[2]
#                 })
#     except OSError:
#         return []

#     logs.reverse()
#     return logs[:limit]


# def clear_detection_logs() -> None:
#     try:
#         if os.path.exists(DETECTION_LOG_FILE):
#             os.remove(DETECTION_LOG_FILE)
#     except OSError:
#         pass

# # ==============================
# # ROUTES
# # ==============================
# @app.get("/healthz")
# def healthz():
#     return {"status": "ok"}

# @app.get("/", response_class=HTMLResponse)
# def home(request: Request):
#     return templates.TemplateResponse("index.html", {
#         "request": request,
#         "logs": read_detection_logs()
#     })


# @app.get("/api/detection-logs")
# def get_detection_logs():
#     return JSONResponse({"logs": read_detection_logs()})


# @app.post("/api/clear-detection-logs")
# def clear_detection_logs_api():
#     clear_detection_logs()
#     return JSONResponse({"success": True})

# @app.get("/api/get-receiver-email")
# async def get_email_endpoint():
#     """API endpoint to get the current receiver email"""
#     email = get_receiver_email()
#     return JSONResponse({"email": email})

# @app.post("/api/set-receiver-email")
# async def set_email_endpoint(request: Request):
#     """API endpoint to set the receiver email"""
#     try:
#         data = await request.json()
#         email = data.get("email", "").strip()
        
#         if not email:
#             return JSONResponse({"error": "Email is required"}, status_code=400)
        
#         if '@' not in email or '.' not in email.split('@')[1]:
#             return JSONResponse({"error": "Invalid email format"}, status_code=400)
        
#         if set_receiver_email(email):
#             return JSONResponse({"success": True, "email": email})
#         else:
#             return JSONResponse({"error": "Failed to save email"}, status_code=500)
#     except Exception as e:
#         print(f"[API] Error setting email: {str(e)}")
#         return JSONResponse({"error": str(e)}, status_code=500)

# @app.post("/predict")
# async def predict(request: Request, file: UploadFile = File(...)):

#     path = save_upload_file(file)
#     with open(path, "wb") as f:
#         f.write(await file.read())

#     try:
#         try:
#             final, chunks = predict_audio(path)
#         except RuntimeError:
#             final, chunks = "Invalid audio input", []
#     finally:
#         if os.path.exists(path):
#             os.remove(path)

#     # Calculate confidence score from chunks
#     confidence = 0.0
#     if chunks:
#         best_chunk = max(chunks, key=lambda x: max(x['gunshot'], x['scream']))
#         confidence = max(best_chunk['gunshot'], best_chunk['scream'])
    
#     # Determine alert statuses
#     gunshot_alert = "Gunshot " in final
#     scream_alert = "Scream " in final

#     if gunshot_alert:
#         append_detection_log("Gunshot", "Upload")
#     if scream_alert:
#         append_detection_log("Scream", "Upload")

#     return JSONResponse({
#         "label": final,
#         "confidence": confidence,
#         "gunshot_alert": gunshot_alert,
#         "scream_alert": scream_alert,
#         "chunks": chunks
#     })


# @app.post("/predict-live", response_class=HTMLResponse)
# async def predict_live(request: Request, file: UploadFile = File(...)):

#     path = save_upload_file(file)
#     with open(path, "wb") as f:
#         f.write(await file.read())

#     try:
#         try:
#             final, chunks = predict_audio(path)
#         except RuntimeError:
#             final, chunks = "Invalid audio input", []
#     finally:
#         if os.path.exists(path):
#             os.remove(path)

#     return templates.TemplateResponse("index.html", {
#         "request": request,
#         "result": final,
#         "chunks": chunks,
#         "logs": read_detection_logs()
#     })


# @app.post("/predict-live-chunk")
# async def predict_live_chunk(file: UploadFile = File(...)):

#     path = save_upload_file(file)
#     original_ext = os.path.splitext(file.filename or "")[1] or ".bin"
#     debug_id = uuid.uuid4().hex
#     debug_raw_path = os.path.join(TEST_RAW_DIR, f"{debug_id}{original_ext}")
#     debug_wav_path = os.path.join(TEST_WAV_DIR, f"{debug_id}.wav")
#     debug_audio_received_path = os.path.join(TEST_AUDIO_RECEIVED_DIR, f"{debug_id}_received.wav")
#     debug_audio_to_model_path = os.path.join(TEST_AUDIO_TO_MODEL_DIR, f"{debug_id}_to_model.npy")

#     with open(path, "wb") as f:
#         f.write(await file.read())

#     if SAVE_LIVE_CHUNKS_FOR_TESTING:
#         try:
#             os.makedirs(TEST_RAW_DIR, exist_ok=True)
#             os.makedirs(TEST_WAV_DIR, exist_ok=True)
#             os.makedirs(TEST_AUDIO_RECEIVED_DIR, exist_ok=True)
#             os.makedirs(TEST_AUDIO_TO_MODEL_DIR, exist_ok=True)
#             shutil.copy2(path, debug_raw_path)
#         except OSError:
#             pass

#     try:
#         try:
#             result = predict_single_live_chunk(
#                 path,
#                 debug_wav_path=debug_wav_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None,
#                 debug_audio_received_path=debug_audio_received_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None,
#                 debug_audio_to_model_path=debug_audio_to_model_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None
#             )
#         except RuntimeError as exc:
#             result = {
#                 "gunshot": 0.0,
#                 "scream": 0.0,
#                 "background": 1.0,
#                 "label": "Background",
#                 "alert": False,
#                 "gunshot_alert": False,
#                 "scream_alert": False,
#                 "error": str(exc),
#                 "debug_chunk": debug_id if SAVE_LIVE_CHUNKS_FOR_TESTING else None
#             }
#     finally:
#         if os.path.exists(path):
#             os.remove(path)

#     if SAVE_LIVE_CHUNKS_FOR_TESTING:
#         result["debug_chunk"] = debug_id

#     if result.get("gunshot_alert"):
#         append_detection_log("Gunshot", "Live")
#     if result.get("scream_alert"):
#         append_detection_log("Scream", "Live")

#     return JSONResponse(result)
# import numpy as np
# import librosa
# import tensorflow as tf
# import subprocess
# import os
# import uuid
# import shutil
# import tempfile
# from datetime import datetime
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from fastapi import FastAPI, Request, UploadFile, File
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.templating import Jinja2Templates
# from fastapi.staticfiles import StaticFiles

# from utils import split_audio, preprocess_chunk as shared_preprocess_chunk

# app = FastAPI()
# templates = Jinja2Templates(directory="templates")
# app.mount("/static", StaticFiles(directory="static"), name="static")

# MODEL_PATH = "model/final_audio_model_v4.h5"


# class CompatibleInputLayer(tf.keras.layers.InputLayer):
#     @classmethod
#     def from_config(cls, config):
#         config = dict(config)
#         if "batch_shape" in config and "batch_input_shape" not in config:
#             config["batch_input_shape"] = tuple(config.pop("batch_shape"))
#         config.pop("optional", None)
#         return super().from_config(config)


# class CompatibleDTypePolicy(tf.keras.mixed_precision.Policy):
#     @classmethod
#     def from_config(cls, config):
#         policy_name = config.get("name", "float32") if isinstance(config, dict) else "float32"
#         return tf.keras.mixed_precision.Policy(policy_name)


# def _sanitize_layer_config(config):
#     config = dict(config)
#     config.pop("quantization_config", None)
#     return config


# class CompatibleDense(tf.keras.layers.Dense):
#     @classmethod
#     def from_config(cls, config):
#         return super().from_config(_sanitize_layer_config(config))


# class CompatibleConv2D(tf.keras.layers.Conv2D):
#     @classmethod
#     def from_config(cls, config):
#         return super().from_config(_sanitize_layer_config(config))


# class CompatibleConv1D(tf.keras.layers.Conv1D):
#     @classmethod
#     def from_config(cls, config):
#         return super().from_config(_sanitize_layer_config(config))


# def load_model_with_compat(model_path):
#     try:
#         return tf.keras.models.load_model(model_path, compile=False)
#     except Exception:
#         return tf.keras.models.load_model(
#             model_path,
#             custom_objects={
#                 "InputLayer": CompatibleInputLayer,
#                 "DTypePolicy": CompatibleDTypePolicy,
#                 "Dense": CompatibleDense,
#                 "Conv2D": CompatibleConv2D,
#                 "Conv1D": CompatibleConv1D,
#             },
#             compile=False,
#         )


# model = load_model_with_compat(MODEL_PATH)

# SAMPLE_RATE = 22050
# CHUNK_SECONDS = 3
# SAMPLES_PER_TRACK = SAMPLE_RATE * CHUNK_SECONDS
# LIVE_MIN_SECONDS = 0.5

# # ── Upload thresholds ──────────────────────────────────────────────────────────
# UPLOAD_GUNSHOT_THRESHOLD = 0.5
# UPLOAD_SCREAM_THRESHOLD = 0.10      # CHANGED: was 0.2, lowered so dataset screams are detected
# UPLOAD_SCREAM_FALLBACK_THRESHOLD = 0.08

# # ── Live thresholds — original, untouched ─────────────────────────────────────
# LIVE_GUNSHOT_CONFIRM_THRESHOLD = 0.22
# LIVE_GUNSHOT_PROBABLE_THRESHOLD = 0.12
# LIVE_SCREAM_THRESHOLD = 0.18

# UPLOAD_GAIN_DB = 0
# LIVE_GAIN_DB = 4

# # ── Live shaping filter — original, untouched ─────────────────────────────────
# LIVE_SHAPING_FILTER = "highpass=f=120,lowpass=f=7000,acompressor=threshold=-22dB:ratio=3:attack=5:release=80,loudnorm"

# UPLOAD_RMS_MIN = 0.003
# LIVE_RMS_MIN = 0.01
# LIVE_SPIKE_BOOST = 1.08
# UPLOAD_DIR = "uploaded_audio"
# SAVE_LIVE_CHUNKS_FOR_TESTING = True
# TEST_CHUNKS_DIR = os.path.join("testing_chunks", "live_chunks")
# TEST_RAW_DIR = os.path.join(TEST_CHUNKS_DIR, "raw")
# TEST_WAV_DIR = os.path.join(TEST_CHUNKS_DIR, "wav")
# TEST_AUDIO_RECEIVED_DIR = os.path.join(TEST_CHUNKS_DIR, "audio_received")
# TEST_AUDIO_TO_MODEL_DIR = os.path.join(TEST_CHUNKS_DIR, "audio_to_model")
# DETECTION_LOG_FILE = os.path.join(tempfile.gettempdir(), "gunshot_predictor_detection_events.tmp.txt")
# MAX_DETECTION_LOG_LINES = 200

# # Email Configuration
# EMAIL_ENABLED = True
# SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
# SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
# SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "sahilbhandare80@gmail.com")
# SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "hxzbgdbbfopqhrme")
# RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "sahilbhandare79@gmail.com")

# EMAIL_CONFIG_DIR = "config"
# EMAIL_CONFIG_FILE = os.path.join(EMAIL_CONFIG_DIR, "receiver_email.txt")

# if os.path.exists(UPLOAD_DIR) and not os.path.isdir(UPLOAD_DIR):
#     UPLOAD_DIR = "uploaded_audio_dir"

# os.makedirs(UPLOAD_DIR, exist_ok=True)
# os.makedirs(EMAIL_CONFIG_DIR, exist_ok=True)
# if SAVE_LIVE_CHUNKS_FOR_TESTING:
#     os.makedirs(TEST_RAW_DIR, exist_ok=True)
#     os.makedirs(TEST_WAV_DIR, exist_ok=True)
#     os.makedirs(TEST_AUDIO_RECEIVED_DIR, exist_ok=True)
#     os.makedirs(TEST_AUDIO_TO_MODEL_DIR, exist_ok=True)


# def _resolve_ffmpeg_path():
#     env_path = os.environ.get("FFMPEG_PATH")
#     if env_path and os.path.isfile(env_path):
#         return env_path
#     path_cmd = shutil.which("ffmpeg")
#     if path_cmd:
#         return path_cmd
#     return None


# def get_receiver_email():
#     if os.path.exists(EMAIL_CONFIG_FILE):
#         try:
#             with open(EMAIL_CONFIG_FILE, 'r') as f:
#                 email = f.read().strip()
#                 if email and '@' in email:
#                     return email
#         except Exception as e:
#             print(f"[CONFIG] Error reading email config: {str(e)}")
#     return RECIPIENT_EMAIL


# def set_receiver_email(email):
#     try:
#         os.makedirs(EMAIL_CONFIG_DIR, exist_ok=True)
#         with open(EMAIL_CONFIG_FILE, 'w') as f:
#             f.write(email.strip())
#         return True
#     except Exception as e:
#         print(f"[CONFIG] Error writing email config: {str(e)}")
#         return False


# def get_email_html_template(label, detection_type, timestamp, probabilities, score):
#     gunshot_prob = probabilities.get('gunshot', 0.0) * 100 if probabilities else 0
#     scream_prob = probabilities.get('scream', 0.0) * 100 if probabilities else 0
#     background_prob = probabilities.get('background', 0.0) * 100 if probabilities else 0
#     score_percent = score * 100 if score is not None else 0

#     alert_color = "#DC2626" if "Gunshot" in label else "#FF6B35"
#     icon = "🔫" if "Gunshot" in label else "📢"

#     html_template = f"""
#     <!DOCTYPE html>
#     <html lang="en">
#     <head>
#         <meta charset="UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0">
#         <style>
#             body {{
#                 font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
#                 margin: 0;
#                 padding: 20px;
#                 background-color: #f5f5f5;
#             }}
#             .container {{
#                 max-width: 600px;
#                 margin: 0 auto;
#                 background-color: #ffffff;
#                 border-radius: 8px;
#                 box-shadow: 0 2px 10px rgba(0,0,0,0.1);
#                 overflow: hidden;
#             }}
#             .header {{
#                 background: linear-gradient(135deg, {alert_color} 0%, #8b1a1a 100%);
#                 color: white;
#                 padding: 30px;
#                 text-align: center;
#             }}
#             .header h1 {{ margin: 0; font-size: 28px; font-weight: bold; }}
#             .header p {{ margin: 10px 0 0 0; font-size: 14px; opacity: 0.9; }}
#             .content {{ padding: 30px; }}
#             .alert-section {{
#                 background-color: #fef2f2;
#                 border-left: 4px solid {alert_color};
#                 padding: 16px;
#                 margin-bottom: 20px;
#                 border-radius: 4px;
#             }}
#             .info-grid {{
#                 display: grid;
#                 grid-template-columns: 1fr 1fr;
#                 gap: 20px;
#                 margin-bottom: 20px;
#             }}
#             .info-item {{
#                 background-color: #f9fafb;
#                 padding: 15px;
#                 border-radius: 6px;
#                 border: 1px solid #e5e7eb;
#             }}
#             .info-label {{
#                 font-size: 12px;
#                 font-weight: 600;
#                 color: #6b7280;
#                 text-transform: uppercase;
#                 margin-bottom: 5px;
#             }}
#             .info-value {{ font-size: 16px; font-weight: 600; color: #111827; }}
#             .probabilities {{
#                 background-color: #f9fafb;
#                 padding: 20px;
#                 border-radius: 6px;
#                 margin-bottom: 20px;
#                 border: 1px solid #e5e7eb;
#             }}
#             .prob-title {{
#                 font-size: 12px;
#                 font-weight: 600;
#                 color: #6b7280;
#                 text-transform: uppercase;
#                 margin-bottom: 12px;
#             }}
#             .prob-item {{
#                 display: flex;
#                 justify-content: space-between;
#                 align-items: center;
#                 margin-bottom: 10px;
#             }}
#             .prob-item:last-child {{ margin-bottom: 0; }}
#             .prob-label {{ color: #374151; font-weight: 500; }}
#             .prob-bar {{
#                 flex: 1;
#                 margin: 0 15px;
#                 height: 8px;
#                 background-color: #e5e7eb;
#                 border-radius: 4px;
#                 overflow: hidden;
#             }}
#             .prob-fill {{ height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 4px; }}
#             .prob-value {{ color: #111827; font-weight: 600; font-size: 14px; min-width: 45px; text-align: right; }}
#             .gunshot-fill {{ background: linear-gradient(90deg, #dc2626, #ef4444) !important; }}
#             .scream-fill {{ background: linear-gradient(90deg, #f97316, #fb923c) !important; }}
#             .background-fill {{ background: linear-gradient(90deg, #10b981, #34d399) !important; }}
#             .action-section {{
#                 background-color: #eff6ff;
#                 border-left: 4px solid #3b82f6;
#                 padding: 16px;
#                 margin-bottom: 20px;
#                 border-radius: 4px;
#             }}
#             .action-section p {{ margin: 0; color: #1e40af; font-size: 14px; }}
#             .footer {{
#                 background-color: #f9fafb;
#                 border-top: 1px solid #e5e7eb;
#                 padding: 20px;
#                 text-align: center;
#                 font-size: 12px;
#                 color: #6b7280;
#             }}
#             .timestamp {{ color: #9ca3af; font-size: 12px; margin-top: 5px; }}
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <div class="header">
#                 <h1>{icon} DETECTION ALERT</h1>
#                 <p>{label.strip()} detected</p>
#             </div>
#             <div class="content">
#                 <div class="alert-section">
#                     <strong>⚠️ {label.upper()} Detection Confirmed</strong>
#                     <p style="margin: 8px 0 0 0; font-size: 14px;">A {label.lower().strip()} event has been detected in your audio stream.</p>
#                 </div>
#                 <div class="info-grid">
#                     <div class="info-item">
#                         <div class="info-label">Detection Type</div>
#                         <div class="info-value">{detection_type.upper()}</div>
#                     </div>
#                     <div class="info-item">
#                         <div class="info-label">Status</div>
#                         <div class="info-value" style="color: {alert_color};">ACTIVE</div>
#                     </div>
#                 </div>
#                 <div class="info-grid">
#                     <div class="info-item">
#                         <div class="info-label">Detection Label</div>
#                         <div class="info-value">{label.strip()}</div>
#                     </div>
#                     <div class="info-item">
#                         <div class="info-label">Confidence Score</div>
#                         <div class="info-value">{score_percent:.2f}%</div>
#                     </div>
#                 </div>
#                 <div class="probabilities">
#                     <div class="prob-title">📊 Detection Probabilities</div>
#                     <div class="prob-item">
#                         <span class="prob-label">🔫 Gunshot</span>
#                         <div class="prob-bar">
#                             <div class="prob-fill gunshot-fill" style="width: {min(gunshot_prob, 100)}%"></div>
#                         </div>
#                         <span class="prob-value">{gunshot_prob:.2f}%</span>
#                     </div>
#                     <div class="prob-item">
#                         <span class="prob-label">📢 Scream</span>
#                         <div class="prob-bar">
#                             <div class="prob-fill scream-fill" style="width: {min(scream_prob, 100)}%"></div>
#                         </div>
#                         <span class="prob-value">{scream_prob:.2f}%</span>
#                     </div>
#                     <div class="prob-item">
#                         <span class="prob-label">🔊 Background</span>
#                         <div class="prob-bar">
#                             <div class="prob-fill background-fill" style="width: {min(background_prob, 100)}%"></div>
#                         </div>
#                         <span class="prob-value">{background_prob:.2f}%</span>
#                     </div>
#                 </div>
#                 <div class="action-section">
#                     <p><strong>ℹ️ Action Required</strong></p>
#                     <p>Please check the audio stream and take appropriate action if necessary. Review the detection details above for more information.</p>
#                 </div>
#                 <div class="timestamp">
#                     <strong>Timestamp:</strong> {timestamp}
#                 </div>
#             </div>
#             <div class="footer">
#                 <p>🎙️ Gunshot &amp; Scream Detection System</p>
#                 <p style="margin: 5px 0 0 0;">This is an automated alert. Do not reply to this email.</p>
#             </div>
#         </div>
#     </body>
#     </html>
#     """
#     return html_template


# def send_alert_email(label, detection_type="upload", score=None, probabilities=None):
#     if not EMAIL_ENABLED:
#         return

#     recipient = get_receiver_email()

#     try:
#         subject = f"🚨 ALERT: {label} Detected ({detection_type.upper()})"
#         timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

#         html_body = get_email_html_template(label, detection_type, timestamp, probabilities or {}, score)

#         msg = MIMEMultipart('alternative')
#         msg['From'] = SENDER_EMAIL
#         msg['To'] = recipient
#         msg['Subject'] = subject
#         msg.attach(MIMEText(html_body, 'html'))

#         with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
#             server.starttls()
#             server.login(SENDER_EMAIL, SENDER_PASSWORD)
#             server.send_message(msg)

#         print(f"[EMAIL] Alert sent to {recipient}: {label}")
#     except Exception as e:
#         print(f"[EMAIL ERROR] Failed to send alert email: {str(e)}")


# def _prediction_from_probs(gun, scream, bg, mode="upload"):
#     gun = float(gun)
#     scream = float(scream)
#     bg = float(bg)

#     if mode == "live":
#         if gun >= LIVE_GUNSHOT_CONFIRM_THRESHOLD:
#             return "Gunshot ", True
#         if gun >= LIVE_GUNSHOT_PROBABLE_THRESHOLD:
#             return "Possible Gunshot ", False
#         if scream >= LIVE_SCREAM_THRESHOLD:
#             return "Scream ", False
#         return "Background", False

#     if gun > UPLOAD_GUNSHOT_THRESHOLD and scream > UPLOAD_SCREAM_THRESHOLD:
#         if scream > gun:
#             return "Scream ", False
#         return "Gunshot ", True

#     if gun > UPLOAD_GUNSHOT_THRESHOLD:
#         return "Gunshot ", True
#     if scream > UPLOAD_SCREAM_THRESHOLD:
#         return "Scream ", False
#     return "Background", False


# def _load_audio_for_prediction(
#     path,
#     min_seconds=0.0,
#     debug_wav_path=None,
#     gain_db=0,
#     use_live_shaping=False,
#     spike_boost=1.0
# ):
#     wav = os.path.splitext(path)[0] + "_converted.wav"
#     try:
#         filter_chain = LIVE_SHAPING_FILTER if use_live_shaping else None
#         convert_to_wav(path, wav, gain_db=gain_db, filter_chain=filter_chain)

#         if debug_wav_path:
#             os.makedirs(os.path.dirname(debug_wav_path), exist_ok=True)
#             try:
#                 shutil.copy2(wav, debug_wav_path)
#             except OSError:
#                 pass

#         audio, _ = librosa.load(wav, sr=SAMPLE_RATE, mono=True)
#         audio = np.asarray(audio, dtype=np.float32)
#         audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

#         if spike_boost > 1.0:
#             audio = np.clip(audio * float(spike_boost), -1.0, 1.0)

#         if audio.size == 0:
#             raise RuntimeError("empty_audio_after_decode")

#         if min_seconds > 0 and audio.size < int(SAMPLE_RATE * min_seconds):
#             raise RuntimeError("audio_too_short")

#         return audio
#     finally:
#         if os.path.exists(wav):
#             os.remove(wav)


# # ==============================
# # CONVERT
# # ==============================
# def convert_to_wav(input_path, output_path, gain_db=0, filter_chain=None):
#     ffmpeg_path = _resolve_ffmpeg_path()
#     if not ffmpeg_path:
#         raise RuntimeError("ffmpeg_not_found")

#     af_filters = []
#     if gain_db:
#         af_filters.append(f"volume={float(gain_db)}dB")
#     if filter_chain:
#         af_filters.append(filter_chain)

#     cmd = [
#         ffmpeg_path,
#         "-hide_banner",
#         "-loglevel", "error",
#         "-nostdin",
#         "-fflags", "+genpts",
#         "-err_detect", "ignore_err",
#         "-i", input_path,
#         "-vn",
#     ]

#     if af_filters:
#         cmd.extend(["-af", ",".join(af_filters)])

#     cmd.extend([
#         "-acodec", "pcm_s16le",
#         "-ac", "1",
#         "-ar", str(SAMPLE_RATE),
#         "-f", "wav",
#         "-y", output_path
#     ])

#     result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

#     if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
#         stderr_lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
#         short_error = stderr_lines[-1] if stderr_lines else "invalid_audio_input"
#         raise RuntimeError(f"ffmpeg_conversion_failed:{short_error}")

#     return output_path


# # ==============================
# # UPLOAD-ONLY helper: pad last chunk to SAMPLES_PER_TRACK
# #
# # Training always used full 3-second chunks. When a WAV file's length is not
# # an exact multiple of 3 s the final tail chunk is shorter, producing a
# # compressed mel-spectrogram the model has never seen — this causes misses on
# # dataset samples. Zero-padding restores the correct shape.
# #
# # Live detection is NOT affected: it still calls split_audio() from utils
# # directly, exactly as before.
# # ==============================
# def _split_audio_upload(audio):
#     chunks = []
#     for start in range(0, len(audio), SAMPLES_PER_TRACK):
#         chunk = audio[start:start + SAMPLES_PER_TRACK]
#         if len(chunk) < SAMPLES_PER_TRACK:
#             chunk = np.pad(chunk, (0, SAMPLES_PER_TRACK - len(chunk)), mode='constant')
#         chunks.append(chunk)
#     return chunks


# # ==============================
# # PREDICT — upload path (uses padded chunking + lower scream threshold)
# # ==============================
# def predict_audio(path):

#     audio = _load_audio_for_prediction(
#         path,
#         gain_db=UPLOAD_GAIN_DB,
#         spike_boost=1.0
#     )
#     chunks = _split_audio_upload(audio)   # padded chunking for uploads only

#     results = []
#     best_score = -1.0
#     best_label = "Background"
#     best_for_email = None
#     max_gun = 0.0
#     max_scream = 0.0
#     max_bg = 1.0

#     for i, chunk in enumerate(chunks):
#         rms = float(np.sqrt(np.mean(np.square(chunk))))
#         if rms < UPLOAD_RMS_MIN:
#             continue

#         processed = shared_preprocess_chunk(chunk)
#         pred = model.predict(processed, verbose=0)[0]
#         gun, scream, bg = pred
#         max_gun = max(max_gun, float(gun))
#         max_scream = max(max_scream, float(scream))
#         max_bg = max(max_bg, float(bg))

#         label, _ = _prediction_from_probs(gun, scream, bg, mode="upload")
#         score = float(max(gun, scream))

#         results.append({
#             "chunk": i + 1,
#             "gunshot": round(float(gun), 3),
#             "scream": round(float(scream), 3),
#             "background": round(float(bg), 3),
#             "label": label
#         })

#         if label == "Gunshot ":
#             candidate_score = float(gun)
#         elif label == "Scream ":
#             candidate_score = float(scream)
#         else:
#             candidate_score = -1.0

#         if candidate_score > best_score:
#             best_score = candidate_score
#             best_label = label
#             best_for_email = {
#                 "gunshot": round(float(gun), 3),
#                 "scream": round(float(scream), 3),
#                 "background": round(float(bg), 3)
#             }

#         if best_label == "Background" and score > best_score:
#             best_score = score
#             best_label = label

#     if best_label == "Background":
#         if max_scream >= UPLOAD_SCREAM_FALLBACK_THRESHOLD and max_scream > max_gun:
#             best_label = "Scream "
#             best_score = max_scream
#             best_for_email = {
#                 "gunshot": round(max_gun, 3),
#                 "scream": round(max_scream, 3),
#                 "background": round(max_bg, 3)
#             }

#     if best_label in ["Gunshot ", "Scream "] and results:
#         send_alert_email(
#             best_label,
#             detection_type="upload",
#             score=best_score,
#             probabilities={
#                 'gunshot': (best_for_email or {}).get('gunshot', 0.0),
#                 'scream': (best_for_email or {}).get('scream', 0.0),
#                 'background': (best_for_email or {}).get('background', 0.0)
#             }
#         )

#     return best_label, results


# # ==============================
# # PREDICT — live chunk (100% original, zero changes)
# # ==============================
# def predict_single_live_chunk(path, debug_wav_path=None, debug_audio_received_path=None, debug_audio_to_model_path=None):

#     audio = _load_audio_for_prediction(
#         path,
#         min_seconds=LIVE_MIN_SECONDS,
#         debug_wav_path=debug_wav_path,
#         gain_db=LIVE_GAIN_DB,
#         use_live_shaping=True,
#         spike_boost=LIVE_SPIKE_BOOST
#     )

#     if debug_audio_received_path:
#         try:
#             os.makedirs(os.path.dirname(debug_audio_received_path), exist_ok=True)
#             import soundfile as sf
#             sf.write(debug_audio_received_path, audio, SAMPLE_RATE)
#         except Exception as e:
#             print(f"[DEBUG] Failed to save audio_received: {str(e)}")

#     chunks = split_audio(audio)
#     preprocessed_chunks = []

#     best = {
#         "gunshot": 0.0,
#         "scream": 0.0,
#         "background": 1.0,
#         "label": "Background",
#         "alert": False,
#         "score": -1.0
#     }

#     for chunk in chunks:
#         rms = float(np.sqrt(np.mean(np.square(chunk))))
#         if rms < LIVE_RMS_MIN:
#             continue

#         processed = shared_preprocess_chunk(chunk)
#         preprocessed_chunks.append(processed)
#         pred = model.predict(processed, verbose=0)[0]
#         gun, scream, bg = pred
#         label, alert = _prediction_from_probs(gun, scream, bg, mode="live")
#         score = float(max(gun, scream))

#         if score > best["score"]:
#             best = {
#                 "gunshot": round(float(gun), 3),
#                 "scream": round(float(scream), 3),
#                 "background": round(float(bg), 3),
#                 "label": label,
#                 "alert": alert,
#                 "score": score
#             }

#     if debug_audio_to_model_path and preprocessed_chunks:
#         try:
#             os.makedirs(os.path.dirname(debug_audio_to_model_path), exist_ok=True)
#             np.save(debug_audio_to_model_path, np.array(preprocessed_chunks))
#         except Exception as e:
#             print(f"[DEBUG] Failed to save audio_to_model: {str(e)}")

#     if best["score"] < 0:
#         return {
#             "gunshot": 0.0,
#             "scream": 0.0,
#             "background": 1.0,
#             "label": "Background",
#             "alert": False,
#             "gunshot_alert": False,
#             "scream_alert": False,
#             "reason": "low_energy"
#         }

#     if best["alert"] or best["label"] in ["Gunshot ", "Scream "]:
#         send_alert_email(
#             best["label"],
#             detection_type="live",
#             score=best["score"],
#             probabilities={
#                 'gunshot': best["gunshot"],
#                 'scream': best["scream"],
#                 'background': best["background"]
#             }
#         )

#     return {
#         "gunshot": best["gunshot"],
#         "scream": best["scream"],
#         "background": best["background"],
#         "label": best["label"],
#         "alert": best["alert"],
#         "gunshot_alert": best["label"] == "Gunshot ",
#         "scream_alert": best["label"] == "Scream ",
#         "live_thresholds": {
#             "gunshot_confirm": LIVE_GUNSHOT_CONFIRM_THRESHOLD,
#             "gunshot_probable": LIVE_GUNSHOT_PROBABLE_THRESHOLD,
#             "scream": LIVE_SCREAM_THRESHOLD
#         }
#     }


# def save_upload_file(file: UploadFile):
#     ext = os.path.splitext(file.filename or "")[1] or ".bin"
#     file_name = f"{uuid.uuid4().hex}{ext}"
#     return os.path.join(UPLOAD_DIR, file_name)


# def append_detection_log(event_type: str, source: str) -> None:
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     line = f"{timestamp}\t{event_type}\t{source}\n"

#     with open(DETECTION_LOG_FILE, "a", encoding="utf-8") as f:
#         f.write(line)

#     try:
#         with open(DETECTION_LOG_FILE, "r", encoding="utf-8") as f:
#             lines = f.readlines()
#         if len(lines) > MAX_DETECTION_LOG_LINES:
#             with open(DETECTION_LOG_FILE, "w", encoding="utf-8") as f:
#                 f.writelines(lines[-MAX_DETECTION_LOG_LINES:])
#     except OSError:
#         pass


# def read_detection_logs(limit: int = 50):
#     if not os.path.exists(DETECTION_LOG_FILE):
#         return []

#     logs = []
#     try:
#         with open(DETECTION_LOG_FILE, "r", encoding="utf-8") as f:
#             for raw in f:
#                 parts = raw.rstrip("\n").split("\t")
#                 if len(parts) != 3:
#                     continue
#                 logs.append({
#                     "timestamp": parts[0],
#                     "event": parts[1],
#                     "source": parts[2]
#                 })
#     except OSError:
#         return []

#     logs.reverse()
#     return logs[:limit]


# def clear_detection_logs() -> None:
#     try:
#         if os.path.exists(DETECTION_LOG_FILE):
#             os.remove(DETECTION_LOG_FILE)
#     except OSError:
#         pass


# # ==============================
# # ROUTES
# # ==============================
# @app.get("/healthz")
# def healthz():
#     return {"status": "ok"}


# @app.get("/", response_class=HTMLResponse)
# def home(request: Request):
#     return templates.TemplateResponse("index.html", {
#         "request": request,
#         "logs": read_detection_logs()
#     })


# @app.get("/api/detection-logs")
# def get_detection_logs():
#     return JSONResponse({"logs": read_detection_logs()})


# @app.post("/api/clear-detection-logs")
# def clear_detection_logs_api():
#     clear_detection_logs()
#     return JSONResponse({"success": True})


# @app.get("/api/get-receiver-email")
# async def get_email_endpoint():
#     email = get_receiver_email()
#     return JSONResponse({"email": email})


# @app.post("/api/set-receiver-email")
# async def set_email_endpoint(request: Request):
#     try:
#         data = await request.json()
#         email = data.get("email", "").strip()

#         if not email:
#             return JSONResponse({"error": "Email is required"}, status_code=400)

#         if '@' not in email or '.' not in email.split('@')[1]:
#             return JSONResponse({"error": "Invalid email format"}, status_code=400)

#         if set_receiver_email(email):
#             return JSONResponse({"success": True, "email": email})
#         else:
#             return JSONResponse({"error": "Failed to save email"}, status_code=500)
#     except Exception as e:
#         print(f"[API] Error setting email: {str(e)}")
#         return JSONResponse({"error": str(e)}, status_code=500)


# @app.post("/predict")
# async def predict(request: Request, file: UploadFile = File(...)):

#     path = save_upload_file(file)
#     with open(path, "wb") as f:
#         f.write(await file.read())

#     try:
#         try:
#             final, chunks = predict_audio(path)
#         except RuntimeError:
#             final, chunks = "Invalid audio input", []
#     finally:
#         if os.path.exists(path):
#             os.remove(path)

#     confidence = 0.0
#     if chunks:
#         best_chunk = max(chunks, key=lambda x: max(x['gunshot'], x['scream']))
#         confidence = max(best_chunk['gunshot'], best_chunk['scream'])

#     gunshot_alert = "Gunshot " in final
#     scream_alert = "Scream " in final

#     if gunshot_alert:
#         append_detection_log("Gunshot", "Upload")
#     if scream_alert:
#         append_detection_log("Scream", "Upload")

#     return JSONResponse({
#         "label": final,
#         "confidence": confidence,
#         "gunshot_alert": gunshot_alert,
#         "scream_alert": scream_alert,
#         "chunks": chunks
#     })


# @app.post("/predict-live", response_class=HTMLResponse)
# async def predict_live(request: Request, file: UploadFile = File(...)):

#     path = save_upload_file(file)
#     with open(path, "wb") as f:
#         f.write(await file.read())

#     try:
#         try:
#             final, chunks = predict_audio(path)
#         except RuntimeError:
#             final, chunks = "Invalid audio input", []
#     finally:
#         if os.path.exists(path):
#             os.remove(path)

#     return templates.TemplateResponse("index.html", {
#         "request": request,
#         "result": final,
#         "chunks": chunks,
#         "logs": read_detection_logs()
#     })


# @app.post("/predict-live-chunk")
# async def predict_live_chunk(file: UploadFile = File(...)):

#     path = save_upload_file(file)
#     original_ext = os.path.splitext(file.filename or "")[1] or ".bin"
#     debug_id = uuid.uuid4().hex
#     debug_raw_path = os.path.join(TEST_RAW_DIR, f"{debug_id}{original_ext}")
#     debug_wav_path = os.path.join(TEST_WAV_DIR, f"{debug_id}.wav")
#     debug_audio_received_path = os.path.join(TEST_AUDIO_RECEIVED_DIR, f"{debug_id}_received.wav")
#     debug_audio_to_model_path = os.path.join(TEST_AUDIO_TO_MODEL_DIR, f"{debug_id}_to_model.npy")

#     with open(path, "wb") as f:
#         f.write(await file.read())

#     if SAVE_LIVE_CHUNKS_FOR_TESTING:
#         try:
#             os.makedirs(TEST_RAW_DIR, exist_ok=True)
#             os.makedirs(TEST_WAV_DIR, exist_ok=True)
#             os.makedirs(TEST_AUDIO_RECEIVED_DIR, exist_ok=True)
#             os.makedirs(TEST_AUDIO_TO_MODEL_DIR, exist_ok=True)
#             shutil.copy2(path, debug_raw_path)
#         except OSError:
#             pass

#     try:
#         try:
#             result = predict_single_live_chunk(
#                 path,
#                 debug_wav_path=debug_wav_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None,
#                 debug_audio_received_path=debug_audio_received_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None,
#                 debug_audio_to_model_path=debug_audio_to_model_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None
#             )
#         except RuntimeError as exc:
#             result = {
#                 "gunshot": 0.0,
#                 "scream": 0.0,
#                 "background": 1.0,
#                 "label": "Background",
#                 "alert": False,
#                 "gunshot_alert": False,
#                 "scream_alert": False,
#                 "error": str(exc),
#                 "debug_chunk": debug_id if SAVE_LIVE_CHUNKS_FOR_TESTING else None
#             }
#     finally:
#         if os.path.exists(path):
#             os.remove(path)

#     if SAVE_LIVE_CHUNKS_FOR_TESTING:
#         result["debug_chunk"] = debug_id

#     if result.get("gunshot_alert"):
#         append_detection_log("Gunshot", "Live")
#     if result.get("scream_alert"):
#         append_detection_log("Scream", "Live")

#     return JSONResponse(result)

import numpy as np
import librosa
import tensorflow as tf
import subprocess
import os
import uuid
import shutil
import tempfile
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from utils import split_audio, preprocess_chunk as shared_preprocess_chunk

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

MODEL_PATH = "model/final_audio_model_v4.h5"


class CompatibleInputLayer(tf.keras.layers.InputLayer):
    @classmethod
    def from_config(cls, config):
        config = dict(config)
        if "batch_shape" in config and "batch_input_shape" not in config:
            config["batch_input_shape"] = tuple(config.pop("batch_shape"))
        config.pop("optional", None)
        return super().from_config(config)


class CompatibleDTypePolicy(tf.keras.mixed_precision.Policy):
    @classmethod
    def from_config(cls, config):
        policy_name = config.get("name", "float32") if isinstance(config, dict) else "float32"
        return tf.keras.mixed_precision.Policy(policy_name)


def _sanitize_layer_config(config):
    config = dict(config)
    config.pop("quantization_config", None)
    return config


class CompatibleDense(tf.keras.layers.Dense):
    @classmethod
    def from_config(cls, config):
        return super().from_config(_sanitize_layer_config(config))


class CompatibleConv2D(tf.keras.layers.Conv2D):
    @classmethod
    def from_config(cls, config):
        return super().from_config(_sanitize_layer_config(config))


class CompatibleConv1D(tf.keras.layers.Conv1D):
    @classmethod
    def from_config(cls, config):
        return super().from_config(_sanitize_layer_config(config))


def load_model_with_compat(model_path):
    try:
        return tf.keras.models.load_model(model_path, compile=False)
    except Exception:
        return tf.keras.models.load_model(
            model_path,
            custom_objects={
                "InputLayer": CompatibleInputLayer,
                "DTypePolicy": CompatibleDTypePolicy,
                "Dense": CompatibleDense,
                "Conv2D": CompatibleConv2D,
                "Conv1D": CompatibleConv1D,
            },
            compile=False,
        )


model = load_model_with_compat(MODEL_PATH)

SAMPLE_RATE = 22050
CHUNK_SECONDS = 3
SAMPLES_PER_TRACK = SAMPLE_RATE * CHUNK_SECONDS
LIVE_MIN_SECONDS = 0.5

# ── Live thresholds — original, untouched ─────────────────────────────────────
LIVE_GUNSHOT_CONFIRM_THRESHOLD = 0.22
LIVE_GUNSHOT_PROBABLE_THRESHOLD = 0.12
LIVE_SCREAM_THRESHOLD = 0.18

# ── Upload: only used for RMS silence gating ──────────────────────────────────
UPLOAD_RMS_MIN = 0.003

UPLOAD_GAIN_DB = 0
LIVE_GAIN_DB = 4

# ── Live shaping filter — original, untouched ─────────────────────────────────
LIVE_SHAPING_FILTER = "highpass=f=120,lowpass=f=7000,acompressor=threshold=-22dB:ratio=3:attack=5:release=80,loudnorm"

LIVE_RMS_MIN = 0.01
LIVE_SPIKE_BOOST = 1.08
UPLOAD_DIR = "uploaded_audio"
SAVE_LIVE_CHUNKS_FOR_TESTING = True
TEST_CHUNKS_DIR = os.path.join("testing_chunks", "live_chunks")
TEST_RAW_DIR = os.path.join(TEST_CHUNKS_DIR, "raw")
TEST_WAV_DIR = os.path.join(TEST_CHUNKS_DIR, "wav")
TEST_AUDIO_RECEIVED_DIR = os.path.join(TEST_CHUNKS_DIR, "audio_received")
TEST_AUDIO_TO_MODEL_DIR = os.path.join(TEST_CHUNKS_DIR, "audio_to_model")
DETECTION_LOG_FILE = os.path.join(tempfile.gettempdir(), "gunshot_predictor_detection_events.tmp.txt")
MAX_DETECTION_LOG_LINES = 200

# Email Configuration
EMAIL_ENABLED = True
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "sahilbhandare80@gmail.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "hxzbgdbbfopqhrme")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "sahilbhandare79@gmail.com")

EMAIL_CONFIG_DIR = "config"
EMAIL_CONFIG_FILE = os.path.join(EMAIL_CONFIG_DIR, "receiver_email.txt")

if os.path.exists(UPLOAD_DIR) and not os.path.isdir(UPLOAD_DIR):
    UPLOAD_DIR = "uploaded_audio_dir"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EMAIL_CONFIG_DIR, exist_ok=True)
if SAVE_LIVE_CHUNKS_FOR_TESTING:
    os.makedirs(TEST_RAW_DIR, exist_ok=True)
    os.makedirs(TEST_WAV_DIR, exist_ok=True)
    os.makedirs(TEST_AUDIO_RECEIVED_DIR, exist_ok=True)
    os.makedirs(TEST_AUDIO_TO_MODEL_DIR, exist_ok=True)


def _resolve_ffmpeg_path():
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    path_cmd = shutil.which("ffmpeg")
    if path_cmd:
        return path_cmd
    return None


def get_receiver_email():
    if os.path.exists(EMAIL_CONFIG_FILE):
        try:
            with open(EMAIL_CONFIG_FILE, 'r') as f:
                email = f.read().strip()
                if email and '@' in email:
                    return email
        except Exception as e:
            print(f"[CONFIG] Error reading email config: {str(e)}")
    return RECIPIENT_EMAIL


def set_receiver_email(email):
    try:
        os.makedirs(EMAIL_CONFIG_DIR, exist_ok=True)
        with open(EMAIL_CONFIG_FILE, 'w') as f:
            f.write(email.strip())
        return True
    except Exception as e:
        print(f"[CONFIG] Error writing email config: {str(e)}")
        return False


def get_email_html_template(label, detection_type, timestamp, probabilities, score):
    gunshot_prob = probabilities.get('gunshot', 0.0) * 100 if probabilities else 0
    scream_prob = probabilities.get('scream', 0.0) * 100 if probabilities else 0
    background_prob = probabilities.get('background', 0.0) * 100 if probabilities else 0
    score_percent = score * 100 if score is not None else 0

    alert_color = "#DC2626" if "Gunshot" in label else "#FF6B35"
    icon = "🔫" if "Gunshot" in label else "📢"

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, {alert_color} 0%, #8b1a1a 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{ margin: 0; font-size: 28px; font-weight: bold; }}
            .header p {{ margin: 10px 0 0 0; font-size: 14px; opacity: 0.9; }}
            .content {{ padding: 30px; }}
            .alert-section {{
                background-color: #fef2f2;
                border-left: 4px solid {alert_color};
                padding: 16px;
                margin-bottom: 20px;
                border-radius: 4px;
            }}
            .info-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 20px;
            }}
            .info-item {{
                background-color: #f9fafb;
                padding: 15px;
                border-radius: 6px;
                border: 1px solid #e5e7eb;
            }}
            .info-label {{
                font-size: 12px;
                font-weight: 600;
                color: #6b7280;
                text-transform: uppercase;
                margin-bottom: 5px;
            }}
            .info-value {{ font-size: 16px; font-weight: 600; color: #111827; }}
            .probabilities {{
                background-color: #f9fafb;
                padding: 20px;
                border-radius: 6px;
                margin-bottom: 20px;
                border: 1px solid #e5e7eb;
            }}
            .prob-title {{
                font-size: 12px;
                font-weight: 600;
                color: #6b7280;
                text-transform: uppercase;
                margin-bottom: 12px;
            }}
            .prob-item {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }}
            .prob-item:last-child {{ margin-bottom: 0; }}
            .prob-label {{ color: #374151; font-weight: 500; }}
            .prob-bar {{
                flex: 1;
                margin: 0 15px;
                height: 8px;
                background-color: #e5e7eb;
                border-radius: 4px;
                overflow: hidden;
            }}
            .prob-fill {{ height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 4px; }}
            .prob-value {{ color: #111827; font-weight: 600; font-size: 14px; min-width: 45px; text-align: right; }}
            .gunshot-fill {{ background: linear-gradient(90deg, #dc2626, #ef4444) !important; }}
            .scream-fill {{ background: linear-gradient(90deg, #f97316, #fb923c) !important; }}
            .background-fill {{ background: linear-gradient(90deg, #10b981, #34d399) !important; }}
            .action-section {{
                background-color: #eff6ff;
                border-left: 4px solid #3b82f6;
                padding: 16px;
                margin-bottom: 20px;
                border-radius: 4px;
            }}
            .action-section p {{ margin: 0; color: #1e40af; font-size: 14px; }}
            .footer {{
                background-color: #f9fafb;
                border-top: 1px solid #e5e7eb;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #6b7280;
            }}
            .timestamp {{ color: #9ca3af; font-size: 12px; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{icon} DETECTION ALERT</h1>
                <p>{label.strip()} detected</p>
            </div>
            <div class="content">
                <div class="alert-section">
                    <strong>⚠️ {label.upper()} Detection Confirmed</strong>
                    <p style="margin: 8px 0 0 0; font-size: 14px;">A {label.lower().strip()} event has been detected in your audio stream.</p>
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Detection Type</div>
                        <div class="info-value">{detection_type.upper()}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Status</div>
                        <div class="info-value" style="color: {alert_color};">ACTIVE</div>
                    </div>
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Detection Label</div>
                        <div class="info-value">{label.strip()}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Confidence Score</div>
                        <div class="info-value">{score_percent:.2f}%</div>
                    </div>
                </div>
                <div class="probabilities">
                    <div class="prob-title">📊 Detection Probabilities</div>
                    <div class="prob-item">
                        <span class="prob-label">🔫 Gunshot</span>
                        <div class="prob-bar">
                            <div class="prob-fill gunshot-fill" style="width: {min(gunshot_prob, 100)}%"></div>
                        </div>
                        <span class="prob-value">{gunshot_prob:.2f}%</span>
                    </div>
                    <div class="prob-item">
                        <span class="prob-label">📢 Scream</span>
                        <div class="prob-bar">
                            <div class="prob-fill scream-fill" style="width: {min(scream_prob, 100)}%"></div>
                        </div>
                        <span class="prob-value">{scream_prob:.2f}%</span>
                    </div>
                    <div class="prob-item">
                        <span class="prob-label">🔊 Background</span>
                        <div class="prob-bar">
                            <div class="prob-fill background-fill" style="width: {min(background_prob, 100)}%"></div>
                        </div>
                        <span class="prob-value">{background_prob:.2f}%</span>
                    </div>
                </div>
                <div class="action-section">
                    <p><strong>ℹ️ Action Required</strong></p>
                    <p>Please check the audio stream and take appropriate action if necessary. Review the detection details above for more information.</p>
                </div>
                <div class="timestamp">
                    <strong>Timestamp:</strong> {timestamp}
                </div>
            </div>
            <div class="footer">
                <p>🎙️ Gunshot &amp; Scream Detection System</p>
                <p style="margin: 5px 0 0 0;">This is an automated alert. Do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_template


def send_alert_email(label, detection_type="upload", score=None, probabilities=None):
    if not EMAIL_ENABLED:
        return

    recipient = get_receiver_email()

    try:
        subject = f"🚨 ALERT: {label} Detected ({detection_type.upper()})"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        html_body = get_email_html_template(label, detection_type, timestamp, probabilities or {}, score)

        msg = MIMEMultipart('alternative')
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print(f"[EMAIL] Alert sent to {recipient}: {label}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send alert email: {str(e)}")


# ── Live prediction logic — original, untouched ───────────────────────────────
def _prediction_from_probs_live(gun, scream, bg):
    gun = float(gun)
    scream = float(scream)
    bg = float(bg)

    if gun >= LIVE_GUNSHOT_CONFIRM_THRESHOLD:
        return "Gunshot ", True
    if gun >= LIVE_GUNSHOT_PROBABLE_THRESHOLD:
        return "Possible Gunshot ", False
    if scream >= LIVE_SCREAM_THRESHOLD:
        return "Scream ", False
    return "Background", False


def _load_audio_for_prediction(
    path,
    min_seconds=0.0,
    debug_wav_path=None,
    gain_db=0,
    use_live_shaping=False,
    spike_boost=1.0
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

        if spike_boost > 1.0:
            audio = np.clip(audio * float(spike_boost), -1.0, 1.0)

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
def convert_to_wav(input_path, output_path, gain_db=0, filter_chain=None):
    ffmpeg_path = _resolve_ffmpeg_path()
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg_not_found")

    af_filters = []
    if gain_db:
        af_filters.append(f"volume={float(gain_db)}dB")
    if filter_chain:
        af_filters.append(filter_chain)

    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel", "error",
        "-nostdin",
        "-fflags", "+genpts",
        "-err_detect", "ignore_err",
        "-i", input_path,
        "-vn",
    ]

    if af_filters:
        cmd.extend(["-af", ",".join(af_filters)])

    cmd.extend([
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "-f", "wav",
        "-y", output_path
    ])

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        stderr_lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
        short_error = stderr_lines[-1] if stderr_lines else "invalid_audio_input"
        raise RuntimeError(f"ffmpeg_conversion_failed:{short_error}")

    return output_path

def preprocess_chunk_upload(audio_chunk):
    """
    Matches Google Colab preprocessing exactly.
    No DC removal, no peak normalization, no 3x boost.
    Used only for uploaded audio.
    """
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

# ==============================
# UPLOAD-ONLY helper: pad last chunk to SAMPLES_PER_TRACK
# ==============================
def _split_audio_upload(audio):
    chunks = []
    for start in range(0, len(audio), SAMPLES_PER_TRACK):
        chunk = audio[start:start + SAMPLES_PER_TRACK]
        if len(chunk) < SAMPLES_PER_TRACK:
            chunk = np.pad(chunk, (0, SAMPLES_PER_TRACK - len(chunk)), mode='constant')
        chunks.append(chunk)
    return chunks


# ==============================
# PREDICT — upload path
#
# Matches Google Colab logic exactly:
#   - Find the chunk with the highest overall confidence (max of all 3 classes)
#   - Use np.argmax on that chunk's prediction to determine the final label
#   - No manual thresholds; the model's softmax output decides the class
# ==============================
def predict_audio(path):

    audio = _load_audio_for_prediction(
        path,
        gain_db=UPLOAD_GAIN_DB,
        spike_boost=1.0
    )
    chunks = _split_audio_upload(audio)

    results = []

    # Track the chunk with the highest confidence across ALL 3 classes (Colab logic)
    best_pred = None
    best_conf = -1.0
    best_chunk_index = -1

    for i, chunk in enumerate(chunks):
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        if rms < UPLOAD_RMS_MIN:
            # Still append a result row so chunk numbers stay consistent
            results.append({
                "chunk": i + 1,
                "gunshot": 0.0,
                "scream": 0.0,
                "background": 1.0,
                "label": "Background"
            })
            continue

        processed = preprocess_chunk_upload(chunk)

        pred = model.predict(processed, verbose=0)[0]
        gun, scream, bg = float(pred[0]), float(pred[1]), float(pred[2])

        # Colab: confidence = max probability across all classes
        confidence = float(np.max(pred))

        # Colab: label = argmax of the prediction vector
        class_index = int(np.argmax(pred))
        class_labels = {0: "Gunshot ", 1: "Scream ", 2: "Background"}
        label = class_labels[class_index]

        results.append({
            "chunk": i + 1,
            "gunshot": round(gun, 3),
            "scream": round(scream, 3),
            "background": round(bg, 3),
            "label": label
        })

        # Track best chunk by overall confidence (Colab logic)
        if confidence > best_conf:
            best_conf = confidence
            best_pred = pred
            best_chunk_index = i

    # Final label: argmax of the best chunk's prediction (Colab logic)
    if best_pred is not None:
        final_class_index = int(np.argmax(best_pred))
        class_labels = {0: "Gunshot ", 1: "Scream ", 2: "Background"}
        final_label = class_labels[final_class_index]
        best_gun  = float(best_pred[0])
        best_scream = float(best_pred[1])
        best_bg   = float(best_pred[2])
    else:
        final_label = "Background"
        best_gun, best_scream, best_bg = 0.0, 0.0, 1.0
        best_conf = 0.0

    if final_label in ("Gunshot ", "Scream "):
        send_alert_email(
            final_label,
            detection_type="upload",
            score=best_conf,
            probabilities={
                "gunshot":    round(best_gun, 3),
                "scream":     round(best_scream, 3),
                "background": round(best_bg, 3),
            }
        )

    return final_label, results


# ==============================
# PREDICT — live chunk (100% original, zero changes)
# ==============================
def predict_single_live_chunk(path, debug_wav_path=None, debug_audio_received_path=None, debug_audio_to_model_path=None):

    audio = _load_audio_for_prediction(
        path,
        min_seconds=LIVE_MIN_SECONDS,
        debug_wav_path=debug_wav_path,
        gain_db=LIVE_GAIN_DB,
        use_live_shaping=True,
        spike_boost=LIVE_SPIKE_BOOST
    )

    if debug_audio_received_path:
        try:
            os.makedirs(os.path.dirname(debug_audio_received_path), exist_ok=True)
            import soundfile as sf
            sf.write(debug_audio_received_path, audio, SAMPLE_RATE)
        except Exception as e:
            print(f"[DEBUG] Failed to save audio_received: {str(e)}")

    chunks = split_audio(audio)
    preprocessed_chunks = []

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
        preprocessed_chunks.append(processed)
        pred = model.predict(processed, verbose=0)[0]
        gun, scream, bg = pred
        label, alert = _prediction_from_probs_live(gun, scream, bg)
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

    if debug_audio_to_model_path and preprocessed_chunks:
        try:
            os.makedirs(os.path.dirname(debug_audio_to_model_path), exist_ok=True)
            np.save(debug_audio_to_model_path, np.array(preprocessed_chunks))
        except Exception as e:
            print(f"[DEBUG] Failed to save audio_to_model: {str(e)}")

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

    if best["alert"] or best["label"] in ["Gunshot ", "Scream "]:
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
        "gunshot_alert": best["label"] == "Gunshot ",
        "scream_alert": best["label"] == "Scream ",
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


def append_detection_log(event_type: str, source: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp}\t{event_type}\t{source}\n"

    with open(DETECTION_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)

    try:
        with open(DETECTION_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_DETECTION_LOG_LINES:
            with open(DETECTION_LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-MAX_DETECTION_LOG_LINES:])
    except OSError:
        pass


def read_detection_logs(limit: int = 50):
    if not os.path.exists(DETECTION_LOG_FILE):
        return []

    logs = []
    try:
        with open(DETECTION_LOG_FILE, "r", encoding="utf-8") as f:
            for raw in f:
                parts = raw.rstrip("\n").split("\t")
                if len(parts) != 3:
                    continue
                logs.append({
                    "timestamp": parts[0],
                    "event": parts[1],
                    "source": parts[2]
                })
    except OSError:
        return []

    logs.reverse()
    return logs[:limit]


def clear_detection_logs() -> None:
    try:
        if os.path.exists(DETECTION_LOG_FILE):
            os.remove(DETECTION_LOG_FILE)
    except OSError:
        pass


# ==============================
# ROUTES
# ==============================
@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "logs": read_detection_logs()
    })


@app.get("/api/detection-logs")
def get_detection_logs():
    return JSONResponse({"logs": read_detection_logs()})


@app.post("/api/clear-detection-logs")
def clear_detection_logs_api():
    clear_detection_logs()
    return JSONResponse({"success": True})


@app.get("/api/get-receiver-email")
async def get_email_endpoint():
    email = get_receiver_email()
    return JSONResponse({"email": email})


@app.post("/api/set-receiver-email")
async def set_email_endpoint(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "").strip()

        if not email:
            return JSONResponse({"error": "Email is required"}, status_code=400)

        if '@' not in email or '.' not in email.split('@')[1]:
            return JSONResponse({"error": "Invalid email format"}, status_code=400)

        if set_receiver_email(email):
            return JSONResponse({"success": True, "email": email})
        else:
            return JSONResponse({"error": "Failed to save email"}, status_code=500)
    except Exception as e:
        print(f"[API] Error setting email: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/predict")
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

    confidence = 0.0
    if chunks:
        best_chunk = max(chunks, key=lambda x: max(x['gunshot'], x['scream']))
        confidence = max(best_chunk['gunshot'], best_chunk['scream'])

    gunshot_alert = "Gunshot " in final
    scream_alert = "Scream " in final

    if gunshot_alert:
        append_detection_log("Gunshot", "Upload")
    if scream_alert:
        append_detection_log("Scream", "Upload")

    return JSONResponse({
        "label": final,
        "confidence": confidence,
        "gunshot_alert": gunshot_alert,
        "scream_alert": scream_alert,
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
        "chunks": chunks,
        "logs": read_detection_logs()
    })


@app.post("/predict-live-chunk")
async def predict_live_chunk(file: UploadFile = File(...)):

    path = save_upload_file(file)
    original_ext = os.path.splitext(file.filename or "")[1] or ".bin"
    debug_id = uuid.uuid4().hex
    debug_raw_path = os.path.join(TEST_RAW_DIR, f"{debug_id}{original_ext}")
    debug_wav_path = os.path.join(TEST_WAV_DIR, f"{debug_id}.wav")
    debug_audio_received_path = os.path.join(TEST_AUDIO_RECEIVED_DIR, f"{debug_id}_received.wav")
    debug_audio_to_model_path = os.path.join(TEST_AUDIO_TO_MODEL_DIR, f"{debug_id}_to_model.npy")

    with open(path, "wb") as f:
        f.write(await file.read())

    if SAVE_LIVE_CHUNKS_FOR_TESTING:
        try:
            os.makedirs(TEST_RAW_DIR, exist_ok=True)
            os.makedirs(TEST_WAV_DIR, exist_ok=True)
            os.makedirs(TEST_AUDIO_RECEIVED_DIR, exist_ok=True)
            os.makedirs(TEST_AUDIO_TO_MODEL_DIR, exist_ok=True)
            shutil.copy2(path, debug_raw_path)
        except OSError:
            pass

    try:
        try:
            result = predict_single_live_chunk(
                path,
                debug_wav_path=debug_wav_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None,
                debug_audio_received_path=debug_audio_received_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None,
                debug_audio_to_model_path=debug_audio_to_model_path if SAVE_LIVE_CHUNKS_FOR_TESTING else None
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

    if result.get("gunshot_alert"):
        append_detection_log("Gunshot", "Live")
    if result.get("scream_alert"):
        append_detection_log("Scream", "Live")

    return JSONResponse(result)