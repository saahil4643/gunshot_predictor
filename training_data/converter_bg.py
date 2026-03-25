from pydub import AudioSegment
import os

SUPPORTED_FORMATS = (".wav", ".mp3", ".flac", ".ogg", ".m4a")

input_folder = "background"
output_folder = "background_wav"

os.makedirs(output_folder, exist_ok=True)

files = [f for f in os.listdir(input_folder) if f.lower().endswith(SUPPORTED_FORMATS)]

count = 0

for file in files:
    try:
        input_path = os.path.join(input_folder, file)

        audio = AudioSegment.from_file(input_path)

        # standardize (VERY IMPORTANT)
        audio = audio.set_frame_rate(44100).set_channels(1)

        output_path = os.path.join(output_folder, f"bg_{count}.wav")
        audio.export(output_path, format="wav")

        count += 1

    except Exception as e:
        print(f"❌ Skipped: {file} | Error: {e}")

print(f"🔥 DONE: Converted {count} background files")