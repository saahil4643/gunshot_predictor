from pydub import AudioSegment
import os
import random

# 📂 Your folders
gun_path = "gunshot_wav"
bg_path = "background_wav"
output_path = "mixed"

os.makedirs(output_path, exist_ok=True)

gun_files = os.listdir(gun_path)
bg_files = os.listdir(bg_path)

NUM_SAMPLES = 1500  # change if needed

for i in range(NUM_SAMPLES):
    try:
        gun_file = random.choice(gun_files)
        bg_file = random.choice(bg_files)

        gun = AudioSegment.from_file(os.path.join(gun_path, gun_file))
        bg = AudioSegment.from_file(os.path.join(bg_path, bg_file))

        # ✅ standardize
        gun = gun.set_frame_rate(44100).set_channels(1)
        bg = bg.set_frame_rate(44100).set_channels(1)

        # ✅ make background long enough
        if len(bg) < len(gun):
            bg = bg * (len(gun) // len(bg) + 1)

        # ✅ take random slice
        start = random.randint(0, len(bg) - len(gun))
        bg = bg[start:start + len(gun)]

        # ✅ reduce background volume
        bg = bg - random.randint(8, 18)

        # ✅ random gunshot position
        pos = random.randint(0, len(bg) - len(gun))

        # 🔥 mix
        mixed = bg.overlay(gun, position=pos).normalize()

        # 💾 save
        filename = f"mix_{i}.wav"
        mixed.export(os.path.join(output_path, filename), format="wav")

        if i % 100 == 0:
            print(f"Created {i} files...")

    except Exception as e:
        print(f"❌ Error at {i}: {e}")

print("🔥 MIXING DONE")