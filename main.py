# =========================================
# 🌐 FLASK SERVER (FINAL)
# =========================================

from flask import Flask, request, jsonify, send_from_directory
from gunshot_detector import detect_gunshot
import os
import uuid

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

    temp_file = f"upload_{uuid.uuid4()}"
    file.save(temp_file)

    try:
        result = detect_gunshot(temp_file)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    return jsonify(result)

# Run server
if __name__ == "__main__":
    app.run(debug=True)