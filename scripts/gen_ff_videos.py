import sys
import os

sys.path.insert(0, "/var/www/mathrelaxing.store")
from services.video_renderer import ANIMATION_GENERATORS

OUTPUT_DIR = "/var/www/mathrelaxing.store/static/videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

items = [
    ("ff_flame_aurora", 30),
    ("ff_flame_phoenix", 25),
    ("ff_flame_crystal", 20),
    ("ff_flame_vortex", 35),
    ("ff_flame_galaxy", 40),
]

for key, duration in items:
    gen_info = ANIMATION_GENERATORS[key]
    out_name = f"{key}_1080p30.mp4"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    print(f"Generating {out_name}...")
    
    # Overwrite if exists
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
        print(f"Done {out_name}")
    except Exception as e:
        print(f"Error {out_name}: {e}")
