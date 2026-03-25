# =========================================
# 🌐 FLASK SERVER (FINAL)
# =========================================

from flask import Flask, request, jsonify, send_from_directory
from gunshot_detector import detect_gunshot
import os
import uuid
import traceback

app = Flask(__name__, template_folder="templates")

# Serve frontend
@app.route("/")
def home():
    return send_from_directory("templates", "index.html")

# Prediction API
@app.route("/predict", methods=["POST"])
def predict():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    original_name = file.filename or ""
    _, ext = os.path.splitext(original_name)
    temp_file = f"upload_{uuid.uuid4()}{ext}"
    file.save(temp_file)

    try:
        result = detect_gunshot(temp_file)
    except Exception as e:
        return jsonify({
            "error": str(e),
            "type": e.__class__.__name__,
            "debug": {
                "cwd": os.getcwd(),
                "uploaded_file": temp_file,
                "traceback": traceback.format_exc()
            }
        }), 500
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    return jsonify(result)

# Run server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)