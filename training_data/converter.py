from pydub import AudioSegment
import os

SUPPORTED_FORMATS = (".wav", ".mp3", ".flac", ".ogg", ".m4a")

input_folder = "gunshot"
output_folder = "gunshot_wav"

os.makedirs(output_folder, exist_ok=True)

files = [f for f in os.listdir(input_folder) if f.lower().endswith(SUPPORTED_FORMATS)]

for i, file in enumerate(files):
    try:
        path = os.path.join(input_folder, file)
        audio = AudioSegment.from_file(path)

        # standardize
        audio = audio.set_frame_rate(44100).set_channels(1)

        output_path = os.path.join(output_folder, f"gun_{i}.wav")
        audio.export(output_path, format="wav")

    except:
        print(f"❌ Skipped: {file}")

print("🔥 Gunshot conversion DONE")