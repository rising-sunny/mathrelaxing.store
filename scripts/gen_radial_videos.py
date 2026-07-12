import sys
import os
import time

sys.path.insert(0, "/var/www/mathrelaxing.store")
from services.video_renderer import ANIMATION_GENERATORS

items = [
    ("rose_spin", 20),
    ("superformula_spin", 15),
    ("superformula_hue", 25),
]

out_dir = "/var/www/mathrelaxing.store/static/videos"
os.makedirs(out_dir, exist_ok=True)

for key, duration in items:
    out_name = f"{key}_1080p30.mp4"
    out_path = os.path.join(out_dir, out_name)
    
    gen_info = ANIMATION_GENERATORS.get(key)
    if not gen_info:
        print(f"Skipping {key}, not found in ANIMATION_GENERATORS")
        continue

    print(f"\nGenerating {out_name}...")
    t0 = time.time()
    
    if os.path.exists(out_path):
        os.remove(out_path)
    
    try:
        gen_info["fn"](
            output_path=out_path,
            fps=30,
            duration_secs=duration,
            width=1080,
            height=1350
        )
        print(f"Done {out_name} in {time.time() - t0:.1f}s")
    except Exception as e:
        print(f"Failed {out_name}: {e}")
